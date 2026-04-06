# PHANTOM R3 — Hướng Dẫn Tải TrueCrypt 7.1a

> Tài liệu này hướng dẫn cách tải, xác minh và cài đặt TrueCrypt 7.1a — phiên bản duy nhất được phép dùng với PHANTOM R3.

---

## ⚠️ Cảnh Báo Quan Trọng — Đọc Trước Khi Tải

### truecrypt.org đã DOWN

> **`truecrypt.org`** — trang chủ chính thức — đã **ngừng hoạt động từ năm 2014**.
> Đội ngũ phát triển đã đóng cửa đột ngột vào ngày 28/05/2014 mà không có lý do công khai rõ ràng.
> **Không truy cập được** — không có mirror chính thức từ nhà phát triển gốc.

### TrueCrypt 7.2 — KHÔNG DÙNG để mã hóa mới

> **TrueCrypt 7.2** là bản phát hành cuối cùng từ đội ngũ gốc (tháng 5/2014).
> Bản này đã bị **vô hiệu hóa tính năng mã hóa mới** — chỉ cho phép **giải mã** (decrypt) các container cũ.
> **KHÔNG sử dụng TrueCrypt 7.2** cho PHANTOM R3.

### ✅ Phải dùng TrueCrypt 7.1a

> **TrueCrypt 7.1a** (phát hành tháng 2/2012) là bản đầy đủ cuối cùng còn hoạt động hoàn toàn:
> - Vừa **mã hóa** (encrypt) lẫn **giải mã** (decrypt)
> - Đã được audit bởi **iSEC Partners** năm 2014 — **không phát hiện backdoor**
> - Tương thích với `tcplay` trên Linux/Raspberry Pi (PHANTOM R3 dùng `tcplay` để mã hóa)
> - **Đây là phiên bản duy nhất được phép dùng với PHANTOM R3**

---

## Các Mirror Đáng Tin Cậy

| # | Nguồn | URL | Độ tin cậy | Ghi chú |
|---|-------|-----|-----------|---------|
| 1 | **GRC.com** (Steve Gibson / Gibson Research Corporation) | `https://www.grc.com/misc/truecrypt/truecrypt.htm` | ⭐⭐⭐⭐⭐ Cao nhất | Có hash SHA256 đã xác minh; Steve Gibson là người uy tín trong cộng đồng bảo mật |
| 2 | **GitHub — DrWhax/truecrypt-archive** | `https://github.com/DrWhax/truecrypt-archive` | ⭐⭐⭐⭐ Cao | Lưu trữ cộng đồng, có signed releases, được nhiều người audit |
| 3 | **GitHub — AuditProject/truecrypt-verified-mirror** | `https://github.com/AuditProject/truecrypt-verified-mirror` | ⭐⭐⭐⭐ Cao | Mirror đã qua quy trình audit độc lập |
| 4 | **SourceForge** | `https://sourceforge.net/projects/truecrypt/files/TrueCrypt/` | ⭐⭐⭐ Trung bình | Archive cũ, còn accessible nhưng không có xác minh hash tích hợp |

> **Khuyến nghị:** Tải từ **GRC.com** trước — sau đó cross-check hash với GitHub DrWhax archive.
> Nếu cả hai hash khớp nhau → file an toàn.

---

## SHA256 Hash Chính Thức của TrueCrypt 7.1a

> **⚠️ Quan trọng:** Bảng dưới đây chỉ mang tính tham khảo cấu trúc.
> Hash chính xác **phải được lấy từ GRC.com** và **cross-check với GitHub DrWhax archive**.
> Không tin tưởng hash từ bất kỳ nguồn nào khác chưa được xác minh.

| Platform | File | SHA256 Hash |
|----------|------|-------------|
| **Windows 32-bit** | `TrueCrypt Setup 7.1a.exe` | Lấy tại: [grc.com/misc/truecrypt](https://www.grc.com/misc/truecrypt/truecrypt.htm) |
| **Windows 64-bit** | `TrueCrypt Setup 7.1a.exe` (cùng installer, hỗ trợ cả 32/64-bit) | Cross-check với GitHub DrWhax archive |
| **macOS** | `TrueCrypt 7.1a Mac OS X.dmg` | Lấy tại GRC.com → so sánh với GitHub archive |
| **Linux 32-bit (console)** | `truecrypt-7.1a-linux-console-x86.tar.gz` | Lấy tại GRC.com → cross-check |
| **Linux 64-bit (console)** | `truecrypt-7.1a-linux-console-x64.tar.gz` | Lấy tại GRC.com → cross-check |
| **Linux 32-bit (GUI)** | `truecrypt-7.1a-linux-x86.tar.gz` | Lấy tại GRC.com → cross-check |
| **Linux 64-bit (GUI)** | `truecrypt-7.1a-linux-x64.tar.gz` | Lấy tại GRC.com → cross-check |

> **Lý do không in hash cứng ở đây:** Hash có thể thay đổi nếu tài liệu này bị sao chép hoặc chỉnh sửa.
> Luôn lấy hash từ nguồn gốc (GRC.com) tại thời điểm tải.

---

## Hướng Dẫn Verify Hash Sau Khi Tải

**Bước 1: Tải file từ GRC.com hoặc GitHub archive**

**Bước 2: Verify hash — chọn lệnh tương ứng với hệ điều hành:**

```powershell
# Windows — PowerShell (chạy bằng cách nhấn Win + X → Windows PowerShell)
Get-FileHash "TrueCrypt Setup 7.1a.exe" -Algorithm SHA256
```

```bash
# macOS / Linux — Terminal
sha256sum "TrueCrypt Setup 7.1a.exe"

# macOS có thể dùng shasum thay thế
shasum -a 256 "TrueCrypt 7.1a Mac OS X.dmg"
```

**Bước 3: So sánh output với hash từ GRC.com**

```
Output mẫu (Windows PowerShell):
Algorithm       Hash                                                                   Path
---------       ----                                                                   ----
SHA256          E4DC7EB635B6E4F84461B6E93F41C30B5A...                                 TrueCrypt Setup 7.1a.exe

→ So sánh dãy hash này với hash trên GRC.com — phải KHỚP HOÀN TOÀN từng ký tự.
```

> ## ❌ Nếu hash KHÔNG KHỚP → XÓA FILE NGAY
>
> - **Không** cài đặt file có hash không khớp
> - **Xóa ngay** file vừa tải
> - Thử tải lại từ nguồn khác (ví dụ từ GRC.com nếu tải từ SourceForge, hoặc ngược lại)
> - Nếu tất cả nguồn đều cho hash không khớp → báo cáo ngay cho quản trị PHANTOM R3

---

## Hướng Dẫn Cài Đặt Nhanh

### Windows

1. Tải file `TrueCrypt Setup 7.1a.exe`
2. Verify hash (bắt buộc — xem hướng dẫn trên)
3. Double-click file `.exe` → chạy installer
4. Chọn **"Install"** → Next → Next → Finish
5. TrueCrypt xuất hiện trong Start Menu

```
Lưu ý Windows: Có thể cần quyền Administrator để cài đặt.
Chuột phải vào file .exe → "Run as administrator"
```

### macOS

1. Tải file `TrueCrypt 7.1a Mac OS X.dmg`
2. Verify hash (bắt buộc)
3. Double-click file `.dmg` để mount
4. Kéo icon **TrueCrypt** vào thư mục **Applications**
5. Mở từ Applications (lần đầu có thể cần vào System Preferences → Security → Allow)

```
Lưu ý macOS: Trên macOS Catalina (10.15) trở lên, TrueCrypt 7.1a
có thể không hoạt động đầy đủ do Apple bỏ hỗ trợ 32-bit kernel extension.
Trong trường hợp đó, dùng VeraCrypt (fork của TrueCrypt, tương thích ngược)
hoặc dùng Linux/Windows để giải mã.
```

### Linux

```bash
# 1. Tải và verify hash trước (xem hướng dẫn trên)

# 2. Giải nén archive
tar xzf truecrypt-7.1a-linux-console-x64.tar.gz

# 3. Chạy installer (console version — không cần GUI)
sudo ./truecrypt-7.1a-setup-console-x64

# 4. Làm theo hướng dẫn trên màn hình (nhấn Enter để chấp nhận)

# --- HOẶC --- dùng tcplay thay thế (khuyến nghị cho Linux) ---
# tcplay là open-source, tương thích hoàn toàn với TrueCrypt 7.1a format

# Debian / Ubuntu
sudo apt-get update && sudo apt-get install tcplay

# Arch Linux
sudo pacman -S tcplay

# Fedora / RHEL
sudo dnf install tcplay
```

> **Khuyến nghị cho Linux:** Dùng `tcplay` thay vì TrueCrypt binary — `tcplay` là open-source, được audit độc lập, và tương thích hoàn toàn với các container TrueCrypt 7.1a do PHANTOM R3 tạo ra.

---

## Lưu Ý Bảo Mật

### Về audit TrueCrypt 7.1a

> **TrueCrypt 7.1a đã được kiểm toán bảo mật độc lập bởi iSEC Partners năm 2014** (Open Crypto Audit Project — OCAP).
> Kết quả: **Không phát hiện backdoor cố ý** hay lỗ hổng nghiêm trọng trong thuật toán mã hóa.
> (Có phát hiện một số vấn đề nhỏ về quản lý bộ nhớ — không ảnh hưởng đến tính bảo mật của dữ liệu đã mã hóa)

### Về phiên bản

> **KHÔNG** nâng cấp lên bất kỳ phiên bản TrueCrypt nào khác ngoài 7.1a.
> **KHÔNG** dùng VeraCrypt để mã hóa mới nếu cần tương thích với PHANTOM R3
> (VeraCrypt thay đổi tham số PBKDF — container VeraCrypt không tương thích ngược với TrueCrypt 7.1a).
> Nếu chỉ cần giải mã trên macOS mới — VeraCrypt có thể dùng để **giải mã** container `.tc` của TrueCrypt 7.1a.

### Kiểm tra sau khi cài

> Sau khi cài xong, **bắt buộc** phải verify bằng cách tạo một container test nhỏ:
>
> 1. Tạo container test 5MB: TrueCrypt → Create Volume → Create encrypted file container
> 2. Mount container test
> 3. Copy một file nhỏ vào
> 4. Dismount
> 5. Mount lại → đọc được file → Cài đặt thành công ✓

### Về nguồn tải

> - Chỉ tải từ các nguồn trong bảng mirror ở trên
> - **Không** tải từ các trang lạ, torrent không rõ nguồn, hay link trong email/chat
> - **Không** tin tưởng bất kỳ hash nào không đến từ GRC.com hoặc GitHub DrWhax archive
> - **Không** cài đặt bất kỳ "TrueCrypt fork" hay "TrueCrypt enhanced" nào — chỉ dùng đúng 7.1a bản gốc (hoặc tcplay trên Linux)

---

*Tài liệu này là một phần của hệ thống PHANTOM R3. Không phân phối ra ngoài.*
