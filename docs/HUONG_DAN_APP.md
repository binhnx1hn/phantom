# Hướng dẫn sử dụng App qua WiFi ESP32

## Tổng quan

Hệ thống gồm 2 ESP32 phát WiFi riêng. Laptop/điện thoại kết nối vào **1 trong 2 node** là có thể dùng app để lấy file — vì 2 node đồng bộ file với nhau.

| Node | SSID | Mật khẩu | IP | Cổng |
|------|------|-----------|----|------|
| Node-1 | `ESP32-Node-1` | `12345678` | `192.168.4.1` | 80 |
| Node-2 | `ESP32-Node-2` | `12345678` | `192.168.5.1` | 80 |

---

## Bước 1 — Kết nối WiFi ESP32

1. Mở cài đặt WiFi trên máy tính / điện thoại
2. Chọn **`ESP32-Node-1`** hoặc **`ESP32-Node-2`**
3. Nhập mật khẩu: **`12345678`**
4. Đợi kết nối thành công (LED ESP32 sáng)

> ⚠️ Sau khi kết nối WiFi ESP32, máy tính **không có internet** — đây là mạng LAN nội bộ.

---

## Bước 2 — Chạy app

```bash
python audio_gui.py
```

App tự động phát hiện đang kết nối Node nào và hiển thị trạng thái:

- 🟢 **"Node-1 kết nối"** — đang dùng `192.168.4.1`
- 🟢 **"Node-2 kết nối"** — đang dùng `192.168.5.1`
- 🔴 **"Chưa kết nối"** — chưa bật WiFi ESP32

---

## Bước 3 — Lấy file từ ESP32 về máy

### Cách 1: Dùng tab "📁 Thư mục folder_test" trong app

1. Chuyển sang tab **"📡 ESP32"**
2. Danh sách file trên SPIFFS hiện ra
3. Click **⬇** bên cạnh file muốn tải
4. File lưu vào `folder_test/` trong thư mục dự án
5. Click **"🗁 Mở thư mục folder_test"** để xem file

### Cách 2: Dùng script sync tự động

```bash
# Sync 1 lần
python dongbo/sync.py

# Sync liên tục mỗi 15 giây
python dongbo/sync.py --watch

# Chỉ sync từ Node-1
python dongbo/sync.py --node a

# Chỉ sync từ Node-2
python dongbo/sync.py --node b
```

File tải về lưu vào: `folder_test/`

### Cách 3: Dùng auto_sync daemon (tự động khi bật WiFi)

```bash
python dongbo/auto_sync.py
```

Script chạy nền, tự động sync khi phát hiện máy kết nối vào WiFi `ESP32-Node-1` hoặc `ESP32-Node-2`.

---

## Bước 4 — Upload file lên ESP32

### Qua app GUI (chuyen.py)

```bash
python dongbo/chuyen.py
```

1. Chờ kết nối node
2. Click **"Gửi file lên ESP32"**
3. Chọn file bất kỳ (WAV, JPG, DOCX, XLSX, PNG...)
4. File upload xong → **LED nháy 3 lần** = thành công

### Qua HTTP trực tiếp

```bash
# Upload file lên Node-1 (đang kết nối WiFi ESP32-Node-1)
curl -X POST http://192.168.4.1/file/upload \
     -H "X-Filename: ten_file.wav" \
     --data-binary @duong/dan/file.wav

# Upload lên Node-2
curl -X POST http://192.168.5.1/file/upload \
     -H "X-Filename: ten_file.wav" \
     --data-binary @duong/dan/file.wav
```

---

## Các API endpoint hữu ích

| Method | URL | Mô tả |
|--------|-----|--------|
| GET | `http://192.168.4.1/status` | Trạng thái Node-1 (heap, SPIFFS, uptime) |
| GET | `http://192.168.5.1/status` | Trạng thái Node-2 |
| GET | `http://<ip>/file/list` | Danh sách file JSON |
| GET | `http://<ip>/file/download?name=<tên>` | Download file |
| POST | `http://<ip>/file/upload` | Upload file (header X-Filename) |
| POST | `http://<ip>/file/delete?name=<tên>` | Xóa file |
| POST | `http://<ip>/sync` | Trigger sync thủ công |

---

## Lưu ý quan trọng

| Tình huống | Giải pháp |
|------------|-----------|
| Không thấy WiFi ESP32 | Nhấn nút **BOOT** trên ESP32 để bật lại |
| App không phát hiện node | Kiểm tra đang kết nối đúng WiFi `ESP32-Node-1/2` |
| File trên 2 node chưa đồng bộ | Đợi ~30–60 giây hoặc gọi `POST /sync` |
| SPIFFS đầy | Xóa bớt file cũ qua app hoặc `DELETE /file/delete` |
| Node-1 không nhận file từ Node-2 | Node-1 RAM giới hạn ~150KB, file lớn sẽ bị skip |

---

## Kiểm tra trạng thái nhanh (trình duyệt)

Mở trình duyệt, truy cập:

```
http://192.168.4.1/status
http://192.168.5.1/status
```

Ví dụ kết quả:
```json
{
  "node": 1,
  "ap_ssid": "ESP32-Node-1",
  "free_heap": 142336,
  "spiffs_total": 1966080,
  "spiffs_used": 524288,
  "spiffs_free": 1441792,
  "file_count": 1,
  "uptime": "00:05:32"
}
```
