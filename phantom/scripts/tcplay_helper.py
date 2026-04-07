#!/usr/bin/env python3
"""
PHANTOM R3 - tcplay PTY Helper
================================
tcplay v3.x reads and writes passwords via /dev/tty (getpass), not stdin/stdout.
subprocess.run(..., input=...) cannot feed passwords to tcplay.

This module uses pexpect to spawn tcplay inside a real PTY so that:
  - tcplay's getpass() writes "Passphrase:" to the PTY slave
  - pexpect reads it and sends the password back through the same PTY
  - All prompts (passphrase, repeat, confirmation) are handled automatically

Functions exposed:
  tcplay_create(device, password, cipher, prf, timeout) -> bool
  tcplay_create_hidden(device, outer_pw, hidden_pw, hidden_size_bytes,
                       cipher, prf, timeout) -> bool
  tcplay_map(device, mapper_name, password, use_hidden, timeout) -> bool
  tcplay_unmap(mapper_name) -> bool
  tcplay_info(device, password) -> dict | None

All functions return True/False (or dict/None for info).
Logging uses the standard 'phantom.tcplay' logger.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

import pexpect

log = logging.getLogger("phantom.tcplay")

# ── tcplay binary path ────────────────────────────────────────────────────────
TCPLAY_BIN = "/usr/sbin/tcplay"

# ── Default cipher / PRF ──────────────────────────────────────────────────────
DEFAULT_CIPHER = "AES-256-XTS"
DEFAULT_PRF    = "SHA512"

# ── pexpect prompt patterns ───────────────────────────────────────────────────
# tcplay uses getpass() which writes directly to /dev/tty.
# Pattern must match case-insensitively; tcplay v3 says "Passphrase: "
_PAT_PASS      = r"(?i)passphrase\s*:"
_PAT_REPEAT    = r"(?i)(repeat|confirm|retype).*passphrase\s*:"
_PAT_OUTER     = r"(?i)outer.*passphrase\s*:"          # hidden-create step
_PAT_HIDDEN    = r"(?i)hidden.*passphrase\s*:"         # hidden-create step
_PAT_CONFIRM   = r"(?i)(are you sure|sure\?|\[y/n\]|\[yes/no\]|overwrite|proceed|continue|will be written)"
_PAT_EOF       = pexpect.EOF
_PAT_TIMEOUT   = pexpect.TIMEOUT


def _run_tcplay(
    args: list[str],
    interactions: list[tuple],   # list of (pattern, response) pairs
    timeout: int = 120,
    label: str = "",
) -> bool:
    """
    Spawn tcplay with given args inside a PTY (via pexpect) and drive it
    through a sequence of (pattern, response) interactions.

    Each interaction is a tuple:
        (pattern_or_list, response_string | None)
    where response_string is sent when the pattern matches.
    None response means 'just wait / no send'.

    After all interactions are exhausted, wait for EOF.

    Returns True on clean exit (rc == 0), False otherwise.
    """
    cmd = [TCPLAY_BIN] + args
    log.debug("[%s] Spawning: %s", label, " ".join(cmd))

    try:
        child = pexpect.spawn(
            cmd[0],
            args=cmd[1:],
            timeout=timeout,
            encoding="utf-8",
            echo=False,          # Don't echo passwords back
            codec_errors="replace",
        )
    except Exception as exc:
        log.error("[%s] Failed to spawn tcplay: %s", label, exc)
        return False

    try:
        # Drive through interactions
        for idx, (pattern, response) in enumerate(interactions):
            patterns = pattern if isinstance(pattern, list) else [pattern]
            # Always add EOF and TIMEOUT as fallback
            watch_list = patterns + [_PAT_EOF, _PAT_TIMEOUT]

            matched = child.expect(watch_list, timeout=timeout)

            if matched >= len(patterns):
                # EOF or TIMEOUT before expected prompt
                kind = "EOF" if matched == len(patterns) else "TIMEOUT"
                log.error(
                    "[%s] Step %d: got %s before pattern %r. "
                    "Buffer so far: %r",
                    label, idx, kind, pattern, child.before,
                )
                child.close(force=True)
                return False

            log.debug(
                "[%s] Step %d matched pattern %r. Buffer: %r",
                label, idx, patterns[matched], child.before,
            )

            if response is not None:
                child.sendline(response)
                log.debug("[%s] Step %d: sent response.", label, idx)

        # Wait for process to finish
        child.expect(_PAT_EOF, timeout=timeout)
        child.close()
        rc = child.exitstatus if child.exitstatus is not None else child.signalstatus
        log.debug("[%s] tcplay exited with rc=%s", label, rc)

        if rc == 0:
            log.info("[%s] tcplay completed successfully.", label)
            return True
        else:
            log.error("[%s] tcplay failed with rc=%s", label, rc)
            return False

    except pexpect.EOF:
        child.close()
        rc = child.exitstatus
        if rc == 0:
            log.info("[%s] tcplay completed (EOF, rc=0).", label)
            return True
        log.error("[%s] tcplay EOF with rc=%s", label, rc)
        return False

    except pexpect.TIMEOUT:
        log.error("[%s] tcplay timed out after %ds.", label, timeout)
        child.close(force=True)
        return False

    except Exception as exc:
        log.error("[%s] Unexpected error driving tcplay: %s", label, exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def tcplay_create(
    device: str,
    password: str,
    cipher: str = DEFAULT_CIPHER,
    prf: str = DEFAULT_PRF,
    timeout: int = 120,
) -> bool:
    """
    Create a standard (non-hidden) TrueCrypt volume on *device*.

    tcplay interaction sequence for --create:
      1. "Passphrase: "         → send password
      2. "Repeat passphrase: "  → send password
      3. "Are you sure ..." OR eof → send "y" or nothing

    Returns True on success.
    """
    args = [
        "--create",
        f"--device={device}",
        f"--cipher={cipher}",
        f"--pbkdf-prf={prf}",
    ]

    interactions = [
        # Step 1: First passphrase prompt
        (_PAT_PASS, password),
        # Step 2: Repeat/confirm passphrase
        (_PAT_REPEAT, password),
        # Step 3: Optional confirmation prompt ("Are you sure?")
        # We try to match it; if it goes straight to EOF that's fine too.
        # Use a combined pattern list so EOF also terminates cleanly.
    ]

    # Handle optional confirmation step separately
    cmd = [TCPLAY_BIN] + args
    log.debug("[tcplay_create] Spawning: %s", " ".join(cmd))

    try:
        child = pexpect.spawn(
            cmd[0], args=cmd[1:],
            timeout=timeout, encoding="utf-8",
            echo=False, codec_errors="replace",
        )
    except Exception as exc:
        log.error("[tcplay_create] Spawn failed: %s", exc)
        return False

    try:
        # Step 1: Passphrase
        i = child.expect([_PAT_PASS, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i != 0:
            log.error("[tcplay_create] Did not receive Passphrase prompt (got %s). buffer=%r",
                      "EOF" if i == 1 else "TIMEOUT", child.before)
            child.close(force=True)
            return False
        child.sendline(password)
        log.debug("[tcplay_create] Sent passphrase.")

        # Step 2: Repeat passphrase
        i = child.expect([_PAT_REPEAT, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i != 0:
            log.error("[tcplay_create] Did not receive Repeat prompt (got %s). buffer=%r",
                      "EOF" if i == 1 else "TIMEOUT", child.before)
            child.close(force=True)
            return False
        child.sendline(password)
        log.debug("[tcplay_create] Sent repeat passphrase.")

        # Step 3: Optional "Are you sure?" confirmation or EOF
        i = child.expect([_PAT_CONFIRM, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 0:
            log.debug("[tcplay_create] Got confirmation prompt, sending 'y'.")
            child.sendline("y")
            # Now wait for EOF
            child.expect(_PAT_EOF, timeout=timeout)
        elif i == 1:
            log.debug("[tcplay_create] Got EOF directly (no confirmation needed).")
        else:
            log.error("[tcplay_create] TIMEOUT waiting after repeat passphrase.")
            child.close(force=True)
            return False

        child.close()
        rc = child.exitstatus
        if rc == 0:
            log.info("[tcplay_create] Container created successfully on %s.", device)
            return True
        log.error("[tcplay_create] tcplay exited with rc=%s on %s.", rc, device)
        return False

    except pexpect.EOF:
        child.close()
        rc = child.exitstatus
        if rc == 0:
            log.info("[tcplay_create] Container created (EOF path) on %s.", device)
            return True
        log.error("[tcplay_create] EOF with rc=%s on %s.", rc, device)
        return False
    except pexpect.TIMEOUT:
        log.error("[tcplay_create] Timed out on %s.", device)
        child.close(force=True)
        return False
    except Exception as exc:
        log.error("[tcplay_create] Error: %s", exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return False


def tcplay_create_hidden(
    device: str,
    outer_password: str,
    hidden_password: str,
    hidden_size_bytes: int,
    cipher: str = DEFAULT_CIPHER,
    prf: str = DEFAULT_PRF,
    timeout: int = 120,
) -> bool:
    """
    Create a hidden volume inside an existing outer volume on *device*.

    tcplay --create --hidden interaction sequence:
      1. "Passphrase: "         → outer_password  (authenticate outer header)
      2. "Passphrase: "         → hidden_password  (new hidden password)
      3. "Repeat passphrase: "  → hidden_password
      4. Optional confirmation  → "y"

    Returns True on success.
    """
    args = [
        "--create",
        "--hidden",
        f"--device={device}",
        f"--cipher={cipher}",
        f"--pbkdf-prf={prf}",
        f"--hidden-size-bytes={hidden_size_bytes}",
    ]

    cmd = [TCPLAY_BIN] + args
    log.debug("[tcplay_create_hidden] Spawning: %s", " ".join(cmd))

    try:
        child = pexpect.spawn(
            cmd[0], args=cmd[1:],
            timeout=timeout, encoding="utf-8",
            echo=False, codec_errors="replace",
        )
    except Exception as exc:
        log.error("[tcplay_create_hidden] Spawn failed: %s", exc)
        return False

    try:
        # Step 1: First passphrase = outer password
        i = child.expect([_PAT_PASS, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i != 0:
            log.error("[tcplay_create_hidden] No Passphrase prompt for outer. buffer=%r", child.before)
            child.close(force=True)
            return False
        child.sendline(outer_password)
        log.debug("[tcplay_create_hidden] Sent outer passphrase.")

        # Step 2: Second passphrase = hidden password
        i = child.expect([_PAT_PASS, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i != 0:
            log.error("[tcplay_create_hidden] No second Passphrase prompt for hidden. buffer=%r", child.before)
            child.close(force=True)
            return False
        child.sendline(hidden_password)
        log.debug("[tcplay_create_hidden] Sent hidden passphrase.")

        # Step 3: Repeat hidden passphrase
        i = child.expect([_PAT_REPEAT, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i != 0:
            log.error("[tcplay_create_hidden] No Repeat prompt for hidden. buffer=%r", child.before)
            child.close(force=True)
            return False
        child.sendline(hidden_password)
        log.debug("[tcplay_create_hidden] Sent hidden repeat passphrase.")

        # Step 4: Optional confirmation
        i = child.expect([_PAT_CONFIRM, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 0:
            child.sendline("y")
            child.expect(_PAT_EOF, timeout=timeout)
        elif i == 2:
            log.error("[tcplay_create_hidden] TIMEOUT at confirmation step.")
            child.close(force=True)
            return False

        child.close()
        rc = child.exitstatus
        if rc == 0:
            log.info("[tcplay_create_hidden] Hidden volume created on %s.", device)
            return True
        log.error("[tcplay_create_hidden] tcplay rc=%s on %s.", rc, device)
        return False

    except pexpect.EOF:
        child.close()
        rc = child.exitstatus
        if rc == 0:
            log.info("[tcplay_create_hidden] Hidden created (EOF path) on %s.", device)
            return True
        log.error("[tcplay_create_hidden] EOF rc=%s on %s.", rc, device)
        return False
    except pexpect.TIMEOUT:
        log.error("[tcplay_create_hidden] Timed out on %s.", device)
        child.close(force=True)
        return False
    except Exception as exc:
        log.error("[tcplay_create_hidden] Error: %s", exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return False


def tcplay_create_with_hidden(
    device: str,
    outer_password: str,
    hidden_password: str,
    hidden_size_mb: int,
    cipher: str = DEFAULT_CIPHER,
    prf: str = DEFAULT_PRF,
    timeout: int = 120,
    weak_keys: bool = False,
) -> bool:
    """
    Create outer + hidden volumes in a single tcplay --create -g pass.

    tcplay -g prompt sequence (verified live on tcplay v3.3):
      1. "Passphrase: "                        → outer_password
      2. "Repeat passphrase: "                 → outer_password (confirm)
      3. "Passphrase for hidden volume: "      → hidden_password
      4. "Repeat passphrase: "                 → hidden_password (confirm)
      5. "Size of hidden volume (e.g. 127M): " → "<hidden_size_mb>M"
      6. "Are you sure ...? (y/n) "            → "y"
      7. EOF + exit 0

    IMPORTANT: "Passphrase:" is a substring of "Passphrase for hidden volume:".
    To avoid matching the wrong prompt, we match the LONGER string first in
    every expect() call that could see either prompt.

    Args:
        device:           Block device path (e.g. /dev/loop3).
        outer_password:   Passphrase for the outer (decoy) volume.
        hidden_password:  Passphrase for the hidden (real) volume.
        hidden_size_mb:   Size of the hidden volume in MB.
        cipher:           tcplay cipher string (default AES-256-XTS).
        prf:              PBKDF PRF string (default SHA512).
        timeout:          Per-prompt timeout in seconds.
        weak_keys:        If True, add -w flag (urandom entropy, testing only).

    Returns:
        True on success (exit 0), False on any failure.
    """
    args = [
        "--create", "-g",
        f"--device={device}",
        f"--cipher={cipher}",
        f"--pbkdf-prf={prf}",
    ]
    if weak_keys:
        args.append("-w")

    cmd = [TCPLAY_BIN] + args
    log.debug("[tcplay_create_with_hidden] Spawning: %s", " ".join(cmd))

    EOF_TIMEOUT = timeout * 10

    try:
        child = pexpect.spawn(
            cmd[0], args=cmd[1:],
            timeout=timeout, encoding="utf-8",
            echo=False, codec_errors="replace",
        )
    except Exception as exc:
        log.error("[tcplay_create_with_hidden] Spawn failed: %s", exc)
        return False

    try:
        # Step 1: outer passphrase — "Passphrase: "
        # Match "Passphrase for hidden volume:" first to avoid substring clash,
        # though it should not appear here. Belt-and-suspenders ordering.
        i = child.expect([_PAT_HIDDEN, _PAT_PASS, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 1:
            child.sendline(outer_password)
            log.debug("[tcplay_create_with_hidden] Sent outer passphrase.")
        else:
            log.error("[tcplay_create_with_hidden] Unexpected at step 1 (i=%d). buffer=%r", i, child.before)
            child.close(force=True)
            return False

        # Step 2: repeat outer — "Repeat passphrase: "
        i = child.expect([_PAT_REPEAT, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 0:
            child.sendline(outer_password)
            log.debug("[tcplay_create_with_hidden] Sent outer repeat.")
        else:
            log.error("[tcplay_create_with_hidden] No Repeat prompt (i=%d). buffer=%r", i, child.before)
            child.close(force=True)
            return False

        # Step 3: hidden passphrase — "Passphrase for hidden volume: "
        i = child.expect([_PAT_HIDDEN, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 0:
            child.sendline(hidden_password)
            log.debug("[tcplay_create_with_hidden] Sent hidden passphrase.")
        else:
            log.error("[tcplay_create_with_hidden] No hidden Passphrase prompt (i=%d). buffer=%r", i, child.before)
            child.close(force=True)
            return False

        # Step 4: repeat hidden — "Repeat passphrase: "
        i = child.expect([_PAT_REPEAT, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 0:
            child.sendline(hidden_password)
            log.debug("[tcplay_create_with_hidden] Sent hidden repeat.")
        else:
            log.error("[tcplay_create_with_hidden] No Repeat for hidden (i=%d). buffer=%r", i, child.before)
            child.close(force=True)
            return False

        # Step 5: size prompt — "Size of hidden volume (e.g. 127M): "
        i = child.expect([r"(?i)size of hidden", _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 0:
            child.sendline(f"{hidden_size_mb}M")
            log.debug("[tcplay_create_with_hidden] Sent hidden size: %dM.", hidden_size_mb)
        else:
            log.error("[tcplay_create_with_hidden] No Size prompt (i=%d). buffer=%r", i, child.before)
            child.close(force=True)
            return False

        # Step 6: confirmation — "Are you sure? (y/n)"
        i = child.expect([_PAT_CONFIRM, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i == 0:
            child.sendline("y")
            log.debug("[tcplay_create_with_hidden] Sent 'y' confirmation. Waiting for erase+header write…")
        elif i == 1:
            log.debug("[tcplay_create_with_hidden] EOF before confirmation (no prompt needed).")
        else:
            log.error("[tcplay_create_with_hidden] TIMEOUT at confirmation step.")
            child.close(force=True)
            return False

        # Wait for erase + header write to finish (may take minutes without -w)
        child.expect(_PAT_EOF, timeout=EOF_TIMEOUT)
        child.close()
        rc = child.exitstatus if child.exitstatus is not None else (child.signalstatus or 255)
        if rc == 0:
            log.info("[tcplay_create_with_hidden] Container created successfully on %s.", device)
            return True
        log.error("[tcplay_create_with_hidden] tcplay rc=%s on %s.", rc, device)
        return False

    except pexpect.EOF:
        child.close()
        rc = child.exitstatus if child.exitstatus is not None else (child.signalstatus or 255)
        if rc == 0:
            log.info("[tcplay_create_with_hidden] Container created (EOF path) on %s.", device)
            return True
        log.error("[tcplay_create_with_hidden] EOF rc=%s on %s.", rc, device)
        return False
    except pexpect.TIMEOUT:
        log.error("[tcplay_create_with_hidden] Timed out on %s.", device)
        try:
            child.close(force=True)
        except Exception:
            pass
        return False
    except Exception as exc:
        log.error("[tcplay_create_with_hidden] Error: %s", exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return False


def tcplay_map(
    device: str,
    mapper_name: str,
    password: str,
    use_hidden: bool = False,
    timeout: int = 60,
) -> bool:
    """
    Map a TrueCrypt volume to /dev/mapper/<mapper_name>.

    tcplay --map interaction:
      1. "Passphrase: " → password

    Returns True on success.
    """
    args = [
        f"--map={mapper_name}",
        f"--device={device}",
    ]
    if use_hidden:
        args.append("--use-hidden")

    cmd = [TCPLAY_BIN] + args
    log.debug("[tcplay_map] Spawning: %s", " ".join(cmd))

    try:
        child = pexpect.spawn(
            cmd[0], args=cmd[1:],
            timeout=timeout, encoding="utf-8",
            echo=False, codec_errors="replace",
        )
    except Exception as exc:
        log.error("[tcplay_map] Spawn failed: %s", exc)
        return False

    try:
        i = child.expect([_PAT_PASS, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i != 0:
            log.error("[tcplay_map] No Passphrase prompt. buffer=%r", child.before)
            child.close(force=True)
            return False
        child.sendline(password)
        log.debug("[tcplay_map] Sent passphrase.")

        # Wait for EOF (mapping is done when tcplay exits)
        child.expect(_PAT_EOF, timeout=timeout)
        child.close()
        rc = child.exitstatus
        if rc == 0:
            log.info("[tcplay_map] Mapped %s → /dev/mapper/%s (hidden=%s).",
                     device, mapper_name, use_hidden)
            return True
        log.error("[tcplay_map] tcplay rc=%s for %s.", rc, device)
        return False

    except pexpect.EOF:
        child.close()
        rc = child.exitstatus
        if rc == 0:
            log.info("[tcplay_map] Mapped (EOF) %s → /dev/mapper/%s.", device, mapper_name)
            return True
        log.error("[tcplay_map] EOF rc=%s.", rc)
        return False
    except pexpect.TIMEOUT:
        log.error("[tcplay_map] Timed out mapping %s.", device)
        child.close(force=True)
        return False
    except Exception as exc:
        log.error("[tcplay_map] Error: %s", exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return False


def tcplay_unmap(mapper_name: str) -> bool:
    """
    Unmap a TrueCrypt dm-crypt mapping.
    Uses subprocess (no password needed).

    Returns True on success.
    """
    try:
        result = subprocess.run(
            [TCPLAY_BIN, "--unmap", mapper_name],
            capture_output=True, check=False,
        )
        if result.returncode == 0:
            log.info("[tcplay_unmap] Unmapped /dev/mapper/%s.", mapper_name)
            return True
        log.error(
            "[tcplay_unmap] Failed (rc=%s): %s",
            result.returncode,
            result.stderr.decode(errors="replace"),
        )
        return False
    except Exception as exc:
        log.error("[tcplay_unmap] Error: %s", exc)
        return False


def tcplay_info(
    device: str,
    password: str,
    use_hidden: bool = False,
    timeout: int = 60,
) -> Optional[dict]:
    """
    Get info about a TrueCrypt volume.

    Returns a dict with parsed info fields, or None on failure.
    """
    args = ["--info", f"--device={device}"]
    if use_hidden:
        args.append("--use-hidden")

    cmd = [TCPLAY_BIN] + args
    log.debug("[tcplay_info] Spawning: %s", " ".join(cmd))

    try:
        child = pexpect.spawn(
            cmd[0], args=cmd[1:],
            timeout=timeout, encoding="utf-8",
            echo=False, codec_errors="replace",
        )
    except Exception as exc:
        log.error("[tcplay_info] Spawn failed: %s", exc)
        return None

    output_lines = []

    try:
        i = child.expect([_PAT_PASS, _PAT_EOF, _PAT_TIMEOUT], timeout=timeout)
        if i != 0:
            log.error("[tcplay_info] No Passphrase prompt. buffer=%r", child.before)
            child.close(force=True)
            return None
        child.sendline(password)

        # Collect all output until EOF
        child.expect(_PAT_EOF, timeout=timeout)
        output_lines = child.before.splitlines() if child.before else []
        child.close()

    except pexpect.EOF:
        output_lines = child.before.splitlines() if child.before else []
        child.close()
    except pexpect.TIMEOUT:
        log.error("[tcplay_info] Timed out.")
        child.close(force=True)
        return None
    except Exception as exc:
        log.error("[tcplay_info] Error: %s", exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return None

    # Parse output lines into a dict
    info: dict = {}
    for line in output_lines:
        if ":" in line:
            key, _, val = line.partition(":")
            info[key.strip()] = val.strip()

    log.info("[tcplay_info] Info for %s: %s", device, info)
    return info if info else None


# ─────────────────────────────────────────────────────────────────────────────
# Loop device helpers (used by encrypt_audio.py and create_hidden_container.py)
# ─────────────────────────────────────────────────────────────────────────────

def setup_loop_device(file_path: str) -> Optional[str]:
    """
    Attach *file_path* to a free loop device and return the loop device path
    (e.g. '/dev/loop2'), or None on failure.
    """
    try:
        result = subprocess.run(
            ["losetup", "--find", "--show", file_path],
            capture_output=True, check=True,
        )
        loop_dev = result.stdout.decode().strip()
        log.debug("[setup_loop] Attached %s → %s", file_path, loop_dev)
        return loop_dev
    except subprocess.CalledProcessError as exc:
        log.error("[setup_loop] losetup failed: %s", exc.stderr.decode(errors="replace"))
        return None


def detach_loop_device(loop_dev: str) -> bool:
    """
    Detach a loop device. Returns True on success.
    """
    try:
        subprocess.run(["losetup", "--detach", loop_dev], check=True, capture_output=True)
        log.debug("[detach_loop] Detached %s.", loop_dev)
        return True
    except subprocess.CalledProcessError as exc:
        log.error("[detach_loop] Failed to detach %s: %s",
                  loop_dev, exc.stderr.decode(errors="replace"))
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility aliases for encrypt_audio.py
# encrypt_audio.py imports: run_tcplay, run_cmd_no_tty, setup_loop, teardown_loop
# ─────────────────────────────────────────────────────────────────────────────

def run_tcplay(
    args: list,
    passwords: list,
    timeout: int = 120,
) -> tuple:
    """
    Generic tcplay runner used by encrypt_audio.py and create_hidden_container.py.

    Uses a state-machine approach: keeps looping over all prompts until EOF,
    feeding passwords in order for passphrase prompts, and answering 'y' for
    confirmation prompts.  This correctly handles tcplay's interaction sequence:

      --create:
        1. "Passphrase: "             → passwords[0]
        2. "Repeat passphrase: "      → passwords[1]
        3. "Are you sure? (y/n) "     → "y"
        4. [Securely erasing...]      (may take minutes)
        5. EOF / exit 0

      --map:
        1. "Passphrase: "             → passwords[0]
        2. EOF / exit 0

      --create --hidden (tcplay_create_hidden):
        1. "Passphrase: "             → passwords[0]  (outer)
        2. "Passphrase for hidden: "  → passwords[1]
        3. "Repeat passphrase: "      → passwords[2]  (hidden confirm)
        4. "Are you sure? (y/n) "     → "y"
        5. EOF

    Args:
        args:      List of tcplay CLI args (without the binary name).
        passwords: Ordered list of passwords to feed at passphrase prompts.
        timeout:   Per-prompt timeout in seconds (default 120).
                   Final EOF wait uses 10× timeout to allow for disk erase.

    Returns:
        Tuple (return_code: int, output: str).
        return_code 0 = success.
    """
    # tcplay --create securely erases + writes headers — may take many minutes
    # on slow storage.  Give final EOF up to 10× the per-prompt timeout.
    EOF_TIMEOUT = timeout * 10

    cmd = [TCPLAY_BIN] + args
    log.debug("[run_tcplay] Spawning: %s", " ".join(cmd))

    output_buf: list = []

    try:
        child = pexpect.spawn(
            cmd[0], args=cmd[1:],
            timeout=timeout,
            encoding="utf-8",
            echo=False,
            codec_errors="replace",
        )
    except Exception as exc:
        log.error("[run_tcplay] Spawn failed: %s", exc)
        return (255, str(exc))

    try:
        pw_index = 0  # index into passwords list

        # State-machine loop: keep handling prompts until EOF or error.
        # We never exit this loop early once passwords are exhausted —
        # tcplay may still have confirmation + erase output to produce.
        while True:
            # Use a shorter per-prompt timeout while waiting for prompts,
            # but a much longer one for the erase phase (after confirmation).
            current_timeout = EOF_TIMEOUT if pw_index >= len(passwords) else timeout

            try:
                i = child.expect(
                    [_PAT_PASS, _PAT_REPEAT, _PAT_CONFIRM, _PAT_EOF, _PAT_TIMEOUT],
                    timeout=current_timeout,
                )
            except pexpect.EOF:
                if child.before:
                    output_buf.append(child.before)
                log.debug("[run_tcplay] EOF caught in expect (pw_index=%d).", pw_index)
                break
            except pexpect.TIMEOUT:
                if child.before:
                    output_buf.append(child.before)
                log.error(
                    "[run_tcplay] Timeout after %ds (pw_index=%d, sent %d/%d passwords).",
                    current_timeout, pw_index, pw_index, len(passwords),
                )
                child.close(force=True)
                return (255, "".join(output_buf) + "\nTIMEOUT")

            if child.before:
                output_buf.append(child.before)

            if i == 0:
                # "Passphrase: " — primary password prompt
                if pw_index < len(passwords):
                    pw = passwords[pw_index]
                    pw_index += 1
                else:
                    # More passphrase prompts than expected — use last known password
                    log.warning(
                        "[run_tcplay] More passphrase prompts than passwords supplied "
                        "(pw_index=%d, len=%d). Reusing last password.",
                        pw_index, len(passwords),
                    )
                    pw = passwords[-1]
                child.sendline(pw)
                log.debug("[run_tcplay] Sent password #%d.", pw_index)

            elif i == 1:
                # "Repeat passphrase: " — confirmation of previous password
                if pw_index < len(passwords):
                    pw = passwords[pw_index]
                    pw_index += 1
                else:
                    pw = passwords[-1]
                child.sendline(pw)
                log.debug("[run_tcplay] Sent repeat password #%d.", pw_index)

            elif i == 2:
                # "Are you sure? (y/n)" — answer yes, then wait for long erase
                child.sendline("y")
                log.debug("[run_tcplay] Sent confirmation 'y'. Waiting for erase+headers (up to %ds)…", EOF_TIMEOUT)

            elif i == 3:
                # EOF — process finished cleanly
                log.debug("[run_tcplay] EOF received (pw_index=%d).", pw_index)
                break

            # i == 4 (TIMEOUT) is handled by the except clause above

        child.close()
        rc = child.exitstatus if child.exitstatus is not None else (child.signalstatus or 255)
        output = "".join(output_buf)

        if rc == 0:
            log.debug("[run_tcplay] Success (rc=0).")
        else:
            log.warning("[run_tcplay] Non-zero rc=%d. output=%r", rc, output[:300])

        return (rc, output)

    except pexpect.EOF:
        if child.before:
            output_buf.append(child.before)
        child.close()
        rc = child.exitstatus if child.exitstatus is not None else (child.signalstatus or 255)
        log.debug("[run_tcplay] Outer EOF handler, rc=%s.", rc)
        return (rc or 0, "".join(output_buf))

    except pexpect.TIMEOUT:
        log.error("[run_tcplay] Outer TIMEOUT handler.")
        try:
            child.close(force=True)
        except Exception:
            pass
        return (255, "".join(output_buf) + "\nOUTER TIMEOUT")

    except Exception as exc:
        log.error("[run_tcplay] Unexpected error: %s", exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return (255, str(exc))


def run_cmd_no_tty(
    cmd: list[str],
    input_data: Optional[bytes] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a shell command without requiring a TTY (alias helper for encrypt_audio.py).

    Unlike tcplay which needs a PTY, regular commands (mount, mkfs, cp, etc.)
    can be called via subprocess directly.
    """
    log.debug("[run_cmd_no_tty] Running: %s", " ".join(cmd))
    return subprocess.run(cmd, input=input_data, capture_output=True, check=check)


def setup_loop(file_path: str) -> Optional[str]:
    """Alias for setup_loop_device — used by encrypt_audio.py."""
    return setup_loop_device(file_path)


def teardown_loop(loop_dev: str) -> bool:
    """Alias for detach_loop_device — used by encrypt_audio.py."""
    return detach_loop_device(loop_dev)


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test (run as root: sudo python3 tcplay_helper.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import tempfile

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if os.geteuid() != 0:
        print("ERROR: Must run as root (sudo python3 tcplay_helper.py)", file=sys.stderr)
        sys.exit(1)

    PASSWORD = "PhantomTest2026!"
    # Create a 5MB test file
    with tempfile.NamedTemporaryFile(suffix=".tc", delete=False) as f:
        test_file = f.name

    print(f"\n=== Self-test: creating 5MB container at {test_file} ===")
    os.system(f"dd if=/dev/urandom of={test_file} bs=1M count=5 2>/dev/null")

    loop = setup_loop_device(test_file)
    if not loop:
        print("FAIL: Could not setup loop device")
        sys.exit(1)

    print(f"Loop device: {loop}")
    print("Creating TrueCrypt container via pexpect...")

    ok = tcplay_create(loop, PASSWORD, timeout=120)
    print(f"tcplay_create → {'OK' if ok else 'FAIL'}")

    detach_loop_device(loop)
    os.unlink(test_file)
    sys.exit(0 if ok else 1)
