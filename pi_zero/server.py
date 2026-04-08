#!/usr/bin/env python3
"""
Pi Zero 2W — File Server (tương thích API ESP32 Node-1)
========================================================
Vai trò : Lưu file trên SD card, phát WiFi AP "PiZero-Node",
          cho ESP32 (Node-2) kết nối vào lấy file mỗi 10 giây.

API tương thích hoàn toàn với ESP32 Node-1:
  GET  /status                ← trạng thái server
  GET  /file/list             ← danh sách file (JSON)
  GET  /file/download?name=   ← tải file theo tên
  POST /file/upload           ← upload file (X-Filename header + raw body)
  POST /file/delete?name=     ← xóa file theo tên
  POST /file/clear            ← xóa tất cả file
  GET  /sync/status           ← ESP32 Node-2 poll (giống Node-1)
  GET  /ram/info              ← thông tin bộ nhớ

Chạy:
  pip install flask
  python3 server.py

Hoặc chạy tự động khi boot:
  sudo cp pi_zero/pizero-server.service /etc/systemd/system/
  sudo systemctl enable pizero-server
  sudo systemctl start pizero-server
"""

import os
import sys
import json
import time
import shutil
import hashlib
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort

# ── Cấu hình ──────────────────────────────────────────────────
FILES_DIR   = Path("/home/pi/files")   # Thư mục lưu file trên SD card
HOST        = "0.0.0.0"
PORT        = 80
MAX_FILE_MB = 50                        # Giới hạn 50 MB mỗi file
NODE_ID     = "pi_zero"

FILES_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_MB * 1024 * 1024

start_time = time.time()

# ── Helper ────────────────────────────────────────────────────
def uptime_str():
    s = int(time.time() - start_time)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def mime_for_ext(ext: str) -> str:
    ext = ext.lower()
    m = {
        ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
        ".flac": "audio/flac", ".aac": "audio/aac",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
        ".txt": "text/plain", ".csv": "text/csv",
        ".json": "application/json", ".xml": "application/xml",
        ".zip": "application/zip",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".bin": "application/octet-stream",
    }
    return m.get(ext, "application/octet-stream")

def sanitize_filename(name: str) -> str:
    name = name.strip()
    if not name:
        return ""
    # Tách base + ext
    p = Path(name)
    base = p.stem
    ext  = p.suffix.lower()  # lowercase ext
    # Sanitize base: chỉ giữ alphanumeric, '-', '_' (tối đa 64 ký tự)
    safe_base = "".join(c for c in base if c.isalnum() or c in "-_")[:64]
    if not safe_base:
        return ""
    # Sanitize ext: chỉ giữ alphanumeric (tối đa 8 ký tự sau dấu chấm)
    safe_ext = "." + "".join(c for c in ext[1:] if c.isalnum())[:8] if ext else ".bin"
    return safe_base + safe_ext

def list_files():
    """Trả về list dict {name, size, mime} cho tất cả file trong FILES_DIR"""
    result = []
    for p in sorted(FILES_DIR.iterdir()):
        if p.is_file():
            sz   = p.stat().st_size
            mime = mime_for_ext(p.suffix)
            result.append({"name": p.name, "size": sz, "mime": mime,
                            "size_kb": f"{sz/1024:.1f} KB"})
    return result

def disk_info():
    total, used, free = shutil.disk_usage(str(FILES_DIR))
    return total, used, free

# ── Routes ────────────────────────────────────────────────────

@app.route("/status")
def handle_status():
    total, used, free = disk_info()
    files = list_files()
    return jsonify({
        "node": NODE_ID,
        "uptime": uptime_str(),
        "file_count": len(files),
        "disk_total": total,
        "disk_used": used,
        "disk_free": free,
        "files_dir": str(FILES_DIR),
        "platform": sys.platform,
    })

@app.route("/file/list")
def handle_file_list():
    files = list_files()
    total, used, free = disk_info()
    return jsonify({
        "files": files,
        "count": len(files),
        "spiffs_total": total,   # giữ tên key tương thích ESP32
        "spiffs_used": used,
        "spiffs_free": free,
    })

@app.route("/sync/status")
def handle_sync_status():
    """ESP32 Node-2 poll — giống /sync/status của Node-1"""
    files = list_files()
    _, used, free = disk_info()
    print(f"[Sync/Status] Thiết bị B hỏi — Danh sách: {len(files)} file")
    return jsonify({
        "node": NODE_ID,
        "file_count": len(files),
        "spiffs_used": used,
        "spiffs_free": free,
        "uptime": uptime_str(),
        "files": [{"name": f["name"], "size": f["size"]} for f in files],
    })

@app.route("/file/download")
def handle_file_download():
    name = request.args.get("name", "").strip()
    if not name:
        # Fallback: trả file đầu tiên (tương thích firmware cũ dùng /file/download)
        files = list_files()
        if not files:
            abort(404)
        name = files[0]["name"]

    # Thử path gốc trước
    fpath = FILES_DIR / name
    if not fpath.exists():
        # Thử sanitize
        safe = sanitize_filename(name)
        fpath = FILES_DIR / safe
        if not fpath.exists():
            print(f"[Download] NOT FOUND: {name}")
            return jsonify({"error": "file not found", "name": name}), 404
        name = safe

    mime = mime_for_ext(fpath.suffix)
    print(f"[Download] '{name}' {fpath.stat().st_size} bytes  MIME={mime}")
    return send_file(
        str(fpath),
        mimetype=mime,
        as_attachment=True,
        download_name=name,
    )

@app.route("/file/upload", methods=["POST"])
def handle_file_upload():
    # Lấy tên file từ header X-Filename hoặc query param name
    xfilename = request.headers.get("X-Filename", "").strip()
    if not xfilename:
        xfilename = request.args.get("name", "").strip()

    save_as = sanitize_filename(xfilename)
    if not save_as:
        # Tạo tên tự động
        save_as = f"file_{int(time.time())}.bin"

    data = request.get_data()
    if not data:
        return jsonify({"error": "empty body"}), 400

    fpath = FILES_DIR / save_as
    fpath.write_bytes(data)
    sz = len(data)
    print(f"[Upload] '{save_as}' {sz} bytes → OK")
    return jsonify({
        "status": "ok",
        "filename": save_as,
        "size": sz,
        "spiffs_saved": True,
    })

@app.route("/file/delete", methods=["POST"])
def handle_file_delete():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "missing name"}), 400

    fpath = FILES_DIR / name
    if not fpath.exists():
        safe = sanitize_filename(name)
        fpath = FILES_DIR / safe
        if not fpath.exists():
            return jsonify({"error": "file not found"}), 404

    fpath.unlink()
    print(f"[Delete] '{name}' → OK")
    return jsonify({"status": "ok"})

@app.route("/file/clear", methods=["POST"])
def handle_file_clear():
    deleted = 0
    for p in FILES_DIR.iterdir():
        if p.is_file():
            p.unlink()
            deleted += 1
    print(f"[Clear] Đã xóa {deleted} file")
    return jsonify({"status": "ok", "deleted": deleted})

@app.route("/file/info")
def handle_file_info():
    """Tương thích firmware cũ"""
    files = list_files()
    wav_files = [f for f in files if f["name"].endswith(".wav")]
    has = len(wav_files) > 0
    sz  = wav_files[0]["size"] if has else 0
    return jsonify({
        "has_file": has,
        "path": "/" + wav_files[0]["name"] if has else "",
        "size": sz,
        "size_kb": f"{sz/1024:.1f}",
        "free_heap": 0,
    })

@app.route("/ram/info")
def handle_ram_info():
    """Tương thích firmware cũ"""
    return jsonify({
        "ram_ready": False,
        "note": "Pi Zero — no RAM buffer (files served from SD card)",
        "free_heap": 0,
    })

@app.route("/audio/info")
def handle_audio_info():
    return handle_file_info()

@app.route("/ram/clear", methods=["POST"])
def handle_ram_clear():
    return jsonify({"status": "ok", "message": "no-op on Pi Zero"})

# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("══════════════════════════════════════════")
    print(" Pi Zero 2W — File Server  (Node tương thích ESP32 Node-1)")
    print("══════════════════════════════════════════")
    print(f" Files dir : {FILES_DIR}")
    print(f" Port      : {PORT}")
    print(f" API       : GET /file/list, GET /file/download?name=, POST /file/upload")
    print(f" Sync poll : GET /sync/status")
    print("══════════════════════════════════════════")

    # Danh sách file hiện có
    files = list_files()
    print(f" Hiện có   : {len(files)} file trong {FILES_DIR}")
    for f in files:
        print(f"   - {f['name']}  ({f['size_kb']})")
    print()

    app.run(host=HOST, port=PORT, debug=False, threaded=True)
