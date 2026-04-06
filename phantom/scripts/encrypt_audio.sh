#!/usr/bin/env bash
# =============================================================================
# PHANTOM R3 — Bash wrapper for encrypt_audio.py
# =============================================================================
# This script is the entry point used by systemd / cron.
# It ensures the Python script runs with the correct environment and privileges.
#
# Usage:
#   ./encrypt_audio.sh [--dry-run] [--source DIR] [--output DIR]
#
# All arguments are forwarded verbatim to encrypt_audio.py.
# =============================================================================

set -euo pipefail

# ── Resolve script directory (works with symlinks) ──────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/encrypt_audio.py"

# ── Default paths (mirror Python constants) ─────────────────────────────────
SOURCE_DIR="/tmp/phantom"
ENCRYPTED_DIR="/phantom/encrypted"
LOG_DIR="/phantom/logs"
SECRET_FILE="/phantom/.secret"

# ── Colour helpers (only when running in a TTY) ──────────────────────────────
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; NC=''
fi

log_info()  { echo -e "${GREEN}[INFO]${NC}  $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >&2; }

# ── Privilege check ──────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (required by tcplay and mount)."
    log_error "Try: sudo $0 $*"
    exit 1
fi

# ── Dependency checks ────────────────────────────────────────────────────────
check_dependency() {
    local cmd="$1"
    if ! command -v "$cmd" &>/dev/null; then
        log_error "Required command not found: ${cmd}"
        return 1
    fi
}

DEPS_OK=true
for dep in python3 tcplay mkfs.fat shred dd mount umount; do
    check_dependency "$dep" || DEPS_OK=false
done

if [[ "$DEPS_OK" == false ]]; then
    log_error "One or more dependencies are missing. Run: sudo apt install tcplay dosfstools coreutils"
    exit 1
fi

# ── Python version check (need 3.9+ for Path.unlink(missing_ok=True)) ────────
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 9 ]]; }; then
    log_warn "Python ${PYTHON_VERSION} detected. Python 3.9+ is recommended."
fi

# ── Ensure required directories exist ────────────────────────────────────────
for dir in "$SOURCE_DIR" "$ENCRYPTED_DIR" "$LOG_DIR"; do
    if [[ ! -d "$dir" ]]; then
        log_info "Creating directory: ${dir}"
        mkdir -p "$dir"
    fi
done

# ── Password sanity check (warn, do not exit — Python will handle error) ─────
if [[ -z "${PHANTOM_PASSWORD:-}" ]] && [[ ! -f "$SECRET_FILE" ]]; then
    log_warn "No password source found: env var PHANTOM_PASSWORD not set and ${SECRET_FILE} not present."
    log_warn "The Python script will exit with an error unless one of these is configured."
fi

if [[ -f "$SECRET_FILE" ]]; then
    # Enforce 600 permissions on secret file
    current_perms=$(stat -c "%a" "$SECRET_FILE" 2>/dev/null || echo "000")
    if [[ "$current_perms" != "600" ]]; then
        log_warn "Fixing insecure permissions on ${SECRET_FILE}: ${current_perms} → 600"
        chmod 600 "$SECRET_FILE"
    fi
fi

# ── Check Python script exists ───────────────────────────────────────────────
if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    log_error "Python script not found: ${PYTHON_SCRIPT}"
    exit 1
fi

# ── Run the Python encryption script ─────────────────────────────────────────
log_info "Starting PHANTOM R3 encryption — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log_info "Python script: ${PYTHON_SCRIPT}"
log_info "Arguments: $*"

python3 "$PYTHON_SCRIPT" "$@"
EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    log_info "Encryption run completed successfully (exit code 0)."
else
    log_error "Encryption run finished with errors (exit code ${EXIT_CODE}). Check logs: ${LOG_DIR}/encrypt_audio.log"
fi

exit $EXIT_CODE
