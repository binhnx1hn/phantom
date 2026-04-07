"""
_test_upload.py — Test upload nhiều định dạng file lên ESP32 Node-1
==================================================================
Cách dùng:
  1. Kết nối WiFi vào "ESP32-Node-1" (password: 12345678)
  2. Chạy: python _test_upload.py

Hoặc upload 1 file cụ thể:
  python _test_upload.py myfile.png
  python _test_upload.py song.wav
  python _test_upload.py report.docx

Node-1 IP : 192.168.4.1  port 80
Node-2 IP : 192.168.5.1  port 80  (sau khi Node-2 sync xong)
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error

NODE1_URL = "http://192.168.4.1"
NODE2_URL = "http://192.168.5.1"


# ── Helpers ──────────────────────────────────────────────────────────────────

def http_get(url, timeout=8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as ex:
        return 0, str(ex).encode()


def http_post_raw(url, data: bytes, headers: dict, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as ex:
        return 0, str(ex).encode()


def fmt_size(n):
    if n >= 1024*1024:
        return f"{n/1024/1024:.2f} MB"
    if n >= 1024:
        return f"{n/1024:.1f} KB"
    return f"{n} B"


def print_json(raw: bytes):
    try:
        d = json.loads(raw)
        print(json.dumps(d, indent=2, ensure_ascii=False))
    except Exception:
        print(raw.decode(errors="replace"))


# ── Upload một file ──────────────────────────────────────────────────────────

def upload_file(filepath: str, base_url: str = NODE1_URL) -> bool:
    filename = os.path.basename(filepath)
    size     = os.path.getsize(filepath)
    print(f"\n{'='*60}")
    print(f"  Upload: {filename}  ({fmt_size(size)})")
    print(f"  URL   : {base_url}/file/upload")
    print(f"{'='*60}")

    with open(filepath, "rb") as f:
        data = f.read()

    headers = {
        "X-Filename":     filename,
        "Content-Type":   "application/octet-stream",
        "Content-Length": str(len(data)),
    }

    t0 = time.time()
    status, resp = http_post_raw(f"{base_url}/file/upload", data, headers)
    elapsed = time.time() - t0

    print(f"  HTTP {status}  ({elapsed:.2f}s)")
    print_json(resp)

    if status == 200:
        d = json.loads(resp)
        saved_name = d.get("filename", "?")
        saved_ok   = d.get("spiffs_saved", False)
        print(f"\n  ✓ Saved as '{saved_name}'  spiffs_saved={saved_ok}")
        return True
    else:
        print(f"\n  ✗ Upload FAILED (HTTP {status})")
        return False


# ── List files ───────────────────────────────────────────────────────────────

def list_files(base_url: str = NODE1_URL):
    print(f"\n{'='*60}")
    print(f"  File list: {base_url}/file/list")
    print(f"{'='*60}")
    status, resp = http_get(f"{base_url}/file/list")
    if status != 200:
        print(f"  HTTP {status}: {resp.decode(errors='replace')}")
        return
    try:
        d = json.loads(resp)
        files = d.get("files", [])
        total = d.get("spiffs_total", 0)
        used  = d.get("spiffs_used",  0)
        free  = d.get("spiffs_free",  0)
        print(f"  Files: {len(files)}   SPIFFS: {fmt_size(used)}/{fmt_size(total)}  (free {fmt_size(free)})")
        for fi in files:
            name = fi.get("name","?")
            sz   = fi.get("size",0)
            mime = fi.get("mime","?")
            dur  = fi.get("duration_sec")
            line = f"    • {name:30s}  {fmt_size(sz):10s}  {mime}"
            if dur is not None:
                line += f"  [{dur:.1f}s]"
            print(line)
    except Exception as ex:
        print(f"  Parse error: {ex}")
        print(resp.decode(errors="replace"))


# ── Download verify ───────────────────────────────────────────────────────────

def download_verify(filename: str, base_url: str = NODE1_URL):
    url = f"{base_url}/file/download?name={filename}"
    print(f"\n  Download verify: {url}")
    status, resp = http_get(url)
    if status == 200:
        print(f"  ✓ {filename}  received {fmt_size(len(resp))}")
    else:
        print(f"  ✗ HTTP {status}: {resp.decode(errors='replace')[:200]}")


# ── Create dummy test files ───────────────────────────────────────────────────

def create_test_files():
    """Tạo file test nhỏ nếu chưa tồn tại"""
    files = []

    # TXT
    p = "test_hello.txt"
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write("Hello ESP32!\nThis is a text file upload test.\n")
    files.append(p)

    # JSON
    p = "test_data.json"
    if not os.path.exists(p):
        with open(p, "w") as f:
            json.dump({"sensor": "esp32", "value": 3.14, "ok": True}, f)
    files.append(p)

    # Binary (fake PNG header)
    p = "test_image.png"
    if not os.path.exists(p):
        # Minimal 1x1 px red PNG (89 bytes)
        png_1x1 = bytes([
            0x89,0x50,0x4E,0x47,0x0D,0x0A,0x1A,0x0A,  # PNG signature
            0x00,0x00,0x00,0x0D,0x49,0x48,0x44,0x52,  # IHDR chunk len=13
            0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,  # width=1, height=1
            0x08,0x02,0x00,0x00,0x00,0x90,0x77,0x53,
            0xDE,0x00,0x00,0x00,0x0C,0x49,0x44,0x41,  # IDAT
            0x54,0x08,0xD7,0x63,0xF8,0xCF,0xC0,0x00,
            0x00,0x00,0x02,0x00,0x01,0xE2,0x21,0xBC,
            0x33,0x00,0x00,0x00,0x00,0x49,0x45,0x4E,  # IEND
            0x44,0xAE,0x42,0x60,0x82,
        ])
        with open(p, "wb") as f:
            f.write(png_1x1)
    files.append(p)

    # WAV (minimal 44-byte header + silence)
    p = "test_silence.wav"
    if not os.path.exists(p):
        import struct
        sr, ch, bps = 8000, 1, 16
        n_samples   = sr  # 1 giây
        data_bytes  = n_samples * ch * (bps // 8)
        wav = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF', 36 + data_bytes, b'WAVE',
            b'fmt ', 16, 1, ch, sr, sr * ch * bps // 8, ch * bps // 8, bps,
            b'data', data_bytes)
        wav += b'\x00' * data_bytes
        with open(p, "wb") as f:
            f.write(wav)
    files.append(p)

    return files


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Kiểm tra kết nối Node-1
    print("Checking Node-1 status...")
    status, resp = http_get(f"{NODE1_URL}/status", timeout=5)
    if status != 200:
        print(f"ERROR: Cannot reach Node-1 ({NODE1_URL})")
        print("  → Hãy kết nối WiFi vào 'ESP32-Node-1' (pass: 12345678)")
        sys.exit(1)
    try:
        d = json.loads(resp)
        print(f"  Node-1 OK  heap={d.get('free_heap',0)//1024}KB"
              f"  spiffs_free={d.get('spiffs_free',0)//1024}KB")
    except Exception:
        print("  Node-1 responded but JSON parse failed")

    # Upload file được chỉ định từ command line
    if len(sys.argv) > 1:
        for filepath in sys.argv[1:]:
            if not os.path.exists(filepath):
                print(f"ERROR: File not found: {filepath}")
                continue
            ok = upload_file(filepath)
            if ok:
                download_verify(os.path.basename(filepath))
        list_files()
        return

    # Không có argument → tạo và upload file test
    print("\nNo file specified — creating and uploading test files...")
    test_files = create_test_files()

    results = {}
    for fp in test_files:
        ok = upload_file(fp)
        results[fp] = ok
        if ok:
            download_verify(os.path.basename(fp))
        time.sleep(0.3)

    list_files()

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for fp, ok in results.items():
        status_str = "✓ OK  " if ok else "✗ FAIL"
        print(f"  {status_str}  {fp}")

    all_ok = all(results.values())
    print(f"\n  {'ALL PASSED' if all_ok else 'SOME FAILED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
