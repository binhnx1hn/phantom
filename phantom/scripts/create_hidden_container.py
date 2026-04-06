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
# Step 2: Create outer TrueCrypt volume header
# ─────────────────────────────────────────────
def create_outer_volume(
    container_path: Path,
    size_mb: int,
    outer_password: str,
    dry_run: bool = False,
) -> bool:
    """Create a TrueCrypt outer volume on a new container file.

    This allocates the container on disk and writes the outer volume header
    using tcplay --create (without --hidden flag).

    Args:
        container_path:  Destination .tc file (will be created/overwritten).
        size_mb:         Total container size in MB.
        outer_password:  Password for the outer (decoy) volume.
        dry_run:         If True, simulate without making changes.

    Returns:
        True on success, False on failure.
    """
    log.info(
        "═══ Creating outer volume: %s (%d MB) ═══",
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
            "[DRY-RUN] Would allocate %d MB and create outer TrueCrypt header on %s.",
            size_mb,
            container_path,
        )
        return True

    # Ensure parent directory exists
    container_path.parent.mkdir(parents=True, exist_ok=True)

    # Allocate container file
    if not _allocate_container(container_path, size_mb):
        return False

    # Write outer volume TrueCrypt header
    # tcplay reads password + confirmation from stdin (two identical lines)
    pw_bytes = (outer_password + "\n").encode() * 2
    try:
        run_cmd(
            [
                "sudo", "tcplay",
                "--create",
                f"--device={container_path}",
                f"--cipher={TCPLAY_CIPHER}",
                f"--pbkdf-prf={TCPLAY_PRF}",
            ],
            input_data=pw_bytes,
        )
        log.info("Outer volume header written to %s.", container_path)
        return True
    except subprocess.CalledProcessError as exc:
        log.error(
            "tcplay --create (outer) failed: %s",
            exc.stderr.decode(errors="replace"),
        )
        container_path.unlink(missing_ok=True)
        return False


# ─────────────────────────────────────────────
# Step 3: Create hidden volume header inside outer
# ─────────────────────────────────────────────
def create_hidden_volume(
    container_path: Path,
    hidden_size_mb: int,
    outer_password: str,
    hidden_password: str,
    dry_run: bool = False,
) -> bool:
    """Write a hidden TrueCrypt volume header inside an existing outer volume.

    tcplay --create --hidden requires:
      - The outer password (to locate the outer header and avoid overwriting it)
      - The hidden password (new password for the inner volume)
      - The hidden volume size (to carve space from the container tail)

    The hidden volume lives in the free space of the outer volume.  tcplay
    places the hidden header at a known offset calculated from the container end
    and hidden_size_mb.

    Args:
        container_path:  Existing .tc file that already has an outer volume header.
        hidden_size_mb:  Size of the hidden volume in MB (≤ 60% of total).
        outer_password:  Outer volume password (needed to protect outer header).
        hidden_password: Password for the hidden volume.
        dry_run:         If True, simulate without making changes.

    Returns:
        True on success, False on failure.
    """
    log.info(
        "═══ Creating hidden volume inside %s (hidden=%d MB) ═══",
        container_path,
        hidden_size_mb,
    )

    if dry_run:
        log.info(
            "[DRY-RUN] Would create hidden volume (%d MB) inside %s.",
            hidden_size_mb,
            container_path,
        )
        return True

    if not container_path.exists():
        log.error("Container file not found: %s", container_path)
        return False

    # tcplay --create --hidden stdin protocol:
    #   Line 1: outer password   (to authenticate and protect outer header)
    #   Line 2: hidden password  (new password for the inner volume)
    #   Line 3: hidden password  (confirmation)
    stdin_data = (
        outer_password + "\n"
        + hidden_password + "\n"
        + hidden_password + "\n"
    ).encode()

    try:
        run_cmd(
            [
                "sudo", "tcplay",
                "--create",
                "--hidden",
                f"--device={container_path}",
                f"--cipher={TCPLAY_CIPHER}",
                f"--pbkdf-prf={TCPLAY_PRF}",
                f"--hidden-size-bytes={hidden_size_mb * 1024 * 1024}",
            ],
            input_data=stdin_data,
        )
        log.info(
            "Hidden volume header written inside %s (%d MB).",
            container_path,
            hidden_size_mb,
        )
        return True
    except subprocess.CalledProcessError as exc:
        log.error(
            "tcplay --create --hidden failed: %s",
            exc.stderr.decode(errors="replace"),
        )
        return False


# ─────────────────────────────────────────────
# Internal: mount a volume, run callback, unmount
# ─────────────────────────────────────────────
def _mount_volume(
    container_path: Path,
    password: str,
    mapper_tag: str,
    use_hidden: bool = False,
    format_fat32: bool = False,
) -> tuple[Optional[str], Optional[Path]]:
    """Map a TrueCrypt volume and mount it under a temporary directory.

    Args:
        container_path: Path to the .tc container.
        password:       Volume password.
        mapper_tag:     Short tag used to build the /dev/mapper name.
        use_hidden:     Pass --use-hidden to tcplay for hidden volume access.
        format_fat32:   Format the mapped device as FAT32 before mounting.

    Returns:
        Tuple (mapper_name, mount_point) on success, (None, None) on failure.
        Caller is responsible for calling _unmount_volume when done.
    """
    mapper_name = _unique_mapper_name(MAPPER_PREFIX, mapper_tag)
    mapper_dev = Path(f"/dev/mapper/{mapper_name}")
    mount_point = Path(tempfile.mkdtemp(prefix="phantom_mnt_"))

    # Build tcplay map command
    map_cmd = [
        "sudo", "tcplay",
        f"--map={mapper_name}",
        f"--device={container_path}",
    ]
    if use_hidden:
        map_cmd.append("--use-hidden")

    pw_bytes = (password + "\n").encode()

    try:
        run_cmd(map_cmd, input_data=pw_bytes)
        log.info(
            "Volume mapped: /dev/mapper/%s (hidden=%s).",
            mapper_name,
            use_hidden,
        )
    except subprocess.CalledProcessError as exc:
        log.error(
            "tcplay --map failed (hidden=%s): %s",
            use_hidden,
            exc.stderr.decode(errors="replace"),
        )
        try:
            mount_point.rmdir()
        except OSError:
            pass
        return None, None

    # Wait for udev to create the /dev/mapper/<name> device node before use.
    # Without this, mkfs.fat or mount may race against udev and see ENOENT.
    try:
        subprocess.run(["sudo", "udevadm", "settle"], capture_output=True, check=False)
    except FileNotFoundError:
        pass  # udevadm not available on all systems; best-effort

    if format_fat32:
        try:
            run_cmd(["sudo", "mkfs.fat", "-F", "32", str(mapper_dev)])
            log.info("FAT32 filesystem created on /dev/mapper/%s.", mapper_name)
        except subprocess.CalledProcessError as exc:
            log.error(
                "mkfs.fat failed on %s: %s",
                mapper_dev,
                exc.stderr.decode(errors="replace"),
            )
            _cleanup_mount(mapper_name, mount_point)
            try:
                mount_point.rmdir()
            except OSError:
                pass
            return None, None

    try:
        run_cmd(["sudo", "mount", str(mapper_dev), str(mount_point)])
        log.info("Mounted /dev/mapper/%s → %s.", mapper_name, mount_point)
        return mapper_name, mount_point
    except subprocess.CalledProcessError as exc:
        log.error(
            "mount failed for /dev/mapper/%s → %s: %s",
            mapper_name,
            mount_point,
            exc.stderr.decode(errors="replace"),
        )
        _cleanup_mount(mapper_name, mount_point)
        try:
            mount_point.rmdir()
        except OSError:
            pass
        return None, None


def _unmount_volume(mapper_name: str, mount_point: Path) -> bool:
    """Unmount a mounted volume and remove the temporary mount directory.

    Returns:
        True if unmount and unmap succeeded; False otherwise.
    """
    success = True

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
    mapper_name, mount_point = _mount_volume(
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
        unmount_ok = _unmount_volume(mapper_name, mount_point)
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
    mapper_name, mount_point = _mount_volume(
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
        unmount_ok = _unmount_volume(mapper_name, mount_point)
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
        mapper_name, mount_point = _mount_volume(
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

        _unmount_volume(mapper_name, mount_point)
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
) -> bool:
    """Orchestrate the full hidden volume container creation pipeline.

    Pipeline:
      1. create_outer_volume       — allocate file + write outer TrueCrypt header
      2. create_hidden_volume      — write hidden header inside outer free space
      3. populate_outer_volume     — mount outer, copy decoy files, unmount
      4. populate_hidden_volume    — mount hidden, copy .opus files, unmount
      5. verify_container          — test-mount both volumes and confirm access

    Size allocation:
      - Total  = total_size_mb
      - Hidden = floor(total * HIDDEN_VOLUME_RATIO)  [60% default]
      - Outer  = remainder                            [40% default]

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

    hidden_size_mb = _calculate_hidden_size_mb(total_size_mb)
    log.info(
        "Size split: outer=%d MB (+headers), hidden=%d MB",
        total_size_mb - hidden_size_mb,
        hidden_size_mb,
    )
    log.info("Opus files: %d", len(opus_files))
    log.info("Decoy dir:  %s", decoy_dir)

    # Idempotency: skip if container already exists
    if container_path.exists() and not dry_run:
        log.warning(
            "Container already exists: %s — delete it first to recreate.",
            container_path,
        )
        return False

    # ── Step 1: Create outer volume ────────────────────────────────────────
    log.info("── Step 1/5: Create outer volume ──────────────────────")
    if not create_outer_volume(container_path, total_size_mb, outer_password, dry_run):
        log.error("Pipeline aborted at step 1 (create outer volume).")
        return False

    # ── Step 2: Create hidden volume inside outer ───────────────────────
    log.info("── Step 2/5: Create hidden volume ─────────────────────")
    if not create_hidden_volume(
        container_path, hidden_size_mb, outer_password, hidden_password, dry_run
    ):
        log.error("Pipeline aborted at step 2 (create hidden volume).")
        if not dry_run:
            container_path.unlink(missing_ok=True)
        return False

    # ── Step 3: Populate outer volume with decoy files ──────────────────
    # MUST happen before step 4 (writing to outer after hidden data is present
    # would corrupt the hidden volume).
    log.info("── Step 3/5: Populate outer volume (decoy) ─────────────")
    if not populate_outer_volume(container_path, outer_password, decoy_dir, dry_run):
        log.error("Pipeline aborted at step 3 (populate outer volume).")
        if not dry_run:
            container_path.unlink(missing_ok=True)
        return False

    # ── Step 4: Populate hidden volume with real audio ──────────────────
    log.info("── Step 4/5: Populate hidden volume (audio) ─────────────")
    if not populate_hidden_volume(container_path, hidden_password, opus_files, dry_run):
        log.error("Pipeline aborted at step 4 (populate hidden volume).")
        if not dry_run:
            container_path.unlink(missing_ok=True)
        return False

    # ── Step 5: Verify both volumes ─────────────────────────────────────
    log.info("── Step 5/5: Verify container ──────────────────────────")
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
