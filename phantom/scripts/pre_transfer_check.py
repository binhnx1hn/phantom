#!/usr/bin/env python3
"""
PHANTOM R3 - Pre-Transfer File Check Script
Validates that only encrypted TrueCrypt containers (.tc) are transmitted over Wi-Fi.
Blocks all unencrypted audio files and any non-.tc file types.

Usage:
    python3 pre_transfer_check.py /path/to/file.tc

Exit codes:
    0 - File is allowed for transfer
    1 - File is blocked (unencrypted or invalid)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────
# Nguyên tắc bất biến của PHANTOM R3:
# Chỉ truyền file đã mã hóa — không bao giờ truyền raw audio qua Wi-Fi.
# Mọi file .opus, .wav, .mp3, .flac đều phải bị block tại đây.
# ─────────────────────────────────────────────

# Các định dạng audio thô — tuyệt đối không được truyền qua mạng không dây
BLOCKED_AUDIO_EXTENSIONS = {".opus", ".wav", ".mp3", ".flac", ".aac", ".ogg", ".m4a"}

# Định dạng cho phép — chỉ TrueCrypt container đã mã hóa
ALLOWED_EXTENSION = ".tc"

# Kích thước header TrueCrypt cần đọc để xác minh (512 bytes = 1 sector)
TRUECRYPT_HEADER_SIZE = 512

# Số byte đầu tiên để kiểm tra — nếu toàn 0 thì container không hợp lệ
TRUECRYPT_SALT_SIZE = 64  # 64 bytes salt đầu tiên trong TrueCrypt header

LOG_DIR = Path("/phantom/logs")
LOG_FILE = LOG_DIR / "pre_transfer_check.log"


# ─────────────────────────────────────────────
# Logging setup (cùng pattern với encrypt_audio.py)
# ─────────────────────────────────────────────
def setup_logging(log_file: Optional[Path] = None) -> logging.Logger:
    """Configure logging with ISO 8601 timestamps to stdout and optionally a log file.

    Args:
        log_file: Optional path to log file. If None or directory not writable,
                  logs only to stdout.

    Returns:
        Configured Logger instance.
    """
    # Format timestamp theo ISO 8601 — giống hệt encrypt_audio.py
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"

    logger = logging.getLogger("pre_transfer_check")
    logger.setLevel(logging.DEBUG)

    # Handler ra stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(stdout_handler)

    # Handler ra file (nếu thư mục tồn tại)
    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
            logger.addHandler(file_handler)
        except OSError:
            # Không fail nếu không ghi được log file (ví dụ trên PC development)
            logger.debug("Cannot write to log file %s — logging to stdout only", log_file)

    return logger


# Module-level logger — được khởi tạo khi import
logger = setup_logging(LOG_FILE if LOG_DIR.parent.exists() else None)


# ─────────────────────────────────────────────
# Core validation functions
# ─────────────────────────────────────────────
def is_encrypted_container(filepath: Path) -> bool:
    """Check whether a .tc file is a valid TrueCrypt container by reading its header.

    A valid TrueCrypt container must:
    1. Have a .tc extension
    2. Be at least TRUECRYPT_HEADER_SIZE bytes in size
    3. Have non-zero salt bytes in the first 64 bytes (the PBKDF2 salt region)
       — an all-zero header indicates an empty/corrupt/fake container

    Args:
        filepath: Path to the .tc file to inspect.

    Returns:
        True if the file appears to be a valid TrueCrypt container, False otherwise.
    """
    # Kiểm tra extension trước — phải là .tc
    if filepath.suffix.lower() != ALLOWED_EXTENSION:
        logger.debug("Not a .tc file: %s", filepath.name)
        return False

    # Kiểm tra kích thước tối thiểu — container TrueCrypt phải có ít nhất 1 sector (512 bytes)
    try:
        file_size = filepath.stat().st_size
    except OSError as exc:
        logger.warning("Cannot stat file %s: %s", filepath, exc)
        return False

    if file_size < TRUECRYPT_HEADER_SIZE:
        logger.warning(
            "File too small (%d bytes < %d bytes): %s",
            file_size, TRUECRYPT_HEADER_SIZE, filepath.name
        )
        return False

    # Đọc 512 bytes đầu tiên (header sector của TrueCrypt)
    try:
        with filepath.open("rb") as fh:
            header_bytes = fh.read(TRUECRYPT_HEADER_SIZE)
    except OSError as exc:
        logger.warning("Cannot read header of %s: %s", filepath, exc)
        return False

    if len(header_bytes) < TRUECRYPT_HEADER_SIZE:
        logger.warning(
            "Short read on header (%d / %d bytes): %s",
            len(header_bytes), TRUECRYPT_HEADER_SIZE, filepath.name
        )
        return False

    # Kiểm tra salt region (64 bytes đầu) — không được toàn 0
    # TrueCrypt dùng random salt cho PBKDF2, nên toàn 0 = container giả/chưa khởi tạo
    salt_region = header_bytes[:TRUECRYPT_SALT_SIZE]
    if all(b == 0 for b in salt_region):
        logger.warning(
            "Header salt region is all-zeros — likely empty or fake container: %s",
            filepath.name
        )
        return False

    # Phần còn lại của header sau salt (bytes 64-512) chứa encrypted header data
    # Không thể verify nếu không có password — nhưng nếu có entropy (không phải toàn 0)
    # thì đây là dấu hiệu tốt rằng container đã được mã hóa và khởi tạo đúng cách
    encrypted_header_region = header_bytes[TRUECRYPT_SALT_SIZE:]
    non_zero_count = sum(1 for b in encrypted_header_region if b != 0)
    entropy_ratio = non_zero_count / len(encrypted_header_region)

    if entropy_ratio < 0.1:
        # Ít hơn 10% byte khác 0 = rất nhiều khả năng container rỗng/giả
        logger.warning(
            "Very low entropy in header (%.1f%% non-zero) — suspect container: %s",
            entropy_ratio * 100, filepath.name
        )
        return False

    logger.debug(
        "Header check passed (entropy %.1f%%, salt non-zero): %s",
        entropy_ratio * 100, filepath.name
    )
    return True


def check_file_before_transfer(filepath: Path) -> dict:
    """Validate a file and determine whether it is safe to transfer over Wi-Fi.

    This is the primary gate function. It enforces the PHANTOM R3 rule:
    only encrypted TrueCrypt containers (.tc) may be transmitted wirelessly.

    Args:
        filepath: Path object pointing to the file to check.

    Returns:
        A dict with keys:
            - "allowed"  (bool): True if transfer is permitted.
            - "reason"   (str):  Human-readable explanation.
            - "filepath" (str):  Absolute path of the checked file.
    """
    abs_path = filepath.resolve()
    result_base = {"allowed": False, "filepath": str(abs_path)}

    # ── Kiểm tra 1: File có tồn tại không? ──
    if not filepath.exists():
        reason = f"BLOCKED: File not found — {abs_path}"
        logger.error(reason)
        return {**result_base, "reason": reason}

    if not filepath.is_file():
        reason = f"BLOCKED: Not a regular file — {abs_path}"
        logger.error(reason)
        return {**result_base, "reason": reason}

    ext = filepath.suffix.lower()

    # ── Kiểm tra 2: Block ngay nếu là file audio chưa mã hóa ──
    # Nguyên tắc bất biến: audio thô KHÔNG BAO GIỜ được truyền qua Wi-Fi
    if ext in BLOCKED_AUDIO_EXTENSIONS:
        reason = (
            f"BLOCKED: Unencrypted audio file ({ext}). "
            "Encrypt first using encrypt_audio.py before transferring."
        )
        logger.error(
            "BLOCKED unencrypted audio: %s (%s)",
            filepath.name, ext.upper()
        )
        return {**result_base, "reason": reason}

    # ── Kiểm tra 3: Chỉ cho phép file .tc ──
    if ext != ALLOWED_EXTENSION:
        reason = (
            f"BLOCKED: File type '{ext}' is not allowed for wireless transfer. "
            "Only encrypted TrueCrypt containers (.tc) are permitted."
        )
        logger.error(
            "BLOCKED unsupported file type: %s (%s)",
            filepath.name, ext
        )
        return {**result_base, "reason": reason}

    # ── Kiểm tra 4: Xác minh header TrueCrypt ──
    # File đúng extension .tc nhưng vẫn cần verify header để đảm bảo đã mã hóa thật
    if not is_encrypted_container(filepath):
        reason = (
            "BLOCKED: File has .tc extension but failed TrueCrypt header validation. "
            "Container may be empty, corrupt, or not a valid TrueCrypt volume."
        )
        logger.error(
            "BLOCKED invalid .tc container (header check failed): %s",
            filepath.name
        )
        return {**result_base, "reason": reason}

    # ── Tất cả kiểm tra qua → cho phép truyền ──
    file_size_mb = filepath.stat().st_size / (1024 * 1024)
    reason = (
        f"ALLOWED: Valid TrueCrypt container ({file_size_mb:.2f} MB). "
        "Safe to transfer over Wi-Fi."
    )
    logger.info(
        "ALLOWED encrypted container: %s (%.2f MB)",
        filepath.name, file_size_mb
    )
    return {"allowed": True, "reason": reason, "filepath": str(abs_path)}


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────
def main() -> None:
    """CLI entry point for pre-transfer file validation.

    Usage:
        python3 pre_transfer_check.py /path/to/file.tc

    Exit codes:
        0 - File allowed for transfer
        1 - File blocked
    """
    if len(sys.argv) != 2:
        print(
            "Usage: python3 pre_transfer_check.py <filepath>\n"
            "Example: python3 pre_transfer_check.py /phantom/encrypted/recording.tc",
            file=sys.stderr
        )
        sys.exit(1)

    filepath = Path(sys.argv[1])

    # Ghi log lúc bắt đầu kiểm tra với timestamp ISO 8601
    logger.info(
        "Pre-transfer check started at %s — checking: %s",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        filepath
    )

    # Thực hiện kiểm tra
    result = check_file_before_transfer(filepath)

    # In kết quả ra stdout theo format dễ đọc
    print()
    print("━" * 60)
    print(f"  PHANTOM R3 — Pre-Transfer Security Check")
    print("━" * 60)
    print(f"  File   : {result['filepath']}")
    print(f"  Status : {'✓ ALLOWED' if result['allowed'] else '✗ BLOCKED'}")
    print(f"  Reason : {result['reason']}")
    print("━" * 60)
    print()

    # Exit code: 0 = allowed, 1 = blocked
    # Nguyên tắc bất biến: nếu blocked thì process phải fail — không được silently pass
    sys.exit(0 if result["allowed"] else 1)


if __name__ == "__main__":
    main()
