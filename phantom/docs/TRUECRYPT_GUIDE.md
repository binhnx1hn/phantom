# PHANTOM R3 — Hướng Dẫn Giải Mã TrueCrypt

> **Dành cho người dùng cuối** — Không yêu cầu kiến thức kỹ thuật.
> Tài liệu này hướng dẫn toàn bộ quy trình: từ khi nhận file `.tc` cho đến khi nghe được audio `.opus`.

---

## Tổng Quan Luồng

```
┌─────────────────────┐
│  Thiết bị PHANTOM   │  ← Thu âm & mã hóa tự động
│  (Raspberry Pi)     │
└──────────┬──────────┘
           │ Wi-Fi ẩn (SSID ẩn)
           ▼
┌─────────────────────┐
│   Android Phone     │  ← Nhận file qua PHANTOM APK
│   (PHANTOM APK)     │
└──────────┬──────────┘
           │ Copy file .tc (USB hoặc cloud)
           ▼
┌─────────────────────┐
│        PC           │  ← Windows / macOS / Linux
│  TrueCrypt 7.1a     │
└──────────┬──────────┘
           │ Mount container .tc
           ▼
┌─────────────────────┐
│  Nghe audio .opus   │  ← VLC / Windows Media Player / ffplay
│  (file đã giải mã)  │
└─────────────────────┘
```

> **Nguyên tắc bảo mật:** File `.tc` khi chưa mount là một khối dữ liệu mã hóa hoàn toàn — không ai đọc được nếu không có đúng password.

---

## Hướng Dẫn Giải Mã Trên Windows

### Yêu cầu
- TrueCrypt 7.1a đã cài đặt (xem [`TRUECRYPT_DOWNLOAD.md`](./TRUECRYPT_DOWNLOAD.md))
- File `.tc` đã copy về máy tính

### Các bước thực hiện

**Bước 1: Tải file `.tc` từ phone về PC**

Có 2 cách:
- **USB:** Kết nối phone vào PC → copy file `.tc` từ thư mục Download về Desktop
- **Cloud:** Nếu dùng cloud storage → download file `.tc` về máy

**Bước 2: Mở TrueCrypt 7.1a**

Vào `Start Menu` → tìm `TrueCrypt` → mở ứng dụng.

**Bước 3: Chọn file `.tc`**

Trong cửa sổ TrueCrypt:
- Click nút **"Select File..."**
- Điều hướng đến file `.tc` vừa copy về
- Click **"Open"**

**Bước 4: Chọn drive letter**

Trong danh sách drive letters ở trên:
- Click chọn một ổ trống, ví dụ **`Z:`**
- (Tránh dùng các ổ đã có dữ liệu)

**Bước 5: Mount container**

- Click nút **"Mount"**
- Hộp thoại nhập password xuất hiện
- Nhập **password đúng** → Click **"OK"**
- Chờ vài giây → TrueCrypt mount thành công

> **Lưu ý:** Nếu nhập sai password, TrueCrypt sẽ báo lỗi. Thử lại với đúng password.

**Bước 6: Nghe file audio**

- Mở **Windows Explorer** (phím `Win + E`)
- Vào ổ **`Z:`** (hoặc drive letter bạn đã chọn)
- Tìm file `.opus` bên trong
- Double-click → nghe bằng **VLC Media Player** hoặc **Windows Media Player**

> **Gợi ý:** VLC miễn phí và hỗ trợ tốt định dạng `.opus`. Tải tại [videolan.org](https://www.videolan.org/).

**Bước 7: Dismount sau khi xong**

Khi đã nghe xong, **bắt buộc** phải dismount:
- Quay lại cửa sổ TrueCrypt
- Chọn drive `Z:` trong danh sách
- Click **"Dismount"**
- Hoặc click **"Dismount All"** để dismount tất cả

> Sau khi dismount, file `.tc` trở lại dạng mã hóa hoàn toàn. **Xóa file `.tc` ngay** nếu không cần nữa.

---

## Hướng Dẫn Giải Mã Trên macOS

### Yêu cầu
- TrueCrypt 7.1a for macOS đã cài đặt
- File `.tc` đã copy về máy

### Các bước thực hiện

**Bước 1: Tải file `.tc` từ phone về Mac**

Kết nối phone qua USB hoặc dùng AirDrop / cloud storage.

**Bước 2: Mở TrueCrypt 7.1a for macOS**

Vào `Applications` → mở **TrueCrypt**.

**Bước 3: Chọn file `.tc`**

- Click **"Select File..."**
- Chọn file `.tc`

**Bước 4: Chọn slot mount**

Click chọn một slot trống trong danh sách.

**Bước 5: Mount container**

- Click **"Mount"**
- Nhập password → **"OK"**
- Mount point mặc định: `/Volumes/phantom` (hoặc tên volume trong container)

**Bước 6: Nghe file audio**

- Mở **Finder**
- Trong sidebar, tìm volume vừa mount (tên `/Volumes/phantom` hoặc tương tự)
- Truy cập vào volume → tìm file `.opus`
- Double-click → nghe bằng **VLC for Mac**

> **Gợi ý:** macOS không tự phát file `.opus` — cần cài VLC.

**Bước 7: Dismount**

- Trong TrueCrypt, chọn slot → click **"Dismount"**
- Hoặc chuột phải vào volume trong Finder → **"Eject"**

---

## Hướng Dẫn Giải Mã Trên Linux

### Yêu cầu
- `tcplay` đã cài đặt: `sudo apt install tcplay` (Debian/Ubuntu) hoặc `sudo pacman -S tcplay` (Arch)
- Quyền `sudo`

### Các bước thực hiện

**Bước 1: Copy file `.tc` về máy**

```bash
# Ví dụ copy từ USB mount
cp /media/user/phone/recording.tc ~/Downloads/recording.tc
```

**Bước 2: Tạo thư mục mount point**

```bash
sudo mkdir -p /mnt/phantom
```

**Bước 3: Map container với tcplay**

```bash
sudo tcplay --map=phantom --device=/path/to/recording.tc
```

Nhập password khi được hỏi → Enter.

**Bước 4: Mount filesystem**

```bash
sudo mount /dev/mapper/phantom /mnt/phantom
```

**Bước 5: Nghe file audio**

```bash
# Dùng ffplay (cài ffmpeg)
ffplay /mnt/phantom/recording.opus

# Hoặc mở bằng VLC
vlc /mnt/phantom/recording.opus

# Hoặc mở file manager
xdg-open /mnt/phantom/
```

**Bước 6: Unmount và unmap sau khi xong**

```bash
# Unmount filesystem trước
sudo umount /mnt/phantom

# Sau đó unmap container
sudo tcplay --unmap=phantom
```

> **Quan trọng:** Phải unmount trước rồi mới unmap — làm ngược sẽ lỗi.

---

## Hướng Dẫn Mount Hidden Volume (2 Lớp Mật Khẩu)

### Hidden Volume là gì?

TrueCrypt cho phép tạo **2 lớp bảo mật** trong cùng 1 file `.tc`:

| Lớp | Password | Nội dung |
|-----|----------|----------|
| **Outer Volume** | Password ngoài (có thể tiết lộ) | File giả / tài liệu vô hại |
| **Hidden Volume** | Password ẩn (tuyệt mật) | File audio thật cần bảo vệ |

### Nguyên tắc hoạt động

- Nhập **password ngoài** → TrueCrypt mount Outer Volume → thấy file giả
- Nhập **password ẩn** → TrueCrypt mount Hidden Volume → thấy file audio thật

> Không ai có thể chứng minh Hidden Volume tồn tại hay không — đây là tính năng **"plausible deniability"** của TrueCrypt.

### Quy trình mount Hidden Volume

Quy trình mount giống hệt mount bình thường — chỉ khác ở bước nhập password:

1. Thực hiện các bước mount như hướng dẫn trên
2. Khi hộp thoại password xuất hiện:
   - Nhập **password ẩn** (hidden password) → mount Hidden Volume → thấy audio thật
   - Nhập **password ngoài** (outer password) → mount Outer Volume → thấy file giả
3. TrueCrypt tự động nhận biết lớp nào dựa trên password

> **Lưu ý quan trọng:** PHANTOM R3 mặc định tạo Hidden Volume. Đảm bảo dùng đúng password tương ứng với lớp cần truy cập.

---

## Test Checklist Cho Từng Platform

| Hạng mục | Windows | macOS | Linux |
|----------|---------|-------|-------|
| Cài TrueCrypt 7.1a | `[ ]` | `[ ]` | `[ ]` (dùng tcplay) |
| Mount container `.tc` thành công | `[ ]` | `[ ]` | `[ ]` |
| Nghe được file `.opus` | `[ ]` | `[ ]` | `[ ]` |
| Dismount thành công | `[ ]` | `[ ]` | `[ ]` |
| Xóa file `.tc` sau khi xong | `[ ]` | `[ ]` | `[ ]` |

> Tick hết tất cả ô trước khi coi quy trình là hoàn tất.

---

## ⚠️ Lưu Ý Quan Trọng

### Về bảo mật file

> **KHÔNG** để file `.tc` trên máy tính sau khi đã nghe xong.
> → **Xóa ngay lập tức** sau khi dismount. File `.tc` dù đã mã hóa vẫn có thể bị brute-force nếu kẻ tấn công có thời gian và tài nguyên đủ lớn.

### Về password

> **KHÔNG** share password qua kênh không an toàn (SMS, email thường, Zalo, Telegram không bật Secret Chat).
> → Chỉ trao đổi password trực tiếp hoặc qua kênh end-to-end encrypted đã xác minh.

### Về trạng thái mã hóa

> Sau khi dismount, file `.tc` **trở lại dạng mã hóa hoàn toàn**. Mọi dữ liệu bên trong đều không thể đọc được nếu không có đúng password.

### Về việc xóa file

> Dùng **secure delete** thay vì xóa thông thường nếu cần đảm bảo dữ liệu không thể phục hồi:
> - **Windows:** `cipher /w:C:\path\to\file` hoặc dùng Eraser
> - **macOS:** `rm -P /path/to/file.tc`
> - **Linux:** `shred -vuz /path/to/file.tc`

---

*Tài liệu này là một phần của hệ thống PHANTOM R3. Không phân phối ra ngoài.*
