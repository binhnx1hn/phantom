# PHANTOM R3 — Hướng dẫn Hidden Volume (Plausible Deniability)

> **Ngôn ngữ tài liệu:** Tiếng Việt  
> **Mục tiêu:** Giải thích cơ chế ẩn, quy trình vận hành, và lệnh sử dụng cho hệ thống Hidden Volume của PHANTOM R3.

---

## Mục lục

1. [Cơ chế hoạt động](#1-cơ-chế-hoạt-động)
2. [Sơ đồ cấu trúc container](#2-sơ-đồ-cấu-trúc-container)
3. [Phân bổ dung lượng](#3-phân-bổ-dung-lượng)
4. [Hướng dẫn sử dụng 2 password](#4-hướng-dẫn-sử-dụng-2-password)
5. [Quy trình tạo container step-by-step](#5-quy-trình-tạo-container-step-by-step)
6. [Lệnh mount từng loại volume](#6-lệnh-mount-từng-loại-volume)
7. [Lưu ý quan trọng](#7-lưu-ý-quan-trọng)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Cơ chế hoạt động

### Hidden Volume là gì?

**Hidden Volume** (ẩn volume) là kỹ thuật mã hoá hai lớp trong một file container duy nhất (`.tc`), cho phép **phủ nhận hợp lý (Plausible Deniability)**:

- Cùng một file `.tc` nhưng chứa **hai vùng dữ liệu độc lập**, mỗi vùng có password riêng.
- Từ bên ngoài, không thể phân biệt đâu là outer volume, đâu là hidden volume — chúng đều trông giống như dữ liệu ngẫu nhiên.
- Ngay cả khi bị ép khai password, người dùng chỉ cần đưa password A (outer) — đối phương sẽ chỉ thấy **file giả vô hại**, không có bằng chứng về sự tồn tại của hidden volume.

### Tại sao "deniable"?

TrueCrypt / tcplay thiết kế container theo nguyên tắc:
- Toàn bộ không gian chưa dùng của outer volume **trông giống hệt dữ liệu ngẫu nhiên**.
- Header của hidden volume được đặt ở vùng **đuôi container** và cũng được mã hoá.
- Không có metadata, không có flag, không có chỉ dấu nào cho biết hidden volume có tồn tại hay không.

> ⚠️ Plausible Deniability chỉ hoạt động nếu: decoy files trông **thuyết phục**, và outer password được giữ sẵn để sử dụng khi bị ép buộc.

---

## 2. Sơ đồ cấu trúc container

```
┌─────────────────────────────────────────────────────────────────────┐
│                    container.tc  (ví dụ: 50 MB)                     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │          OUTER VOLUME HEADER  (~512 bytes, vùng đầu)          │  │
│  │  • Mã hoá bằng: outer_password + AES-256-XTS + SHA-512 PBKDF  │  │
│  │  • Chứa: khoá mã hoá của outer volume, checksum, metadata     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │          OUTER VOLUME DATA  (FAT32, ~20 MB)                   │  │
│  │  • Decoy files: diary.txt, todo.txt, shopping.txt, …          │  │
│  │  • Khi mount bằng outer_password → thấy các file này          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║        "FREE SPACE" của outer volume                         ║  │
│  ║   (Thực ra là toàn bộ vùng chứa Hidden Volume)               ║  │
│  ║                                                               ║  │
│  ║  ┌─────────────────────────────────────────────────────────┐  ║  │
│  ║  │      HIDDEN VOLUME HEADER  (~512 bytes, gần đuôi)        │  ║  │
│  ║  │  • Mã hoá bằng: hidden_password + AES-256-XTS + SHA-512  │  ║  │
│  ║  │  • Không thể phát hiện nếu không biết hidden_password    │  ║  │
│  ║  └─────────────────────────────────────────────────────────┘  ║  │
│  ║                                                               ║  │
│  ║  ┌─────────────────────────────────────────────────────────┐  ║  │
│  ║  │      HIDDEN VOLUME DATA  (FAT32, ~30 MB)                 │  ║  │
│  ║  │  • Real audio files: rec_001.opus, rec_002.opus, …       │  ║  │
│  ║  │  • Khi mount bằng hidden_password → thấy audio files     │  ║  │
│  ║  └─────────────────────────────────────────────────────────┘  ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Chú thích:
  ══ = vùng hidden volume (trông như "free space" khi mount outer)
  ── = vùng outer volume (thực sự hiển thị khi dùng outer password)
```

---

## 3. Phân bổ dung lượng

Script tự động phân bổ theo tỉ lệ 40/60:

| Vùng | Tỉ lệ | Ví dụ (50 MB) | Nội dung |
|------|-------|--------------|----------|
| Outer Volume | 40% | ~20 MB | Decoy files (text, notes) |
| Hidden Volume | 60% | ~30 MB | File audio `.opus` thật |

> **Lý do**: Hidden volume thường chứa file âm thanh lớn hơn; 60% đảm bảo đủ chỗ cho nhiều file `.opus`.  
> File audio Opus ~1 giờ ghi âm ≈ 30–60 MB ở bitrate trung bình.

---

## 4. Hướng dẫn sử dụng 2 password

### 4.1 Password A — Outer Password (dùng khi bị ép khai)

```
Tình huống: Bị yêu cầu cung cấp password để kiểm tra thiết bị.
Hành động:  Cung cấp OUTER PASSWORD (password A).
Kết quả:    Đối phương chỉ thấy decoy files vô hại (diary, todo, shopping list...).
            Không có bằng chứng nào về sự tồn tại của hidden volume.
```

**Ví dụ lệnh mount outer volume** (để cho đối phương thấy):
```bash
sudo tcplay --map=phantom_outer --device=recording.tc
# Nhập outer password khi được hỏi
sudo mount /dev/mapper/phantom_outer /mnt/phantom
ls /mnt/phantom
# → diary.txt  todo.txt  shopping.txt  meeting_notes.txt  book_notes.txt  budget.txt
```

### 4.2 Password B — Hidden Password (dùng khi muốn truy cập thật)

```
Tình huống: Truy xuất file audio ghi âm thực sự.
Hành động:  Dùng HIDDEN PASSWORD (password B) với flag --use-hidden.
Kết quả:    Thấy và có thể truy cập các file .opus thật.
```

**Ví dụ lệnh mount hidden volume**:
```bash
sudo tcplay --map=phantom_hidden --device=recording.tc --use-hidden
# Nhập hidden password khi được hỏi
sudo mount /dev/mapper/phantom_hidden /mnt/phantom_real
ls /mnt/phantom_real
# → rec_20240315_143022.opus  rec_20240316_091500.opus  ...
```

---

## 5. Quy trình tạo container step-by-step

### Bước 0: Chuẩn bị file giả (decoy)

```bash
# Tạo decoy files vào /tmp/phantom/decoy/
python3 create_decoy_files.py --output-dir /tmp/phantom/decoy

# Kiểm tra
ls /tmp/phantom/decoy/
# → diary.txt  todo.txt  shopping.txt  meeting_notes.txt  book_notes.txt  budget.txt
```

### Bước 1: Đặt password qua biến môi trường (bảo mật hơn CLI)

```bash
export PHANTOM_OUTER_PASSWORD="mat_khau_gia_vo_hai"
export PHANTOM_HIDDEN_PASSWORD="mat_khau_am_thanh_that"
```

> ⚠️ Không bao giờ dùng cùng một password cho cả 2 volume!

### Bước 2: Chạy script tạo container đầy đủ

```bash
sudo python3 create_hidden_container.py \
    --output /phantom/encrypted/recording.tc \
    --size 50 \
    --audio-files /tmp/phantom/*.opus \
    --decoy-dir /tmp/phantom/decoy
```

Hoặc với password trực tiếp (kém bảo mật hơn):

```bash
sudo python3 create_hidden_container.py \
    --output recording.tc \
    --size 50 \
    --outer-password "mat_khau_gia" \
    --hidden-password "mat_khau_that" \
    --audio-files /tmp/phantom/rec1.opus /tmp/phantom/rec2.opus \
    --decoy-dir /tmp/phantom/decoy
```

### Bước 3: Dry-run (kiểm tra trước khi thực thi)

```bash
sudo python3 create_hidden_container.py \
    --output recording.tc \
    --size 50 \
    --outer-password "mat_khau_gia" \
    --hidden-password "mat_khau_that" \
    --audio-files /tmp/phantom/*.opus \
    --dry-run
```

### Bước 4: Xác nhận container (verify)

Script tự động verify sau khi tạo xong. Nếu muốn verify thủ công:

```bash
# Mount outer — phải thấy decoy files
sudo tcplay --map=test_outer --device=recording.tc
sudo mount /dev/mapper/test_outer /mnt/test
ls /mnt/test/
sudo umount /mnt/test
sudo tcplay --unmap test_outer

# Mount hidden — phải thấy audio files
sudo tcplay --map=test_hidden --device=recording.tc --use-hidden
sudo mount /dev/mapper/test_hidden /mnt/test
ls /mnt/test/
sudo umount /mnt/test
sudo tcplay --unmap test_hidden
```

---

## 6. Lệnh mount từng loại volume

### Mount Outer Volume (decoy)

```bash
# Tạo mapper
sudo tcplay --map=phantom_outer --device=/path/to/container.tc
# Nhập outer password

# Mount
sudo mkdir -p /mnt/phantom_outer
sudo mount /dev/mapper/phantom_outer /mnt/phantom_outer

# Xong, xem files
ls /mnt/phantom_outer/

# Unmount và đóng
sudo umount /mnt/phantom_outer
sudo tcplay --unmap phantom_outer
```

### Mount Hidden Volume (real)

```bash
# Tạo mapper với flag --use-hidden
sudo tcplay --map=phantom_hidden --device=/path/to/container.tc --use-hidden
# Nhập hidden password

# Mount
sudo mkdir -p /mnt/phantom_hidden
sudo mount /dev/mapper/phantom_hidden /mnt/phantom_hidden

# Xong, xem files
ls /mnt/phantom_hidden/

# Unmount và đóng
sudo umount /mnt/phantom_hidden
sudo tcplay --unmap phantom_hidden
```

### Script mount nhanh (sử dụng thực tế)

```bash
# Đặt biến
CONTAINER="/phantom/encrypted/recording.tc"
OUTER_PASS="mat_khau_gia"
HIDDEN_PASS="mat_khau_that"
MOUNT_POINT="/mnt/phantom"

# Mount outer
echo "$OUTER_PASS" | sudo tcplay --map=phantom_outer --device="$CONTAINER"
sudo mount /dev/mapper/phantom_outer "$MOUNT_POINT"

# Mount hidden
echo "$HIDDEN_PASS" | sudo tcplay --map=phantom_hidden --device="$CONTAINER" --use-hidden
sudo mount /dev/mapper/phantom_hidden "$MOUNT_POINT"
```

---

## 7. Lưu ý quan trọng

### ⛔ TUYỆT ĐỐI KHÔNG làm sau khi hidden volume đã có dữ liệu:

```
❌ Không bao giờ MOUNT OUTER VOLUME với quyền GHI (write)
   sau khi hidden volume đã được populate với file thật!

   Lý do: FAT32 filesystem của outer volume có thể ghi dữ liệu
   mới vào vùng "free space" — chính là vùng chứa hidden volume data.
   Điều này sẽ CORRUPT file audio trong hidden volume một cách im lặng
   và không thể phục hồi.
```

### Thứ tự bắt buộc khi tạo container:

```
1. create_outer_volume      ← tạo file + outer header
2. create_hidden_volume     ← tạo hidden header bên trong
3. populate_outer_volume    ← copy decoy files (PHẢI TRƯỚC bước 4)
4. populate_hidden_volume   ← copy audio thật (LUÔN SAU bước 3)
5. verify_container         ← kiểm tra cả 2 volume mount được
```

> Script `create_hidden_container.py` tự động tuân thủ thứ tự này.

### Bảo mật password:

| Thực hành | Khuyến nghị |
|-----------|-------------|
| Lưu password | Dùng biến môi trường (`export`), **không** lưu vào file text |
| Đặt password | Outer password phải dễ nhớ khi bị ép; hidden password phải mạnh |
| Password giống nhau | **Tuyệt đối không** — script sẽ từ chối nếu 2 password giống nhau |
| Chia sẻ password | Chỉ outer password mới được tiết lộ khi bị ép buộc |

### Tương thích TrueCrypt 7.1a trên PC (Windows/macOS/Linux):

- Container `.tc` tạo bởi tcplay hoàn toàn tương thích với TrueCrypt 7.1a.
- Khi mở trên PC: chọn file `.tc` → nhập password → chọn **Standard Volume** (outer) hoặc **Hidden Volume** tuỳ password.
- VeraCrypt (successor của TrueCrypt) cũng đọc được format này.

---

## 8. Troubleshooting

### `tcplay --create` hỏi password nhưng script bị treo

**Nguyên nhân:** tcplay không nhận stdin đúng cách.  
**Xử lý:** Đảm bảo dùng `subprocess.run(..., input=pw_bytes)` như trong script. Không dùng `stdin=subprocess.PIPE` tách biệt.

### `mkfs.fat` báo lỗi "device is busy"

**Nguyên nhân:** Mapper chưa sẵn sàng ngay sau `tcplay --map`.  
**Xử lý:** Script đã xử lý bằng retry logic. Nếu vẫn lỗi, chạy thủ công:
```bash
sudo udevadm settle
sudo mkfs.fat -F 32 /dev/mapper/phantom_hv_outer_XXXXX
```

### Mount outer volume — thấy audio files (lẽ ra phải thấy decoy)

**Nguyên nhân:** Đã nhập sai password (nhập hidden password thay vì outer password).  
**Xử lý:** Unmount, unmap, rồi mount lại với đúng outer password.

### Hidden volume bị corrupt

**Nguyên nhân:** Outer volume bị mount ở chế độ write sau khi hidden đã có dữ liệu.  
**Xử lý:** Không thể phục hồi. Phải tạo lại container từ đầu.  
**Phòng tránh:** Sau khi chạy `populate_hidden_volume`, **không bao giờ** ghi thêm vào outer volume.

### Container không verify được

**Nguyên nhân:** Thứ tự populate sai, hoặc script bị interrupt giữa chừng.  
**Xử lý:**
```bash
# Dọn dẹp mapper còn sót
sudo tcplay --unmap phantom_hv_outer_XXXXX
sudo tcplay --unmap phantom_hv_hidden_XXXXX

# Xoá container và tạo lại
rm -f /path/to/container.tc
sudo python3 create_hidden_container.py --output /path/to/container.tc [...]
```

---

## Tóm tắt nhanh

```
Tạo container:
  sudo python3 create_decoy_files.py
  sudo python3 create_hidden_container.py --output rec.tc --size 50 \
      --outer-password "A" --hidden-password "B" --audio-files *.opus

Bị ép khai → dùng password A → chỉ thấy decoy files ✓
Truy cập thật → dùng password B + --use-hidden → thấy audio files ✓
```

---

*Tài liệu này là một phần của PHANTOM R3 — Covert Intelligence Collection System.*  
*Phiên bản: R3.1 | Ngày cập nhật: 2026-04-06*
