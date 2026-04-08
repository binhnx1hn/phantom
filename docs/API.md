# ESP32 File Transfer — API Reference

## Kết nối

| Node | WiFi SSID | Mật khẩu | Base URL |
|------|-----------|----------|----------|
| Node-1 | `ESP32-Node-1` | `12345678` | `http://192.168.4.1` |
| Node-2 | `ESP32-Node-2` | `12345678` | `http://192.168.5.1` |

> Kết nối WiFi vào **1 trong 2 node** là đủ — 2 node đồng bộ file với nhau.

---

## 1. GET `/status` — Trạng thái thiết bị

**Request:**
```
GET http://192.168.4.1/status
```

**Response `200 OK`:**
```json
{
  "node": 1,
  "ap_ssid": "ESP32-Node-1",
  "ap_ip": "192.168.4.1",
  "uptime": "00:05:32",
  "free_heap": 142336,
  "spiffs_has_file": true,
  "spiffs_total": 1966080,
  "spiffs_used": 524288,
  "spiffs_free": 1441792,
  "ram_ready": true,
  "ram_size": 524288,
  "node_enabled": true,
  "builtin_wav_size": 8192
}
```

**Dùng để:** Kiểm tra thiết bị online, xem dung lượng SPIFFS còn trống.

---

## 2. GET `/file/list` — Danh sách tất cả file trong SPIFFS

**Request:**
```
GET http://192.168.4.1/file/list
```

**Response `200 OK`:**
```json
{
  "files": [
    {
      "name": "audio.wav",
      "path": "/audio.wav",
      "size": 524288,
      "size_kb": "512.0 KB",
      "mime": "audio/wav",
      "duration_sec": 32.75
    },
    {
      "name": "demo_1.jpg",
      "path": "/demo_1.jpg",
      "size": 102400,
      "size_kb": "100.0 KB",
      "mime": "image/jpeg"
    }
  ],
  "count": 2,
  "spiffs_total": 1966080,
  "spiffs_used": 626688,
  "spiffs_free": 1339392
}
```

**Lưu ý:**
- `duration_sec` chỉ có với file `.wav`
- `mime` tự động theo đuôi file

---

## 3. GET `/file/download` — Tải file về máy

**Request (có tên file):**
```
GET http://192.168.4.1/file/download?name=audio.wav
GET http://192.168.4.1/file/download?name=demo_1.jpg
GET http://192.168.4.1/file/download?name=demo_2.docx
```

**Request (không có tên → trả về `audio.wav` mặc định):**
```
GET http://192.168.4.1/file/download
```

**Response `200 OK`:**
- Body = nội dung file nhị phân
- Header `Content-Type` theo loại file
- Header `Content-Disposition: attachment; filename="<tên>"`
- Header `Content-Length: <kích thước>`

**Response lỗi:**
```json
{ "error": "not found" }        // 404 — file không tồn tại
{ "error": "invalid filename" } // 400 — tên file không hợp lệ
```

**Ví dụ tải bằng Python:**
```python
import urllib.request
url = "http://192.168.4.1/file/download?name=audio.wav"
with urllib.request.urlopen(url, timeout=30) as r:
    data = r.read()
open("audio.wav", "wb").write(data)
```

**Ví dụ tải bằng curl:**
```bash
curl -o audio.wav "http://192.168.4.1/file/download?name=audio.wav"
curl -o demo.jpg  "http://192.168.4.1/file/download?name=demo_1.jpg"
```

---

## 4. POST `/file/upload` — Upload file lên ESP32 (HTTP port 80)

**Request:**
```
POST http://192.168.4.1/file/upload
Header: X-Filename: ten_file.wav
Header: Content-Type: application/octet-stream
Header: Content-Length: <kích thước bytes>
Body: <nội dung file nhị phân>
```

**Response `200 OK`:**
```json
{ "ok": true, "saved": "audio.wav", "size": 524288 }
```

**Response lỗi:**
```json
{ "error": "file too large" }   // 413 — vượt quá 1.8 MB
{ "error": "save failed" }      // 500 — SPIFFS đầy hoặc lỗi ghi
```

**Ví dụ upload bằng Python:**
```python
import socket

def upload_file(host, filename, filepath):
    data = open(filepath, "rb").read()
    s = socket.socket()
    s.settimeout(30)
    s.connect((host, 80))
    req = (
        f"POST /file/upload HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"X-Filename: {filename}\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"Content-Length: {len(data)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    s.sendall(req)
    s.sendall(data)
    resp = b""
    while True:
        c = s.recv(4096)
        if not c: break
        resp += c
    s.close()
    return resp.decode(errors="replace")

# Dùng:
upload_file("192.168.4.1", "audio.wav", "local/audio.wav")
upload_file("192.168.5.1", "photo.jpg", "local/photo.jpg")
```

**Ví dụ upload bằng curl:**
```bash
curl -X POST http://192.168.4.1/file/upload \
     -H "X-Filename: audio.wav" \
     -H "Content-Type: application/octet-stream" \
     --data-binary @audio.wav
```

**LED sau upload:** nháy **3 lần** = thành công, không nháy = thất bại.

---

## 5. POST `/file/upload` — Upload qua Raw TCP port 8081 (khuyên dùng cho file lớn)

Port 8081 bypass thư viện WebServer, tránh lỗi chunked encoding với file lớn.

**Request (giống HTTP nhưng gửi đến port 8081):**
```
POST /upload HTTP/1.1
Host: 192.168.4.1:8081
X-Filename: ten_file.wav
Content-Type: audio/wav
Content-Length: <kích thước>
Connection: close

<nội dung file nhị phân>
```

**Ví dụ Python port 8081:**
```python
import socket

def upload_tcp(host, filename, filepath, port=8081):
    data = open(filepath, "rb").read()
    s = socket.socket()
    s.settimeout(30)
    s.connect((host, port))
    req = (
        f"POST /upload HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"X-Filename: {filename}\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"Content-Length: {len(data)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    s.sendall(req)
    sent = 0
    while sent < len(data):
        s.sendall(data[sent:sent+4096])
        sent += 4096
    s.close()

upload_tcp("192.168.4.1", "audio.wav", "local/audio.wav")
```

---

## 6. POST `/file/delete` — Xóa file

**Request:**
```
POST http://192.168.4.1/file/delete?name=demo_1.jpg
```

**Response `200 OK`:**
```json
{ "ok": true, "deleted": "demo_1.jpg" }
```

**Response lỗi:**
```json
{ "error": "not found" }
```

---

## 7. POST `/file/clear` — Xóa file audio.wav chính

**Request:**
```
POST http://192.168.4.1/file/clear
```

**Response `200 OK`:**
```json
{ "ok": true }
```

---

## 8. GET `/file/info` — Thông tin file audio.wav chính

**Request:**
```
GET http://192.168.4.1/file/info
```

**Response `200 OK`:**
```json
{
  "has_file": true,
  "path": "/audio.wav",
  "size": 524288,
  "size_kb": "512.0",
  "wav_info": {
    "channels": 1,
    "sample_rate": 16000,
    "bits_per_sample": 16,
    "duration_sec": 32.75
  },
  "free_heap": 142336
}
```

---

## 9. GET `/ram/info` — Thông tin RAM buffer (chỉ WAV)

**Request:**
```
GET http://192.168.4.1/ram/info
```

**Response `200 OK`:**
```json
{
  "ram_ready": true,
  "ram_size": 524288,
  "channels": 1,
  "sample_rate": 16000,
  "bits_per_sample": 16,
  "duration_sec": 32.75
}
```

---

## 10. POST `/sync` — Trigger đồng bộ thủ công (Node-2 only)

Chỉ có trên **Node-2** (`192.168.5.1`). Yêu cầu Node-2 kết nối vào Node-1 và sync file ngay lập tức.

**Request:**
```
POST http://192.168.5.1/sync
```

**Response `200 OK`:**
```json
{ "ok": true, "downloaded": 2 }
```

---

## 11. GET `/sync/status` — Trạng thái đồng bộ (Node-1 only)

Chỉ có trên **Node-1** (`192.168.4.1`). Node-2 gọi endpoint này trước khi sync.

**Request:**
```
GET http://192.168.4.1/sync/status
```

**Response `200 OK`:**
```json
{
  "ready": true,
  "file_count": 3,
  "spiffs_free": 1339392
}
```

---

## Tóm tắt tất cả endpoint

| Method | Endpoint | Port | Mô tả | Node |
|--------|----------|------|--------|------|
| GET | `/status` | 80 | Trạng thái thiết bị | Cả 2 |
| GET | `/file/list` | 80 | Danh sách file SPIFFS | Cả 2 |
| GET | `/file/download?name=<tên>` | 80 | Tải file về | Cả 2 |
| POST | `/file/upload` | 80 | Upload file (HTTP) | Cả 2 |
| POST | `/upload` | **8081** | Upload file (Raw TCP) | Cả 2 |
| POST | `/file/delete?name=<tên>` | 80 | Xóa file | Cả 2 |
| POST | `/file/clear` | 80 | Xóa audio.wav | Cả 2 |
| GET | `/file/info` | 80 | Info file audio.wav | Cả 2 |
| GET | `/ram/info` | 80 | Info RAM buffer | Cả 2 |
| POST | `/sync` | 80 | Sync thủ công | **Node-2** |
| GET | `/sync/status` | 80 | Trạng thái sync | **Node-1** |

---

## Script Python lấy toàn bộ file từ ESP32

```python
"""
download_all.py — Lấy toàn bộ file từ ESP32 về folder_test/
Kết nối WiFi ESP32-Node-1 hoặc ESP32-Node-2 trước khi chạy.
"""
import urllib.request, json, os
from pathlib import Path

NODES = ["192.168.4.1", "192.168.5.1"]
OUT_DIR = Path("folder_test")
OUT_DIR.mkdir(exist_ok=True)

def get_file_list(ip):
    try:
        with urllib.request.urlopen(f"http://{ip}/file/list", timeout=5) as r:
            return json.loads(r.read())["files"]
    except:
        return []

def download_file(ip, name, dest):
    url = f"http://{ip}/file/download?name={name}"
    with urllib.request.urlopen(url, timeout=30) as r:
        dest.write_bytes(r.read())
    print(f"  ✓ {name} ({dest.stat().st_size//1024} KB)")

for ip in NODES:
    files = get_file_list(ip)
    if not files:
        print(f"[{ip}] Không kết nối được hoặc không có file")
        continue
    print(f"\n[{ip}] {len(files)} file:")
    for f in files:
        name = f["name"]
        dest = OUT_DIR / name
        if dest.exists():
            print(f"  - {name} (đã có, bỏ qua)")
            continue
        download_file(ip, name, dest)

print(f"\nXong! File trong: {OUT_DIR.resolve()}")
```

Chạy:
```bash
python download_all.py
```
