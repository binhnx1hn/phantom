# ESP32 LAN Communication - API Reference

## 🖥️ Thông tin thiết bị

| Thiết bị | MAC | IP | Port | Vai trò |
|---------|-----|-----|------|---------|
| ESP32 #1 | f4:65:0b:d7:ce:70 | 192.168.1.11 | 80 | Server |
| ESP32 #2 | a4:f0:0f:84:05:60 | 192.168.1.12 | 81 | Client |

---

## 📡 API - ESP32 #1 (Server) - Port 80

### 1. Lấy data trên Server
```
GET http://192.168.1.11/data
```
```bash
curl http://192.168.1.11/data
```

### 2. Gửi data lên Server (từ máy tính hoặc Client)
```
POST http://192.168.1.11/data
Content-Type: application/json
```
```bash
curl -X POST http://192.168.1.11/data \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Xin chao Server!\"}"
```

### 3. Server push data xuống Client (outbox)
```
POST http://192.168.1.11/outbox
Content-Type: application/json
```
```bash
curl -X POST http://192.168.1.11/outbox \
  -H "Content-Type: application/json" \
  -d "{\"cmd\":\"blink\",\"value\":5}"
```
> Client tự poll /outbox mỗi 3 giây và nhận tự động.

### 4. Xem trạng thái Server
```
GET http://192.168.1.11/status
```
```bash
curl http://192.168.1.11/status
```

---

## 📱 API - ESP32 #2 (Client) - Port 81

### 5. Lấy data trên Client
```
GET http://192.168.1.12:81/data
```
```bash
curl http://192.168.1.12:81/data
```

### 6. Cập nhật data trên Client
```
POST http://192.168.1.12:81/data
Content-Type: application/json
```
```bash
curl -X POST http://192.168.1.12:81/data \
  -H "Content-Type: application/json" \
  -d "{\"sensor\":\"temperature\",\"value\":25.5}"
```

### 7. Client gửi data lên Server ngay lập tức
```
POST http://192.168.1.12:81/send
Content-Type: application/json (tùy chọn)
```
```bash
# Gửi body mới lên Server
curl -X POST http://192.168.1.12:81/send \
  -H "Content-Type: application/json" \
  -d "{\"alert\":\"motion detected!\"}"

# Gửi data hiện tại của Client lên Server (không cần body)
curl -X POST http://192.168.1.12:81/send
```

### 8. Xem trạng thái Client
```
GET http://192.168.1.12:81/status
```
```bash
curl http://192.168.1.12:81/status
```

---

## 🔄 Luồng dữ liệu

```
Máy tính → POST /data → ESP32 #1 Server
Máy tính → POST /outbox → ESP32 #1 → (3 giây) → ESP32 #2 Client tự nhận
ESP32 #2 Client → POST /send → ESP32 #1 Server (ngay lập tức)
Máy tính → POST /data (Client) → ESP32 #2 (cập nhật local)
```

---

## 🧪 Test nhanh tất cả API

```bash
# 1. Gửi data lên Server
curl -X POST http://192.168.1.11/data -H "Content-Type: application/json" -d "{\"msg\":\"hello server\"}"

# 2. Đọc data Server
curl http://192.168.1.11/data

# 3. Server push xuống Client
curl -X POST http://192.168.1.11/outbox -H "Content-Type: application/json" -d "{\"cmd\":\"hello client\"}"

# 4. Client gửi lên Server
curl -X POST http://192.168.1.12:81/send -H "Content-Type: application/json" -d "{\"msg\":\"hello from client\"}"

# 5. Xem status cả 2
curl http://192.168.1.11/status
curl http://192.168.1.12:81/status
```
