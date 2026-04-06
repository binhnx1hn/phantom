#!/usr/bin/env python3
"""
PHANTOM R3 - Audio Encryption Script
Encrypts recorded Opus audio files into TrueCrypt-compatible containers (.tc)
using tcplay with AES-256-XTS + SHA-512 PBKDF.

Compatible with TrueCrypt 7.1a on PC for decryption.

Requires Python 3.8+ (compatible with Raspberry Pi OS Bullseye/Bookworm).
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
# Configuration constants
# ─────────────────────────────────────────────
OPUS_SOURCE_DIR   = Path("/tmp/phantom")          # Directory scanned for .opus files
ENCRYPTED_DIR     = Path("/phantom/encrypted")    # Output directory for .tc containers
LOG_DIR           = Path("/phantom/logs")         # Log file directory
LOG_FILE          = LOG_DIR / "encrypt_audio.log"
SECRET_FILE       = Path("/phantom/.secret")      # Password file (chmod 600)
ENV_PASSWORD_KEY  = "PHANTOM_PASSWORD"            # Environment variable name for password

CONTAINER_OVERHEAD_PCT = 0.20    # 20% extra space overhead inside container
CONTAINER_MIN_MB       = 5       # Minimum container size in MB
FAT32_OVERHEAD_MB      = 1       # FAT32 filesystem metadata overhead (MB)

TCPLAY_CIPHER  = "AES-256-XTS"
TCPLAY_PRF     = "SHA512"
MAPPER_PREFIX  = "phantom_tc_"   # /dev/mapper/<name> prefix


# ─────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────
def setup_logging(log_file: Path, dry_run: bool = False) -> logging.Logger:
    """Configure logging with ISO 8601 timestamps to both stdout and log file.

    Args:
        log_file: Absolute path to the log file (directory must exist).
        dry_run:  When True, skip file handler (no disk writes).
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]
    if not dry_run:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)
    logger = logging.getLogger("phantom.encrypt")
    if dry_run:
        logger.info("DRY-RUN mode enabled — no actual changes will be made.")
    return logger


log = logging.getLogger("phantom.encrypt")


# ─────────────────────────────────────────────
# Password management
# ─────────────────────────────────────────────
def load_password() -> str:
    """
    Load encryption password in priority order:
      1. Environment variable PHANTOM_PASSWORD
      2. File /phantom/.secret (must be chmod 600)
    Raises RuntimeError if no password source is found.
    """
    # Priority 1: environment variable
    pw = os.environ.get(ENV_PASSWORD_KEY, "").strip()
    if pw:
        log.info("Password loaded from environment variable %s.", ENV_PASSWORD_KEY)
        return pw

    # Priority 2: secret file
    if SECRET_FILE.exists():
        st = SECRET_FILE.stat()
        # Warn if permissions are too open (not 0o600)
        if st.st_mode & 0o077:
            log.warning(
                "Secret file %s has insecure permissions (%o). Expected 600.",
                SECRET_FILE,
                st.st_mode & 0o777,
            )
        pw = SECRET_FILE.read_text(encoding="utf-8").strip()
        if pw:
            log.info("Password loaded from secret file %s.", SECRET_FILE)
            return pw

    raise RuntimeError(
        f"No password found. Set env var '{ENV_PASSWORD_KEY}' or create '{SECRET_FILE}' (chmod 600)."
    )


# ─────────────────────────────────────────────
# Helper: run subprocess
# ─────────────────────────────────────────────
def _sanitize_mapper_name(stem: str) -> str:
    """
    Convert a filename stem into a safe /dev/mapper name.
    Replaces any character that is not alphanumeric or underscore with '_'.
    Truncates to 63 characters (Linux device name limit).
    """
    safe = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    # Ensure it doesn't start with a digit (dm-crypt constraint)
    if safe and safe[0].isdigit():
        safe = "_" + safe
    return safe[:63]


def run_cmd(
    cmd: list[str],
    input_data: Optional[bytes] = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """
    Execute a shell command and return its CompletedProcess.
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


# ─────────────────────────────────────────────
# Container size calculation
# ─────────────────────────────────────────────
def calculate_container_size_mb(file_size_bytes: int) -> int:
    """
    Calculate required TrueCrypt container size in whole MBs.
    Formula: max(CONTAINER_MIN_MB, ceil(file_bytes / 1MB * (1 + overhead)) + FAT32_overhead)
    """
    file_mb = file_size_bytes / (1024 * 1024)
    required = math.ceil(file_mb * (1 + CONTAINER_OVERHEAD_PCT)) + FAT32_OVERHEAD_MB
    return max(CONTAINER_MIN_MB, required)


# ─────────────────────────────────────────────
# Core: create TrueCrypt container
# ─────────────────────────────────────────────
def create_truecrypt_container(
    output_path: Path,
    size_mb: int,
    password: str,
    dry_run: bool = False,
) -> bool:
    """
    Create a TrueCrypt-compatible container file using tcplay.

    Steps:
      1. Allocate container file with dd (sparse pre-allocation)
      2. Call tcplay --create to initialise TrueCrypt headers

    Returns True on success, False on failure.
    """
    log.info("Creating container: %s (%d MB)", output_path, size_mb)

    if dry_run:
        log.info("[DRY-RUN] Would create container %s (%d MB).", output_path, size_mb)
        return True

    # Step 1: Allocate container file
    try:
        run_cmd([
            "dd",
            "if=/dev/urandom",
            f"of={output_path}",
            "bs=1M",
            f"count={size_mb}",
        ])
        log.info("Container file allocated: %s", output_path)
    except subprocess.CalledProcessError as exc:
        log.error("Failed to allocate container file: %s", exc.stderr.decode(errors="replace"))
        return False

    # Step 2: Initialise TrueCrypt headers via tcplay
    # tcplay prompts for password TWICE (password + confirmation).
    # Both are fed through stdin to avoid leaking them in the process list.
    pw_line = (password + "\n").encode()
    pw_bytes = pw_line + pw_line  # password\npassword\n  (enter + confirm)
    try:
        run_cmd(
            [
                "sudo", "tcplay",
                "--create",
                f"--device={output_path}",
                f"--cipher={TCPLAY_CIPHER}",
                f"--pbkdf-prf={TCPLAY_PRF}",
            ],
            input_data=pw_bytes,
        )
        log.info("TrueCrypt headers written to %s.", output_path)
        return True
    except subprocess.CalledProcessError as exc:
        log.error(
            "tcplay --create failed for %s: %s",
            output_path,
            exc.stderr.decode(errors="replace"),
        )
        # Remove partially-created container
        output_path.unlink(missing_ok=True)
        return False


# ─────────────────────────────────────────────
# Core: encrypt file into container
# ─────────────────────────────────────────────
def encrypt_file_to_container(
    opus_file: Path,
    tc_output: Path,
    password: str,
    dry_run: bool = False,
) -> bool:
    """
    Encrypt a single .opus file into a TrueCrypt container.

    Workflow:
      1. Calculate container size
      2. Create TrueCrypt container
      3. Map (mount) container via tcplay
      4. Format mapped device as FAT32
      5. Mount FAT32 volume
      6. Copy .opus file into volume
      7. Unmount FAT32 volume
      8. Unmap TrueCrypt container
      9. Verify container file exists and is non-empty

    Returns True on success, False on any failure.
    """
    if not opus_file.exists():
        log.error("Source file not found: %s", opus_file)
        return False

    file_size = opus_file.stat().st_size
    size_mb = calculate_container_size_mb(file_size)
    mapper_name = f"{MAPPER_PREFIX}{_sanitize_mapper_name(opus_file.stem)}_{int(time.time())}"
    mapper_dev = Path(f"/dev/mapper/{mapper_name}")
    mount_point = Path(tempfile.mkdtemp(prefix="phantom_mnt_"))

    log.info(
        "Encrypting '%s' (%d bytes) → '%s' [%d MB container]",
        opus_file.name, file_size, tc_output.name, size_mb,
    )

    if dry_run:
        log.info(
            "[DRY-RUN] Would encrypt %s → %s (%d MB).",
            opus_file, tc_output, size_mb,
        )
        mount_point.rmdir()
        return True

    # Step 1-2: Create container
    if not create_truecrypt_container(tc_output, size_mb, password, dry_run=dry_run):
        mount_point.rmdir()
        return False

    pw_bytes = (password + "\n").encode()

    try:
        # Step 3: Map (open) the container
        run_cmd(
            [
                "sudo", "tcplay",
                f"--map={mapper_name}",
                f"--device={tc_output}",
            ],
            input_data=pw_bytes,
        )
        log.info("Container mapped to /dev/mapper/%s", mapper_name)

        # Step 4: Format mapped device as FAT32
        run_cmd([
            "sudo", "mkfs.fat", "-F", "32", str(mapper_dev),
        ])
        log.info("FAT32 filesystem created on %s.", mapper_dev)

        # Step 5: Mount FAT32 volume
        run_cmd([
            "sudo", "mount", str(mapper_dev), str(mount_point),
        ])
        log.info("Volume mounted at %s.", mount_point)

        # Step 6: Copy .opus file into volume
        dest_file = mount_point / opus_file.name
        run_cmd([
            "sudo", "cp", str(opus_file), str(dest_file),
        ])
        log.info("File copied to container: %s", dest_file)

        # Step 7: Sync and unmount FAT32 volume
        run_cmd(["sync"])
        run_cmd(["sudo", "umount", str(mount_point)])
        log.info("Volume unmounted from %s.", mount_point)

        # Step 8: Unmap (close) TrueCrypt container
        run_cmd([
            "sudo", "tcplay",
            "--unmap", mapper_name,
        ])
        log.info("Container unmapped: %s", mapper_name)

        # Step 9: Verify container
        if not tc_output.exists() or tc_output.stat().st_size == 0:
            log.error("Container file missing or empty after encryption: %s", tc_output)
            return False

        log.info("Encryption successful: %s", tc_output)
        return True

    except subprocess.CalledProcessError as exc:
        log.error(
            "Encryption pipeline failed for %s: %s",
            opus_file.name,
            exc.stderr.decode(errors="replace") if exc.stderr else str(exc),
        )
        # Attempt cleanup — best-effort, ignore errors
        _cleanup_after_failure(mapper_name, mount_point, tc_output)
        return False

    finally:
        # Always remove temp mount point directory
        try:
            mount_point.rmdir()
        except OSError:
            pass


def _cleanup_after_failure(
    mapper_name: str,
    mount_point: Path,
    tc_output: Path,
) -> None:
    """Best-effort cleanup after an encryption failure."""
    try:
        subprocess.run(["sudo", "umount", str(mount_point)], capture_output=True)
    except Exception:
        pass
    try:
        subprocess.run(["sudo", "tcplay", "--unmap", mapper_name], capture_output=True)
    except Exception:
        pass
    try:
        tc_output.unlink(missing_ok=True)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Secure delete
# ─────────────────────────────────────────────
def secure_delete(file_path: Path, dry_run: bool = False) -> bool:
    """
    Securely delete a file using shred with 3 overwrite passes.
    Falls back to os.unlink if shred is unavailable.
    Returns True on success, False on failure.
    """
    if not file_path.exists():
        log.warning("secure_delete: file not found: %s", file_path)
        return True  # Already gone — treat as success

    if dry_run:
        log.info("[DRY-RUN] Would shred -n 3 -z -u %s", file_path)
        return True

    try:
        run_cmd(["shred", "-n", "3", "-z", "-u", str(file_path)])
        log.info("Securely deleted: %s", file_path)
        return True
    except FileNotFoundError:
        # shred not available — fall back to simple unlink
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


# ─────────────────────────────────────────────
# Main processing loop
# ─────────────────────────────────────────────
def process_directory(
    source_dir: Path,
    output_dir: Path,
    password: str,
    dry_run: bool = False,
) -> dict:
    """
    Scan source_dir for .opus files and encrypt each one.
    Returns a summary dict with counts: total, success, failed, skipped.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    opus_files = sorted(source_dir.glob("*.opus"))
    if not opus_files:
        log.info("No .opus files found in %s.", source_dir)
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    log.info("Found %d .opus file(s) to process.", len(opus_files))
    summary = {"total": len(opus_files), "success": 0, "failed": 0, "skipped": 0}

    for opus_file in opus_files:
        tc_name = opus_file.stem + ".tc"
        tc_path = output_dir / tc_name

        # Idempotency check: skip if container already exists
        if tc_path.exists():
            log.info("Container already exists, skipping: %s", tc_path)
            summary["skipped"] += 1
            continue

        start_ts = datetime.now(tz=timezone.utc).isoformat()
        log.info("─── [%s] Processing: %s ───", start_ts, opus_file.name)

        success = encrypt_file_to_container(opus_file, tc_path, password, dry_run=dry_run)

        if success:
            # Only delete source after confirmed successful encryption
            deleted = secure_delete(opus_file, dry_run=dry_run)
            if not deleted:
                log.warning(
                    "Encryption succeeded but could not delete source: %s", opus_file
                )
            summary["success"] += 1
            log.info("✓ Done: %s → %s", opus_file.name, tc_name)
        else:
            # Keep source file intact on any failure
            summary["failed"] += 1
            log.error(
                "✗ Failed: %s — source file preserved at %s", opus_file.name, opus_file
            )

    return summary


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PHANTOM R3 — Opus-to-TrueCrypt encryption tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Normal run (reads password from env/file)
  sudo python3 encrypt_audio.py

  # Dry-run (no actual encryption or deletion)
  sudo python3 encrypt_audio.py --dry-run

  # Custom source/output directories
  sudo python3 encrypt_audio.py --source /data/audio --output /data/encrypted
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate all operations without making actual changes.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=OPUS_SOURCE_DIR,
        help=f"Directory containing .opus files (default: {OPUS_SOURCE_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ENCRYPTED_DIR,
        help=f"Directory for output .tc containers (default: {ENCRYPTED_DIR})",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=LOG_DIR,
        help=f"Directory for log files (default: {LOG_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Resolve log file path from --log-dir argument
    log_file = args.log_dir / "encrypt_audio.log"
    setup_logging(log_file=log_file, dry_run=args.dry_run)

    run_start = datetime.now(tz=timezone.utc)
    log.info("═══ PHANTOM R3 Encryption started at %s ═══", run_start.isoformat())
    log.info("Source: %s | Output: %s | Dry-run: %s", args.source, args.output, args.dry_run)

    # Check that source directory exists
    if not args.source.exists():
        log.error("Source directory does not exist: %s", args.source)
        return 1

    # Load password
    try:
        password = load_password()
    except RuntimeError as exc:
        log.error("Password error: %s", exc)
        return 1

    # Process all .opus files
    summary = process_directory(
        source_dir=args.source,
        output_dir=args.output,
        password=password,
        dry_run=args.dry_run,
    )

    run_end = datetime.now(tz=timezone.utc)
    elapsed = (run_end - run_start).total_seconds()

    log.info(
        "═══ Run complete in %.1fs — Total: %d | Success: %d | Failed: %d | Skipped: %d ═══",
        elapsed,
        summary["total"],
        summary["success"],
        summary["failed"],
        summary["skipped"],
    )

    # Return non-zero exit code if any file failed
    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
