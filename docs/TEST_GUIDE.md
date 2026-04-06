# 📋 Hướng dẫn Test ESP32 Audio Demo v2.0
**Ngày:** 2026-04-06 | **Firmware:** v2.0 | **Hardware:** 2× NodeMCU-32S

---

## Chuẩn bị trước khi test

| Vật dụng | Ghi chú |
|---|---|
| Node-1 (ESP32 Server) | MAC: `a4:f0:0f:84:05:60` — firmware đã nạp |
| Node-2 (ESP32 Client) | MAC: `f4:65:0b:d7:ce:70` — firmware đã nạp |
| Laptop (cùng máy) | Python + PlatformIO đã cài |
| File WAV test | `demo_client_to_server.wav` trong project root |
| Dây USB data | Dùng để monitor Serial nếu cần |
| Pin dự phòng | Cho Bước 2 chuyển nguồn |

---

## ⚠️ Cài WiFi Profile trước (1 lần duy nhất)

Mở **Command Prompt as Administrator**, chạy:
```cmd
netsh wlan add profile filename="d:\ESP32\esp32_node1_profile.xml"
netsh wlan add profile filename="d:\ESP32\esp32_node2_profile.xml"
```

Kiểm tra:
```cmd
netsh wlan show profiles
```
→ Phải thấy `ESP32-Node-1` và `ESP32-Node-2` trong danh sách.

---

## 🔵 BƯỚC 1 — Upload file vào Node-1

### Mục tiêu
- Node-1 phát WiFi ẩn, laptop kết nối được
- GUI hiện trạng thái upload thành công + filelist

### Thực hiện

**1.1 Cấp nguồn Node-1 (cắm USB)**
- Cắm Node-1 vào USB
- ✅ **Kỳ vọng:** LED nháy **1 lần dài** (chưa có file SPIFFS) HOẶC **3 lần** (nếu đã có file cũ)
- LED sáng liên tục = Node-1 sẵn sàng

**1.2 Kết nối WiFi ẩn Node-1**
```cmd
netsh wlan connect name="ESP32-Node-1"
```
- ✅ **Kỳ vọng:** `Connection request was completed successfully`
- Kiểm tra IP: `ipconfig` → thấy `192.168.4.x`

**1.3 Xác nhận Node-1 hoạt động**
Mở trình duyệt: http://192.168.4.1/status
- ✅ **Kỳ vọng:** JSON trả về `{"node":1,"ap_ssid":"ESP32-Node-1",...}`

Kiểm tra filelist: http://192.168.4.1/file/list
- ✅ **Kỳ vọng:** `{"files":[],"count":0,...}` (chưa có file)

**1.4 Mở GUI**
```cmd
cd d:\ESP32
python audio_gui.py
```
- ✅ **Kỳ vọng:** GUI mở, status strip hiện `🟢 Node-1 (Thiết bị 1) đã kết nối — sẵn sàng upload`
- Filelist panel hiện `📂 Chưa có file trong SPIFFS`

**1.5 Upload file WAV**
- Trong GUI → chọn file `demo_client_to_server.wav`
- Nhấn nút **Upload to Server** (hoặc tương đương)
- ✅ **Kỳ vọng:**
  - Banner xanh: `✅ Upload thành công! XXX KB đã lưu vào SPIFFS`
  - Banner tự ẩn sau 5 giây
  - Filelist cập nhật: hiện `audio.wav | XX.X KB | X.XXs`
  - Node-1 LED nháy **5 lần** nhanh

**1.6 Xác nhận SPIFFS đã lưu**
Trình duyệt: http://192.168.4.1/file/info
- ✅ **Kỳ vọng:** `{"has_file":true,"size":XXXXX,...}`

**1.7 Đóng GUI** (Bước 1 hoàn tất)

---

## 🟡 BƯỚC 2 — Chuyển nguồn Node-1

### Mục tiêu
- File WAV tồn tại trong SPIFFS sau khi tắt/bật nguồn
- Node-1 đọc file và báo hiệu bằng LED

### Thực hiện

**2.1 Ngắt kết nối WiFi**
```cmd
netsh wlan disconnect
```

**2.2 Rút USB Node-1**
- Rút dây USB khỏi Node-1
- Đợi 3 giây

**2.3 Cắm pin dự phòng vào Node-1**
- ✅ **Kỳ vọng:** Node-1 boot lại → LED nháy **3 lần** (có file trong SPIFFS)
- Nếu LED nháy 1 lần dài → file bị mất, quay lại Bước 1

**2.4 Xác nhận (tùy chọn — nếu muốn kiểm tra)**
- Kết nối lại WiFi Node-1: `netsh wlan connect name="ESP32-Node-1"`
- Trình duyệt: http://192.168.4.1/file/info → `"has_file":true`
- Ngắt WiFi lại: `netsh wlan disconnect`

---

## 🟢 BƯỚC 3 — Tự động truyền file Node-1 → Node-2

### Mục tiêu
- Node-2 boot, tự kết nối WiFi ẩn Node-1, lấy file
- Node-2 LED nháy 5 lần xác nhận
- Node-1 tự shutdown (deep sleep)

### Thực hiện

**3.1 Cấp nguồn Node-2**
- Cắm dây USB vào Node-2 (hoặc dùng nguồn khác)
- ✅ **Kỳ vọng trong ~15-30 giây:**
  - Node-2 LED nháy 1-2 lần (đang thử kết nối Node-1)
  - Node-2 LED nháy liên tục nhẹ (đang kết nối WiFi Node-1)
  - **Node-2 LED nháy 5 lần nhanh** = sync thành công ✅
  - Node-1 LED nháy 2 lần rồi tắt = deep sleep ✅

**3.2 Nếu Node-2 LED nháy 3 lần chậm** → sync thất bại
- Nguyên nhân: Node-1 chưa boot xong / không tìm thấy
- Thử lại: nhấn Reset Node-2

**3.3 Xác nhận Node-2 có file (tùy chọn)**
- Kết nối WiFi Node-2: `netsh wlan connect name="ESP32-Node-2"`
- Trình duyệt: http://192.168.5.1/status → `"sync_done":true,"spiffs_has_file":true`
- Trình duyệt: http://192.168.5.1/file/info → `"has_file":true`
- Ngắt WiFi: `netsh wlan disconnect`

---

## 🔴 BƯỚC 4 — Laptop tải file từ Node-2

### Mục tiêu
- Laptop kết nối WiFi ẩn Node-2
- GUI tự động tải file về `~/Downloads/audio_esp32.wav`
- Mở GUI → file đã có sẵn

### Thực hiện

**4.1 Kết nối WiFi ẩn Node-2**
```cmd
netsh wlan connect name="ESP32-Node-2"
```
- ✅ **Kỳ vọng:** `Connection request was completed successfully`
- Kiểm tra: `ipconfig` → thấy `192.168.5.x`

**4.2 Mở GUI**
```cmd
cd d:\ESP32
python audio_gui.py
```
- ✅ **Kỳ vọng trong ~5-15 giây:**
  - Status hiện `🟢 Node-2 (Thiết bị 2) đã kết nối — đang tải file tự động...`
  - Background thread bắt đầu download
  - Banner xanh: `✅ File đã sẵn sàng trong Downloads! (XXX KB)`

**4.3 Kiểm tra file**
```cmd
dir "%USERPROFILE%\Downloads\audio_esp32.wav"
```
- ✅ **Kỳ vọng:** File tồn tại, kích thước > 1000 bytes

**4.4 Phát file kiểm tra nội dung**
- Double-click `audio_esp32.wav` trong Downloads
- ✅ **Kỳ vọng:** File phát được, nội dung giống file gốc đã upload ở Bước 1

---

## 🛠️ Xử lý sự cố

| Triệu chứng | Nguyên nhân | Giải pháp |
|---|---|---|
| Node-1 LED không sáng | Nguồn không đủ | Thử cổng USB khác |
| `netsh wlan connect` báo lỗi | Chưa cài profile | Chạy lại lệnh `netsh wlan add profile` |
| GUI không detect Node | Chưa kết nối WiFi đúng | Kiểm tra `ipconfig`, phải thấy 192.168.4.x hoặc 5.x |
| Upload thất bại | Node-1 chưa sẵn sàng | Đợi 10s sau khi LED sáng, thử lại |
| Node-2 không sync | Node-1 chưa boot | Reset Node-2 sau khi Node-1 LED sáng |
| File không download | Node-2 chưa có file | Kiểm tra Bước 3 có LED 5 lần không |
| Banner không hiện | GUI không detect đúng node | Kiểm tra status strip, thử `GET /status` thủ công |

---

## 📊 Checklist Tổng kết

```
[ ] Bước 1.1 — Node-1 cấp nguồn → LED sáng
[ ] Bước 1.2 — Kết nối WiFi ẩn ESP32-Node-1 thành công
[ ] Bước 1.3 — /status trả về node:1
[ ] Bước 1.4 — GUI detect Node-1 tự động
[ ] Bước 1.5 — Upload WAV → banner ✅ → filelist cập nhật
[ ] Bước 1.6 — /file/info xác nhận has_file:true
[ ] Bước 2.1 — Rút USB → cắm pin → LED nháy 3 lần
[ ] Bước 2.2 — /file/info sau reboot vẫn has_file:true
[ ] Bước 3.1 — Node-2 boot → LED 5 lần (sync OK)
[ ] Bước 3.2 — Node-1 LED tắt (deep sleep)
[ ] Bước 3.3 — /status Node-2: sync_done:true
[ ] Bước 4.1 — Kết nối WiFi ẩn ESP32-Node-2 thành công
[ ] Bước 4.2 — GUI detect Node-2 → auto-download bắt đầu
[ ] Bước 4.3 — Banner ✅ File đã sẵn sàng
[ ] Bước 4.4 — ~/Downloads/audio_esp32.wav tồn tại và phát được
```

---

## 🔄 Reset để test lại

Để test lại từ đầu:
1. Xóa file SPIFFS Node-1: http://192.168.4.1/file/clear (POST) hoặc nút Clear trong GUI
2. Reset Node-2 (nút RESET trên board)
3. Xóa file local: `del "%USERPROFILE%\Downloads\audio_esp32.wav"`
4. Bắt đầu lại từ Bước 1
