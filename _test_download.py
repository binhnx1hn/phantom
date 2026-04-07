"""
_test_download.py — Kiểm tra download từ ESP32 (Thiết bị B = 192.168.5.1)
Chạy: python _test_download.py
"""
import socket, time

HOST = "192.168.5.1"
PORT = 80

def test_raw(filename, timeout=30):
    print(f"\n{'='*60}")
    print(f"Test download: {filename}  (timeout={timeout}s)")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        req = (f"GET /file/download?name={filename} HTTP/1.1\r\n"
               f"Host: {HOST}\r\nConnection: close\r\n\r\n")
        s.sendall(req.encode())

        # Đọc tất cả raw bytes
        raw = b""
        try:
            while True:
                c = s.recv(4096)
                if not c: break
                raw += c
        except: pass

        if not raw:
            print("ERROR: Không nhận được bytes nào!")
            return

        # Tìm header/body split
        sep = raw.find(b"\r\n\r\n")
        if sep < 0:
            print(f"ERROR: Không tìm thấy \\r\\n\\r\\n  (raw len={len(raw)})")
            print("Raw (hex):", raw[:200].hex())
            return

        headers = raw[:sep].decode(errors="replace")
        body    = raw[sep+4:]

        print(f"Status: {headers.split(chr(13))[0]}")
        for line in headers.split("\r\n")[1:]:
            if line.strip():
                print(f"  {line}")
        print(f"Body bytes: {len(body)}")
        if len(body) > 0:
            print(f"Body[0:16] hex: {body[:16].hex()}")
        else:
            print("BODY IS EMPTY!")

    except Exception as e:
        print(f"Exception: {e}")
    finally:
        try: s.close()
        except: pass

def test_list():
    print(f"\n{'='*60}")
    print("Test /file/list  (timeout=30s)")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(30)
    try:
        s.connect((HOST, PORT))
        s.sendall(f"GET /file/list HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n".encode())
        raw = b""
        try:
            while True:
                c = s.recv(4096)
                if not c: break
                raw += c
        except: pass
        sep = raw.find(b"\r\n\r\n")
        if sep >= 0:
            body = raw[sep+4:].decode(errors="replace")
            print(body[:800])
        else:
            print("No body found, raw:", raw[:200])
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        try: s.close()
        except: pass

if __name__ == "__main__":
    test_list()
    test_raw("U3listening.docx")
    test_raw("Testcase.xlsx")
    test_raw("note.docx")
