#!/usr/bin/env bash
# =============================================================================
# PHANTOM R3 — Test Suite for @binhnx1hn tasks
# Tests: #6, #16, #17, #18, #19, #20, #21
#
# Usage:
#   sudo bash scripts/run_tests.sh
#   sudo bash scripts/run_tests.sh --task 6
#   sudo bash scripts/run_tests.sh --task 16
#   sudo bash scripts/run_tests.sh --task 17
#   sudo bash scripts/run_tests.sh --task 18
#   sudo bash scripts/run_tests.sh --task 19
#   sudo bash scripts/run_tests.sh --task 21
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

pass() { echo -e "${GREEN}✅ PASS${NC} — $*"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "${RED}❌ FAIL${NC} — $*"; FAIL_COUNT=$((FAIL_COUNT+1)); }
warn() { echo -e "${YELLOW}⚠️  WARN${NC} — $*"; }
info() { echo -e "${CYAN}ℹ️  ${NC}$*"; }
header() { echo -e "\n${BOLD}${CYAN}════════════════════════════════════════════${NC}"; echo -e "${BOLD}${CYAN}  $*${NC}"; echo -e "${BOLD}${CYAN}════════════════════════════════════════════${NC}"; }

PASS_COUNT=0
FAIL_COUNT=0

# ─────────────────────────────────────────────
# Paths & passwords (test values)
# ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHANTOM_DIR="/phantom"
SCRIPTS_DIR="${PHANTOM_DIR}/scripts"
ENCRYPTED_DIR="${PHANTOM_DIR}/encrypted"
LOGS_DIR="${PHANTOM_DIR}/logs"
SECRET_FILE="${PHANTOM_DIR}/.secret"

TEST_OPUS_DIR="/tmp/phantom_test_$$"
TEST_OUTER_PASS="test_outer_pass_$$"
TEST_HIDDEN_PASS="test_hidden_pass_$$"
TEST_CONTAINER="${ENCRYPTED_DIR}/test_run_$$.tc"
CONTAINER_SIZE=20   # MB

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
require_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}ERROR:${NC} Must run as root: sudo bash $0"
        exit 1
    fi
}

tc_map_via_pty() {
    # Map a TrueCrypt container by piping password through stdin.
    # tcplay reads password from stdin when no PTY is available.
    # This avoids the need for 'expect' or a controlling terminal.
    local map_name="$1" device="$2" password="$3"
    echo "${password}" | tcplay --map="${map_name}" --device="${device}" 2>&1
}

cleanup_all() {
    # Best-effort cleanup after tests
    sudo umount /mnt/t_outer_$$ /mnt/t_hidden_$$ /mnt/t_decrypt_$$ 2>/dev/null || true
    sudo tcplay --unmap "t_outer_$$"   2>/dev/null || true
    sudo tcplay --unmap "t_hidden_$$"  2>/dev/null || true
    sudo tcplay --unmap "t_decrypt_$$" 2>/dev/null || true
    sudo losetup -D 2>/dev/null || true
    rm -rf /mnt/t_outer_$$ /mnt/t_hidden_$$ /mnt/t_decrypt_$$ 2>/dev/null || true
    rm -rf "$TEST_OPUS_DIR" 2>/dev/null || true
    rm -f "$TEST_CONTAINER" 2>/dev/null || true
    rm -f /tmp/received_test_$$.tc 2>/dev/null || true
}

trap cleanup_all EXIT

# ─────────────────────────────────────────────
# Parse --task argument
# ─────────────────────────────────────────────
RUN_TASK="all"
if [[ "${1:-}" == "--task" && -n "${2:-}" ]]; then
    RUN_TASK="$2"
fi

should_run() {
    [[ "$RUN_TASK" == "all" ]] || [[ "$RUN_TASK" == "$1" ]]
}

# =============================================================================
# TASK 6 — Automatic encryption: .opus → TrueCrypt container
# =============================================================================
test_task6() {
    header "TASK 6 — Tự động mã hóa .opus → TrueCrypt container"

    # 6.1 — Create fake opus file
    info "6.1 Tạo file .opus giả để test"
    mkdir -p "$TEST_OPUS_DIR"
    dd if=/dev/urandom of="${TEST_OPUS_DIR}/test_rec.opus" bs=1M count=1 2>/dev/null
    [[ -f "${TEST_OPUS_DIR}/test_rec.opus" ]] \
        && pass "6.1 File .opus test tạo thành công (1MB)" \
        || fail "6.1 Không tạo được file .opus"

    # 6.2 — Dry-run
    info "6.2 Test dry-run encrypt_audio.py"
    OUT=$(python3 "${SCRIPTS_DIR}/encrypt_audio.py" \
        --dry-run \
        --source "$TEST_OPUS_DIR" \
        --output "${ENCRYPTED_DIR}" \
        --log-dir "${LOGS_DIR}" 2>&1)
    echo "$OUT" | grep -q "DRY-RUN" \
        && pass "6.2 Dry-run mode hoạt động" \
        || fail "6.2 Dry-run không hoạt động"
    echo "$OUT" | grep -q "Encryption started" \
        && pass "6.2 Script khởi động đúng" \
        || fail "6.2 Script không khởi động"

    # 6.3 — Real encryption
    info "6.3 Test mã hóa thật (tạo container .tc)"
    # Set password via env
    EXPECTED_TC="${ENCRYPTED_DIR}/test_rec.tc"
    rm -f "$EXPECTED_TC"
    PHANTOM_PASSWORD="$(cat ${SECRET_FILE})" \
        python3 "${SCRIPTS_DIR}/encrypt_audio.py" \
        --source "$TEST_OPUS_DIR" \
        --output "${ENCRYPTED_DIR}" \
        --log-dir "${LOGS_DIR}" 2>&1 | tail -5

    # 6.4 — Verify output
    info "6.4 Kiểm tra kết quả"
    if [[ -f "$EXPECTED_TC" ]]; then
        TC_SIZE=$(du -sh "$EXPECTED_TC" | cut -f1)
        pass "6.4 Container .tc đã tạo: $EXPECTED_TC ($TC_SIZE)"
    else
        fail "6.4 Không tìm thấy container .tc tại $EXPECTED_TC"
    fi

    if [[ ! -f "${TEST_OPUS_DIR}/test_rec.opus" ]]; then
        pass "6.4 File .opus gốc đã bị xóa sau mã hóa"
    else
        warn "6.4 File .opus gốc còn tồn tại (có thể do lỗi shred/quyền)"
    fi

    # Clean up test container
    rm -f "$EXPECTED_TC"
}

# =============================================================================
# TASK 16 — Pre-transfer check: only encrypted .tc allowed over Wi-Fi
# =============================================================================
test_task16() {
    header "TASK 16 — Dữ liệu truyền qua Wi-Fi luôn ở dạng đã mã hóa"

    # Create test files
    mkdir -p "$TEST_OPUS_DIR"
    dd if=/dev/urandom of="${TEST_OPUS_DIR}/raw.opus" bs=1K count=10 2>/dev/null
    echo "not a tc file" > "${TEST_OPUS_DIR}/fake.tc"
    echo "text" > "${TEST_OPUS_DIR}/document.txt"

    # Find a real .tc container to test ALLOW case
    REAL_TC=$(ls "${ENCRYPTED_DIR}"/*.tc 2>/dev/null | head -1 || true)

    # 16.1 — Block raw .opus
    # Note: disable set -e for this block — python3 exits 1 when blocking, which is expected
    info "16.1 Test BLOCK file .opus thô"
    set +e
    python3 "${SCRIPTS_DIR}/pre_transfer_check.py" "${TEST_OPUS_DIR}/raw.opus" > /tmp/ptc_out.txt 2>&1
    RC_161=$?
    set -e
    OUT_161=$(cat /tmp/ptc_out.txt)
    [[ $RC_161 -ne 0 ]] \
        && pass "16.1 .opus thô bị BLOCKED đúng (exit=$RC_161)" \
        || fail "16.1 .opus thô KHÔNG bị blocked (exit=$RC_161)"
    echo "$OUT_161" | grep -q "BLOCKED" \
        && pass "16.1 Output chứa 'BLOCKED'" \
        || fail "16.1 Output không chứa 'BLOCKED'"

    # 16.2 — Block non-.tc
    info "16.2 Test BLOCK file không phải .tc"
    set +e
    python3 "${SCRIPTS_DIR}/pre_transfer_check.py" "${TEST_OPUS_DIR}/document.txt" > /tmp/ptc_out.txt 2>&1
    RC_162=$?
    set -e
    [[ $RC_162 -ne 0 ]] \
        && pass "16.2 .txt bị BLOCKED đúng (exit=$RC_162)" \
        || fail "16.2 .txt KHÔNG bị blocked (exit=$RC_162)"

    # 16.3 — Block fake .tc (empty/low-entropy header)
    info "16.3 Test BLOCK .tc giả (header không hợp lệ)"
    set +e
    python3 "${SCRIPTS_DIR}/pre_transfer_check.py" "${TEST_OPUS_DIR}/fake.tc" > /tmp/ptc_out.txt 2>&1
    RC_163=$?
    set -e
    [[ $RC_163 -ne 0 ]] \
        && pass "16.3 .tc giả bị BLOCKED đúng (exit=$RC_163)" \
        || fail "16.3 .tc giả KHÔNG bị blocked (exit=$RC_163)"

    # 16.4 — Allow real .tc
    if [[ -n "$REAL_TC" ]]; then
        info "16.4 Test ALLOW file .tc thật"
        set +e
        python3 "${SCRIPTS_DIR}/pre_transfer_check.py" "$REAL_TC" > /tmp/ptc_out.txt 2>&1
        RC_164=$?
        set -e
        OUT_164=$(cat /tmp/ptc_out.txt)
        [[ $RC_164 -eq 0 ]] \
            && pass "16.4 .tc thật được ALLOWED (exit=$RC_164)" \
            || fail "16.4 .tc thật bị BLOCKED (exit=$RC_164 — sai)"
        echo "$OUT_164" | grep -q "ALLOWED" \
            && pass "16.4 Output chứa 'ALLOWED'" \
            || fail "16.4 Output không chứa 'ALLOWED'"
    else
        warn "16.4 Không có .tc sẵn để test ALLOW — chạy task 6 trước"
    fi
    rm -f /tmp/ptc_out.txt
}

# =============================================================================
# TASK 17 — Hidden volume / plausible deniability
# =============================================================================
test_task17() {
    header "TASK 17 — Plausible deniability: Hidden Volume"

    # 17.1 — Generate decoy files
    info "17.1 Tạo decoy files"
    python3 "${SCRIPTS_DIR}/create_decoy_files.py" \
        --output-dir /tmp/phantom/decoy 2>&1 | tail -3
    DECOY_COUNT=$(ls /tmp/phantom/decoy/*.txt 2>/dev/null | wc -l)
    [[ $DECOY_COUNT -ge 5 ]] \
        && pass "17.1 Decoy files tạo thành công ($DECOY_COUNT files)" \
        || fail "17.1 Thiếu decoy files ($DECOY_COUNT/6)"

    # 17.2 — Dry-run hidden container
    info "17.2 Test dry-run create_hidden_container.py"
    mkdir -p "$TEST_OPUS_DIR"
    dd if=/dev/urandom of="${TEST_OPUS_DIR}/audio_secret.opus" bs=1M count=1 2>/dev/null
    PHANTOM_OUTER_PASSWORD="$TEST_OUTER_PASS" \
    PHANTOM_HIDDEN_PASSWORD="$TEST_HIDDEN_PASS" \
        python3 "${SCRIPTS_DIR}/create_hidden_container.py" \
        --output "$TEST_CONTAINER" \
        --size "$CONTAINER_SIZE" \
        --audio-files "${TEST_OPUS_DIR}/audio_secret.opus" \
        --decoy-dir /tmp/phantom/decoy \
        --dry-run 2>&1 | tail -5
    pass "17.2 Dry-run hoàn thành không lỗi"

    # 17.3 — Real hidden container
    info "17.3 Tạo hidden container thật ($CONTAINER_SIZE MB)"
    rm -f "$TEST_CONTAINER"
    PHANTOM_OUTER_PASSWORD="$TEST_OUTER_PASS" \
    PHANTOM_HIDDEN_PASSWORD="$TEST_HIDDEN_PASS" \
        python3 "${SCRIPTS_DIR}/create_hidden_container.py" \
        --output "$TEST_CONTAINER" \
        --size "$CONTAINER_SIZE" \
        --audio-files "${TEST_OPUS_DIR}/audio_secret.opus" \
        --decoy-dir /tmp/phantom/decoy \
        --log-dir "${LOGS_DIR}" \
        --weak-keys 2>&1 | tail -8

    if [[ -f "$TEST_CONTAINER" ]]; then
        TC_SIZE=$(du -sh "$TEST_CONTAINER" | cut -f1)
        pass "17.3 Hidden container tạo thành công: $TEST_CONTAINER ($TC_SIZE)"
    else
        fail "17.3 Không tạo được container"
        return 1
    fi

    # Setup loop device
    LOOP=$(losetup --find --show "$TEST_CONTAINER")
    info "Loop device: $LOOP"
    sleep 1

    # 17.4 — Mount outer volume
    info "17.4 Mount OUTER volume (outer password)"
    tc_map_via_pty "t_outer_$$" "$LOOP" "$TEST_OUTER_PASS"
    udevadm settle 2>/dev/null; sleep 1
    if [[ -e "/dev/mapper/t_outer_$$" ]]; then
        mkdir -p "/mnt/t_outer_$$"
        mount "/dev/mapper/t_outer_$$" "/mnt/t_outer_$$"
        TXT_COUNT=$(find "/mnt/t_outer_$$" -maxdepth 1 -name "*.txt" 2>/dev/null | wc -l | tr -d '[:space:]')
        OPUS_COUNT=$(find "/mnt/t_outer_$$" -maxdepth 1 -name "*.opus" 2>/dev/null | wc -l | tr -d '[:space:]')
        [[ "$TXT_COUNT" -ge 1 && "$OPUS_COUNT" -eq 0 ]] \
            && pass "17.4 Outer volume: thấy $TXT_COUNT .txt, không thấy .opus" \
            || fail "17.4 Outer volume: txt=$TXT_COUNT, opus=$OPUS_COUNT (expected txt≥1, opus=0)"
        umount "/mnt/t_outer_$$"; rmdir "/mnt/t_outer_$$"
        tcplay --unmap "t_outer_$$" 2>/dev/null
    else
        fail "17.4 Không mount được outer volume"
    fi
    losetup -d "$LOOP" 2>/dev/null; sleep 2

    # 17.5 — Mount hidden volume
    info "17.5 Mount HIDDEN volume (hidden password)"
    LOOP=$(losetup --find --show "$TEST_CONTAINER")
    tc_map_via_pty "t_hidden_$$" "$LOOP" "$TEST_HIDDEN_PASS"
    udevadm settle 2>/dev/null; sleep 1
    if [[ -e "/dev/mapper/t_hidden_$$" ]]; then
        mkdir -p "/mnt/t_hidden_$$"
        mount "/dev/mapper/t_hidden_$$" "/mnt/t_hidden_$$"
        OPUS_COUNT=$(ls "/mnt/t_hidden_$$"/*.opus 2>/dev/null | wc -l)
        [[ $OPUS_COUNT -ge 1 ]] \
            && pass "17.5 Hidden volume: thấy $OPUS_COUNT .opus file(s)" \
            || fail "17.5 Hidden volume: không thấy .opus"
        umount "/mnt/t_hidden_$$"; rmdir "/mnt/t_hidden_$$"
        tcplay --unmap "t_hidden_$$" 2>/dev/null
    else
        fail "17.5 Không mount được hidden volume"
    fi
    losetup -d "$LOOP" 2>/dev/null
}

# =============================================================================
# TASK 18 — TrueCrypt 7.1a compatibility: AES-256-XTS + SHA-512, auth
# =============================================================================
test_task18() {
    header "TASK 18 — Chỉ giải mã bằng TrueCrypt 7.1a với đúng mật khẩu"

    # Need a container — use existing or create minimal one
    EXISTING_TC=$(ls "${ENCRYPTED_DIR}"/*.tc 2>/dev/null | head -1 || true)
    if [[ -z "$EXISTING_TC" ]]; then
        warn "Không có .tc trong ${ENCRYPTED_DIR} — tạo container test mới"
        # Create minimal standard container (not hidden) for cipher check
        dd if=/dev/urandom of="$TEST_CONTAINER" bs=1M count=6 2>/dev/null
        printf 'TestPass123!\nTestPass123!\n' | tcplay --create \
            --device="$TEST_CONTAINER" \
            --cipher=AES-256-XTS \
            --pbkdf-prf=SHA512 2>/dev/null
        EXISTING_TC="$TEST_CONTAINER"
        CHECK_PASS="TestPass123!"
    else
        info "Dùng container: $EXISTING_TC"
        # Use outer password from hidden_test.tc if available
        if [[ "$EXISTING_TC" == *"hidden_test"* ]]; then
            CHECK_PASS="decoy_outer_2026"
        else
            CHECK_PASS="$(cat ${SECRET_FILE})"
        fi
    fi

    LOOP=$(losetup --find --show "$EXISTING_TC")
    sleep 1

    # 18.1 — Verify cipher and PRF
    info "18.1 Kiểm tra cipher AES-256-XTS + PRF SHA-512"
    INFO=$(script -q -c "expect -c \"
set timeout 30
spawn tcplay --info --device=${LOOP}
expect \\\"Passphrase:\\\"
send \\\"${CHECK_PASS}\\\r\\\"
expect eof
\"" /dev/null 2>&1)
    echo "$INFO"

    echo "$INFO" | grep -qi "AES-256-XTS" \
        && pass "18.1 Cipher: AES-256-XTS ✓" \
        || fail "18.1 Cipher không phải AES-256-XTS"
    echo "$INFO" | grep -qi "SHA512" \
        && pass "18.1 PRF: SHA-512 ✓" \
        || fail "18.1 PRF không phải SHA-512"

    losetup -d "$LOOP" 2>/dev/null; sleep 1

    # 18.2 — Wrong password rejected
    info "18.2 Sai password bị từ chối"
    LOOP=$(losetup --find --show "$EXISTING_TC")
    WRONG_MAP="t_wrong_$$"
    tc_map_via_pty "$WRONG_MAP" "$LOOP" "absolutely_wrong_password_xyz_12345" 2>/dev/null || true
    udevadm settle 2>/dev/null; sleep 1
    if [[ -e "/dev/mapper/${WRONG_MAP}" ]]; then
        fail "18.2 Sai password được chấp nhận (BUG!)"
        tcplay --unmap "$WRONG_MAP" 2>/dev/null
    else
        pass "18.2 Sai password bị từ chối — không tạo mapper"
    fi
    losetup -d "$LOOP" 2>/dev/null
}

# =============================================================================
# TASK 19+20 — Full decryption flow on Linux (simulate PC user)
# =============================================================================
test_task19() {
    header "TASK 19+20 — Luồng giải mã đầy đủ trên Linux (mô phỏng PC)"

    # Always create a fresh container dedicated to task 19+20
    # (never reuse TEST_CONTAINER from task 17 — it may already exist)
    TASK19_TC="${ENCRYPTED_DIR}/task19_test_$$.tc"
    TASK19_OUTER_PASS="outer_task19_2026"
    TASK19_HIDDEN_PASS="hidden_task19_2026"

    info "Tạo container mới cho task 19+20: $TASK19_TC"
    mkdir -p "$TEST_OPUS_DIR"
    dd if=/dev/urandom of="${TEST_OPUS_DIR}/audio_task19.opus" bs=1M count=1 2>/dev/null
    python3 "${SCRIPTS_DIR}/create_decoy_files.py" --output-dir /tmp/phantom/decoy 2>/dev/null
    PHANTOM_OUTER_PASSWORD="$TASK19_OUTER_PASS" \
    PHANTOM_HIDDEN_PASSWORD="$TASK19_HIDDEN_PASS" \
        python3 "${SCRIPTS_DIR}/create_hidden_container.py" \
        --output "$TASK19_TC" \
        --size "$CONTAINER_SIZE" \
        --audio-files "${TEST_OPUS_DIR}/audio_task19.opus" \
        --decoy-dir /tmp/phantom/decoy \
        --log-dir "${LOGS_DIR}" \
        --weak-keys 2>/dev/null
    if [[ ! -f "$TASK19_TC" ]]; then
        fail "Không tạo được container cho task 19+20"
        return 1
    fi
    USE_TC="$TASK19_TC"
    USE_PASS="$TASK19_HIDDEN_PASS"

    # Step 1: Simulate receiving file
    info "Step 1: Nhận file .tc (mô phỏng download từ phone)"
    cp "$USE_TC" "/tmp/received_test_$$.tc"
    [[ -f "/tmp/received_test_$$.tc" ]] \
        && pass "Step 1: File .tc nhận thành công ($(du -sh /tmp/received_test_$$.tc | cut -f1))" \
        || fail "Step 1: Không nhận được file"

    # Step 2: Validate before processing
    info "Step 2: pre_transfer_check validation"
    python3 "${SCRIPTS_DIR}/pre_transfer_check.py" "/tmp/received_test_$$.tc" 2>&1 \
        | grep -q "ALLOWED" \
        && pass "Step 2: File .tc validated — ALLOWED" \
        || warn "Step 2: File không pass pre_transfer_check"

    # Step 3: Setup loop device
    info "Step 3: Setup loop device"
    LOOP=$(losetup --find --show "/tmp/received_test_$$.tc")
    pass "Step 3: Loop device: $LOOP"
    sleep 1

    # Step 4: Map container
    info "Step 4: tcplay --map (mount hidden volume)"
    tc_map_via_pty "t_decrypt_$$" "$LOOP" "$USE_PASS"
    udevadm settle 2>/dev/null; sleep 1

    if [[ ! -e "/dev/mapper/t_decrypt_$$" ]]; then
        fail "Step 4: tcplay --map thất bại"
        losetup -d "$LOOP" 2>/dev/null
        return 1
    fi
    pass "Step 4: Container mapped → /dev/mapper/t_decrypt_$$"

    # Step 5: Mount filesystem
    info "Step 5: mount FAT32 volume"
    mkdir -p "/mnt/t_decrypt_$$"
    mount "/dev/mapper/t_decrypt_$$" "/mnt/t_decrypt_$$"
    pass "Step 5: Volume mounted tại /mnt/t_decrypt_$$"

    # Step 6: Access audio files
    info "Step 6: Truy cập file audio .opus"
    ls -lh "/mnt/t_decrypt_$$/"
    OPUS_FILE=$(ls "/mnt/t_decrypt_$$"/*.opus 2>/dev/null | head -1 || true)
    if [[ -n "$OPUS_FILE" ]]; then
        FSIZE=$(du -sh "$OPUS_FILE" | cut -f1)
        pass "Step 6: Tìm thấy audio: $OPUS_FILE ($FSIZE)"
        info "       → Trên PC thật: ffplay '$OPUS_FILE' hoặc vlc '$OPUS_FILE'"
    else
        fail "Step 6: Không tìm thấy .opus trong volume"
    fi

    # Step 7: Dismount
    info "Step 7: Unmount + unmap + detach"
    umount "/mnt/t_decrypt_$$"   && pass "Step 7a: Filesystem unmounted"
    tcplay --unmap "t_decrypt_$$" && pass "Step 7b: Container unmapped"
    losetup -d "$LOOP"            && pass "Step 7c: Loop device detached"
    rmdir "/mnt/t_decrypt_$$"

    # Step 8: Secure delete
    info "Step 8: Secure delete file .tc"
    shred -uz "/tmp/received_test_$$.tc" 2>/dev/null
    [[ ! -f "/tmp/received_test_$$.tc" ]] \
        && pass "Step 8: File .tc đã xóa an toàn" \
        || fail "Step 8: File .tc vẫn còn tồn tại"

    # Platform support summary
    echo ""
    info "Platform support (theo TRUECRYPT_GUIDE.md):"
    echo "  ✅ Linux  — tcplay (tested above)"
    echo "  📋 Windows — TrueCrypt 7.1a GUI (see docs/TRUECRYPT_GUIDE.md)"
    echo "  📋 macOS  — TrueCrypt 7.1a / VeraCrypt (see docs/TRUECRYPT_GUIDE.md)"
}

# =============================================================================
# TASK 21 — Documentation completeness
# =============================================================================
test_task21() {
    header "TASK 21 — Tài liệu hướng dẫn TrueCrypt 7.1a"

    DOCS_DIR="$(dirname "${SCRIPT_DIR}")/docs"
    DL_FILE="${DOCS_DIR}/TRUECRYPT_DOWNLOAD.md"
    GD_FILE="${DOCS_DIR}/TRUECRYPT_GUIDE.md"

    # TRUECRYPT_DOWNLOAD.md
    info "Kiểm tra TRUECRYPT_DOWNLOAD.md"
    [[ -f "$DL_FILE" ]] && pass "21.1 TRUECRYPT_DOWNLOAD.md tồn tại ($(wc -l < "$DL_FILE") dòng)" || fail "21.1 File không tồn tại"
    grep -qi "GRC.com"   "$DL_FILE" && pass "21.2 GRC.com mirror có trong tài liệu"   || fail "21.2 Thiếu GRC.com mirror"
    grep -qi "DrWhax"    "$DL_FILE" && pass "21.3 GitHub DrWhax mirror có"             || fail "21.3 Thiếu DrWhax mirror"
    grep -qi "SHA256"    "$DL_FILE" && pass "21.4 Hướng dẫn verify SHA256 có"         || fail "21.4 Thiếu SHA256 instructions"
    grep -qi "7\.1a"     "$DL_FILE" && pass "21.5 Phiên bản 7.1a được chỉ định rõ"    || fail "21.5 Thiếu version 7.1a"
    grep -qi "Windows"   "$DL_FILE" && pass "21.6 Hướng dẫn cài Windows có"           || fail "21.6 Thiếu Windows guide"
    grep -qi "macOS"     "$DL_FILE" && pass "21.7 Hướng dẫn cài macOS có"             || fail "21.7 Thiếu macOS guide"
    grep -qi "Linux"     "$DL_FILE" && pass "21.8 Hướng dẫn cài Linux có"             || fail "21.8 Thiếu Linux guide"

    echo ""
    # TRUECRYPT_GUIDE.md
    info "Kiểm tra TRUECRYPT_GUIDE.md"
    [[ -f "$GD_FILE" ]] && pass "21.9 TRUECRYPT_GUIDE.md tồn tại ($(wc -l < "$GD_FILE") dòng)" || fail "21.9 File không tồn tại"
    grep -qi "Windows"        "$GD_FILE" && pass "21.10 Hướng dẫn giải mã Windows"     || fail "21.10 Thiếu Windows"
    grep -qi "macOS"          "$GD_FILE" && pass "21.11 Hướng dẫn giải mã macOS"       || fail "21.11 Thiếu macOS"
    grep -qi "Linux"          "$GD_FILE" && pass "21.12 Hướng dẫn giải mã Linux"       || fail "21.12 Thiếu Linux"
    grep -qi "hidden volume"  "$GD_FILE" && pass "21.13 Hướng dẫn Hidden Volume"       || fail "21.13 Thiếu Hidden Volume"
    grep -qi "tcplay"         "$GD_FILE" && pass "21.14 tcplay được đề cập cho Linux"   || fail "21.14 Thiếu tcplay"
    grep -qi "opus"           "$GD_FILE" && pass "21.15 .opus audio được hướng dẫn"    || fail "21.15 Thiếu .opus instructions"
    grep -qi "dismount\|umount" "$GD_FILE" && pass "21.16 Dismount instructions có"    || fail "21.16 Thiếu dismount"
}

# =============================================================================
# MAIN
# =============================================================================
require_root

echo -e "${BOLD}${CYAN}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║        PHANTOM R3 — Test Suite @binhnx1hn            ║"
echo "║  Tasks: #6, #16, #17, #18, #19+20, #21               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Mode  : task=${RUN_TASK}"
echo "  Time  : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "  Device: $(uname -n)"
echo ""

should_run "6"  && test_task6
should_run "16" && test_task16
should_run "17" && test_task17
should_run "18" && test_task18
should_run "19" && test_task19
should_run "21" && test_task21

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}════════════════════════════════════════════${NC}"
echo -e "${BOLD}  TEST SUMMARY${NC}"
echo -e "${BOLD}${CYAN}════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}PASS: $PASS_COUNT${NC}"
echo -e "  ${RED}FAIL: $FAIL_COUNT${NC}"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "  TOTAL: $TOTAL"
echo ""
if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}  ✅ ALL TESTS PASSED — @binhnx1hn tasks verified!${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}  ❌ $FAIL_COUNT TEST(S) FAILED — check output above${NC}"
    exit 1
fi
