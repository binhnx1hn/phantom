# ESP32 Audio Demo — BA Research & Spec
**Version:** 2.0  
**Date:** 2026-04-06  
**Author:** BA Agent  
**Classification:** FEATURE (v1.0 → v2.0 Demo-Ready)

---

## 1. Source Audit Summary

| File | Key Finding |
|------|-------------|
| [`esp32_server/src/main.cpp:40`](../esp32_server/src/main.cpp:40) | `AP_HIDDEN false` — must flip to `true` |
| [`esp32_server/src/main.cpp:227`](../esp32_server/src/main.cpp:227) | `POST /file/upload` rejects body, redirects to TCP 8080 — no `/shutdown` endpoint exists |
| [`esp32_server/src/main.cpp:148`](../esp32_server/src/main.cpp:148) | `GET /status` returns `node:1` — usable for GUI auto-detect |
| [`esp32_client/src/main.cpp:41`](../esp32_client/src/main.cpp:41) | `MY_AP_HIDDEN false` — must flip to `true` |
| [`esp32_client/src/main.cpp:57`](../esp32_client/src/main.cpp:57) | AP IP is `192.168.5.1` — GUI currently has wrong `CLIENT_IP=192.168.4.2` |
| [`esp32_client/src/main.cpp:142`](../esp32_client/src/main.cpp:142) | `syncFromNode1()` complete but does NOT call `POST /shutdown` after sync |
| [`audio_gui.py:24`](../audio_gui.py:24) | `CLIENT_IP="192.168.4.2"` — wrong; Node-2 AP is `192.168.5.1` |
| [`audio_gui.py:47`](../audio_gui.py:47) | `tcp_upload()` uses raw TCP 8080 — works but GUI shows no filelist/banner |
| [`esp32_ap_profile.xml`](../esp32_ap_profile.xml) | Profile SSID is `ESP32-Audio-AP` — does NOT match Node-1 SSID `ESP32-Node-1` or Node-2 `ESP32-Node-2`; two separate profiles needed |

---

## 2. WiFi Hidden SSID — Windows Profile Spec

[`esp32_ap_profile.xml`](../esp32_ap_profile.xml) defines structure for connecting to hidden SSIDs on Windows via `netsh wlan add profile`.

**Two profiles required for demo:**

### Profile A — Node-1
```xml
<name>ESP32-Node-1</name>
<nonBroadcast>true</nonBroadcast>
<authentication>WPA2PSK</authentication>
<keyMaterial>12345678</keyMaterial>
```
Install: `netsh wlan add profile filename="esp32_node1_profile.xml"`

### Profile B — Node-2
```xml
<name>ESP32-Node-2</name>
<nonBroadcast>true</nonBroadcast>
<authentication>WPA2PSK</authentication>
<keyMaterial>12345678</keyMaterial>
```
Install: `netsh wlan add profile filename="esp32_node2_profile.xml"`

**Connect command:** `netsh wlan connect name="ESP32-Node-1"`

> ⚠️ Without XML profile, Windows cannot connect to hidden SSID via standard UI. Profile must be installed BEFORE demo.

---

## 3. Contracts

### CONTRACT BE-01-A — Node-1: Hidden AP
| Field | Value |
|-------|-------|
| **Goal** | Node-1 AP broadcasts hidden SSID so it is invisible in WiFi scan list |
| **Constraints** | Change only [`AP_HIDDEN`](../esp32_server/src/main.cpp:40) from `false` → `true`; no other WiFi config change; password/channel unchanged |
| **Output** | `WiFi.softAP("ESP32-Node-1","12345678",1,true,4)` — 4th arg `true`; verified via laptop WiFi scan showing no "ESP32-Node-1" in list; XML profile connects successfully |
| **Failure** | AP still visible in scan → `softAP()` 4th param not set; verify `AP_HIDDEN` define is consumed at [`esp32_server/src/main.cpp:410`](../esp32_server/src/main.cpp:410) equivalent call |

---

### CONTRACT BE-01-B — Node-1: GET /file/list Endpoint
| Field | Value |
|-------|-------|
| **Goal** | Expose list of files on SPIFFS so GUI can render filelist panel |
| **Constraints** | Must register on HTTP port 80; must return valid JSON; `spiffs_free` must use `SPIFFS.totalBytes()-SPIFFS.usedBytes()`; max file count in demo = 1 (`/audio.wav`) |
| **Output** | See §4.1 API Contract below; registered in `setup()` as `server.on("/file/list", HTTP_GET, handleFileList)` |
| **Failure** | Returns 404 → handler not registered; returns empty array when file exists → `SPIFFS.open("/","r")` directory iteration bug; `spiffs_free` = 0 → wrong calculation |

---

### CONTRACT BE-01-C — Node-1: POST /shutdown Endpoint
| Field | Value |
|-------|-------|
| **Goal** | Node-1 enters deep sleep (permanent off) after Node-2 confirms file received |
| **Constraints** | Must send HTTP 200 response BEFORE sleeping; delay ≥ 1000 ms between response and `esp_deep_sleep_start()`; no wake stub needed (demo never wakes Node-1 again); include `#include <esp_sleep.h>` |
| **Output** | See §4.2 API Contract; Node-1 LED blinks 2× fast then goes dark; `esp_deep_sleep_start()` called |
| **Failure** | Response never sent (client times out) → response flushed before delay; Node-1 restarts instead of sleeping → must use `esp_deep_sleep_start()` not `ESP.restart()` |

---

### CONTRACT BE-02-A — Node-2: Hidden AP
| Field | Value |
|-------|-------|
| **Goal** | Node-2 AP broadcasts hidden SSID; Laptop-2 connects via XML profile |
| **Constraints** | Change only [`MY_AP_HIDDEN`](../esp32_client/src/main.cpp:41) from `false` → `true`; channel 6 preserved (different from Node-1 channel 1) |
| **Output** | `WiFi.softAP(MY_AP_SSID,MY_AP_PASSWORD,MY_AP_CHANNEL,true,MY_AP_MAX_CON)` at [`esp32_client/src/main.cpp:400`](../esp32_client/src/main.cpp:400) |
| **Failure** | Node-2 AP still visible → `MY_AP_HIDDEN` define not passed to `softAP()` |

---

### CONTRACT BE-02-B — Node-2: Call POST /shutdown After Sync
| Field | Value |
|-------|-------|
| **Goal** | After successful file sync + LED blink, Node-2 signals Node-1 to shut down |
| **Constraints** | Call only when `syncDone == true` and `ramReady == true`; use existing `WiFiClient` TCP or `HTTPClient`; call AFTER `blinkLED(5,80)` and AFTER `WiFi.disconnect(false)` — must reconnect STA briefly or call before disconnect; timeout 3s |
| **Output** | `POST http://192.168.4.1/shutdown` returns 200; Node-1 enters deep sleep; Serial prints `[Sync] Shutdown Node-1 OK` |
| **Failure** | Shutdown call before WiFi.disconnect → timing issue resolved by calling shutdown before `WiFi.disconnect(false)` at [`esp32_client/src/main.cpp:217`](../esp32_client/src/main.cpp:217); 404 response → Node-1 firmware not updated |

---

### CONTRACT FE-01-A — GUI: Fix CLIENT_IP
| Field | Value |
|-------|-------|
| **Goal** | GUI correctly addresses Node-2 AP |
| **Constraints** | Change [`CLIENT_IP`](../audio_gui.py:27) from `"192.168.4.2"` → `"192.168.5.1"`; update `CLIENT_HTTP=80`, `CLIENT_AUDIO=8080` (ports unchanged) |
| **Output** | All `http_get(CLIENT_IP,...)` calls reach Node-2 HTTP server correctly |
| **Failure** | Connection timeout to Node-2 → IP still wrong |

---

### CONTRACT FE-01-B — GUI: Auto-Detect Node Mode
| Field | Value |
|-------|-------|
| **Goal** | GUI polls `/status` on both known IPs and automatically shows the correct panel (upload for Node-1, download for Node-2) |
| **Constraints** | Poll interval 3 s; try `192.168.4.1` first then `192.168.5.1`; parse `"node"` field; run in daemon thread; do NOT block main thread; auto-detect starts after `after(800,...)` existing timer |
| **Output** | See §5.1 GUI Logic Contract; `_detected_node` variable set to `1` or `2`; UI panel switches automatically; status strip shows "🟢 Node-1 detected" or "🟢 Node-2 detected" |
| **Failure** | Both IPs unreachable → show "⚪ No ESP32 found — check WiFi"; wrong panel shown → `node` field parsed incorrectly |

---

### CONTRACT FE-01-C — GUI: Filelist Panel (Node-1)
| Field | Value |
|-------|-------|
| **Goal** | When connected to Node-1, show list of files on SPIFFS with name, size, duration, download button |
| **Constraints** | Call `GET /file/list` (new) or fall back to `GET /file/info`; refresh every 5 s or after upload; table columns: Filename \| Size \| Duration \| Action |
| **Output** | Tkinter `ttk.Treeview` or Frame-based table inside CONTROL tab left panel; "📂 No files" placeholder when empty; "⬇ Download" button per row triggers `tcp_download()` |
| **Failure** | Table empty despite file existing → `/file/list` not returning `files` array; download button does nothing → callback not bound |

---

### CONTRACT FE-01-D — GUI: Upload Status Banner
| Field | Value |
|-------|-------|
| **Goal** | After successful upload, show a prominent green banner with file size |
| **Constraints** | Banner height 36px; background `#22c55e`; text `"✅ Upload thành công! {size_kb} KB"`; auto-hide after 5000 ms using `after(5000, banner.destroy)`; shown via `place()` or `pack()` at top of CONTROL tab |
| **Output** | Banner appears within 200 ms of upload TCP response; disappears after 5 s; on failure show red banner `"❌ Upload thất bại: {error}"` |
| **Failure** | Banner never shows → upload success path not triggering banner call; banner stays forever → `after()` cancel not working; check `self.after(5000,...)` called on main thread |

---

### CONTRACT FE-01-E — GUI: Auto-Download Background Thread (Node-2)
| Field | Value |
|-------|-------|
| **Goal** | When GUI detects Node-2, automatically download file to `~/Downloads/audio_esp32.wav` in background; when user opens GUI manually the file is already present |
| **Constraints** | Single daemon thread; poll every 5 s until `data > 44 bytes`; max 12 retries (60 s total); save path `os.path.join(os.path.expanduser("~"), "Downloads", "audio_esp32.wav")`; do NOT overwrite if file already exists and `size > 44` |
| **Output** | File written to Downloads; banner shows `"✅ File đã sẵn sàng trong Downloads!"`; `_bg_downloaded` flag set `True`; thread exits |
| **Failure** | Thread runs but file size 0 → Node-2 has no file yet (sync not complete); `PermissionError` on Downloads path → fallback to Desktop; banner not shown → call `self.after(0, show_banner, msg)` from thread (not direct widget update) |

---

## 4. API Contracts

### 4.1 GET /file/list (Node-1 NEW)

**Endpoint:** `GET http://192.168.4.1/file/list`  
**Handler:** `handleFileList()` — register in [`esp32_server/src/main.cpp`](../esp32_server/src/main.cpp) `setup()`

**Response 200:**
```json
{
  "files": [
    {
      "name": "audio.wav",
      "path": "/audio.wav",
      "size": 234567,
      "size_kb": "229.1 KB",
      "duration_sec": 5.32
    }
  ],
  "count": 1,
  "spiffs_total": 1458176,
  "spiffs_used": 234567,
  "spiffs_free": 1223609
}
```

**Response when empty:**
```json
{ "files": [], "count": 0, "spiffs_total": 1458176, "spiffs_used": 0, "spiffs_free": 1458176 }
```

**Implementation notes:**
- Use `SPIFFS.open("/", "r")` to iterate directory
- For each file, open and read 44-byte WAV header to extract `duration_sec`
- `size_kb` = `snprintf("%.1f KB", size/1024.0f)`
- No authentication required

---

### 4.2 POST /shutdown (Node-1 NEW)

**Endpoint:** `POST http://192.168.4.1/shutdown`  
**Handler:** `handleShutdown()` — register in `setup()`  
**Body:** empty (no payload required)

**Response 200 (sent BEFORE sleep):**
```json
{ "status": "ok", "message": "Entering deep sleep", "uptime_ms": 12345 }
```

**Response 503 (if called while upload in progress — optional guard):**
```json
{ "status": "error", "message": "Upload in progress" }
```

**Implementation (C++ pseudocode):**
```cpp
void handleShutdown() {
  String resp = "{\"status\":\"ok\",\"message\":\"Entering deep sleep\","
                "\"uptime_ms\":" + String(millis()) + "}";
  server.send(200, "application/json", resp);
  server.client().flush();
  server.client().stop();
  delay(1000);
  blinkLED(2, 150);   // visual confirm
  Serial.println("[Shutdown] Deep sleep now");
  esp_deep_sleep_start();   // requires #include <esp_sleep.h>
}
```

**Caller (Node-2):** calls before `WiFi.disconnect(false)` inside `syncFromNode1()`  
**Includes required:** `#include <esp_sleep.h>`

---

### 4.3 GET /status — Response Fields (Both Nodes, for GUI detect)

Node-1 [`handleStatus()`](../esp32_server/src/main.cpp:149) already returns `"node":1`.  
Node-2 [`handleStatus()`](../esp32_client/src/main.cpp:234) already returns `"node":2`.

**GUI detection algorithm:**
```
1. GET http://192.168.4.1/status  →  parse "node" field
2. GET http://192.168.5.1/status  →  parse "node" field
3. First 200 response wins
4. If node==1 → show Upload + Filelist mode
5. If node==2 → show Download mode + start bg thread
6. If both fail → show offline state
```

---

## 5. GUI Spec

### 5.1 Auto-Detect Logic

```
Class: App
New field: _detected_node: int | None = None
New field: _bg_dl_started: bool = False
New field: _bg_downloaded: bool = False

Method: _poll_detect() [daemon thread, period 3s]
  candidates = [("192.168.4.1", 80), ("192.168.5.1", 80)]
  for (ip, port) in candidates:
    data = http_get_json(f"http://{ip}:{port}/status", timeout=2)
    if data and "node" in data:
      node = int(data["node"])
      if node != self._detected_node:
        self._detected_node = node
        self.after(0, self._on_node_detected, node, ip)
      break
  schedule next call: self.after(3000, lambda: thread(_poll_detect))
```

### 5.2 On Node-1 Detected

```
_on_node_detected(node=1, ip="192.168.4.1"):
  - Update status strip: "🟢 Node-1 (192.168.4.1) — Upload mode"
  - Show upload panel (existing _build_left_panel)
  - Refresh filelist: call GET /file/list → render _filelist_frame
  - Schedule filelist refresh every 5s
```

### 5.3 On Node-2 Detected

```
_on_node_detected(node=2, ip="192.168.5.1"):
  - Update status strip: "🟢 Node-2 (192.168.5.1) — Download mode"
  - Hide upload buttons, show download status
  - If not _bg_dl_started:
      _bg_dl_started = True
      start daemon thread: _bg_download_thread(ip)
```

### 5.4 Background Download Thread

```python
def _bg_download_thread(self, node2_ip: str):
    save_path = os.path.join(os.path.expanduser("~"), "Downloads", "audio_esp32.wav")
    # Skip if already downloaded
    if os.path.exists(save_path) and os.path.getsize(save_path) > 44:
        self._bg_downloaded = True
        self.after(0, self._show_banner, "✅ File đã sẵn sàng trong Downloads!", "green")
        return
    retries = 0
    while retries < 12 and not self._bg_downloaded:
        data = tcp_download(node2_ip, 8080, "/audio.wav", timeout=20)
        if len(data) > 44:
            try:
                with open(save_path, "wb") as f:
                    f.write(data)
                self._bg_downloaded = True
                self.after(0, self._show_banner,
                           f"✅ File đã sẵn sàng! {len(data)//1024} KB → Downloads", "green")
                return
            except PermissionError:
                # Fallback: Desktop
                fallback = os.path.join(os.path.expanduser("~"), "Desktop", "audio_esp32.wav")
                with open(fallback, "wb") as f:
                    f.write(data)
                self._bg_downloaded = True
                self.after(0, self._show_banner,
                           f"✅ File lưu tại Desktop! {len(data)//1024} KB", "green")
                return
        retries += 1
        time.sleep(5)
    if not self._bg_downloaded:
        self.after(0, self._show_banner, "⚠️ Không tải được file từ Node-2", "red")
```

### 5.5 Upload Banner Spec

```python
def _show_banner(self, message: str, color: str = "green"):
    """color: 'green' | 'red' | 'yellow'"""
    COLOR_MAP = {"green": "#22c55e", "red": "#ef4444", "yellow": "#f59e0b"}
    bg = COLOR_MAP.get(color, "#22c55e")
    if hasattr(self, "_banner") and self._banner:
        try: self._banner.destroy()
        except: pass
    banner = tk.Frame(self, bg=bg, height=36)
    banner.pack(fill="x", padx=10, pady=(2,0))
    banner.pack_propagate(False)
    tk.Label(banner, text=message, bg=bg, fg="white",
             font=("Segoe UI", 11, "bold")).pack(expand=True)
    self._banner = banner
    self.after(5000, lambda: banner.destroy() if banner.winfo_exists() else None)
```

### 5.6 Filelist Panel Spec

```
Widget: ttk.Treeview with columns ["name", "size", "duration", "action"]
Location: Inside _build_left_panel, below upload buttons
Refresh trigger: after upload success, after detect Node-1, every 5s
Data source:
  - Node-1: GET /file/list  (new endpoint)
  - Node-2: GET /file/info  (existing, single file)
Columns:
  #0 (icon): "📄"
  name:       "Tên file"      width=120
  size:       "Kích thước"    width=90
  duration:   "Thời lượng"    width=80
  action:     [Download btn]  width=80   ← use ttk.Button in cell or right-click menu
Empty state: Single row "📂 Chưa có file"
```

---

## 6. WiFi Profile Files Required

Two XML profile files must be added to project root (matching structure of [`esp32_ap_profile.xml`](../esp32_ap_profile.xml)):

| File | SSID | For |
|------|------|-----|
| `esp32_node1_profile.xml` | `ESP32-Node-1` | Laptop-1, Bước 1 |
| `esp32_node2_profile.xml` | `ESP32-Node-2` | Laptop-2, Bước 4 |

The existing [`esp32_ap_profile.xml`](../esp32_ap_profile.xml) uses SSID `ESP32-Audio-AP` — this is the **old topology** name and does NOT match current Node SSIDs. It should be deprecated or renamed.

**Install commands (run as Admin on Windows):**
```bat
netsh wlan add profile filename="esp32_node1_profile.xml"
netsh wlan add profile filename="esp32_node2_profile.xml"
netsh wlan connect name="ESP32-Node-1"
```

---

## 7. Risk Register

| ID | Risk | Severity | Likelihood | Mitigation |
|----|------|----------|------------|------------|
| R1 | **CH340 driver "Unknown"** on Windows 10 — COM port inaccessible, cannot flash firmware | 🔴 HIGH | HIGH (known issue) | Install CH341SER from https://www.wch.cn/downloads/CH341SER_EXE.html; verify Device Manager shows "OK" before demo; pre-flash both nodes day before |
| R2 | **Windows blocks hidden SSID** without pre-installed XML profile | 🔴 HIGH | HIGH | Pre-install both XML profiles; test connection day before; have USB hotspot as fallback |
| R3 | **Node-2 sync fails** if Node-1 not ready when Node-2 boots (race condition) | 🟡 MED | MED | Node-2 [`setup()`](../esp32_client/src/main.cpp:438) has `delay(1000)` before sync; if fails → Node-2 uses built-in WAV; add POST /sync retry button in GUI |
| R4 | **SPIFFS corruption** after repeated write cycles (flash endurance) | 🟡 MED | LOW | `SPIFFS.begin(true)` auto-formats on mount failure; demo file written once; acceptable risk |
| R5 | **GUI CLIENT_IP wrong** — currently `192.168.4.2` should be `192.168.5.1` | 🔴 HIGH | CONFIRMED | Fix in FE-01-A contract; single-line change in [`audio_gui.py:27`](../audio_gui.py:27) |
| R6 | **Post /shutdown called before TCP disconnect** — Node-2 STA disconnects, then tries to reach Node-1 | 🟡 MED | MED | Reorder: call `POST /shutdown` while STA still connected, THEN `WiFi.disconnect(false)`; see BE-02-B contract |
| R7 | **Tkinter widget update from non-main thread** — `RuntimeError` crash | 🟡 MED | HIGH | All GUI updates use `self.after(0, callback)` pattern; direct widget calls from threads forbidden |
| R8 | **WAV file > 400KB** rejected by SPIFFS (MAX_FILE_SIZE limit) | 🟢 LOW | LOW | User must provide WAV ≤ 400KB for demo; GUI shows file size at selection; add warning if > 350KB |
| R9 | **`esp32_ap_profile.xml` SSID mismatch** — file has `ESP32-Audio-AP` but nodes use `ESP32-Node-1`/`ESP32-Node-2` | 🔴 HIGH | CONFIRMED | Create two new profile XML files; existing file is legacy |
| R10 | **Deep sleep irreversible during demo** — accidental `POST /shutdown` before Node-2 syncs | 🟡 MED | LOW | Add guard: Node-1 `handleShutdown()` rejects if no SPIFFS file exists; GUI shutdown button hidden in Node-1 mode |

---

## 8. Change Impact Matrix

| Change | File | Line | Type | Risk |
|--------|------|------|------|------|
| `AP_HIDDEN = true` | [`esp32_server/src/main.cpp:40`](../esp32_server/src/main.cpp:40) | 40 | 1-char | R2 |
| Add `handleFileList()` + register | [`esp32_server/src/main.cpp`](../esp32_server/src/main.cpp) | ~245 new | NEW fn | R4 |
| Add `handleShutdown()` + register | [`esp32_server/src/main.cpp`](../esp32_server/src/main.cpp) | ~260 new | NEW fn | R10 |
| `#include <esp_sleep.h>` | [`esp32_server/src/main.cpp:29`](../esp32_server/src/main.cpp:29) | 29 | include | — |
| `MY_AP_HIDDEN = true` | [`esp32_client/src/main.cpp:41`](../esp32_client/src/main.cpp:41) | 41 | 1-char | R2 |
| Call `POST /shutdown` in `syncFromNode1()` | [`esp32_client/src/main.cpp:217`](../esp32_client/src/main.cpp:217) | ~214 | 5 lines | R6 |
| Fix `CLIENT_IP` | [`audio_gui.py:27`](../audio_gui.py:27) | 27 | 1-char | R5 |
| Add `_poll_detect()` thread | [`audio_gui.py`](../audio_gui.py) | new | NEW fn | R7 |
| Add `_bg_download_thread()` | [`audio_gui.py`](../audio_gui.py) | new | NEW fn | R7 |
| Add `_show_banner()` | [`audio_gui.py`](../audio_gui.py) | new | NEW fn | — |
| Add filelist `ttk.Treeview` | [`audio_gui.py`](../audio_gui.py) | new | UI widget | — |
| Create `esp32_node1_profile.xml` | project root | new | NEW file | R2/R9 |
| Create `esp32_node2_profile.xml` | project root | new | NEW file | R2/R9 |

---

## 9. Acceptance Criteria — Demo Flow

### Bước 1 ✅ PASS when:
- [ ] WiFi scan on Laptop-1 does NOT show "ESP32-Node-1"
- [ ] Laptop-1 connects via XML profile
- [ ] GUI auto-detects Node-1 within 5 s of opening
- [ ] Upload WAV file → progress shows → green banner "✅ Upload thành công! {N} KB"
- [ ] Filelist panel refreshes showing `audio.wav` with size and duration

### Bước 2 ✅ PASS when:
- [ ] Node-1 LED blinks exactly 3× after reboot with SPIFFS file present
- [ ] `GET /status` still returns `spiffs_has_file: true` after reboot

### Bước 3 ✅ PASS when:
- [ ] Node-2 LED blinks exactly 5× after sync
- [ ] Node-2 `GET /status` returns `sync_done: true, spiffs_has_file: true`
- [ ] Node-1 becomes unreachable within 3 s of Node-2 sync completion (deep sleep)
- [ ] Node-1 LED goes dark

### Bước 4 ✅ PASS when:
- [ ] WiFi scan on Laptop-2 does NOT show "ESP32-Node-2"
- [ ] Laptop-2 connects via XML profile
- [ ] GUI auto-detects Node-2 within 5 s
- [ ] `~/Downloads/audio_esp32.wav` exists and size > 44 bytes within 60 s
- [ ] Banner shows "✅ File đã sẵn sàng trong Downloads!"
- [ ] File playable in media player

---

## 10. BA Sign-off

**Spec status:** READY FOR IMPLEMENTATION  
**Pending dev tasks:** BE-01, BE-02, FE-01 (see [`docs/project.md`](project.md) Task Board)  
**Signal to PM:** `spec-ready` → pm
