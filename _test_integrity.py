"""
_test_integrity.py — So sánh file gốc vs file đã download từ ESP32
Chạy: python _test_integrity.py
"""
import socket, os, time
from pathlib import Path

HOST = "192.168.5.1"
PORT = 80
ORIGINAL_DIR = Path("dongbo")
DOWNLOAD_DIR = Path.home() / "Downloads"

def download_raw(filename, timeout=45):
    """Download file từ ESP32, trả về raw bytes."""
    import urllib.parse
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        enc = urllib.parse.quote(filename, safe=".-_")
        s.sendall(f"GET /file/download?name={enc} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n".encode())
        raw = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                c = s.recv(4096)
                if not c: break
                raw += c
            except: break
        sep = raw.find(b"\r\n\r\n")
        if sep < 0: return None, "No header sep"
        headers = raw[:sep].decode(errors="replace")
        body = raw[sep+4:]
        status = headers.split("\r\n")[0]
        cl = -1
        for line in headers.split("\r\n")[1:]:
            if line.lower().startswith("content-length:"):
                cl = int(line.split(":")[1].strip())
        return body, f"status={status}  CL={cl}  got={len(body)}"
    except Exception as e:
        return None, f"Exception: {e}"
    finally:
        try: s.close()
        except: pass

def check_file(fname):
    orig_path = ORIGINAL_DIR / fname
    dl_path   = DOWNLOAD_DIR / fname

    print(f"\n{'='*60}")
    print(f"File: {fname}")

    # Original
    if orig_path.exists():
        orig = orig_path.read_bytes()
        print(f"  Original size : {len(orig)} bytes")
        print(f"  Original[0:8] : {orig[:8].hex()}")
    else:
        orig = None
        print(f"  Original      : NOT FOUND in dongbo/")

    # Download fresh from ESP32
    print(f"  Downloading from ESP32...")
    t0 = time.time()
    body, info = download_raw(fname)
    elapsed = time.time() - t0
    print(f"  {info}  ({elapsed:.1f}s)")

    if body is None:
        print("  DOWNLOAD FAILED")
        return

    print(f"  Downloaded[0:8]: {body[:8].hex()}")

    if orig is not None:
        if len(body) == len(orig):
            match = body == orig
            print(f"  Size match    : YES")
            print(f"  Content match : {'YES ✓' if match else 'NO ✗'}")
            if not match:
                # Find first diff
                for i in range(min(len(body), len(orig))):
                    if body[i] != orig[i]:
                        print(f"  First diff at byte {i}: orig={orig[i]:02x} got={body[i]:02x}")
                        print(f"  Context orig[{i-4}:{i+8}]: {orig[max(0,i-4):i+8].hex()}")
                        print(f"  Context got [{i-4}:{i+8}]: {body[max(0,i-4):i+8].hex()}")
                        break
        else:
            print(f"  Size MISMATCH : orig={len(orig)}  got={len(body)}")
            # Check if got is truncated at null byte
            null_pos = orig.find(b'\x00')
            print(f"  First null in orig at byte: {null_pos}")
            if null_pos > 0 and len(body) == null_pos:
                print(f"  *** TRUNCATED AT NULL BYTE — upload bug (server.arg('plain') cuts at \\0) ***")
            elif len(body) < len(orig):
                print(f"  Got {len(orig)-len(body)} bytes LESS than original")
            else:
                print(f"  Got {len(body)-len(orig)} bytes MORE than original")

    # Save for manual inspection
    out = DOWNLOAD_DIR / f"_check_{fname}"
    out.write_bytes(body)
    print(f"  Saved to: {out}")

if __name__ == "__main__":
    for f in ["U3listening.docx", "Testcase.xlsx", "note.docx"]:
        check_file(f)
