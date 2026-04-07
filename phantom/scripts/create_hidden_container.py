#!/usr/bin/env python3
"""
PHANTOM R3 - Hidden Volume Container Creator
Creates a TrueCrypt-compatible container (.tc) with Hidden Volume support
for plausible deniability.

Architecture:
  - Outer Volume  (password A): decoy/harmless files visible under coercion
  - Hidden Volume (password B): real .opus audio recordings, invisible from outside

Uses tcplay (TrueCrypt-compatible, sudo apt install tcplay) on Raspberry Pi OS Lite.
Compatible with TrueCrypt 7.1a on PC for decryption.

Requires Python 3.8+ and root/sudo access.

Environment variables:
  PHANTOM_OUTER_PASSWORD   - outer volume password (fallback to --outer-password)
  PHANTOM_HIDDEN_PASSWORD  - hidden volume password (fallback to --hidden-password)

NOTE: tcplay reads passphrase from /dev/tty (not stdin).
      This script uses 'expect' + losetup loop device to work around that.
      Install: sudo apt install expect
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Import pexpect-based tcplay helper
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from tcplay_helper import tcplay_create_with_hidden

# ─────────────────────────────────────────────
# Configuration constants
# ─────────────────────────────────────────────
LOG_DIR = Path("/phantom/logs")
LOG_FILE = LOG_DIR / "hidden_container.log"

TCPLAY_CIPHER = "AES-256-XTS"
TCPLAY_PRF = "SHA512"

MAPPER_PREFIX = "phantom_hv_"

# Hidden volume occupies 60% of total container space; outer gets 40%.
# This leaves enough room for outer filesystem overhead while hiding
# the presence of the hidden volume inside the free space of the outer.
HIDDEN_VOLUME_RATIO = 0.60

# Minimum sizes in MB
MIN_TOTAL_SIZE_MB = 10
MIN_HIDDEN_SIZE_MB = 5

ENV_OUTER_PASSWORD = "PHANTOM_OUTER_PASSWORD"
ENV_HIDDEN_PASSWORD = "PHANTOM_HIDDEN_PASSWORD"


# ─────────────────────────────────────────────
# Logging setup  (mirrors encrypt_audio.py pattern)
# ─────────────────────────────────────────────
def setup_logging(log_file: Path, dry_run: bool = False) -> logging.Logger:
    """Configure logging with ISO 8601 timestamps to stdout and optionally a log file.

    Args:
        log_file: Absolute path to the log file.
        dry_run:  When True, skip file handler (no disk writes).
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if not dry_run:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)
    logger = logging.getLogger("phantom.hidden")
    if dry_run:
        logger.info("DRY-RUN mode enabled — no actual changes will be made.")
    return logger


log = logging.getLogger("phantom.hidden")


# ─────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────
def load_password(env_key: str, cli_value: Optional[str], label: str) -> str:
    """Load a password with priority: env var → CLI argument.

    Args:
        env_key:   Name of the environment variable to check first.
        cli_value: Value passed via CLI argument (may be None).
        label:     Human-readable label for error messages.

    Returns:
        The password string.

    Raises:
        RuntimeError if no password is found from any source.
    """
    pw = os.environ.get(env_key, "").strip()
    if pw:
        log.info("Password [%s] loaded from environment variable %s.", label, env_key)
        return pw

    if cli_value:
        stripped = cli_value.strip()
        if stripped:
            log.info("Password [%s] loaded from CLI argument.", label)
            return stripped

    raise RuntimeError(
        f"No {label} password found. "
        f"Set env var '{env_key}' or pass --{label.lower().replace(' ', '-')}-password."
    )


# ─────────────────────────────────────────────
# Utility helpers  (reused from encrypt_audio.py)
# ─────────────────────────────────────────────
def _sanitize_mapper_name(stem: str) -> str:
    """Convert a filename stem into a safe /dev/mapper name.

    Replaces any character that is not alphanumeric or underscore with '_'.
    Truncates to 63 characters (Linux device name limit).
    """
    safe = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    if safe and safe[0].isdigit():
        safe = "_" + safe
    return safe[:63]


def run_cmd(
    cmd: List[str],
    input_data: Optional[bytes] = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Execute a command and return its CompletedProcess.

    Raises subprocess.CalledProcessError on non-zero exit when check=True.
    """
    log.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=capture,
        check=check,
    )
    return result


def _setup_loop_device(file_path: Path) -> str:
    """Attach a file to a loop device and return device path (e.g. '/dev/loop3').

    Required because tcplay v3.x needs a block device, not a plain file.
    Caller must call _detach_loop_device() when done.

    Raises subprocess.CalledProcessError if losetup fails.
    """
    result = subprocess.run(
        ["sudo", "losetup", "--find", "--show", str(file_path)],
        capture_output=True,
        check=True,
    )
    loop_dev = result.stdout.decode().strip()
    log.debug("Loop device attached: %s → %s", file_path, loop_dev)
    return loop_dev


def _detach_loop_device(loop_dev: str) -> None:
    """Detach a loop device. Best-effort — errors are logged but not raised."""
    try:
        subprocess.run(
            ["sudo", "losetup", "--detach", loop_dev],
            capture_output=True,
            check=True,
        )
        log.debug("Loop device detached: %s", loop_dev)
    except Exception as exc:
        log.warning("Failed to detach loop device %s: %s", loop_dev, exc)


def _tcl_str(s: str) -> str:
    """Escape a string for safe embedding inside a Tcl double-quoted string."""
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("[", "\\[")
         .replace("]", "\\]")
         .replace("$", "\\$")
    )


def _tcplay_create_expect(
    device: str,
    password: str,
    cipher: str,
    prf: str,
) -> bool:
    """Run tcplay --create (standard volume, no hidden) via 'expect'.

    tcplay reads passphrases from /dev/tty (not stdin), so we must use
    expect to interact with it.

    Prompt sequence for standard volume:
      1. Passphrase:
      2. Repeat passphrase:
      3. Confirmation "y"

    Args:
        device:   Block device path (e.g. /dev/loop3).
        password: Passphrase for the volume.
        cipher:   tcplay cipher string.
        prf:      PBKDF PRF string.

    Returns:
        True on success (exit 0), False on failure.
    """
    pw_safe = _tcl_str(password)
    cmd_str = (
        f"tcplay --create --device={device}"
        f" --cipher={cipher} --pbkdf-prf={prf}"
    )
    expect_script = f"""
set timeout 120
spawn {cmd_str}
expect "Passphrase:"
send "{pw_safe}\\r"
expect "Repeat passphrase:"
send "{pw_safe}\\r"
expect -re {{Are you sure.*\\?}}
send "y\\r"
expect eof
catch wait result
exit [lindex $result 3]
"""

    try:
        result = subprocess.run(
            ["sudo", "expect", "-c", expect_script],
            capture_output=True,
            check=True,
        )
        log.debug(
            "expect/tcplay --create output: %s",
            result.stdout.decode(errors="replace").strip(),
        )
        return True
    except subprocess.CalledProcessError as exc:
        log.error(
            "expect/tcplay --create failed: stdout=%s stderr=%s",
            exc.stdout.decode(errors="replace").strip(),
            exc.stderr.decode(errors="replace").strip(),
        )
        return False


def _tcplay_create_with_hidden_expect(
    device: str,
    outer_password: str,
    hidden_password: str,
    hidden_size_mb: int,
    cipher: str,
    prf: str,
    weak_keys: bool = False,
) -> bool:
    """Run tcplay --create -g (outer + hidden volume together) via 'expect'.

    With the -g / --hidden flag, tcplay v3.3 creates both outer and hidden headers
    in a single pass.  The ACTUAL prompt sequence (verified on tcplay v3.3 live):
      1. "Passphrase:"                       ← outer volume passphrase
      2. "Repeat passphrase:"                ← outer (confirmation)
      3. "Passphrase for hidden volume:"     ← hidden volume passphrase
      4. "Repeat passphrase:"                ← hidden (confirmation)
      5. "The total volume size of ... is N M (bytes)"
      6. "Size of hidden volume (e.g. 127M):" ← tcplay asks for hidden size in MB
      7. "Are you sure ...?"                  ← final y/n confirmation

    Args:
        device:          Block device path (e.g. /dev/loop3).
        outer_password:  Passphrase for the outer (decoy) volume.
        hidden_password: Passphrase for the hidden (real) volume.
        hidden_size_mb:  Size of the hidden volume in MB (sent to the size prompt).
        cipher:          tcplay cipher string.
        prf:             PBKDF PRF string.
        weak_keys:       If True, pass -w to tcplay (use urandom, testing only).

    Returns:
        True on success (exit 0), False on failure.
    """
    outer_safe = _tcl_str(outer_password)
    hidden_safe = _tcl_str(hidden_password)
    # Add -w (--weak-keys) flag when requested — speeds up test by using urandom
    # instead of a strong entropy source.  Never use in production.
    weak_flag = " -w" if weak_keys else ""
    cmd_str = (
        f"tcplay --create -g --device={device}"
        f" --cipher={cipher} --pbkdf-prf={prf}{weak_flag}"
    )
    # tcplay v3.3 -g FULL prompt sequence (verified by live strace + expect capture):
    #   1. "Passphrase:"                       → outer password
    #   2. "Repeat passphrase:"   (1st time)   → outer password (confirm)
    #   3. "Passphrase for hidden volume:"     → hidden password
    #   4. "Repeat passphrase:"   (2nd time)   → hidden password (confirm)
    #   5. "Size of hidden volume (e.g. 127M):" → hidden size in MB
    #   6. "Are you sure ...?"                 → "y"
    #
    # IMPORTANT: "Passphrase:" is a substring of "Passphrase for hidden volume:".
    # Using sequential expect/send would match the shorter string first.
    # Fix: state-machine with a counter so "Repeat passphrase:" sends the right password,
    # and an explicit pattern for "Size of hidden volume".
    expect_script = f"""
set timeout 300
set passphrase_count 0
spawn {cmd_str}
expect {{
    "Passphrase for hidden volume:" {{
        send "{hidden_safe}\\r"
        exp_continue
    }}
    "Repeat passphrase:" {{
        # 1st occurrence → outer confirmation; 2nd → hidden confirmation
        incr passphrase_count
        if {{$passphrase_count == 1}} {{
            send "{outer_safe}\\r"
        }} else {{
            send "{hidden_safe}\\r"
        }}
        exp_continue
    }}
    "Passphrase:" {{
        send "{outer_safe}\\r"
        exp_continue
    }}
    "Size of hidden volume" {{
        # tcplay asks how large the hidden volume should be inside the container
        send "{hidden_size_mb}M\\r"
        exp_continue
    }}
    -re {{Are you sure.*\\?}} {{
        send "y\\r"
        exp_continue
    }}
    eof {{
        catch wait result
        exit [lindex $result 3]
    }}
    timeout {{
        puts "\\nERROR: tcplay timed out waiting for prompt."
        exit 1
    }}
}}
"""

    try:
        result = subprocess.run(
            ["sudo", "expect", "-c", expect_script],
            capture_output=True,
            check=True,
        )
        log.debug(
            "expect/tcplay --create -g output: %s",
            result.stdout.decode(errors="replace").strip(),
        )
        return True
    except subprocess.CalledProcessError as exc:
        log.error(
            "expect/tcplay --create -g failed: stdout=%s stderr=%s",
            exc.stdout.decode(errors="replace").strip(),
            exc.stderr.decode(errors="replace").strip(),
        )
        return False


def _tcplay_map_expect(
    mapper_name: str,
    device: str,
    password: str,
    use_hidden: bool = False,
) -> bool:
    """Run tcplay --map via 'expect' to supply passphrase through a PTY.

    tcplay v3.3 does NOT have a --use-hidden flag for --map.
    To mount the hidden volume, simply supply the hidden password —
    tcplay tries both outer and hidden headers and uses whichever
    password matches.  The use_hidden parameter is kept for callers
    but has no effect on the tcplay command line.

    Args:
        mapper_name: Name for /dev/mapper/<name>.
        device:      Loop device path (e.g. /dev/loop1).
                     Must be a block device — tcplay cannot map raw files.
        password:    Volume passphrase (outer or hidden).
        use_hidden:  Informational only (logged). No tcplay flag is added.

    Returns:
        True on success (exit 0), False on failure.
    """
    pw_safe = _tcl_str(password)
    # tcplay v3.3: --map does NOT accept --use-hidden.
    # The correct password automatically selects outer vs hidden volume.
    cmd_str = f"tcplay --map={mapper_name} --device={device}"

    expect_script = f"""
set timeout 60
spawn {cmd_str}
expect "Passphrase:"
send "{pw_safe}\\r"
expect eof
catch wait result
exit [lindex $result 3]
"""
    try:
        result = subprocess.run(
            ["sudo", "expect", "-c", expect_script],
            capture_output=True,
            check=True,
        )
        log.debug(
            "expect/tcplay --map output (hidden=%s): %s",
            use_hidden,
            result.stdout.decode(errors="replace").strip(),
        )
        return True
    except subprocess.CalledProcessError as exc:
        log.error(
            "expect/tcplay --map failed for %s (use_hidden=%s): stdout=%s stderr=%s",
            mapper_name,
            use_hidden,
            exc.stdout.decode(errors="replace").strip(),
            exc.stderr.decode(errors="replace").strip(),
        )
        return False


def secure_delete(file_path: Path, dry_run: bool = False) -> bool:
    """Securely overwrite and delete a file using shred (3 passes).

    Falls back to os.unlink if shred is not available.

    Returns:
        True on success or if file does not exist; False on error.
    """
    if not file_path.exists():
        return True

    if dry_run:
        log.info("[DRY-RUN] Would shred -n 3 -z -u %s", file_path)
        return True

    try:
        run_cmd(["shred", "-n", "3", "-z", "-u", str(file_path)])
        log.info("Securely deleted: %s", file_path)
        return True
    except FileNotFoundError:
        log.warning("shred not found, falling back to os.unlink for %s.", file_path)
        try:
            file_path.unlink()
            log.info("Deleted (no shred): %s", file_path)
            return True
        except OSError as exc:
            log.error("Failed to delete %s: %s", file_path, exc)
            return False
    except subprocess.CalledProcessError as exc:
        log.error(
            "shred failed for %s: %s",
            file_path,
            exc.stderr.decode(errors="replace"),
        )
        return False


def _unique_mapper_name(prefix: str, tag: str) -> str:
    """Generate a unique /dev/mapper name using a tag and current timestamp."""
    safe_tag = _sanitize_mapper_name(tag)
    ts = int(time.time())
    name = f"{prefix}{safe_tag}_{ts}"
    return name[:63]


def _cleanup_mount(
    mapper_name: str,
    mount_point: Optional[Path],
    container_path: Optional[Path] = None,
    remove_container: bool = False,
) -> None:
    """Best-effort cleanup: unmount, unmap, optionally remove container file."""
    if mount_point and mount_point.exists():
        try:
            subprocess.run(["sudo", "umount", str(mount_point)], capture_output=True)
            log.debug("Unmounted %s (cleanup).", mount_point)
        except Exception:
            pass
        try:
            mount_point.rmdir()
        except Exception:
            pass

    try:
        subprocess.run(["sudo", "tcplay", "--unmap", mapper_name], capture_output=True)
        log.debug("Unmapped %s (cleanup).", mapper_name)
    except Exception:
        pass

    if remove_container and container_path:
        try:
            container_path.unlink(missing_ok=True)
            log.debug("Removed partial container %s (cleanup).", container_path)
        except Exception:
            pass


def _calculate_hidden_size_mb(total_size_mb: int) -> int:
    """Calculate hidden volume size from total container size.

    Hidden volume uses HIDDEN_VOLUME_RATIO (60%) of the total space.
    The hidden volume header occupies the innermost region of the container,
    so tcplay needs to know its size explicitly during --create --hidden.

    Returns:
        Hidden volume size in MB (at least MIN_HIDDEN_SIZE_MB).
    """
    hidden_mb = int(total_size_mb * HIDDEN_VOLUME_RATIO)
    return max(MIN_HIDDEN_SIZE_MB, hidden_mb)


# ─────────────────────────────────────────────
# Step 1: Allocate container file on disk
# ─────────────────────────────────────────────
def _allocate_container(container_path: Path, size_mb: int) -> bool:
    """Pre-allocate the container file filled with random bytes via dd.

    Using /dev/urandom ensures there is no exploitable pattern to distinguish
    the outer volume header region from the hidden volume area.

    Returns:
        True on success, False on failure.
    """
    log.info("Allocating container file: %s (%d MB, random fill).", container_path, size_mb)
    try:
        run_cmd([
            "dd",
            "if=/dev/urandom",
            f"of={container_path}",
            "bs=1M",
            f"count={size_mb}",
        ])
        log.info("Container file allocated: %s (%d MB).", container_path, size_mb)
        return True
    except subprocess.CalledProcessError as exc:
        log.error(
            "dd failed while allocating %s: %s",
            container_path,
            exc.stderr.decode(errors="replace"),
        )
        return False


# ─────────────────────────────────────────────
# Steps 2+3 combined: Create outer + hidden volumes
# ─────────────────────────────────────────────
def create_outer_and_hidden_volumes(
    container_path: Path,
    size_mb: int,
    outer_password: str,
    hidden_password: str,
    dry_run: bool = False,
    weak_keys: bool = False,
) -> bool:
    """Allocate container and create both outer and hidden TrueCrypt headers.

    Uses 'tcplay --create -g' which creates outer + hidden volumes in ONE pass.
    tcplay -g asks for the hidden volume size interactively.

    Prompt sequence (handled via expect):
      1. "Passphrase:"                        ← outer volume passphrase
      2. "Repeat passphrase:"                 ← outer (confirmation)
      3. "Passphrase for hidden volume:"      ← hidden volume passphrase
      4. "Repeat passphrase:"                 ← hidden (confirmation)
      5. "Size of hidden volume (e.g. 127M):" ← hidden size in MB (sent as "<N>M")
      6. "Are you sure ...?" y

    Args:
        container_path:  Destination .tc file (will be created/overwritten).
        size_mb:         Total container size in MB.
        outer_password:  Password for the outer (decoy) volume.
        hidden_password: Password for the hidden (real) volume.
        dry_run:         If True, simulate without making changes.
        weak_keys:       If True, pass -w to tcplay (urandom instead of /dev/random).
                         Dramatically speeds up testing — NEVER use in production.

    Returns:
        True on success, False on failure.
    """
    log.info(
        "═══ Creating outer+hidden volumes: %s (%d MB) ═══",
        container_path,
        size_mb,
    )

    if size_mb < MIN_TOTAL_SIZE_MB:
        log.error(
            "Container size %d MB is below minimum %d MB.", size_mb, MIN_TOTAL_SIZE_MB
        )
        return False

    if dry_run:
        log.info(
            "[DRY-RUN] Would allocate %d MB and create outer+hidden TrueCrypt headers on %s.",
            size_mb,
            container_path,
        )
        return True

    # Ensure parent directory exists
    container_path.parent.mkdir(parents=True, exist_ok=True)

    # Allocate container file with random bytes (urandom fill for security)
    if not _allocate_container(container_path, size_mb):
        return False

    # Attach to loop device (tcplay requires a block device, not a plain file)
    try:
        loop_dev = _setup_loop_device(container_path)
    except subprocess.CalledProcessError as exc:
        log.error(
            "losetup failed for %s: %s",
            container_path,
            exc.stderr.decode(errors="replace"),
        )
        container_path.unlink(missing_ok=True)
        return False

    # Write both outer and hidden volume headers via expect (-g flag)
    try:
        # Calculate hidden volume size: 60% of total, minimum MIN_HIDDEN_SIZE_MB
        hidden_size_mb = max(MIN_HIDDEN_SIZE_MB, int(size_mb * HIDDEN_VOLUME_RATIO))
        log.info(
            "Hidden volume size: %d MB (%.0f%% of %d MB total).",
            hidden_size_mb,
            HIDDEN_VOLUME_RATIO * 100,
            size_mb,
        )
        ok = tcplay_create_with_hidden(
            device=loop_dev,
            outer_password=outer_password,
            hidden_password=hidden_password,
            hidden_size_mb=hidden_size_mb,
            cipher=TCPLAY_CIPHER,
            prf=TCPLAY_PRF,
            timeout=120,
            weak_keys=weak_keys,
        )
        if ok:
            log.info(
                "Outer+hidden volume headers written to %s (via %s).",
                container_path,
                loop_dev,
            )
        else:
            container_path.unlink(missing_ok=True)
        return ok
    finally:
        _detach_loop_device(loop_dev)


# ─────────────────────────────────────────────
# Internal: mount a volume, run callback, unmount
# ─────────────────────────────────────────────
def _mount_volume(
    container_path: Path,
    password: str,
    mapper_tag: str,
    use_hidden: bool = False,
    format_fat32: bool = False,
) -> tuple[Optional[str], Optional[Path], Optional[str]]:
    """Map a TrueCrypt volume and mount it under a temporary directory.

    Args:
        container_path: Path to the .tc container.
        password:       Volume password.
        mapper_tag:     Short tag used to build the /dev/mapper name.
        use_hidden:     Pass --use-hidden to tcplay for hidden volume access.
        format_fat32:   Format the mapped device as FAT32 before mounting.

    Returns:
        Tuple (mapper_name, mount_point, loop_dev) on success,
        (None, None, None) on failure.
        Caller is responsible for calling _unmount_volume(mapper_name, mount_point, loop_dev).
    """
    mapper_name = _unique_mapper_name(MAPPER_PREFIX, mapper_tag)
    mapper_dev = Path(f"/dev/mapper/{mapper_name}")
    mount_point = Path(tempfile.mkdtemp(prefix="phantom_mnt_"))

    # Attach container to loop device for tcplay --map
    try:
        loop_dev = _setup_loop_device(container_path)
    except subprocess.CalledProcessError as exc:
        log.error(
            "losetup failed for %s: %s",
            container_path,
            exc.stderr.decode(errors="replace"),
        )
        try:
            mount_point.rmdir()
        except OSError:
            pass
        return None, None, None

    # Map volume via expect (tcplay reads passphrase from /dev/tty)
    ok = _tcplay_map_expect(mapper_name, loop_dev, password, use_hidden=use_hidden)
    if not ok:
        _detach_loop_device(loop_dev)
        try:
            mount_point.rmdir()
        except OSError:
            pass
        return None, None, None

    log.info(
        "Volume mapped: /dev/mapper/%s (hidden=%s).",
        mapper_name,
        use_hidden,
    )

    # Wait for udev to create the /dev/mapper/<name> device node before use.
    # Without this, mkfs.fat or mount may race against udev and see ENOENT.
    try:
        subprocess.run(["sudo", "udevadm", "settle"], capture_output=True, check=False)
    except FileNotFoundError:
        pass  # udevadm not available on all systems; best-effort

    # Extra wait to ensure dm-crypt device node appears in /dev/mapper/
    time.sleep(0.5)

    if format_fat32:
        try:
            # Let mkfs.fat auto-select FAT type — FAT32 needs ≥65536 clusters,
            # small volumes (<64 MB) will use FAT16 automatically, which is fine
            # for TrueCrypt containers and fully readable by TrueCrypt 7.1a.
            run_cmd(["sudo", "mkfs.fat", str(mapper_dev)])
            log.info("FAT filesystem created on /dev/mapper/%s.", mapper_name)
        except subprocess.CalledProcessError as exc:
            log.error(
                "mkfs.fat failed on %s: %s",
                mapper_dev,
                exc.stderr.decode(errors="replace"),
            )
            _cleanup_mount(mapper_name, mount_point)
            _detach_loop_device(loop_dev)
            try:
                mount_point.rmdir()
            except OSError:
                pass
            return None, None, None

    try:
        run_cmd(["sudo", "mount", str(mapper_dev), str(mount_point)])
        log.info("Mounted /dev/mapper/%s → %s.", mapper_name, mount_point)
        return mapper_name, mount_point, loop_dev
    except subprocess.CalledProcessError as exc:
        log.error(
            "mount failed for /dev/mapper/%s → %s: %s",
            mapper_name,
            mount_point,
            exc.stderr.decode(errors="replace"),
        )
        _cleanup_mount(mapper_name, mount_point)
        _detach_loop_device(loop_dev)
        try:
            mount_point.rmdir()
        except OSError:
            pass
        return None, None, None


def _unmount_volume(
    mapper_name: str,
    mount_point: Path,
    loop_dev: Optional[str] = None,
) -> bool:
    """Unmount a mounted volume, unmap dm-crypt device, and detach loop device.

    Args:
        mapper_name: /dev/mapper/<name> to unmap.
        mount_point: Temporary directory to unmount and remove.
        loop_dev:    Loop device to detach (e.g. '/dev/loop3').
                     If None, no loop device is detached.

    Returns:
        True if all operations succeeded; False otherwise.
    """
    success = True

    # Step 1: sync + unmount filesystem
    try:
        run_cmd(["sync"])
        run_cmd(["sudo", "umount", str(mount_point)])
        log.info("Unmounted %s.", mount_point)
    except subprocess.CalledProcessError as exc:
        log.error(
            "umount failed for %s: %s",
            mount_point,
            exc.stderr.decode(errors="replace"),
        )
        success = False

    # Step 2: unmap dm-crypt device
    try:
        run_cmd(["sudo", "tcplay", "--unmap", mapper_name])
        log.info("Unmapped /dev/mapper/%s.", mapper_name)
    except subprocess.CalledProcessError as exc:
        log.error(
            "tcplay --unmap failed for %s: %s",
            mapper_name,
            exc.stderr.decode(errors="replace"),
        )
        success = False

    # Step 3: detach the specific loop device that was created for this mount
    if loop_dev:
        _detach_loop_device(loop_dev)

    # Step 4: clean up temporary mount directory
    try:
        mount_point.rmdir()
    except OSError:
        pass

    return success


# ─────────────────────────────────────────────
# Step 4: Populate outer volume with decoy files
# ─────────────────────────────────────────────
def populate_outer_volume(
    container_path: Path,
    outer_password: str,
    decoy_files_dir: Path,
    dry_run: bool = False,
) -> bool:
    """Mount the outer volume and copy decoy files into it.

    ⚠️  IMPORTANT: Never write to the outer volume after the hidden volume has
    been populated with real data.  Doing so may corrupt hidden volume content
    because the outer volume's filesystem can overwrite the hidden volume's
    data region.  Call this function BEFORE populate_hidden_volume.

    Args:
        container_path:  Path to the .tc container.
        outer_password:  Outer volume password.
        decoy_files_dir: Directory whose contents are copied into the outer volume.
        dry_run:         If True, simulate without making changes.

    Returns:
        True on success, False on failure.
    """
    log.info(
        "═══ Populating outer volume with decoy files from %s ═══",
        decoy_files_dir,
    )

    if dry_run:
        decoy_files = list(decoy_files_dir.glob("*")) if decoy_files_dir.exists() else []
        log.info(
            "[DRY-RUN] Would copy %d decoy file(s) from %s into outer volume of %s.",
            len(decoy_files),
            decoy_files_dir,
            container_path,
        )
        return True

    if not container_path.exists():
        log.error("Container file not found: %s", container_path)
        return False

    if not decoy_files_dir.exists():
        log.warning("Decoy files directory not found: %s — outer volume will be empty.", decoy_files_dir)

    # Mount outer volume (format FAT32 on first mount)
    mapper_name, mount_point, loop_dev = _mount_volume(
        container_path,
        outer_password,
        mapper_tag="outer",
        use_hidden=False,
        format_fat32=True,
    )
    if not mapper_name:
        return False

    copy_ok = True
    try:
        if decoy_files_dir.exists():
            for src in decoy_files_dir.iterdir():
                if src.is_file():
                    dest = mount_point / src.name
                    run_cmd(["sudo", "cp", str(src), str(dest)])
                    log.info("Copied decoy file: %s → %s", src.name, dest)
        else:
            log.warning("No decoy files to copy — outer volume created empty.")
    except subprocess.CalledProcessError as exc:
        log.error(
            "Failed to copy decoy files: %s",
            exc.stderr.decode(errors="replace"),
        )
        copy_ok = False
    finally:
        unmount_ok = _unmount_volume(mapper_name, mount_point, loop_dev)
        if not unmount_ok:
            copy_ok = False

    if copy_ok:
        log.info("Outer volume populated successfully.")
    return copy_ok


# ─────────────────────────────────────────────
# Step 5: Populate hidden volume with real audio files
# ─────────────────────────────────────────────
def populate_hidden_volume(
    container_path: Path,
    hidden_password: str,
    real_files: List[Path],
    dry_run: bool = False,
) -> bool:
    """Mount the hidden volume and copy real .opus files into it.

    After this step, never mount the outer volume with write access — doing so
    may silently overwrite the hidden volume's data blocks.

    Args:
        container_path:  Path to the .tc container.
        hidden_password: Hidden volume password.
        real_files:      List of .opus files to copy.
        dry_run:         If True, simulate without making changes.

    Returns:
        True on success, False on failure.
    """
    log.info(
        "═══ Populating hidden volume with %d audio file(s) ═══",
        len(real_files),
    )

    if dry_run:
        for f in real_files:
            log.info("[DRY-RUN] Would copy %s into hidden volume of %s.", f, container_path)
        return True

    if not container_path.exists():
        log.error("Container file not found: %s", container_path)
        return False

    if not real_files:
        log.warning("No audio files provided — hidden volume will be empty.")

    # Mount hidden volume (format FAT32 on first write)
    mapper_name, mount_point, loop_dev = _mount_volume(
        container_path,
        hidden_password,
        mapper_tag="hidden",
        use_hidden=True,
        format_fat32=True,
    )
    if not mapper_name:
        return False

    copy_ok = True
    try:
        for opus_file in real_files:
            if not opus_file.exists():
                log.warning("Audio file not found, skipping: %s", opus_file)
                continue
            dest = mount_point / opus_file.name
            run_cmd(["sudo", "cp", str(opus_file), str(dest)])
            log.info("Copied audio file: %s → hidden volume", opus_file.name)
    except subprocess.CalledProcessError as exc:
        log.error(
            "Failed to copy audio files: %s",
            exc.stderr.decode(errors="replace"),
        )
        copy_ok = False
    finally:
        unmount_ok = _unmount_volume(mapper_name, mount_point, loop_dev)
        if not unmount_ok:
            copy_ok = False

    if copy_ok:
        log.info("Hidden volume populated successfully.")
    return copy_ok


# ─────────────────────────────────────────────
# Step 6: Verify both volumes mount correctly
# ─────────────────────────────────────────────
def verify_container(
    container_path: Path,
    outer_password: str,
    hidden_password: str,
    dry_run: bool = False,
) -> bool:
    """Test-mount both outer and hidden volumes to verify the container is valid.

    This does NOT format or write anything — it only opens, lists files, then
    closes each volume.

    Args:
        container_path:  Path to the .tc container.
        outer_password:  Outer volume password.
        hidden_password: Hidden volume password.
        dry_run:         If True, simulate without making changes.

    Returns:
        True if both volumes open and list successfully; False otherwise.
    """
    log.info("═══ Verifying container: %s ═══", container_path)

    if dry_run:
        log.info("[DRY-RUN] Would verify outer and hidden volumes of %s.", container_path)
        return True

    if not container_path.exists():
        log.error("Container file not found for verification: %s", container_path)
        return False

    results = {}

    for label, password, use_hidden in [
        ("outer", outer_password, False),
        ("hidden", hidden_password, True),
    ]:
        log.info("Verifying %s volume …", label)
        mapper_name, mount_point, loop_dev = _mount_volume(
            container_path,
            password,
            mapper_tag=f"verify_{label}",
            use_hidden=use_hidden,
            format_fat32=False,   # Do NOT format — we want read-only verification
        )
        if not mapper_name:
            log.error("%s volume: mount FAILED.", label.capitalize())
            results[label] = False
            continue

        # List files in the mounted volume
        try:
            result = subprocess.run(
                ["sudo", "ls", "-lh", str(mount_point)],
                capture_output=True,
                text=True,
            )
            file_list = result.stdout.strip()
            log.info("%s volume files:\n%s", label.capitalize(), file_list or "(empty)")
            results[label] = True
        except Exception as exc:
            log.warning("Could not list files in %s volume: %s", label, exc)
            results[label] = True  # Mount succeeded; listing is non-critical

        _unmount_volume(mapper_name, mount_point, loop_dev)
        log.info("%s volume: OK ✓", label.capitalize())

    all_ok = all(results.values())
    if all_ok:
        log.info("Container verification PASSED — both volumes accessible.")
    else:
        failed = [k for k, v in results.items() if not v]
        log.error("Container verification FAILED for: %s", ", ".join(failed))
    return all_ok


# ─────────────────────────────────────────────
# Orchestrator: full pipeline
# ─────────────────────────────────────────────
def create_full_hidden_container(
    container_path: Path,
    total_size_mb: int,
    outer_password: str,
    hidden_password: str,
    opus_files: List[Path],
    decoy_dir: Path,
    dry_run: bool = False,
    weak_keys: bool = False,
) -> bool:
    """Orchestrate the full hidden volume container creation pipeline.

    Pipeline (4 steps):
      1. create_outer_and_hidden_volumes  — allocate file + write outer+hidden headers
                                            via 'tcplay --create -g' in one pass
      2. populate_outer_volume            — mount outer, copy decoy files, unmount
      3. populate_hidden_volume           — mount hidden, copy .opus files, unmount
      4. verify_container                 — test-mount both volumes and confirm access

    Note: tcplay -g manages size allocation internally — no explicit hidden size needed.

    Args:
        container_path:  Destination .tc file path.
        total_size_mb:   Total container size in MB.
        outer_password:  Password for the outer (decoy) volume.
        hidden_password: Password for the hidden (real) volume.
        opus_files:      List of .opus audio files to store in the hidden volume.
        decoy_dir:       Directory of decoy files for the outer volume.
        dry_run:         If True, simulate the entire pipeline without changes.

    Returns:
        True on full pipeline success, False on any step failure.
    """
    start_ts = datetime.now(tz=timezone.utc).isoformat()
    log.info(
        "╔══════════════════════════════════════════════════════╗"
    )
    log.info("║  PHANTOM R3 — Hidden Container Pipeline Start       ║")
    log.info(
        "╚══════════════════════════════════════════════════════╝"
    )
    log.info("Started at: %s", start_ts)
    log.info("Container:  %s", container_path)
    log.info("Total size: %d MB", total_size_mb)

    # tcplay -g manages size allocation internally — no explicit split needed
    log.info("Size:       %d MB total (tcplay -g manages outer/hidden split)", total_size_mb)
    log.info("Opus files: %d", len(opus_files))
    log.info("Decoy dir:  %s", decoy_dir)

    # Idempotency: skip if container already exists
    if container_path.exists() and not dry_run:
        log.warning(
            "Container already exists: %s — delete it first to recreate.",
            container_path,
        )
        return False

    # ── Step 1: Create outer + hidden volumes in one tcplay -g call ────────
    log.info("── Step 1/4: Create outer+hidden volumes ───────────────")
    if not create_outer_and_hidden_volumes(
        container_path, total_size_mb, outer_password, hidden_password,
        dry_run=dry_run, weak_keys=weak_keys,
    ):
        log.error("Pipeline aborted at step 1 (create outer+hidden volumes).")
        return False

    # ── Step 2: Populate outer volume with decoy files ──────────────────
    # MUST happen before step 3 (writing to outer after hidden data is present
    # would corrupt the hidden volume).
    log.info("── Step 2/4: Populate outer volume (decoy) ─────────────")
    if not populate_outer_volume(container_path, outer_password, decoy_dir, dry_run):
        log.error("Pipeline aborted at step 2 (populate outer volume).")
        if not dry_run:
            container_path.unlink(missing_ok=True)
        return False

    # ── Step 3: Populate hidden volume with real audio ──────────────────
    log.info("── Step 3/4: Populate hidden volume (audio) ─────────────")
    if not populate_hidden_volume(container_path, hidden_password, opus_files, dry_run):
        log.error("Pipeline aborted at step 3 (populate hidden volume).")
        if not dry_run:
            container_path.unlink(missing_ok=True)
        return False

    # ── Step 4: Verify both volumes ─────────────────────────────────────
    log.info("── Step 4/4: Verify container ──────────────────────────")
    if not verify_container(container_path, outer_password, hidden_password, dry_run):
        log.error("Verification failed — container may be corrupt.")
        return False

    end_ts = datetime.now(tz=timezone.utc).isoformat()
    log.info(
        "╔══════════════════════════════════════════════════════╗"
    )
    log.info("║  Pipeline COMPLETE — container ready                ║")
    log.info(
        "╚══════════════════════════════════════════════════════╝"
    )
    log.info("Completed at: %s", end_ts)
    actual_mb = container_path.stat().st_size / (1024 * 1024) if not dry_run else float(total_size_mb)
    log.info("Container:    %s  (%.1f MB)", container_path, actual_mb)
    log.info("")
    log.info("┌─ Access instructions ─────────────────────────────────")
    log.info("│  Outer (decoy)  password → opens harmless files only")
    log.info("│  Hidden (real)  password → opens audio recordings")
    log.info("│")
    log.info("│  ⚠  Never mount outer volume after hidden data is written!")
    log.info("└───────────────────────────────────────────────────────")
    return True


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PHANTOM R3 — Create TrueCrypt hidden volume container",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic hidden container from env passwords
  export PHANTOM_OUTER_PASSWORD="decoy_pass"
  export PHANTOM_HIDDEN_PASSWORD="real_pass"
  sudo python3 create_hidden_container.py \\
      --output /phantom/encrypted/recording.tc \\
      --size 50 \\
      --audio-files /tmp/phantom/*.opus

  # Explicit passwords via CLI
  sudo python3 create_hidden_container.py \\
      --output recording.tc \\
      --size 50 \\
      --outer-password "decoy_pass" \\
      --hidden-password "real_pass" \\
      --audio-files /tmp/phantom/rec1.opus /tmp/phantom/rec2.opus \\
      --decoy-dir /tmp/phantom/decoy

  # Dry-run (no changes to disk)
  sudo python3 create_hidden_container.py \\
      --output recording.tc \\
      --size 50 \\
      --outer-password "decoy_pass" \\
      --hidden-password "real_pass" \\
      --audio-files /tmp/phantom/*.opus \\
      --dry-run
        """,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination path for the .tc container file (e.g. /phantom/encrypted/rec.tc).",
    )
    parser.add_argument(
        "--size",
        type=int,
        required=True,
        help=f"Total container size in MB (minimum {MIN_TOTAL_SIZE_MB} MB).",
    )
    parser.add_argument(
        "--outer-password",
        type=str,
        default=None,
        help="Outer (decoy) volume password. Overridden by PHANTOM_OUTER_PASSWORD env var.",
    )
    parser.add_argument(
        "--hidden-password",
        type=str,
        default=None,
        help="Hidden (real) volume password. Overridden by PHANTOM_HIDDEN_PASSWORD env var.",
    )
    parser.add_argument(
        "--audio-files",
        type=str,
        nargs="*",
        default=[],
        help="One or more .opus files to store in the hidden volume. Supports glob patterns.",
    )
    parser.add_argument(
        "--decoy-dir",
        type=Path,
        default=Path("/tmp/phantom/decoy"),
        help="Directory containing decoy files for the outer volume (default: /tmp/phantom/decoy).",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=LOG_DIR,
        help=f"Directory for log files (default: {LOG_DIR}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate all operations without making actual disk changes.",
    )
    parser.add_argument(
        "--weak-keys",
        action="store_true",
        dest="weak_keys",
        help=(
            "Pass -w (--weak-keys) to tcplay: use urandom instead of /dev/random for "
            "key material.  Dramatically speeds up testing on Raspberry Pi. "
            "NEVER use in production — reduces entropy quality."
        ),
    )
    return parser.parse_args()


def _resolve_audio_files(patterns: List[str]) -> List[Path]:
    """Expand glob patterns in audio file arguments to actual Path objects."""
    resolved: List[Path] = []
    for pattern in patterns:
        expanded = glob.glob(pattern)
        if expanded:
            resolved.extend(Path(p) for p in sorted(expanded))
        else:
            # Treat as a literal path even if glob found nothing
            p = Path(pattern)
            if p.exists():
                resolved.append(p)
            else:
                log.warning("Audio file/pattern not found: %s", pattern)
    return resolved


def main() -> int:
    args = parse_args()

    log_file = args.log_dir / "hidden_container.log"
    setup_logging(log_file=log_file, dry_run=args.dry_run)

    run_start = datetime.now(tz=timezone.utc)
    log.info(
        "═══ PHANTOM R3 Hidden Container started at %s ═══",
        run_start.isoformat(),
    )

    # Load passwords
    try:
        outer_password = load_password(
            ENV_OUTER_PASSWORD, args.outer_password, "outer"
        )
        hidden_password = load_password(
            ENV_HIDDEN_PASSWORD, args.hidden_password, "hidden"
        )
    except RuntimeError as exc:
        log.error("Password error: %s", exc)
        return 1

    if outer_password == hidden_password:
        log.error(
            "Outer and hidden passwords must be DIFFERENT. "
            "Using the same password defeats plausible deniability."
        )
        return 1

    # Resolve audio file paths (expand globs)
    opus_files = _resolve_audio_files(args.audio_files)
    log.info("Resolved %d audio file(s).", len(opus_files))

    # Validate size
    if args.size < MIN_TOTAL_SIZE_MB:
        log.error(
            "Container size %d MB is below minimum %d MB.",
            args.size,
            MIN_TOTAL_SIZE_MB,
        )
        return 1

    # Run the full pipeline
    success = create_full_hidden_container(
        container_path=args.output,
        total_size_mb=args.size,
        outer_password=outer_password,
        hidden_password=hidden_password,
        opus_files=opus_files,
        decoy_dir=args.decoy_dir,
        dry_run=args.dry_run,
        weak_keys=args.weak_keys,
    )

    run_end = datetime.now(tz=timezone.utc)
    elapsed = (run_end - run_start).total_seconds()
    log.info(
        "═══ Finished in %.1f s — Status: %s ═══",
        elapsed,
        "SUCCESS" if success else "FAILED",
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
