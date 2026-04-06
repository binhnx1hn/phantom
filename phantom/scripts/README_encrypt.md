# PHANTOM R3 — Hệ thống mã hóa âm thanh

## Tổng quan

Script này tự động mã hóa các file ghi âm `.opus` từ Raspberry Pi Zero 2W thành các container TrueCrypt (`.tc`) tương thích 100% với TrueCrypt 7.1a trên PC. Mã hóa sử dụng thuật toán **AES-256-XTS** với PBKDF là **SHA-512**.

```
/tmp/phantom/*.opus
        │
        ▼  encrypt_audio.py
/phantom/encrypted/*.tc   (TrueCrypt container, AES-256-XTS + SHA-512)
        +
/phantom/logs/encrypt_audio.log
```

---

## Cấu trúc file

```
/phantom/
├── scripts/
│   ├── encrypt_audio.py          # Script Python chính
│   ├── encrypt_audio.sh          # Bash wrapper (dùng cho systemd/cron)
│   ├── phantom_encrypt.service   # Systemd service unit
│   └── README_encrypt.md         # Tài liệu này
├── encrypted/                    # Thư mục chứa file .tc đã mã hóa
├── logs/
│   └── encrypt_audio.log         # Log toàn bộ hoạt động
└── .secret                       # File chứa password (chmod 600)

/tmp/phantom/                     # Thư mục tạm chứa file .opus chờ mã hóa
```

---

## 1. Cài đặt dependencies

```bash
# Cập nhật package list
sudo apt update

# Cài tcplay (TrueCrypt-compatible, hỗ trợ AES-256 + SHA-512)
sudo apt install -y tcplay

# Cài dosfstools (mkfs.fat để format FAT32 bên trong container)
sudo apt install -y dosfstools

# Cài coreutils (shred để xóa file an toàn — thường đã có sẵn)
sudo apt install -y coreutils

# Kiểm tra cài đặt
tcplay --version
mkfs.fat --version
shred --version
```

---

## 2. Tạo cấu trúc thư mục trên RPi

```bash
sudo mkdir -p /tmp/phantom
sudo mkdir -p /phantom/encrypted
sudo mkdir -p /phantom/logs
sudo mkdir -p /phantom/scripts
```

---

## 3. Cấu hình password

Password mã hóa được load theo thứ tự ưu tiên:

### Cách A — Environment variable (ưu tiên cao hơn)

```bash
export PHANTOM_PASSWORD="your_strong_password_here"
```

Hoặc thêm vào `/phantom/.env` (dùng cho systemd `EnvironmentFile`):

```bash
# /phantom/.env
PHANTOM_PASSWORD=your_strong_password_here
```

```bash
sudo chmod 600 /phantom/.env
```

### Cách B — File secret (đơn giản hơn cho production)

```bash
echo -n "your_strong_password_here" | sudo tee /phantom/.secret
sudo chmod 600 /phantom/.secret
sudo chown root:root /phantom/.secret
```

> ⚠️ **Lưu ý bảo mật:** Password phải dài ít nhất 20 ký tự, kết hợp chữ hoa/thường/số/ký tự đặc biệt. File `.secret` phải có quyền `chmod 600`.

---

## 4. Cài đặt script

```bash
# Copy scripts lên RPi (ví dụ từ máy tính qua SCP)
scp phantom/scripts/encrypt_audio.py  pi@raspberrypi:/phantom/scripts/
scp phantom/scripts/encrypt_audio.sh  pi@raspberrypi:/phantom/scripts/
scp phantom/scripts/phantom_encrypt.service pi@raspberrypi:/tmp/

# Trên RPi: đặt quyền thực thi
sudo chmod +x /phantom/scripts/encrypt_audio.sh
sudo chmod +x /phantom/scripts/encrypt_audio.py
```

---

## 5. Bật systemd service

```bash
# Copy service file vào thư mục systemd
sudo cp /tmp/phantom_encrypt.service /etc/systemd/system/

# Reload systemd để nhận file mới
sudo systemctl daemon-reload

# Enable service (tự chạy khi boot)
sudo systemctl enable phantom_encrypt.service

# Chạy ngay lập tức (để test)
sudo systemctl start phantom_encrypt.service

# Kiểm tra trạng thái
sudo systemctl status phantom_encrypt.service

# Xem log systemd
sudo journalctl -u phantom-encrypt -f
```

---

## 6. Cấu hình cron (thay thế cho systemd)

Nếu muốn dùng cron thay vì systemd, thêm vào crontab của root:

```bash
sudo crontab -e
```

Thêm dòng sau để chạy mỗi 15 phút:

```cron
*/15 * * * * /phantom/scripts/encrypt_audio.sh >> /phantom/logs/cron.log 2>&1
```

---

## 7. Chạy thủ công

```bash
# Chạy bình thường (đọc password từ env hoặc /phantom/.secret)
sudo python3 /phantom/scripts/encrypt_audio.py

# Chạy dry-run (test không thực sự mã hóa)
sudo python3 /phantom/scripts/encrypt_audio.py --dry-run

# Chỉ định thư mục nguồn và đích tùy chỉnh
sudo python3 /phantom/scripts/encrypt_audio.py \
    --source /custom/audio \
    --output /custom/encrypted

# Chạy qua Bash wrapper
sudo /phantom/scripts/encrypt_audio.sh
sudo /phantom/scripts/encrypt_audio.sh --dry-run
```

---

## 8. Giải thích từng bước trong script

### 8.1 Load password (`load_password`)

1. Kiểm tra biến môi trường `PHANTOM_PASSWORD` trước.
2. Nếu không có, đọc từ file `/phantom/.secret`.
3. Kiểm tra quyền file (cảnh báo nếu không phải `600`).
4. Raise `RuntimeError` nếu không tìm thấy password.

### 8.2 Tính kích thước container (`calculate_container_size_mb`)

```
container_mb = max(5, ceil(file_mb × 1.20) + 1)
```

- **+20%** overhead để chứa FAT32 metadata và dự phòng.
- **+1 MB** cho FAT32 filesystem header.
- **Tối thiểu 5 MB** để container hợp lệ.

### 8.3 Tạo container TrueCrypt (`create_truecrypt_container`)

```bash
# Bước 1: Cấp phát file với dữ liệu ngẫu nhiên (tăng bảo mật)
dd if=/dev/urandom of=output.tc bs=1M count=<size_mb>

# Bước 2: Ghi TrueCrypt header với tcplay
sudo tcplay --create \
    --device=output.tc \
    --cipher=AES-256-XTS \
    --pbkdf-prf=SHA512
# (password được nhập qua stdin — không lộ trong process list)
```

### 8.4 Mã hóa file vào container (`encrypt_file_to_container`)

```bash
# Bước 3: Mount container
sudo tcplay --map=phantom_tc_<name>_<ts> --device=output.tc

# Bước 4: Format FAT32 (tương thích TrueCrypt 7.1a)
sudo mkfs.fat -F 32 /dev/mapper/phantom_tc_<name>_<ts>

# Bước 5: Mount FAT32 volume vào thư mục tạm
sudo mount /dev/mapper/... /tmp/phantom_mnt_xxxxx

# Bước 6: Copy file .opus vào volume
sudo cp recording.opus /tmp/phantom_mnt_xxxxx/

# Bước 7: Sync và unmount
sync
sudo umount /tmp/phantom_mnt_xxxxx

# Bước 8: Unmap container
sudo tcplay --unmap phantom_tc_<name>_<ts>

# Bước 9: Kiểm tra file .tc tồn tại và không rỗng
```

### 8.5 Xóa file gốc an toàn (`secure_delete`)

```bash
shred -n 3 -z -u recording.opus
# -n 3  : ghi đè 3 lần với dữ liệu ngẫu nhiên
# -z    : lần cuối ghi đè bằng zeros (xóa dấu vết)
# -u    : xóa file sau khi shred xong
```

Nếu `shred` không có, fallback về `os.unlink` (xóa thông thường).

### 8.6 Xử lý lỗi

| Tình huống | Hành động |
|-----------|-----------|
| Tạo container thất bại | Xóa file container dở dang, log error, giữ file .opus |
| Mount/format thất bại | Cleanup mapper + mount point, log error, giữ file .opus |
| Copy thất bại | Cleanup toàn bộ, log error, giữ file .opus |
| Shred thất bại sau mã hóa thành công | Log warning, giữ file .opus (không xóa) |
| File .tc đã tồn tại | Bỏ qua (idempotent), log info |

---

## 9. Giải mã trên PC (TrueCrypt 7.1a)

Trên máy tính Windows/Linux/macOS với TrueCrypt 7.1a:

1. Mở TrueCrypt → **Select File** → chọn file `.tc`
2. Chọn một drive letter rảnh → **Mount**
3. Nhập password đã cấu hình → **OK**
4. File `.opus` xuất hiện trong drive letter đã chọn
5. Sau khi xem xong → **Dismount**

> ✅ Container 100% tương thích TrueCrypt 7.1a vì dùng cùng cipher (AES-256-XTS) và PBKDF (SHA-512).

---

## 10. Kiểm tra và troubleshoot

### Kiểm tra tcplay hoạt động

```bash
# Test tạo container nhỏ thủ công
echo "testpassword" | sudo tcplay --create \
    --device=/tmp/test.tc \
    --cipher=AES-256-XTS \
    --pbkdf-prf=SHA512
ls -lh /tmp/test.tc
```

### Xem log

```bash
# Log file từ Python script
tail -f /phantom/logs/encrypt_audio.log

# Log từ systemd
sudo journalctl -u phantom-encrypt --since "1 hour ago"
```

### Kiểm tra container có hợp lệ không

```bash
echo "yourpassword" | sudo tcplay \
    --info \
    --device=/phantom/encrypted/recording_20240101_120000.tc
```

### Debug dry-run

```bash
sudo python3 /phantom/scripts/encrypt_audio.py --dry-run
```

---

## 11. Bảo mật

- File `.secret` và `.env` phải có quyền `chmod 600` và `chown root:root`.
- Không bao giờ commit password vào git repository.
- Nên dùng password khác nhau cho mỗi thiết bị PHANTOM.
- Container dùng `dd if=/dev/urandom` để đảm bảo không thể phân biệt vùng được mã hóa với vùng trống.
- File `.opus` gốc được `shred -n 3` để chống recovery từ flash memory.

---

*PHANTOM R3 Encryption System — Task #6*
