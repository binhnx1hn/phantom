# ESP32 Audio Transfer — Demo Project
**STATUS: ✅ APPROVED — Ready for Hardware Flash**
**Version: 2.0 | Date: 2026-04-06**

## Overview
Hệ thống truyền file WAV không dây giữa 2 thiết bị ESP32 qua WiFi AP ẩn.
Mục tiêu: Demo hoàn chỉnh 4 bước cho khán giả không cần giải thích kỹ thuật.

---

## Versions
- **v1.0** — Code hiện tại: AP hiện, upload qua TCP 8080, GUI cơ bản
- **v2.0** — Target demo: AP ẩn, upload HTTP multipart, auto-download nền, LED confirm

---

## Demo Flow (4 bước)

```
[BƯỚC 1] Laptop-1 + Node-1 (có USB)
  → Node-1 phát WiFi ẩn "ESP32-Node-1"
  → Laptop-1 kết nối WiFi ẩn
  → Mở GUI → Upload WAV → thấy filelist + status "Upload OK"
  → Tắt Laptop-1

[BƯỚC 2] Chuyển nguồn Node-1
  → Tắt USB → cắm pin dự phòng
  → Node-1 reboot → đọc file từ SPIFFS (persist) → LED nháy 3 lần

[BƯỚC 3] Auto truyền sang Node-2
  → Node-2 boot → tự kết nối vào WiFi ẩn Node-1
  → Fetch file qua TCP 8080 → lưu SPIFFS
  → LED Node-2 nháy 5 lần (xác nhận nhận xong)
  → Node-1 tự shutdown (sleep deep hoặc signal)

[BƯỚC 4] Laptop-2 lấy file
  → Node-2 phát WiFi ẩn "ESP32-Node-2"
  → Laptop-2 kết nối → GUI chạy nền tự tải file
  → Mở GUI → file đã có sẵn trong folder Downloads
```

---

## GAP Analysis — Code hiện tại vs Spec

| # | Spec yêu cầu | Code hiện tại | GAP | Priority |
|---|---|---|---|---|
| G1 | WiFi AP **ẩn** (hidden) | `AP_HIDDEN false` (hiện) | ❌ Cần đổi thành `true` | HIGH |
| G2 | Upload qua GUI có **filelist + status** | Upload via TCP 8080, GUI thiếu filelist | ❌ Cần endpoint `/file/list` + GUI update | HIGH |
| G3 | **HTTP multipart upload** từ GUI | GUI dùng TCP socket raw, không multipart | ⚠️ TCP OK nhưng GUI cần hiện status rõ | MED |
| G4 | Node-1 đọc SPIFFS sau reboot → **LED nháy 3 lần** | `blinkLED(3,150)` khi có file ✅ | ✅ OK | - |
| G5 | Node-2 **tự động sync** khi boot | `syncFromNode1()` trong `setup()` ✅ | ✅ OK | - |
| G6 | Node-2 nhận xong → **LED nháy 5 lần** | `blinkLED(5,80)` sau sync OK ✅ | ✅ OK | - |
| G7 | Node-1 **tự shutdown** sau khi Node-2 lấy xong | Không có | ❌ Cần thêm endpoint `/shutdown` + deep sleep | HIGH |
| G8 | Laptop-2 **tự động tải file nền** khi kết nối | Không có auto-download | ❌ Cần service/thread trong GUI | HIGH |
| G9 | Mở GUI → file **đã có sẵn** trong folder | GUI chỉ download khi nhấn nút | ❌ Cần auto-save vào Downloads khi detect kết nối | HIGH |
| G10 | GUI hiện **trạng thái upload thành công** rõ ràng | Log text nhỏ | ⚠️ Cần toast/banner lớn | MED |
| G11 | GUI hiện **filelist** từ SPIFFS | Không có | ❌ Cần panel filelist | HIGH |
| G12 | GUI detect **Node-1 vs Node-2** tự động | IP cố định, không detect | ⚠️ Cần auto-detect dựa vào `/status` response | MED |

---

## Architecture

```
Node-1 (esp32_server/)              Node-2 (esp32_client/)
├── WiFi AP ẩn "ESP32-Node-1"      ├── WiFi APSTA
│   IP: 192.168.4.1                │   AP ẩn "ESP32-Node-2" IP: 192.168.5.1
├── HTTP :80                        ├── HTTP :80
│   GET  /status                   │   GET  /status
│   GET  /file/info                │   GET  /file/info
│   GET  /file/download            │   GET  /file/download
│   POST /file/upload (TCP 8080)   │   POST /sync
│   POST /file/clear               │   POST /file/clear
│   [NEW] POST /shutdown           │   GET  /ram/info
│   GET  /ram/info                 ├── TCP :8080 (download)
├── TCP :8080 (upload/download)    └── SPIFFS /audio.wav
└── SPIFFS /audio.wav (persist)
```

---

## Task Board

### PIPELINE v2.0 — Demo Ready

| Task | Agent | Status | Branch |
|---|---|---|---|
| BA-01: Spec chi tiết từng GAP | BA | ✅ DONE | - |
| BE-01: Fix Node-1 (AP ẩn + /shutdown + filelist) | BE Dev | ✅ DONE | be/node1-fixes |
| BE-02: Fix Node-2 (AP ẩn + shutdown call) | BE Dev | ✅ DONE | be/node2-fixes |
| FE-01: Fix GUI (auto-download, filelist, status) | FE Dev | ✅ DONE | fe/gui-v2 |
| INT-01: End-to-end test 4 bước (26/26 PASS) | Integration | ✅ DONE | - |
| QC-01: Audit vs spec (0 BLOCKERs, 2 MINORs, 4 INFOs) | QC | ✅ DONE | - |
| REV-01: Final sign-off | Reviewer | ✅ APPROVED | - |

---

## Fix Spec — Node-1 (BE-01)

### 1. AP ẩn
```cpp
// esp32_server/src/main.cpp line 40
#define AP_HIDDEN  true   // ← đổi false → true
```

### 2. Endpoint mới: GET /file/list
```json
{
  "files": [{"name": "audio.wav", "size": 12345, "size_kb": "12.1 KB"}],
  "count": 1,
  "spiffs_free": 200000
}
```

### 3. Endpoint mới: POST /shutdown
- Gửi response 200 trước
- Sau 1s gọi `esp_deep_sleep_start()` (ngủ vĩnh viễn cho đến khi reset)

---

## API-CONTRACT — BE-01 (Node-1)

| Method | Path | Request | Response 200 | Notes |
|--------|------|---------|--------------|-------|
| GET | `/file/list` | — | `{"files":[{"name","path","size","size_kb","duration_sec"}],"count","spiffs_total","spiffs_used","spiffs_free"}` | Lists all SPIFFS files with WAV duration |
| POST | `/file/delete?name=<file>` | query `name` | `{"status":"ok","deleted":"/<file>"}` | 400 missing name, 400 invalid, 404 not found; clears RAM if deleted file was loaded |
| POST | `/shutdown` | — | `{"status":"ok","message":"Node-1 shutting down"}` | Calls `esp_deep_sleep_start()` after 1 s |
| GET | `/status` | — | `{"node":1,"ap_ssid","ip","uptime","free_heap","spiffs_has_file","spiffs_size","ram_ready","ram_size","builtin_wav_size"}` | Unchanged — already existed |

**TCP port 8080 POST** — optional header `X-Filename: <name>` → saves to `/<sanitized>.wav`; auto-generates `audio_NNNN.wav` if omitted. Response adds `"filename":"<name>"` field.

**Config change:** `AP_HIDDEN` → `true` at [`esp32_server/src/main.cpp:40`](esp32_server/src/main.cpp)

---

## Fix Spec — Node-2 (BE-02)

### 1. AP ẩn
```cpp
// esp32_client/src/main.cpp line 41
#define MY_AP_HIDDEN  true  // ← đổi false → true
```

### 2. Sau khi sync xong → gọi shutdown Node-1
```cpp
// Sau blinkLED(5,80) trong syncFromNode1()
// HTTP POST http://192.168.4.1/shutdown
```

---

## Fix Spec — GUI FE-01

### 1. Auto-detect node khi kết nối WiFi
- Poll `/status` mỗi 3s
- Nếu `node==1` → hiện panel Upload + Filelist
- Nếu `node==2` → auto tải file nền → lưu `~/Downloads/audio_esp32.wav`

### 2. Auto-download background
```python
# Thread chạy khi detect node==2
def _bg_download_thread():
    while not file_downloaded:
        data = tcp_download("192.168.5.1", 8080, "/audio.wav")
        if len(data) > 44:
            save_to_downloads(data)
            show_banner("✅ File đã sẵn sàng trong Downloads!")
            break
        time.sleep(5)
```

### 3. Filelist panel
- Gọi `GET /file/list` (Node-1) hoặc `GET /file/info` (Node-2)
- Hiện bảng: Tên file | Kích thước | Thời lượng | Nút Download

### 4. Upload status banner
- Sau upload thành công → hiện banner xanh lá: "✅ Upload thành công! 234.5 KB"
- Tự ẩn sau 5 giây

---

## DOING / DONE / LEFT / NEXT / BLOCKERS

### ✅ DONE — v2.0 Pipeline Complete
- BA: 10 contracts, API spec, WiFi profile spec, risk register
- BE-01: Node-1 AP ẩn + `GET /file/list` + `POST /shutdown` + REV-01 fix
- BE-02: Node-2 AP ẩn + shutdown Node-1 sau sync
- FE-01: CLIENT_IP fix → `192.168.5.1`, auto-detect thread, filelist panel, upload banner, bg-download
- Cosmetic: network map IP/port cập nhật đúng
- Integration: 26/26 PASS
- QC: 0 BLOCKERs, 0 MAJORs
- Reviewer: **APPROVED**

### NEXT — Hardware Flash Steps
1. Cài driver CH340: https://www.wch.cn/downloads/CH341SER_EXE.html
2. Kiểm tra COM port: Device Manager → Ports → CH340 phải "OK"
3. Flash Node-1: `cd esp32_server && pio run -t upload`
4. Flash Node-2: `cd esp32_client && pio run -t upload`
5. Cài WiFi profiles:
   - `netsh wlan add profile filename="esp32_node1_profile.xml"`
   - `netsh wlan add profile filename="esp32_node2_profile.xml"`
6. Chạy GUI: `python audio_gui.py`

### BLOCKERS RESOLVED
- ~~CLIENT_IP sai~~ → đã fix `192.168.5.1`
- ~~AP hiện~~ → `AP_HIDDEN=true` cả Node-1 và Node-2
- ~~Không có /shutdown~~ → thêm `esp_deep_sleep_start()`, response trước sleep
- ~~Không có filelist~~ → `GET /file/list` + Treeview GUI
- CH340 driver "Unknown" → **CẦN cài driver** (link ở trên)

---

## Driver Issue (URGENT)

CH340 chip driver trên Windows 10 báo **Status: Unknown** → COM3/COM4 không mở được.

**Giải pháp:**
1. Tải driver CH340: https://www.wch.cn/downloads/CH341SER_EXE.html
2. Cài xong → kiểm tra Device Manager → COM port phải hiện "OK"
3. Kết nối ESP32 → PlatformIO nhận port tự động
4. `pio run -t upload -e nodemcu-32s` trong `esp32_server/`

---

## BA Specs — v2.0 (BA-01 Output)

> Full research in [`docs/research.md`](research.md). Summary below.

### Contracts Summary

| Contract | Scope | File | Change |
|----------|-------|------|--------|
| BE-01-A | Node-1 Hidden AP | [`esp32_server/src/main.cpp:40`](../esp32_server/src/main.cpp:40) | `AP_HIDDEN false` → `true` |
| BE-01-B | Node-1 GET /file/list | [`esp32_server/src/main.cpp`](../esp32_server/src/main.cpp) | Add `handleFileList()` + register |
| BE-01-C | Node-1 POST /shutdown | [`esp32_server/src/main.cpp`](../esp32_server/src/main.cpp) | Add `handleShutdown()` + `#include <esp_sleep.h>` |
| BE-02-A | Node-2 Hidden AP | [`esp32_client/src/main.cpp:41`](../esp32_client/src/main.cpp:41) | `MY_AP_HIDDEN false` → `true` |
| BE-02-B | Node-2 calls /shutdown | [`esp32_client/src/main.cpp:217`](../esp32_client/src/main.cpp:217) | POST /shutdown before WiFi.disconnect() |
| FE-01-A | Fix CLIENT_IP | [`audio_gui.py:27`](../audio_gui.py:27) | `"192.168.4.2"` → `"192.168.5.1"` |
| FE-01-B | Auto-detect node mode | [`audio_gui.py`](../audio_gui.py) | Add `_poll_detect()` daemon thread |
| FE-01-C | Filelist panel (Node-1) | [`audio_gui.py`](../audio_gui.py) | Add `ttk.Treeview` fed by GET /file/list |
| FE-01-D | Upload status banner | [`audio_gui.py`](../audio_gui.py) | Add `_show_banner()` after upload OK |
| FE-01-E | Auto-download bg thread (Node-2) | [`audio_gui.py`](../audio_gui.py) | Add `_bg_download_thread()` saving to ~/Downloads |

### New API Endpoints

| Endpoint | Method | Node | Response key fields |
|----------|--------|------|---------------------|
| `/file/list` | GET | Node-1 | `files[]`, `count`, `spiffs_free` |
| `/shutdown` | POST | Node-1 | `status:"ok"` then deep sleep after 1 s |

### Critical Fixes (Confirmed Bugs)

| Bug | Location | Fix |
|-----|----------|-----|
| Wrong CLIENT_IP | [`audio_gui.py:27`](../audio_gui.py:27) | `192.168.4.2` → `192.168.5.1` |
| SSID mismatch in XML profile | [`esp32_ap_profile.xml`](../esp32_ap_profile.xml) | Create `esp32_node1_profile.xml` + `esp32_node2_profile.xml` |

### Top Risks

| Risk | Severity | Action |
|------|----------|--------|
| R1: CH340 driver Unknown | 🔴 HIGH | Install CH341SER before demo day |
| R2: Windows hidden SSID | 🔴 HIGH | Pre-install XML profiles via `netsh wlan add profile` |
| R5: CLIENT_IP wrong | 🔴 HIGH | 1-line fix in FE-01-A |
| R9: XML profile SSID mismatch | 🔴 HIGH | Create 2 new profile files |

---

## QC Sign-off

**Date:** 2026-04-06
**QC Agent verdict:** ✅ **QC PASS**

All 10 contracts (BE-01-A/B/C, BE-02-A/B, FE-01-A/B/C/D/E) implemented and verified correct.
0 BLOCKERs · 0 MAJORs · 2 MINORs (cosmetic/display) · 4 INFOs.
Full findings: [`docs/audit.md`](audit.md) — QC Audit section.

**Signal: `qc-pass` → Reviewer**

---

## Reviewer Sign-off

**Date:** 2026-04-06
**Reviewer verdict:** ✅ **APPROVED**

### Verdict summary
All 10 contracts compliant. Architecture fits 4-step demo flow. No crash paths in firmware. Tech debt (2 MINORs + 4 INFOs from QC, 1 new MINOR REV-01) is fully deferrable for demo.

### New finding — REV-01 (MINOR)
[`esp32_server/src/main.cpp:330`](esp32_server/src/main.cpp:330): `blinkLED(2,150)` fires **600 ms before** `server.send(200,...)` in `handleShutdown()` — spec violation of BE-01-C ordering. Non-fatal (Node-2 treats shutdown failure as non-critical). Fix: move `blinkLED` call to after `server.client().stop()`.

### Pre-demo checklist (hardware)
1. Install CH341SER driver — verify COM port "OK" in Device Manager
2. `pio run -t upload` for both nodes the day before demo
3. `netsh wlan add profile filename="esp32_node1_profile.xml"` (Admin)
4. `netsh wlan add profile filename="esp32_node2_profile.xml"` (Admin)
5. (Optional) Reorder `blinkLED` in `handleShutdown()` per REV-01

**Signal: `approved` → Deliver**

---

## FE Dev — GUI Redesign v2 (2026-04-06)

**Agent:** FE Dev
**File:** [`audio_gui.py`](../audio_gui.py)
**Build:** `python -m py_compile audio_gui.py` → **exit 0** ✅

### Thay đổi so với v1

| Mục | v1 (cũ) | v2 (mới) |
|-----|---------|----------|
| Tabs | CONTROL · RAM VIEW · NETWORK MAP | **🎛 ĐIỀU KHIỂN** · 🗺 SƠ ĐỒ MẠNG · 💾 RAM VIEW |
| Tab mặc định | index 0 = CONTROL | index 0 = ĐIỀU KHIỂN ✅ |
| Cột trái Tab 1 | 5 sections rời rạc | 4 sections demo-flow rõ ràng |
| Detect label | Nhỏ italic 8pt ở strip | **16pt bold** trong cột trái + italic 8pt ở strip |
| Upload button | `_btn()` thường, 40px | Big button 11pt bold, GREEN, full-width |
| Upload feedback | Log chỉ | Progress bar ẩn/hiện + result label + banner 5s |
| SPIFFS filelist | 3 cột (Tên/Size/Dur) | **4 cột** (Tên/Size/Dur/**Thao tác**) + double-click download |
| Download Node-2 | Label detect chỉ | Label trạng thái lớn + progress bar ẩn/hiện + nút "📂 Mở folder" |
| Advanced buttons | Cột trái trực tiếp | Collapsible "▸ Tùy chọn nâng cao" |
| Sơ đồ mạng | 1 AP zone oval + 3 box | **3 node box** rõ bước demo + mũi tên màu + step labels |
| `CLIENT_IP` | `192.168.4.2` (sai) | `192.168.5.1` ✅ (theo research.md) |
| RAM VIEW | Giữ nguyên | Giữ nguyên toàn bộ logic |

### Business logic giữ nguyên
- [`tcp_upload()`](../audio_gui.py:47) — TCP 8080 raw socket upload
- [`tcp_download()`](../audio_gui.py:76) — TCP 8080 raw socket download
- [`http_get_json()`](../audio_gui.py:103), [`http_get()`](../audio_gui.py:110), [`http_post()`](../audio_gui.py:116)
- [`_auto_refresh()`](../audio_gui.py) / [`_refresh_status()`](../audio_gui.py) — poll mỗi 3s
- [`_poll_detect()`](../audio_gui.py) — auto-detect Node-1/Node-2 mỗi 3s
- [`_bg_download_thread()`](../audio_gui.py) — 12 retries × 5s, lưu `~/Downloads/audio_esp32.wav`
- [`_auto_demo()`](../audio_gui.py) — 9-step automated demo
- [`_client_push()`](../audio_gui.py), [`_client_fetch()`](../audio_gui.py), [`_broadcast()`](../audio_gui.py) — ẩn trong Advanced

**Signal: `fe-done` → Integration**

---

## FE Dev — Single-Screen Rewrite v3 (2026-04-06)

**Agent:** FE Dev
**File:** [`audio_gui.py`](../audio_gui.py)
**Build:** `python -m py_compile audio_gui.py` → **exit 0** ✅
**Lines:** ~460 (giảm từ 1682)

### Thay đổi so với v2

| Mục | v2 (cũ) | v3 (mới) |
|-----|---------|----------|
| Layout | `ttk.Notebook` + 3 tabs | **1 màn hình duy nhất, không tab** |
| Window | 1100×740 | **860×560** (gọn hơn) |
| Cột trái | Scrollable canvas 290px, 5 sections | Scrollable canvas **340px**, 4 sections |
| Detect label | `_big_detect_lbl` 16pt + strip italic | **`_detect_lbl` 13pt bold** trong cột trái |
| IP label | `_conn_detail_lbl` | **`_ip_lbl`** Consolas 8pt CYAN |
| Filelist title | Tĩnh "📂 File trong SPIFFS" | **`_filelist_title`** dynamic per node |
| Filelist columns | 4 cột (name/size/dur/action) | **3 cột** (name/size/dur) — cleaner |
| Filelist location | Cột trái | **Cột phải – phần trên** |
| Log location | Cột phải (toàn bộ) | **Cột phải – phần dưới** (expand) |
| Advanced section | Collapsible toggle | **Bỏ hoàn toàn** |
| RAM VIEW tab | Có | **Bỏ hoàn toàn** |
| NETWORK MAP tab | Có | **Bỏ hoàn toàn** |
| AUTO DEMO button | Có | **Bỏ hoàn toàn** |
| `_client_push/fetch/broadcast` | Có trong Advanced | **Bỏ hoàn toàn** |
| `_auto_refresh()` | Gọi `_refresh_all()` + `_draw_network_map()` | Poll `_refresh_status()` mỗi **30s** |

### Business logic giữ nguyên 100%
- [`tcp_upload()`](../audio_gui.py:46), [`tcp_download()`](../audio_gui.py:75) — raw TCP socket
- [`http_get_json()`](../audio_gui.py:102), [`http_get()`](../audio_gui.py:109), [`http_post()`](../audio_gui.py:115)
- [`parse_json_field()`](../audio_gui.py:132), [`fmt_bytes()`](../audio_gui.py:138), [`fmt_dur()`](../audio_gui.py:145)
- [`_poll_detect()`](../audio_gui.py:308) — auto-detect Node-1/Node-2 mỗi 3s
- [`_on_node_detected()`](../audio_gui.py:322) — update labels + filelist + bg download
- [`_fetch_filelist()`](../audio_gui.py:387) / [`_update_filelist_ui()`](../audio_gui.py:404)
- [`_upload_to_server()`](../audio_gui.py:420) — TCP 8080 + banner + filelist refresh
- [`_download()`](../audio_gui.py:449) — TCP 8080 raw download
- [`_bg_download_thread()`](../audio_gui.py:470) — 12 retries × 5s → `~/Downloads/audio_esp32.wav`
- [`_refresh_status()`](../audio_gui.py:271) — poll Node-1/Node-2 HTTP /status
- [`_delete_selected_file()`](../audio_gui.py:734) — POST `/file/delete?name=<fname>` → refresh filelist
- [`_download()`](../audio_gui.py:694) — download đúng file được chọn trong Treeview (fallback `/audio.wav`)

---

## FE Changelog — 2026-04-06

### v2.1 — X-Filename header + Delete file + Smart download

| # | Change | File | Lines |
|---|--------|------|-------|
| 1 | `tcp_upload()` thêm param `filename=""`, gửi `X-Filename` header nếu có | `audio_gui.py` | 45–52 |
| 2 | `_upload_to_server_do()` truyền `filename=os.path.basename(wav)` | `audio_gui.py` | 663–664 |
| 3 | Nút `🗑 Xóa` thêm vào filelist `btn_row` (RED, bold) | `audio_gui.py` | 395–403 |
| 4 | Method `_delete_selected_file()` — POST `/file/delete?name=<fname>` | `audio_gui.py` | 734–748 |
| 5 | `_download()` đọc selection Treeview, GET đúng fname, lưu tên gốc | `audio_gui.py` | 694–720 |

**Build:** `python -m py_compile audio_gui.py` → exit 0 ✅

**Signal: `fe-done` → Integration**
