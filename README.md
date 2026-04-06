# ESP32 Audio Transfer - Chuyền WAV 2 chiều giữa 2 ESP32

## Kiến trúc

```
[ESP32 Server]  ──── phát WiFi AP ────  [ESP32 Client]
  192.168.4.1   ←── push audio ──────  192.168.4.2
  192.168.4.1   ────serve audio ──────→ 192.168.4.2
```

| Board | Vai trò | IP | WiFi |
|---|---|---|---|
| ESP32 #1 Server | Phát WiFi AP (ẩn), nhận và serve audio | `192.168.4.1` | AP "ESP32-Audio-AP" |
| ESP32 #2 Client | Kết nối vào AP, tự push + fetch audio | `192.168.4.2` | STA (kết nối vào Server) |

---

## Tự động khi boot

Khi ESP32 Client khởi động:
1. Kết nối WiFi **"ESP32-Audio-AP"** (password: `12345678`)
2. **Push**: Gửi `test.wav` nhúng sẵn lên Server
3. **Fetch**: Kéo audio từ Server về RAM

Không cần làm gì thêm - 2 ESP32 tự chuyền audio cho nhau.

---

## API - ESP32 SERVER (`192.168.4.1`)

> PC phải kết nối WiFi **"ESP32-Audio-AP"** mới gọi được

### `GET /status` (port 80)
Xem trạng thái Server.
```bash
curl http://192.168.4.1/status
```
```json
{
  "mode": "AP",
  "ssid": "ESP32-Audio-AP",
  "ip": "192.168.4.1",
  "stations": 1,
  "free_heap": 210000,
  "ram_audio_ready": true,
  "ram_audio_bytes": 16044,
  "builtin_wav_bytes": 16044
}
```

### `GET /audio/info` (port 80)
Xem thông tin audio đang có trên Server.
```bash
curl http://192.168.4.1/audio/info
```
```json
{
  "ready": true,
  "source": "ram",
  "size": 16044,
  "kb": "15.7",
  "upload": "http://192.168.4.1:8080/upload",
  "download": "http://192.168.4.1:8080/audio.wav"
}
```
- `source: "ram"` → audio do Client upload lên
- `source: "builtin"` → audio nhúng sẵn trong firmware

### `POST /upload` (port **8080**)
Upload file WAV lên Server (Client hoặc PC gửi lên).
```bash
# Upload từ PC
curl -X POST http://192.168.4.1:8080/upload \
     --data-binary @test.wav \
     -H "Content-Type: audio/wav"
```
```json
{"status": "ok", "received": 16044, "expected": 16044}
```
- Ghi đè audio trong RAM của Server
- LED nhấp nháy 5 lần khi nhận xong

### `GET /audio.wav` (port **8080**)
Download audio từ Server về.
```bash
curl http://192.168.4.1:8080/audio.wav -o from_server.wav
start from_server.wav   # Mở nghe
```
- Ưu tiên trả về audio trong RAM (Client đã upload)
- Nếu RAM trống → trả về `test.wav` nhúng sẵn trong firmware

---

## API - ESP32 CLIENT (`192.168.4.2`)

### `GET /status` (port **81**)
Xem trạng thái Client.
```bash
curl http://192.168.4.2:81/status
```
```json
{
  "mode": "STA",
  "ap_ssid": "ESP32-Audio-AP",
  "ip": "192.168.4.2",
  "server": "192.168.4.1",
  "free_heap": 185000,
  "ram_audio_ready": true,
  "ram_audio_bytes": 16044,
  "builtin_wav_bytes": 16044
}
```

### `GET /audio/info` (port 81)
Xem thông tin audio đang có trên Client.
```bash
curl http://192.168.4.2:81/audio/info
```

### `POST /audio/push_builtin` (port **81**) ⭐ QUAN TRỌNG NHẤT
**Client gửi `test.wav` nhúng sẵn lên Server.**
```bash
curl -X POST http://192.168.4.2:81/audio/push_builtin
```
```json
{"status": "sent", "bytes": 16044}
```
- Client lấy `test.wav` nhúng trong firmware → POST lên `192.168.4.1:8080/upload`
- LED nhấp nháy 5 lần khi gửi xong

### `POST /audio/push` (port 81)
Client gửi audio đang có trong RAM lên Server (nếu RAM trống thì dùng built-in).
```bash
curl -X POST http://192.168.4.2:81/audio/push
```

### `POST /audio/fetch` (port **81**) ⭐ QUAN TRỌNG NHẤT
**Client kéo audio từ Server về RAM.**
```bash
curl -X POST http://192.168.4.2:81/audio/fetch
```
```json
{"status": "ok", "bytes": 16044}
```
- Client GET `192.168.4.1:8080/audio.wav` → lưu vào RAM
- LED nhấp nháy 3 lần khi nhận xong

### `POST /upload` (port **8081**)
Upload file WAV vào RAM của Client (từ PC).
```bash
curl -X POST http://192.168.4.2:8081/upload \
     --data-binary @new_audio.wav \
     -H "Content-Type: audio/wav"
```
- Dùng khi muốn thay audio mà không cần flash lại firmware

### `GET /audio.wav` (port **8081**)
Download audio từ Client về PC.
```bash
curl http://192.168.4.2:8081/audio.wav -o from_client.wav
start from_client.wav
```

---

## Kịch bản Demo: Truyền File ESP32 → ESP32

### 🔌 Chuẩn bị phần cứng

```
[PC Windows]                [ESP32 #1 - SERVER]      [ESP32 #2 - CLIENT]
  WiFi card            ←──── AP: ESP32-Audio-AP ────→  kết nối vào AP
  kết nối AP                  IP: 192.168.4.1            IP: 192.168.4.2
  192.168.4.x                 Port 80  (HTTP API)        Port 81  (HTTP API)
                              Port 8080 (TCP Audio)      Port 8081 (TCP Audio)
```

> **Lưu ý**: Cả PC, Server, Client đều dùng chung WiFi `ESP32-Audio-AP`.
> File audio được truyền qua **WiFi TCP** và lưu trong **RAM heap** của ESP32 (không cần SD card).

---

### BƯỚC 1 — Flash firmware lên 2 ESP32

```bash
# Cắm ESP32 Server vào PC trước, ghi nhớ COM port (vd: COM3)
# Cắm ESP32 Client, ghi nhớ COM port (vd: COM4)

# Flash tự động cả 2:
python deploy.py

# HOẶC flash thủ công từng cái:
cd esp32_server  && pio run --target upload --upload-port COM3
cd esp32_client  && pio run --target upload --upload-port COM4
```

Sau khi flash xong:
- LED ESP32 Server **sáng liên tục** → AP đã phát
- LED ESP32 Client **nhấp nháy** rồi **sáng** → đã kết nối Server

---

### BƯỚC 2 — Mở Serial Monitor xem log

**Terminal 1 — Server log:**
```bash
cd esp32_server && pio device monitor --port COM3 --baud 115200
```
Bạn sẽ thấy:
```
[AP] SSID    : ESP32-Audio-AP (hidden)
[AP] IP      : 192.168.4.1
[AP] Heap    : 298000 bytes
[Ready] Server Endpoints:
  GET  http://192.168.4.1/ram/list   <- XEM FILE TRONG RAM
  GET  http://192.168.4.1/ram/info   <- CHI TIET WAV HEADER
```

**Terminal 2 — Client log:**
```bash
cd esp32_client && pio device monitor --port COM4 --baud 115200
```
Bạn sẽ thấy quá trình **tự động** khi Client boot:
```
[WiFi] Connecting to AP: ESP32-Audio-AP
[WiFi] Connected! Client IP: 192.168.4.2

[Auto] BUOC 1: Dang ky voi Server...
[Register] OK : {"status":"ok","registered":"192.168.4.2:8081"}

[Auto] BUOC 2: Push test.wav len Server...
[Push_builtin] OK - 16044/16044 bytes        ← ✅ FILE ĐÃ GỬI LÊN SERVER

[Auto] BUOC 3: Fetch audio tu Server...
[Fetch] OK - 16044/16044 bytes (15.7 KB)     ← ✅ SERVER TRẢ LẠI FILE

===== KET QUA =====
  Register   : OK
  Push ->Svr : OK (16044 bytes)
  Fetch<-Svr : OK (16044 bytes)
  WAV Info   : 8000Hz 1ch 16bit 1.00s
====================
```

---

### BƯỚC 3 — Kết nối PC vào WiFi `ESP32-Audio-AP`

```
WiFi SSID    : ESP32-Audio-AP   (mạng ẩn, nhập tay)
Password     : 12345678
PC sẽ nhận IP: 192.168.4.x (thường 192.168.4.100+)
```

---

### BƯỚC 4 — Mở RAM Viewer từ PC (xem file đã nhận)

```bash
python ram_viewer.py --client 192.168.4.2
```

Chọn **menu 2** → xem danh sách file trong RAM Server:
```
═══ SERVER RAM FILE LIST ═══
  Tổng file đã nhận : 1
  RAM đang dùng     : 15.7 KB
  
  [0] ★ ACTIVE   192.168.4.2      client_push    16,044 B (15.6 KB)  00:00:08  WAV ✓
       └─ WAV: 8000Hz, 1ch, 16bit, 1.00s
```

> **Đây là bằng chứng**: file `test.wav` từ ESP32 Client (`192.168.4.2`) đã được truyền
> và đang nằm trong **RAM heap** của ESP32 Server!

Chọn **menu 3** → xem chi tiết WAV header:
```
═══ SERVER RAM BUFFER INFO ═══
  ✅ FILE TRONG RAM
  Kích thước  : 16,044 bytes (15.6 KB)
  Magic bytes : RIFF
  Nhận từ     : 192.168.4.2        ← IP của ESP32 Client
  Nguồn       : client_push
  
  WAV HEADER
  Format      : PCM (code 1)
  Channels    : 1 (Mono)
  Sample Rate : 8000 Hz
  Bits/Sample : 16 bit
  Duration    : 1.00s
```

---

### BƯỚC 5 — Các thao tác demo thêm

**A. Client → Server (thủ công, lặp lại bất kỳ lúc nào):**
```bash
curl -X POST http://192.168.4.2:81/audio/push_builtin
# Rồi xem RAM Server:
curl http://192.168.4.1/ram/list
```

**B. Server → tất cả Client (Broadcast):**
```bash
curl -X POST http://192.168.4.1/broadcast
# Server sẽ push audio tới TẤT CẢ Client đã đăng ký
# Client nhận xong → xem RAM Client:
curl http://192.168.4.2:81/ram/info
```

**C. Download file từ Server về PC để nghe:**
```bash
curl http://192.168.4.1:8080/audio.wav -o from_server.wav
start from_server.wav
```

**D. Upload file WAV mới từ PC lên Server:**
```bash
curl -X POST http://192.168.4.1:8080/upload ^
     --data-binary @my_audio.wav ^
     -H "Content-Type: audio/wav"
# Xác nhận:
curl http://192.168.4.1/ram/info
```

**E. Xem hex dump (16 bytes đầu = WAV magic + header):**
```bash
curl "http://192.168.4.1/ram/hex?offset=0&len=44"
```
Output:
```json
{
  "hex": "52 49 46 46 24 3E 00 00 57 41 56 45 66 6D 74 20...",
  "ascii": "RIFF$>..WAVEfmt ..."
}
```

**F. Demo đầy đủ bằng Python script:**
```bash
python ram_viewer.py --client 192.168.4.2 --demo
python -X utf8 test_transfer.py --client 192.168.4.2 --file test.wav
```

---

### BƯỚC 6 — Xem RAM Client (file Client đã nhận)

```bash
curl http://192.168.4.2:81/ram/info
```
```json
{
  "ram_ready": true,
  "size_bytes": 16044,
  "is_wav": true,
  "received_from": "192.168.4.1",
  "source": "fetch",
  "wav_header": {
    "channels": 1,
    "sample_rate": 8000,
    "bits_per_sample": 16,
    "duration_sec": 1.00
  }
}
```

---

### Tóm tắt luồng truyền file

```
ESP32 Client RAM/Flash          WiFi TCP              ESP32 Server RAM
────────────────────────────────────────────────────────────────────
test_wav.h (Flash, 16KB)
        │
        │  POST :8080/upload (TCP)
        └──────────────────────────────────────────► audioBuffer[]
                                                      malloc(16044)
                                                      recordRamFile()
                                                      /ram/list ✓
                                                      /ram/info ✓
        ◄──────────────────────────────────────────── GET :8080/audio.wav
audioBuffer[] (RAM)
/ram/info ✓
```

### A. Chuyền audio từ Client → Server (thủ công)
```bash
curl -X POST http://192.168.4.2:81/audio/push_builtin
curl http://192.168.4.1:8080/audio.wav -o result.wav && start result.wav
```

### B. Chuyền audio từ Server → Client (thủ công)
```bash
curl -X POST http://192.168.4.2:81/audio/fetch
curl http://192.168.4.2:8081/audio.wav -o result.wav && start result.wav
```

### C. Thay audio mới từ PC (không cần flash lại)
```bash
# 1. Upload audio mới vào Client
curl -X POST http://192.168.4.2:8081/upload --data-binary @new_audio.wav -H "Content-Type: audio/wav"
# 2. Push lên Server
curl -X POST http://192.168.4.2:81/audio/push
# 3. Download về nghe
curl http://192.168.4.1:8080/audio.wav -o result.wav && start result.wav
```

### D. Test đầy đủ bằng script
```bash
python -X utf8 test_transfer.py --client 192.168.4.2 --file test.wav
```

---

## File trong project

| File | Chức năng |
|---|---|
| `test.wav` | File audio gốc (440Hz, 2s, 8kHz mono) |
| `test_audio_gen.py` | Tạo lại `test.wav` nếu mất |
| `gen_wav_header.py` | Convert `test.wav` → `test_wav.h` |
| `h_to_wav.py` | Convert `test_wav.h` → `.wav` để nghe |
| `deploy.py` | All-in-one: gen header + flash cả 2 board |
| `test_transfer.py` | Test script từ PC qua WiFi AP |
| `esp32_server/src/main.cpp` | Firmware Server (AP mode) |
| `esp32_client/src/main.cpp` | Firmware Client (STA mode, auto push+fetch) |

## Quy trình thay audio mới

```bash
# 1. Đặt file WAV mới (8kHz/16kHz, mono, tối đa ~180KB)
# 2. Deploy (gen header + flash tự động)
python deploy.py new_audio.wav

# HOẶC không cần flash, upload qua WiFi:
curl -X POST http://192.168.4.2:8081/upload --data-binary @new_audio.wav -H "Content-Type: audio/wav"
curl -X POST http://192.168.4.2:81/audio/push
```

## Convert .h → .wav để nghe

```bash
python h_to_wav.py
# hoặc
python h_to_wav.py --input esp32_server/src/test_wav.h --output check.wav
start check.wav
```
