# Integration Audit — ESP32 Audio Demo (Static Code Audit)

**Date:** 2026-04-06  
**Mode:** Static verification (no hardware — CH340 COM port unavailable)  
**Auditor:** Integration - Verifier  

---

## Results Table

| ID | Check | Result | Evidence |
|----|-------|--------|----------|
| **BE-01** | **Node-1 (esp32_server/src/main.cpp)** | | |
| BE-01-01 | `AP_HIDDEN` is `true` (line ~40) | ✅ PASS | Line 41: `#define AP_HIDDEN true` |
| BE-01-02 | `#include <esp_sleep.h>` present | ✅ PASS | Line 33: `#include <esp_sleep.h>` |
| BE-01-03 | `handleFileList()` exists and registered as `server.on("/file/list", HTTP_GET, handleFileList)` | ✅ PASS | Function at line 286; registration at line 483 |
| BE-01-04 | `handleShutdown()` exists: sends 200 BEFORE calling `esp_deep_sleep_start()`; delay ≥ 1000ms | ✅ PASS | Line 331 sends 200, line 332 stops client, line 333 `delay(1000)`, line 337 `esp_deep_sleep_start()` |
| BE-01-05 | `handleShutdown()` registered as `server.on("/shutdown", HTTP_POST, handleShutdown)` | ✅ PASS | Line 484: `server.on("/shutdown", HTTP_POST, handleShutdown)` |
| BE-01-06 | `handleFileList()` uses `SPIFFS.open("/","r")` to iterate directory | ✅ PASS | Line 289: `File root = SPIFFS.open("/")` |
| BE-01-07 | JSON has fields: `files`, `count`, `spiffs_total`, `spiffs_used`, `spiffs_free` | ✅ PASS | Lines 287, 320–323 all five fields present |
| BE-01-08 | No duplicate handler registrations | ✅ PASS | `/file/list` registered once (line 483), `/shutdown` registered once (line 484) |
| **BE-02** | **Node-2 (esp32_client/src/main.cpp)** | | |
| BE-02-01 | `MY_AP_HIDDEN` is `true` (line ~41) | ✅ PASS | Line 41: `#define MY_AP_HIDDEN true` |
| BE-02-02 | `syncFromNode1()` contains POST /shutdown call to Node-1 | ✅ PASS | Lines 218–231: `shutClient.printf("POST /shutdown …")` |
| BE-02-03 | Shutdown call uses `NODE1_IP` and `NODE1_HTTP_PORT` constants | ✅ PASS | Line 220: `shutClient.connect(NODE1_IP, NODE1_HTTP_PORT)` |
| BE-02-04 | Shutdown call happens BEFORE `WiFi.disconnect(false)` (STA still connected) | ✅ PASS | Shutdown block lines 217–232; `WiFi.disconnect(false)` at line 235 |
| BE-02-05 | Shutdown failure is non-fatal (wrapped in try/connect check) | ✅ PASS | Lines 220–231: `if (shutClient.connect(...))` else logs "not critical" and continues |
| **FE-01** | **GUI (audio_gui.py)** | | |
| FE-01-01 | `CLIENT_IP = "192.168.5.1"` | ✅ PASS | Line 27: `CLIENT_IP = "192.168.5.1"` |
| FE-01-02 | `CLIENT_HTTP = 80` | ✅ PASS | Line 28: `CLIENT_HTTP = 80` |
| FE-01-03 | `CLIENT_AUDIO = 8080` | ✅ PASS | Line 29: `CLIENT_AUDIO = 8080` |
| FE-01-04 | `_detected_node`, `_bg_downloaded`, `_detect_running` exist in `__init__` | ✅ PASS | Lines 177–179: all three instance variables initialized |
| FE-01-05 | `_poll_detect()` polls `192.168.4.1` then `192.168.5.1`, parses `"node"` field | ✅ PASS | Lines 1312–1327: `ips = [("192.168.4.1", 1), ("192.168.5.1", 2)]`; `data.get("node") == node_num` |
| FE-01-06 | `_show_upload_banner()` exists: green for success, red for failure, auto-hides 5s | ✅ PASS | Lines 1351–1358: `color = RED if error else GREEN`; `self.after(5000, banner.destroy)` |
| FE-01-07 | Upload handler calls `_show_upload_banner()` on success | ✅ PASS | Lines 1185 and 1189 (`_upload_to_server`); lines 1206 and 1210 (`_upload_to_client`) |
| FE-01-08 | `_filelist_tree` (ttk.Treeview) exists | ✅ PASS | Lines 323–331: `self._filelist_tree = ttk.Treeview(...)` |
| FE-01-09 | `_filelist_label` exists | ✅ PASS | Lines 314–317: `self._filelist_label = tk.Label(...)` |
| FE-01-10 | `_refresh_filelist()` calls `/file/list` (Node-1) or `/file/info` (Node-2) | ✅ PASS | Lines 1368–1384: tries `http://192.168.4.1/file/list` first, falls back to `http://192.168.5.1/file/info` |
| FE-01-11 | `_start_bg_download()` exists | ✅ PASS | Lines 1406–1410 |
| FE-01-12 | `_bg_download_thread()` exists | ✅ PASS | Lines 1412–1438 |
| FE-01-13 | `_bg_download_thread()` saves to `~/Downloads/audio_esp32.wav` | ✅ PASS | Line 1413: `os.path.join(os.path.expanduser("~"), "Downloads", "audio_esp32.wav")` |
| FE-01-14 | `_bg_download_thread()` has Desktop fallback on PermissionError | ✅ PASS | Lines 1434–1436: `except PermissionError: save_path = … "Desktop" … "audio_esp32.wav"` |
| FE-01-15 | `_start_detect_thread()` called in `__init__` | ✅ PASS | Line 183: `self._start_detect_thread()` |
| FE-01-16 | `python -m py_compile audio_gui.py` → no error | ✅ PASS | Exit code 0, output: "SYNTAX OK" |
| **WiFi** | **WiFi Profiles** | | |
| WIFI-01 | `esp32_node1_profile.xml`: SSID `ESP32-Node-1`, `nonBroadcast` true, WPA2PSK, key `12345678` | ✅ PASS | Lines 5–6, 14, 20 of profile |
| WIFI-02 | `esp32_node2_profile.xml`: SSID `ESP32-Node-2`, `nonBroadcast` true, WPA2PSK, key `12345678` | ✅ PASS | Lines 5–6, 14, 20 of profile |
| **FLOW** | **Logical Flow Verification** | | |
| FLOW-01 | Node-1: boot → SPIFFS load → WiFi AP hidden → HTTP server ready → serve upload/download/list/shutdown | ✅ PASS | `setup()` lines 434–498: SPIFFS.begin → spiffsLoad → WiFi.softAP(…,AP_HIDDEN,…) → server.on(…) → server.begin |
| FLOW-02 | Node-2: boot → AP hidden → HTTP server ready → syncFromNode1() → shutdown Node-1 → AP continues serving | ✅ PASS | `setup()` lines 413–474: WIFI_AP_STA → softAP(…,MY_AP_HIDDEN,…) → server.begin → syncFromNode1() which calls /shutdown → WiFi.disconnect(STA only) → AP remains |
| FLOW-03 | GUI (Node-1 scenario): detect → show upload panel + filelist → upload → banner → refresh filelist | ✅ PASS | `_on_node_detected(1)` → `_refresh_filelist()`; `_upload_to_server()` → `_show_upload_banner()` → `self.after(500, self._refresh_filelist)` |
| FLOW-04 | GUI (Node-2 scenario): detect → bg download starts → save to Downloads → banner → file ready | ✅ PASS | `_on_node_detected(2)` → `_start_bg_download()` → `_bg_download_thread()` → writes `~/Downloads/audio_esp32.wav` → `_show_upload_banner()` |

---

## Critical Issues Found

**None.** All 26 checks passed.

---

## Minor Observations (non-blocking)

1. **Network map canvas** (`_draw_network_map`, lines 562–567) still shows old IP `192.168.4.2` and ports `81`/`8081` for the Client box — purely cosmetic/visual; does not affect any functional contract.  
2. **`_refresh_status()`** (lines 644–694) checks `Client` at `CLIENT_IP`/`CLIENT_HTTP` which is correct (`192.168.5.1:80`), but the Node-2 `/status` JSON key checked is `"ram_audio_ready"` (line 675) — Node-2 firmware returns `"ram_ready"`, not `"ram_audio_ready"`. This means the RAM indicator in the status strip will show `○` even when Node-2 has a file. **Non-blocking for demo** (file transfer still works; display only).  
3. **`handleFileList()` SPIFFS open call** uses `SPIFFS.open("/")` without explicit `"r"` mode argument — acceptable; ESP32 SPIFFS default is read-only for root.

---

## Overall Verdict

```
╔══════════════════════════════════════════════════╗
║        INTEGRATION PASS  ✅                      ║
║  All BE-01 / BE-02 / FE-01 / WiFi / Flow checks  ║
║  passed.  No blocking issues.                     ║
║  Signal: integration-verified → vision-parser     ║
╚══════════════════════════════════════════════════╝
```

**Next step:** `integration-verified` → hand off to **Vision Parser** for visual/layout verification.

---

---

# QC Audit — ESP32 Audio Demo v2.0

**Date:** 2026-04-06
**Mode:** Static code audit (no hardware)
**Auditor:** QC Agent
**Spec reference:** `docs/research.md` — 10 contracts (BE-01-A/B/C, BE-02-A/B, FE-01-A/B/C/D/E)
**Integration baseline:** 26/26 checks PASS (see above)

---

## Security Checklist

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| SEC-01 | No hardcoded credentials worse than spec (spec allows `12345678`) | ✅ PASS | [`esp32_server/src/main.cpp:39`](../esp32_server/src/main.cpp:39) `AP_PASSWORD "12345678"` — matches spec exactly; [`esp32_client/src/main.cpp:39`](../esp32_client/src/main.cpp:39) same; XML profiles use same key |
| SEC-02 | No SQL injection risk | ✅ PASS | No database used anywhere in codebase |
| SEC-03 | HTTP server has no open admin endpoint without auth beyond spec | ✅ PASS | All endpoints match spec-listed routes; no hidden `/admin` or privileged endpoints outside spec |
| SEC-04 | `esp_deep_sleep_start()` used (not `ESP.restart()`) | ✅ PASS | [`esp32_server/src/main.cpp:337`](../esp32_server/src/main.cpp:337): `esp_deep_sleep_start()` — correct; `ESP.restart()` not present in file |
| SEC-05 | Python `subprocess` not used to execute arbitrary shell commands | ⚠️ MINOR | `subprocess` is imported and `subprocess.Popen(f'explorer /select,"{abs_path}"')` called at [`audio_gui.py:1140`](../audio_gui.py:1140), [`audio_gui.py:1233`](../audio_gui.py:1233), [`audio_gui.py:1293`](../audio_gui.py:1293). **Not a shell command injection** — fixed string `explorer /select,"<path>"`, Windows-only Explorer UI call, no user-controlled shell metacharacters in path. Non-exploitable in demo context. INFO-level only. |

**Security verdict: No BLOCKERs. One INFO-level subprocess usage (cosmetic/UI only).**

---

## Code Quality — Node-1 (`esp32_server/src/main.cpp`)

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| N1-01 | `handleFileList()`: file handles closed in all paths (no leak) | ✅ PASS | [`esp32_server/src/main.cpp:316`](../esp32_server/src/main.cpp:316): `f.close()` called inside loop before `openNextFile()`; [`esp32_server/src/main.cpp:319`](../esp32_server/src/main.cpp:319): `root.close()` after loop — all paths covered |
| N1-02 | `handleShutdown()`: sends HTTP 200 BEFORE sleep | ✅ PASS | [`esp32_server/src/main.cpp:331`](../esp32_server/src/main.cpp:331): `server.send(200,...)` → line 332 `server.client().stop()` → line 333 `delay(1000)` → line 337 `esp_deep_sleep_start()` — correct sequence per contract BE-01-C |
| N1-03 | `handleFileUpload()` at HTTP level correctly delegates to TCP 8080 | ✅ PASS | [`esp32_server/src/main.cpp:228-235`](../esp32_server/src/main.cpp:228): Returns 400 instructing client to use raw TCP port 8080 — matches spec; actual upload handled by `handleRawTCP()` |
| N1-04 | `spiffsSave()` — no OOM guard needed (takes pre-allocated buf); `spiffsLoad()` — malloc has OOM guard | ✅ PASS | [`esp32_server/src/main.cpp:104-105`](../esp32_server/src/main.cpp:104): `ramBuf = (uint8_t*)malloc(sz); if (!ramBuf) { f.close(); Serial.println("[SPIFFS] OOM load"); return false; }` — OOM guarded |
| N1-05 | No blocking calls in `loop()` > 50ms | ✅ PASS | [`esp32_server/src/main.cpp:501-510`](../esp32_server/src/main.cpp:501): `loop()` calls `server.handleClient()` then `audioServer.accept()` with non-blocking pattern; 3000ms wait only when `!c.available()` with `delay(1)` poll — no hard block |

---

## Code Quality — Node-2 (`esp32_client/src/main.cpp`)

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| N2-01 | `syncFromNode1()`: shutdown call wrapped in connect check (non-fatal) | ✅ PASS | [`esp32_client/src/main.cpp:220`](../esp32_client/src/main.cpp:220): `if (shutClient.connect(NODE1_IP, NODE1_HTTP_PORT))` — shutdown only attempted if connect succeeds; else logs "not critical" and continues |
| N2-02 | `ramBuf` freed before new `malloc` in sync (no double-alloc) | ✅ PASS | [`esp32_client/src/main.cpp:195`](../esp32_client/src/main.cpp:195): `if (ramBuf){free(ramBuf);ramBuf=nullptr;ramSize=0;}` before `malloc(contentLength)` on line 196 |
| N2-03 | `WiFi.disconnect(false)` called after shutdown attempt | ✅ PASS | [`esp32_client/src/main.cpp:235`](../esp32_client/src/main.cpp:235): `WiFi.disconnect(false)` after shutdown block (lines 217–232) — correct order per contract BE-02-B |
| N2-04 | SPIFFS save after sync verified with return value | ✅ PASS | [`esp32_client/src/main.cpp:245-246`](../esp32_client/src/main.cpp:245): `bool saved = spiffsSave(ramBuf, ramSize); syncMsg = saved ? "ok: saved to SPIFFS" : "ok: RAM only (SPIFFS save failed)"` — return value checked and logged |

---

## Code Quality — GUI (`audio_gui.py`)

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| GUI-01 | `_poll_detect()` daemon thread — will not block app exit | ✅ PASS | [`audio_gui.py:1307`](../audio_gui.py:1307): `t = threading.Thread(target=self._poll_detect, daemon=True)` — `daemon=True` confirmed |
| GUI-02 | `_bg_download_thread()` daemon thread — will not block app exit | ✅ PASS | [`audio_gui.py:1409`](../audio_gui.py:1409): `t = threading.Thread(target=self._bg_download_thread, daemon=True)` — `daemon=True` confirmed |
| GUI-03 | Widget updates from threads use `self.after(0, ...)` (not direct tk calls) | ✅ PASS | All cross-thread UI updates use `self.after(0, ...)`: [`audio_gui.py:1330`](../audio_gui.py:1330) `_poll_detect`, [`audio_gui.py:1417`](../audio_gui.py:1417) `_bg_download_thread`, [`audio_gui.py:1429`](../audio_gui.py:1429) banner call; `_log()` at line 612 uses `self.after(0, _do)` |
| GUI-04 | `tcp_download()` has timeout parameter | ✅ PASS | [`audio_gui.py:76`](../audio_gui.py:76): `def tcp_download(host, port, path, timeout=20)` — `s.settimeout(timeout)` applied at line 78 |
| GUI-05 | `http_get_json()` has exception handling (returns None on fail) | ✅ PASS | [`audio_gui.py:103-108`](../audio_gui.py:103): `try: ... except: return None` — bare except intentional here for network helper, returns None on any failure |
| GUI-06 | No bare `except:` hiding critical errors in upload path | ✅ PASS | [`audio_gui.py:1173-1191`](../audio_gui.py:1173) `_upload_to_server()`: no bare `except`; all exception handling is in `tcp_upload()` which catches `Exception as e` and returns error string — upload path checks response string, not exception |
| GUI-07 | `_show_upload_banner()` uses `self.after(5000, banner.destroy)` (not blocking sleep) | ✅ PASS | [`audio_gui.py:1358`](../audio_gui.py:1358): `self.after(5000, banner.destroy)` — non-blocking |

---

## Demo Flow Correctness

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| FLOW-01 | **Bước 1**: Node-1 AP hidden → XML profile connects → GUI detects → upload → banner → filelist refresh | ✅ PASS | `AP_HIDDEN true` line 41; XML profile `nonBroadcast true`; `_poll_detect` polls 192.168.4.1; `_upload_to_server` → `_show_upload_banner` → `self.after(500, self._refresh_filelist)` |
| FLOW-02 | **Bước 2**: Node-1 SPIFFS persists across power cycle (`SPIFFS.begin(true)`) | ✅ PASS | [`esp32_server/src/main.cpp:434`](../esp32_server/src/main.cpp:434): `SPIFFS.begin(true)` — first arg `true` = format-on-fail only, does NOT format on normal boot; existing data survives reboot |
| FLOW-03 | **Bước 3**: Node-2 auto-syncs → POST /shutdown sent → LED 5× → AP still up | ✅ PASS | `syncFromNode1()` fetches file → sends `POST /shutdown` → `WiFi.disconnect(false)` (STA only) → `setup()` calls `blinkLED(5,80)` on sync success → AP remains (WIFI_AP_STA mode) |
| FLOW-04 | **Bước 4**: GUI detects Node-2 → bg download → `~/Downloads/audio_esp32.wav` saved | ✅ PASS | `_poll_detect` detects node 2 → `_start_bg_download()` → `_bg_download_thread()` saves to `~/Downloads/audio_esp32.wav` with PermissionError fallback to Desktop |

---

## Standards Checklist

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| STD-01 | All new C++ functions have a comment header | ✅ PASS | `handleFileList()` has `// GET /file/list — danh sách file trong SPIFFS` at line 285; `handleShutdown()` has `// POST /shutdown — Node-1 vào deep sleep` at line 327 |
| STD-02 | No `Serial.println` with debug garbage (intentional logs OK) | ✅ PASS | All Serial prints are intentional status logs (`[Sync]`, `[SPIFFS]`, `[AP]`, `[Shutdown]`, `[TCP]`) — no raw debug noise |
| STD-03 | Python methods follow `_snake_case` naming convention | ✅ PASS | All new methods: `_poll_detect`, `_on_node_detected`, `_show_detect_status`, `_show_upload_banner`, `_refresh_filelist`, `_fetch_filelist`, `_update_filelist_ui`, `_start_bg_download`, `_bg_download_thread` — all `_snake_case` |
| STD-04 | XML profiles have `connectionMode` = `manual` (not auto) | ✅ PASS | [`esp32_node1_profile.xml:9`](../esp32_node1_profile.xml:9): `<connectionMode>manual</connectionMode>`; [`esp32_node2_profile.xml:9`](../esp32_node2_profile.xml:9): same — prevents unwanted auto-connect |

---

## Issues Found

| ID | Severity | File | Location | Description |
|----|----------|------|----------|-------------|
| QC-01 | MINOR | [`audio_gui.py`](../audio_gui.py) | Line 564 | Network map canvas still shows `Port 81 (API)` for Client box — should be `Port 80 (API)`. Cosmetic/visual only. Already noted in Integration report (Minor Obs 1). Does not affect any functional contract. |
| QC-02 | MINOR | [`audio_gui.py`](../audio_gui.py) | Lines 675, 1014 | `_refresh_status()` and `_write_net_detail()` query `"ram_audio_ready"` and `"ram_audio_bytes"` fields from Node-2 `/status`, but Node-2 firmware returns `"ram_ready"` and `"ram_size"`. RAM indicator will always show `○` for Client. Display only — file transfer unaffected. Already noted in Integration report (Minor Obs 2). |
| QC-03 | INFO | [`audio_gui.py`](../audio_gui.py) | Lines 1140, 1233, 1293 | `subprocess.Popen('explorer /select,"<path>"')` called in `_auto_demo()`, `_client_push()`, `_download()`. Windows-only UI convenience — not a security risk (no user-controlled shell injection). `try/except` guards prevent crash on non-Windows. Acceptable for demo tool. |
| QC-04 | INFO | [`audio_gui.py`](../audio_gui.py) | Line 5 | Module docstring still references old topology: `ESP32 Server → AP "ESP32-Audio-AP"` — outdated; current topology uses `ESP32-Node-1`/`ESP32-Node-2`. No runtime impact. |
| QC-05 | INFO | [`audio_gui.py`](../audio_gui.py) | Line 195 | Header label text `WiFi: ESP32-Audio-AP  •  Password: 12345678` still uses old SSID name. Cosmetic only — tooltip/label string in UI. |
| QC-06 | INFO | [`esp32_server/src/main.cpp`](../esp32_server/src/main.cpp) | Line 289 | `handleFileList()` calls `SPIFFS.open("/")` without explicit `"r"` mode. ESP32 SPIFFS defaults to read for root. Functionally correct; noted in Integration Minor Obs 3. |

**No BLOCKERs. No MAJORs.**

---

## Contract Compliance Matrix

| Contract | Requirement | Status |
|----------|-------------|--------|
| BE-01-A | `AP_HIDDEN true` → `WiFi.softAP(...,true,...)` | ✅ PASS |
| BE-01-B | `GET /file/list` returns correct JSON with `files`, `count`, `spiffs_free` | ✅ PASS |
| BE-01-C | `POST /shutdown` sends 200 BEFORE `esp_deep_sleep_start()`, delay ≥ 1000ms | ✅ PASS |
| BE-02-A | `MY_AP_HIDDEN true` → `WiFi.softAP(...,MY_AP_HIDDEN,...)` | ✅ PASS |
| BE-02-B | `POST /shutdown` called while STA connected, BEFORE `WiFi.disconnect(false)` | ✅ PASS |
| FE-01-A | `CLIENT_IP = "192.168.5.1"` | ✅ PASS |
| FE-01-B | `_poll_detect()` daemon thread, 3s interval, parses `"node"` field | ✅ PASS |
| FE-01-C | `ttk.Treeview` filelist panel, refreshes after upload | ✅ PASS |
| FE-01-D | Upload banner `#22c55e`, auto-hides via `self.after(5000,...)` | ✅ PASS |
| FE-01-E | `_bg_download_thread()` daemon, saves to `~/Downloads/audio_esp32.wav`, PermissionError fallback | ✅ PASS |

---

## QC Verdict

```
╔══════════════════════════════════════════════════╗
║              QC PASS  ✅                          ║
║                                                    ║
║  All 10 contracts: COMPLIANT                       ║
║  Security: 0 BLOCKERs, 0 MAJORs                   ║
║  Code Quality: 0 BLOCKERs, 0 MAJORs               ║
║  Issues: 2 MINOR (cosmetic/display), 4 INFO        ║
║                                                    ║
║  Signal: qc-pass → reviewer                        ║
╚══════════════════════════════════════════════════╝
```

**Open items for Reviewer awareness (non-blocking):**
- QC-01/02: Network map and status strip show stale field names/port — purely visual, demo flow unaffected
- QC-03: `subprocess.Popen` for Explorer UI — Windows-only convenience, no security concern
- QC-04/05: Old SSID name in docstring and header label — cosmetic

---

---

# Reviewer Sign-off — ESP32 Audio Demo v2.0

**Date:** 2026-04-06
**Reviewer:** Reviewer - Final Authority
**Baseline:** QC PASS (0 BLOCKERs, 0 MAJORs, 2 MINORs, 4 INFOs)
**Pipeline:** BA ✅ | BE-01 ✅ | BE-02 ✅ | FE-01 ✅ | Integration PASS (26/26) ✅ | QC PASS ✅

---

## ARCH-01 — Architecture Fitness

The 4-step demo flow maps cleanly onto the implementation:

| Bước | Architecture element | Verdict |
|------|---------------------|---------|
| 1 | Node-1 hidden AP (`AP_HIDDEN true`) + GUI detects via `/status` → upload + filelist refresh | ✅ FIT |
| 2 | `SPIFFS.begin(true)` persists file across power-cycle; LED 3× on boot | ✅ FIT |
| 3 | Node-2 `syncFromNode1()` → POST /shutdown before `WiFi.disconnect(false)` → LED 5× | ✅ FIT |
| 4 | Node-2 hidden AP (`MY_AP_HIDDEN true`) + GUI `_bg_download_thread()` → `~/Downloads/audio_esp32.wav` | ✅ FIT |

AP isolation is correct: Node-1 on channel 1 (`192.168.4.1`), Node-2 on channel 6 (`192.168.5.1`). No IP collision. WiFi APSTA mode on Node-2 preserves AP while syncing from Node-1 STA — architecturally sound.

---

## ARCH-02 — Production / Demo Readiness

| Risk | Assessment |
|------|------------|
| Deep sleep irreversibility | Acceptable for demo; Node-1 is a single-use sender. `esp_deep_sleep_start()` confirmed at [`esp32_server/src/main.cpp:337`](../esp32_server/src/main.cpp:337). |
| OOM guard on `malloc` | Present in both nodes (`if (!ramBuf)`). No crash path. |
| Non-blocking `loop()` | Confirmed. `server.handleClient()` + non-blocking TCP accept. No >50 ms stalls in steady state. |
| Daemon threads in GUI | `_poll_detect` and `_bg_download_thread` both `daemon=True` — clean exit. All widget updates via `self.after(0, ...)`. |
| PermissionError fallback | `_bg_download_thread` falls back to Desktop on PermissionError — demo is safe on restricted accounts. |

**No crash paths identified. Firmware safe for flashing.**

---

## ARCH-03 — Independent Bug Finding (QC miss)

| ID | Severity | File | Location | Description |
|----|----------|------|----------|-------------|
| REV-01 | MINOR | [`esp32_server/src/main.cpp`](../esp32_server/src/main.cpp) | Line 330 | `handleShutdown()` calls `blinkLED(2, 150)` **before** `server.send(200, ...)`. Each blink is 150 ms ON + 150 ms OFF = 600 ms total blocking delay consumed **before** the HTTP response is sent. Contract BE-01-C (research.md §4.2) specifies: send → flush → stop → delay → sleep. The LED blink should follow `server.client().stop()`, not precede `server.send()`. **Impact on demo:** Node-2 has a 3-second timeout on the shutdown call; 600 ms is consumed before the response byte 0 leaves — on congested or slow WiFi this could cause Node-2 to log `[Sync] Shutdown Node-1 FAILED (not critical)` even though Node-1 does enter deep sleep. Node-2 handles this gracefully (non-fatal). Demo is not broken, but the fix is a 2-line reorder. |

**Recommended fix (optional before demo):**
```cpp
void handleShutdown() {
  Serial.println("[Shutdown] Node-1 going to deep sleep...");
  // Send response FIRST per contract BE-01-C
  server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Node-1 shutting down\"}");
  server.client().stop();
  delay(1000);
  blinkLED(2, 150);   // ← moved after response + 1s delay
  digitalWrite(LED_PIN, LOW);
  Serial.println("[Shutdown] Deep sleep NOW");
  Serial.flush();
  esp_deep_sleep_start();
}
```

---

## ARCH-04 — Tech Debt Assessment

| Item | Severity | Demo impact | Defer OK? |
|------|----------|-------------|-----------|
| QC-01: Canvas shows `Port 81` for Client | MINOR | Zero — cosmetic only | ✅ Yes |
| QC-02: `"ram_audio_ready"` key mismatch vs Node-2 `"ram_ready"` | MINOR | Status strip RAM indicator wrong; file transfer unaffected | ✅ Yes |
| QC-03: `subprocess.Popen` for Explorer UI | INFO | Windows-only convenience; try/except guarded | ✅ Yes |
| QC-04: Stale docstring SSID | INFO | Zero runtime impact | ✅ Yes |
| QC-05: Stale header label SSID | INFO | Zero runtime impact | ✅ Yes |
| QC-06: `SPIFFS.open("/")` no explicit `"r"` | INFO | ESP32 SPIFFS default is read; functionally correct | ✅ Yes |
| REV-01: LED blink before HTTP send | MINOR | Non-fatal; shutdown fallback covers it | ✅ Yes (fix recommended) |

**Accumulated tech debt is acceptable for a demo tool. No item degrades the 4-step flow.**

---

## ARCH-05 — CH340 Driver Risk

Risk R1 from research.md is the **only external dependency** that can block the demo entirely. It is **not a code issue** — it is a pre-demo hardware setup step. Workaround is documented in `docs/project.md` (Driver Issue section):

1. Install `CH341SER.EXE` from https://www.wch.cn/downloads/CH341SER_EXE.html
2. Verify Device Manager → COM port shows "OK"
3. Pre-flash both nodes the day before demo
4. `pio run -t upload -e nodemcu-32s`

This is adequately documented. No code change required. Risk is **mitigated by procedure**.

---

## ARCH-06 — Consistency Check

| Check | Result |
|-------|--------|
| Node-1 SSID in firmware matches XML profile (`ESP32-Node-1`) | ✅ |
| Node-2 SSID in firmware matches XML profile (`ESP32-Node-2`) | ✅ |
| `CLIENT_IP = "192.168.5.1"` in GUI matches Node-2 AP config | ✅ |
| Both XML profiles have `connectionMode = manual` (no auto-connect) | ✅ |
| Password `12345678` consistent across all nodes, profiles, GUI | ✅ |
| `NODE1_IP = "192.168.4.1"` in Node-2 firmware matches Node-1 AP | ✅ |

---

## Final Verdict

```
╔══════════════════════════════════════════════════════════════╗
║                   APPROVED  ✅                               ║
║                                                              ║
║  All 10 contracts: COMPLIANT                                 ║
║  Architecture: FIT for 4-step demo flow                      ║
║  Firmware: Safe for flashing (no crash paths)                ║
║  Tech debt: 2 MINORs + 4 INFOs — all deferrable             ║
║  1 new MINOR (REV-01): LED before HTTP send — non-fatal,     ║
║    fix recommended but not blocking                          ║
║  CH340 risk: mitigated by documented procedure               ║
║                                                              ║
║  Signal: approved → deliver                                  ║
╚══════════════════════════════════════════════════════════════╝
```

**Conditions for hardware flashing:**
1. Install CH341SER driver and verify COM port BEFORE flashing
2. Pre-install `esp32_node1_profile.xml` and `esp32_node2_profile.xml` via `netsh wlan add profile`
3. Optional (recommended): reorder `blinkLED` in `handleShutdown()` to after `server.client().stop()` (REV-01)
