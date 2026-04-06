"""
test_transfer.py - Test chuyền file audio ESP32 Server (AP) ↔ ESP32 Client ↔ PC
=================================================================================
Topology:
  [ESP32 Server] phát WiFi AP "ESP32-Audio-AP"
  [ESP32 Client] kết nối vào AP → IP cấp phát (thường 192.168.4.2)
  [PC]           kết nối vào AP → IP cấp phát (thường 192.168.4.3)

  Server IP cố định : 192.168.4.1
  Server audio port : 8080
  Client audio port : 8081
  Client HTTP port  : 81

Cách dùng:
  # Chỉ test với Server (PC phải kết nối WiFi "ESP32-Audio-AP")
  python test_transfer.py --file test.wav

  # Test đầy đủ Server + Client (cần biết IP của Client)
  python test_transfer.py --client 192.168.4.2 --file test.wav

  # Xem IP Client bằng cách nhìn Serial Monitor của ESP32 Client sau khi boot
"""

import socket
import os
import sys
import time
import argparse
import urllib.request

# ─── Server mặc định (AP mode cố định) ───────────────────────────────────────
SERVER_IP         = "192.168.4.1"
SERVER_HTTP_PORT  = 80
SERVER_AUDIO_PORT = 8080

CLIENT_HTTP_PORT  = 81
CLIENT_AUDIO_PORT = 8081

# ─── Màu terminal ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"; RED    = "\033[91m"; YELLOW = "\033[93m"
CYAN   = "\033[96m"; RESET  = "\033[0m";  BOLD   = "\033[1m"

def ok(msg):     print(f"  {GREEN}[OK] {msg}{RESET}")
def err(msg):    print(f"  {RED}[FAIL] {msg}{RESET}")
def info(msg):   print(f"  {CYAN}>> {msg}{RESET}")
def warn(msg):   print(f"  {YELLOW}[WARN] {msg}{RESET}")
def header(msg): print(f"\n{BOLD}{CYAN}{'-'*60}\n  {msg}\n{'-'*60}{RESET}")

# ─── TCP raw HTTP (giống ESP32 WiFiClient) ────────────────────────────────────
def tcp_upload(host, port, path, data: bytes, timeout=20) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
    except Exception as e:
        return f"CONNECT_ERROR: {e}"
    req = (f"POST {path} HTTP/1.1\r\n"
           f"Host: {host}:{port}\r\n"
           f"Content-Type: audio/wav\r\n"
           f"Content-Length: {len(data)}\r\n"
           f"Connection: close\r\n\r\n").encode()
    s.sendall(req)
    sent = 0
    while sent < len(data):
        s.sendall(data[sent:sent+1024])
        sent += min(1024, len(data)-sent)
    resp = b""
    try:
        while True:
            chunk = s.recv(4096)
            if not chunk: break
            resp += chunk
    except socket.timeout:
        pass
    s.close()
    return resp.decode(errors="replace")


def tcp_download(host, port, path, timeout=20) -> bytes:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
    except Exception as e:
        warn(f"CONNECT_ERROR: {e}")
        return b""
    req = (f"GET {path} HTTP/1.1\r\n"
           f"Host: {host}:{port}\r\n"
           f"Connection: close\r\n\r\n").encode()
    s.sendall(req)
    raw = b""
    try:
        while True:
            chunk = s.recv(4096)
            if not chunk: break
            raw += chunk
    except socket.timeout:
        pass
    s.close()
    sep = b"\r\n\r\n"
    idx = raw.find(sep)
    if idx == -1:
        warn("Không tìm thấy HTTP header separator")
        return b""
    headers = raw[:idx].decode(errors="replace")
    body    = raw[idx+4:]
    first_line = headers.split("\r\n")[0]
    if "200 OK" not in first_line:
        warn(f"HTTP response: {first_line}")
        return b""
    return body


def http_post(host, port, path, timeout=15) -> str:
    url = f"http://{host}:{port}{path}"
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode()
    except Exception as e:
        return f"ERROR: {e}"


def http_get(host, port, path, timeout=10) -> str:
    url = f"http://{host}:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode()
    except Exception as e:
        return f"ERROR: {e}"

# ─── Bước test ────────────────────────────────────────────────────────────────

def test_server_status():
    header(f"[1] Kiểm tra ESP32 Server ({SERVER_IP}:80/status)")
    info(f"GET http://{SERVER_IP}:{SERVER_HTTP_PORT}/status")
    resp = http_get(SERVER_IP, SERVER_HTTP_PORT, "/status")
    if "ERROR" in resp:
        err(f"Không kết nối được Server!\n     → {resp}")
        err("Hãy chắc chắn PC đã kết nối WiFi 'ESP32-Audio-AP'")
        return False
    ok(f"Server: {resp}")
    return True


def test_upload_to_server(wav_data, wav_file):
    header(f"[2] PC → Upload '{wav_file}' lên Server (:8080/upload)")
    info(f"POST http://{SERVER_IP}:{SERVER_AUDIO_PORT}/upload  [{len(wav_data):,} bytes]")
    t0 = time.time()
    resp = tcp_upload(SERVER_IP, SERVER_AUDIO_PORT, "/upload", wav_data)
    elapsed = time.time() - t0
    if "CONNECT_ERROR" in resp:
        err(f"Lỗi kết nối: {resp}")
        return False
    if "200 OK" in resp and '"status":"ok"' in resp:
        ok(f"Upload thành công! {len(wav_data):,} bytes trong {elapsed:.2f}s")
        body = resp.split("\r\n\r\n")[-1] if "\r\n\r\n" in resp else resp
        ok(f"Response: {body}")
        return True
    err(f"Upload thất bại!\n{resp[:300]}")
    return False


def test_server_audio_info():
    header(f"[3] Kiểm tra audio info trên Server")
    resp = http_get(SERVER_IP, SERVER_HTTP_PORT, "/audio/info")
    if "ERROR" in resp:
        err(resp); return False
    ok(f"Info: {resp}")
    return True


def test_download_from_server(save_path):
    header(f"[4] PC ← Download audio từ Server (:8080/audio.wav)")
    info(f"GET http://{SERVER_IP}:{SERVER_AUDIO_PORT}/audio.wav → {save_path}")
    t0 = time.time()
    body = tcp_download(SERVER_IP, SERVER_AUDIO_PORT, "/audio.wav")
    elapsed = time.time() - t0
    if len(body) < 44:
        err(f"Download thất bại! Nhận {len(body)} bytes")
        return False
    with open(save_path, "wb") as f: f.write(body)
    ok(f"Download thành công! {len(body):,} bytes trong {elapsed:.2f}s → {save_path}")
    return True


def test_verify(original, downloaded):
    header(f"[5] So sánh file gốc vs tải về")
    orig = open(original, "rb").read()
    down = open(downloaded, "rb").read()
    info(f"Gốc: {len(orig):,} bytes  |  Tải về: {len(down):,} bytes")
    if orig == down:
        ok("File KHỚP HOÀN TOÀN ✔")
        return True
    elif orig[:44] == down[:44]:
        warn("WAV header khớp nhưng data khác (có thể bị cắt)")
    else:
        err("File KHÔNG khớp!")
    return False


def test_client_status(client_ip):
    header(f"[6] Kiểm tra ESP32 Client ({client_ip}:{CLIENT_HTTP_PORT}/status)")
    resp = http_get(client_ip, CLIENT_HTTP_PORT, "/status")
    if "ERROR" in resp:
        err(f"Không kết nối được Client!\n     → {resp}")
        return False
    ok(f"Client: {resp}")
    return True


def test_upload_to_client(client_ip, wav_data, wav_file):
    header(f"[7] PC → Upload '{wav_file}' lên Client (:8081/upload)")
    info(f"POST http://{client_ip}:{CLIENT_AUDIO_PORT}/upload  [{len(wav_data):,} bytes]")
    t0 = time.time()
    resp = tcp_upload(client_ip, CLIENT_AUDIO_PORT, "/upload", wav_data)
    elapsed = time.time() - t0
    if "CONNECT_ERROR" in resp:
        err(f"Lỗi kết nối: {resp}"); return False
    if "200 OK" in resp and '"status":"ok"' in resp:
        ok(f"Upload thành công! {len(wav_data):,} bytes trong {elapsed:.2f}s")
        return True
    err(f"Upload thất bại!\n{resp[:300]}")
    return False


def test_client_push(client_ip):
    header(f"[8] Client → Server (Client tự đẩy audio lên Server)")
    info(f"POST http://{client_ip}:{CLIENT_HTTP_PORT}/audio/push")
    resp = http_post(client_ip, CLIENT_HTTP_PORT, "/audio/push")
    if '"status":"sent"' in resp:
        ok(f"Client đẩy lên Server thành công! {resp}")
        return True
    err(f"Thất bại: {resp}")
    return False


def test_client_fetch(client_ip):
    header(f"[9] Client ← Server (Client tự kéo audio từ Server về)")
    info(f"POST http://{client_ip}:{CLIENT_HTTP_PORT}/audio/fetch")
    resp = http_post(client_ip, CLIENT_HTTP_PORT, "/audio/fetch")
    if '"status":"ok"' in resp:
        ok(f"Client kéo từ Server thành công! {resp}")
        return True
    err(f"Thất bại: {resp}")
    return False


def test_download_from_client(client_ip, save_path):
    header(f"[10] PC ← Download audio từ Client (:8081/audio.wav)")
    info(f"GET http://{client_ip}:{CLIENT_AUDIO_PORT}/audio.wav → {save_path}")
    t0 = time.time()
    body = tcp_download(client_ip, CLIENT_AUDIO_PORT, "/audio.wav")
    elapsed = time.time() - t0
    if len(body) < 44:
        err(f"Download thất bại! Nhận {len(body)} bytes")
        return False
    with open(save_path, "wb") as f: f.write(body)
    ok(f"Download thành công! {len(body):,} bytes trong {elapsed:.2f}s → {save_path}")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Test chuyền audio ESP32 Server(AP) ↔ Client ↔ PC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python test_transfer.py                          # chỉ test Server
  python test_transfer.py --client 192.168.4.2    # test cả Server + Client
  python test_transfer.py --file my_audio.wav     # dùng file WAV khác
        """
    )
    parser.add_argument("--client", default=None,
                        help="IP của ESP32 Client (xem Serial Monitor sau khi boot)")
    parser.add_argument("--file",   default="test.wav",
                        help="File WAV để test (mặc định: test.wav)")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}")
    print(f"  ESP32 AUDIO TRANSFER TEST")
    print(f"  Server (AP): {SERVER_IP}  Audio port: {SERVER_AUDIO_PORT}")
    print(f"  Client     : {args.client or '(bo qua)'}  Audio port: {CLIENT_AUDIO_PORT}")
    print(f"  WiFi AP    : ESP32-Audio-AP  Password: 12345678")
    print(f"  Test file  : {args.file}")
    print(f"{'='*60}{RESET}")

    if not os.path.exists(args.file):
        err(f"File '{args.file}' không tồn tại!")
        info("Tạo file test: python test_audio_gen.py")
        sys.exit(1)

    wav_data = open(args.file, "rb").read()
    info(f"Đọc '{args.file}': {len(wav_data):,} bytes ({len(wav_data)/1024:.1f} KB)")

    results = {}

    # ── Phần 1: PC ↔ Server ──────────────────────────────────────────────────
    print(f"\n{BOLD}{YELLOW}---  PHAN 1: PC <-> ESP32 SERVER (AP)  ---{RESET}")
    results["1_server_status"] = test_server_status()

    if results["1_server_status"]:
        results["2_upload_server"]  = test_upload_to_server(wav_data, args.file)
        results["3_server_info"]    = test_server_audio_info()
        if results["2_upload_server"]:
            dl_s = "downloaded_from_server.wav"
            results["4_dl_server"] = test_download_from_server(dl_s)
            if results["4_dl_server"]:
                results["5_verify_server"] = test_verify(args.file, dl_s)

    # ── Phần 2: PC ↔ Client + Client ↔ Server ────────────────────────────────
    if args.client:
        print(f"\n{BOLD}{YELLOW}---  PHAN 2: PC <-> ESP32 CLIENT ({args.client})  ---{RESET}")
        results["6_client_status"] = test_client_status(args.client)

        if results["6_client_status"]:
            results["7_upload_client"] = test_upload_to_client(args.client, wav_data, args.file)

            if results["7_upload_client"]:
                results["8_client_push"]  = test_client_push(args.client)
                time.sleep(1)

            results["9_client_fetch"] = test_client_fetch(args.client)
            time.sleep(1)

            dl_c = "downloaded_from_client.wav"
            results["10_dl_client"] = test_download_from_client(args.client, dl_c)
            if results["10_dl_client"]:
                results["11_verify_client"] = test_verify(args.file, dl_c)
    else:
        warn("Bỏ qua test Client (thêm --client <IP> để test)")

    # ── Tóm tắt ──────────────────────────────────────────────────────────────
    labels = {
        "1_server_status":  "Kết nối Server",
        "2_upload_server":  "Upload → Server",
        "3_server_info":    "Audio info Server",
        "4_dl_server":      "Download ← Server",
        "5_verify_server":  "So sánh file (Server)",
        "6_client_status":  "Kết nối Client",
        "7_upload_client":  "Upload → Client",
        "8_client_push":    "Client push → Server",
        "9_client_fetch":   "Client fetch ← Server",
        "10_dl_client":     "Download ← Client",
        "11_verify_client": "So sánh file (Client)",
    }
    print(f"\n{BOLD}{'='*60}\n  TOM TAT KET QUA\n{'='*60}{RESET}")
    all_pass = True
    for key in sorted(labels):
        if key in results:
            (ok if results[key] else err)(labels[key])
            if not results[key]: all_pass = False

    print()
    if all_pass:
        print(f"  {GREEN}{BOLD}[OK] TAT CA BUOC THANH CONG!{RESET}")
    else:
        print(f"  {RED}{BOLD}[FAIL] MOT SO BUOC THAT BAI - xem chi tiet ben tren{RESET}")
    print()

    # Hướng dẫn nhanh bằng curl
    print(f"{BOLD}{CYAN}{'-'*60}")
    print(f"  LENH CURL TUONG DUONG")
    print(f"{'-'*60}{RESET}")
    f = args.file
    s = SERVER_IP; sp = SERVER_AUDIO_PORT
    c = args.client or "<CLIENT_IP>"; cp = CLIENT_AUDIO_PORT; ch = CLIENT_HTTP_PORT
    print(f"  # Kiểm tra Server")
    print(f"  curl http://{s}/status")
    print(f"  # Upload WAV lên Server")
    print(f"  curl -X POST http://{s}:{sp}/upload --data-binary @{f} -H \"Content-Type: audio/wav\"")
    print(f"  # Download WAV từ Server")
    print(f"  curl http://{s}:{sp}/audio.wav -o dl_server.wav")
    if args.client:
        print(f"  # Upload WAV lên Client")
        print(f"  curl -X POST http://{c}:{cp}/upload --data-binary @{f} -H \"Content-Type: audio/wav\"")
        print(f"  # Client đẩy lên Server")
        print(f"  curl -X POST http://{c}:{ch}/audio/push")
        print(f"  # Client kéo từ Server")
        print(f"  curl -X POST http://{c}:{ch}/audio/fetch")
        print(f"  # Download WAV từ Client")
        print(f"  curl http://{c}:{cp}/audio.wav -o dl_client.wav")
    print()


if __name__ == "__main__":
    main()
