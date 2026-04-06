# PHANTOM-R3 — KẾ HOẠCH POC
> Tổng hợp từ: (1) Tài liệu kỹ thuật tiếng Việt, (2) Tài liệu kỹ thuật tiếng Anh, (3) Ghi âm cuộc họp "Đường Nối"  
> Ngày: 04/04/2026

---

## PHẦN 1 — TÓM TẮT Ý NGƯỜI NÓI (từ ghi âm)

### 🎯 Mục tiêu buổi demo
Làm một buổi **POC demo** với kiến trúc đơn giản nhất có thể:
- **2 thiết bị** đặt ở 2 nơi → đồng bộ file với nhau qua **Wi-Fi ẩn**
- **1 điện thoại** chạy **APK** → kết nối vào mạng thiết bị → lấy file

### 💬 Các ý chính của người nói

| # | Ý chính | Trích dẫn gốc |
|---|---------|---------------|
| 1 | Thiết bị dùng **ESP32** hoặc **Raspberry Pi Zero W** | *"Bên trong nó sẽ là một cái mạch ESP32 hoặc là Raspberry Pi Zero W"* |
| 2 | 2 thiết bị đồng bộ qua **Wi-Fi 2.4 GHz ẩn (hidden SSID)** | *"nó sai với nhau qua Wi-Fi 2.4 nhưng mà phải ẩn"* |
| 3 | Wi-Fi ẩn **chỉ kết nối được bằng APK** độc quyền | *"Wi-Fi ẩn đấy chỉ kết nối được bằng file APK trên điện thoại này thôi"* |
| 4 | Công nghệ đồng bộ dùng **Blockchain** — mỗi thiết bị là 1 node | *"về cái công nghệ để sai là phải dùng blockchain… cái này là 1 cái nốt, cái này là 1 cái nốt"* |
| 5 | **Bài toán khó nhất là đồng bộ** — ghi âm tính sau | *"Ghi âm là tính sau, cái đồng bộ mới là cái khổ"* |
| 6 | File ghi âm phải được **mã hóa thành .bin** 15 phút/lần, xóa file gốc | *"về 15 phút thì tôi mạng hóa 1 lần mà tôi xóa cái phai ghi âm đi"* |
| 7 | Điện thoại nhận file .bin **không nghe được** — phải về **máy chủ giải mã** | *"cái thẳng nghiệp bụng mà nó đến nó lấy cái phai này về nó không nghe được, nó phải mang về cơ quan mà cắm vào máy chủ"* |
| 8 | Gợi ý dùng **VeraCrypt** cho phần mã hóa/giải mã | *"dùng luôn cái phần này trên là chú creep… VeraCrypt 7.2"* |
| 9 | Kích thước thiết bị **nhỏ nhất có thể**, micro **nhỏ, gọn, xịn** — đắt không vấn đề | *"kích cướp nhỏ nhất có thể… ghi âm này dùng micro này nhưng mà thật bé, đắt không vấn đề"* |
| 10 | **Demo không cần vỏ** — cứ để mạch trần | *"trong buổi demo là thậm sĩ không cần phải vỏ, nhưng mà demo là cứ để đây, cái cục này ở đây"* |
| 11 | App điện thoại phải hiện **trạng thái đồng bộ + thời gian còn lại** | *"phải chẳng thái 1 là đồng bộng đến cuối là đến ngày nào giờ nào… phải estimate chẳng là khoảng 10 giây nữa"* |
| 12 | **Deadline 2 tuần** → đưa danh sách linh kiện để chốt mua | *"phít bách cho anh bụng lấy cho anh trong chiều 2 tuần, để anh chốt mua luôn là pháp luôn"* |
| 13 | Tìm **ít nhất 3 phương án** đồng bộ bằng AI/GPT | *"ném vào agent, ném vào GPT, tìm mọi thể loại, tìm cho anh ít nhất 3 phương hãi"* |
| 14 | Cần xác định **khoảng cách truyền tối đa** (use case truyền không tiếp xúc) | *"mình phải báo với người ta xem cái khoảng cách tuổi đa là khoảng bao xa"* |

---

## PHẦN 2 — SO SÁNH: Ý NGƯỜI NÓI vs TÀI LIỆU KỸ THUẬT

| Hạng mục | Tài liệu kỹ thuật (Spec) | Người nói (Ghi âm) | Nhận xét |
|---|---|---|---|
| **Phần cứng chính** | Không chỉ định chip cụ thể | ESP32 hoặc RPi Zero W | ✅ Phù hợp — cần chọn 1 trong 2 |
| **Kết nối** | 2.4 GHz / 5 GHz dual-band, FHSS | Wi-Fi 2.4 GHz ẩn | ⚠️ Spec yêu cầu dual-band + FHSS, người nói chỉ đề cập 2.4 ẩn — **POC dùng 2.4 trước** |
| **Đồng bộ** | Blockchain distributed ledger | Blockchain — mỗi thiết bị là 1 node | ✅ Nhất quán |
| **Mã hóa** | AES-256-GCM + RSA-4096 | Mã hóa thành .bin, dùng VeraCrypt | ⚠️ Spec dùng AES-256-GCM/RSA, người nói đề xuất VeraCrypt — **POC dùng VeraCrypt để nhanh, sau nâng cấp** |
| **Lưu trữ** | 32 GB eMMC, anti-forensic wipe | Thẻ nhớ SD | ⚠️ Spec dùng eMMC, người nói nói thẻ nhớ — **POC dùng SD card trước cho đơn giản** |
| **Xóa file gốc** | Sau khi truyền thành công | 15 phút mã hóa 1 lần, xóa file gốc | ✅ Cùng mục đích, người nói chi tiết hơn về chu kỳ |
| **APK điện thoại** | Android APK độc quyền | App "Phantom R3" trên điện thoại | ✅ Nhất quán |
| **Phone không lưu data giải mã** | Encrypted payload → home server | Nhận .bin về → giải mã tại máy chủ | ✅ Nhất quán |
| **Kích thước** | 85×55×22mm, 68g | Nhỏ nhất có thể, không cần vỏ cho POC | ✅ Nhất quán — vỏ làm sau |
| **Tầm phủ** | 100m indoor / 300m outdoor | ~100m Wi-Fi 2.4 | ✅ Nhất quán |
| **Pin** | LiPo 3000mAh, 72h ghi âm | Pin riêng, dùng được | ✅ Nhất quán — spec chi tiết hơn |
| **Micro** | MEMS 3-element beamforming | Micro nhỏ, gọn, xịn | ✅ Nhất quán — người nói không quan tâm spec kỹ |
| **Giải mã** | RSA-4096 private key, home server | Máy chủ tại cơ quan, VeraCrypt | ⚠️ Spec dùng RSA+AES, người nói gợi ý VeraCrypt — cần đồng nhất sau POC |

---

## PHẦN 3 — KẾ HOẠCH CÁC VIỆC CẦN LÀM

### 🔴 GIAI ĐOẠN 1 — MVP POC (2 tuần — Theo deadline người nói)

**Mục tiêu:** 2 thiết bị đồng bộ file + điện thoại lấy được file → demo được cho sếp

#### Sprint 1A: Nghiên cứu & Chọn phần cứng (Tuần 1, ngày 1–3)

- [ ] **[HW-01]** So sánh ESP32 vs Raspberry Pi Zero W:
  - Tầm phủ Wi-Fi tối đa
  - Khả năng chạy blockchain node nhẹ
  - Tiêu thụ pin
  - Kích thước, giá thành
- [ ] **[HW-02]** Chọn **micro nhỏ nhất, chất lượng tốt nhất** (MEMS I2S preferred — ICS-43434 hoặc tương đương)
- [ ] **[HW-03]** Chọn **pin** phù hợp (LiPo, dung lượng đủ 8–12h cho POC)
- [ ] **[HW-04]** Liệt kê toàn bộ danh sách linh kiện → **gửi anh chốt mua trong 2 tuần**

#### Sprint 1B: Nghiên cứu đồng bộ (Tuần 1, ngày 1–5) — **Ưu tiên số 1**

- [ ] **[SYNC-01]** Tìm **ít nhất 3 phương án** đồng bộ file qua Wi-Fi ẩn giữa 2 thiết bị:
  - Phương án A: **Syncthing** (P2P file sync, open source, chạy được trên RPi/Linux)
  - Phương án B: **Custom MQTT + broker nội bộ** (lightweight, dùng được trên ESP32)
  - Phương án C: **Lightweight blockchain node** (IOTA, Hyperledger Fabric mini, hoặc custom hash chain)
- [ ] **[SYNC-02]** Đánh giá từng phương án theo tiêu chí: tốc độ, độ ổn định, kích thước binary, chạy được offline
- [ ] **[SYNC-03]** Vẽ sơ đồ kiến trúc mạng (Thiết bị 1 ↔ Thiết bị 2 ↔ Điện thoại)

#### Sprint 1C: Prototype đồng bộ (Tuần 1–2)

- [ ] **[PROTO-01]** Setup 2 thiết bị (dùng RPi/ESP32 dev board) → phát Wi-Fi ẩn
- [ ] **[PROTO-02]** Copy file vào thiết bị 1 → tự đồng bộ sang thiết bị 2 (không cần người tác động)
- [ ] **[PROTO-03]** Điện thoại (APK) kết nối vào → nhìn thấy 2 thiết bị → kéo file về
- [ ] **[PROTO-04]** APK hiển thị: danh sách thiết bị + trạng thái đồng bộ + thời gian còn lại (estimate)

#### Sprint 1D: Mã hóa cơ bản (Tuần 2)

- [ ] **[ENC-01]** Tích hợp **VeraCrypt** (hoặc AES-256 script) vào pipeline:
  - Ghi âm → lưu file tạm → **mã hóa thành .bin mỗi 15 phút** → xóa file gốc
- [ ] **[ENC-02]** Điện thoại nhận file **.bin (không nghe được)**
- [ ] **[ENC-03]** Setup **home server giải mã** (script đơn giản): nhận .bin → giải mã → phát file audio

---

### 🟡 GIAI ĐOẠN 2 — Alpha (3–4 tuần tiếp theo)

**Mục tiêu:** Nâng cấp bảo mật + hoàn thiện tính năng theo spec kỹ thuật

- [ ] **[SEC-01]** Thay VeraCrypt bằng **AES-256-GCM + RSA-4096** đúng chuẩn spec
- [ ] **[SEC-02]** Tích hợp **Hardware Security Module (ATECC608A)** vào thiết bị
- [ ] **[SEC-03]** **Ephemeral session keys** — xoay vòng theo phiên
- [ ] **[SEC-04]** **Anti-forensic wipe** sau khi truyền thành công (DoD 5220.22-M)
- [ ] **[RF-01]** **FHSS frequency hopping** + MAC address randomization
- [ ] **[RF-02]** Nâng lên **dual-band 2.4/5 GHz** (theo spec)
- [ ] **[AUDIO-01]** Tối ưu ghi âm: VAD (Voice Activity Detection) để tiết kiệm pin
- [ ] **[AUDIO-02]** Nâng cấp lên mảng MEMS 3 phần tử nếu ESP32 hỗ trợ
- [ ] **[BAT-01]** Tối ưu pin → đạt **72 giờ ghi âm liên tục**
- [ ] **[STORE-01]** Nâng từ SD card lên **eMMC 5.1** với AES-XTS full-disk encryption

---

### 🟢 GIAI ĐOẠN 3 — Beta / Field Test

**Mục tiêu:** Sản phẩm hoàn chỉnh, đóng vỏ, test thực địa

- [ ] **[HW-FINAL-01]** Thiết kế và in **PCB tùy chỉnh** (4 lớp, 80×50mm)
- [ ] **[HW-FINAL-02]** **Vỏ máy** đúng 85×55×22mm (3D print hoặc CNC nhôm)
- [ ] **[HW-FINAL-03]** Đạt chuẩn **IP54** (gioăng silicone chống bụi/nước)
- [ ] **[HW-FINAL-04]** **Chân sạc từ tính** (magnetic pogo-pin)
- [ ] **[TEST-01]** Test thực địa: khoảng cách truyền (xác định chính xác tầm tối đa theo yêu cầu người nói)
- [ ] **[TEST-02]** Test nhiệt độ (−10°C đến +55°C)
- [ ] **[TEST-03]** Scale lên **200 thiết bị** đồng thời

---

## PHẦN 4 — PHÂN CÔNG ĐỀ XUẤT

| Việc | Người phụ trách | Thời hạn |
|------|----------------|----------|
| Nghiên cứu phần cứng ESP32 vs RPi0W | Dev phần cứng | Ngày 3 |
| Danh sách linh kiện → gửi anh | Dev phần cứng | Tuần 2 |
| Nghiên cứu 3 phương án đồng bộ | Dev backend | Ngày 5 |
| Sơ đồ kiến trúc mạng | Dev backend | Ngày 5 |
| Prototype 2 thiết bị đồng bộ | Dev phần cứng + backend | Tuần 2 |
| APK Android cơ bản | Dev mobile | Tuần 2 |
| Script mã hóa .bin + home server giải mã | Dev backend | Tuần 2 |

---

## PHẦN 5 — RỦI RO CẦN LƯU Ý

| Rủi ro | Mức độ | Giải pháp |
|--------|--------|-----------|
| ESP32 RAM không đủ chạy blockchain node | 🔴 Cao | Dùng RPi Zero W cho POC; custom lightweight sync thay blockchain đầy đủ |
| Wi-Fi ẩn 2.4 GHz bị detect bởi RF scanner | 🟡 Trung bình | FHSS + MAC random (Phase 2) |
| Blockchain sync chậm khi nhiều node | 🟡 Trung bình | Giới hạn 2–3 node cho POC; scale sau |
| Pin không đủ 72h với ghi âm liên tục | 🟡 Trung bình | Dùng VAD; chọn pin dung lượng phù hợp |
| Tài liệu spec ghi 1 TB storage nhưng hardware ghi 32 GB | 🟡 Trung bình | Xác nhận lại với sếp; POC dùng SD 32 GB |

---

*Tổng hợp từ: PHR3-SPEC-2024-0048 Rev 3.2.0 + Ghi âm cuộc họp "Đường Nối" (~11:50)*  
*Ngày tạo: 04/04/2026*
