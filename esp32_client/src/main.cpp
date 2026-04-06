/*
 * ESP32 #2 - CLIENT (Auto bidirectional audio transfer)
 * ─────────────────────────────────────────────────────────────
 * - Kết nối vào AP: "ESP32-Audio-AP" / "12345678"
 * - Server IP  : 192.168.4.1
 *
 * Sau khi kết nối WiFi, Client tự động:
 *   BƯỚC 1: Push test.wav (nhúng sẵn) lên Server  → POST :8080/upload
 *   BƯỚC 2: Fetch audio ngược từ Server về RAM     → GET  :8080/audio.wav
 *
 * LED báo hiệu:
 *   5 nháy nhanh = push thành công
 *   3 nháy vừa  = fetch thành công
 *   2 nháy chậm = lỗi
 *
 * Port 81   : JSON API (status, push, fetch, push_builtin)
 * Port 8081 : Raw TCP (upload vào / download từ Client)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "test_wav.h"   // test.wav nhúng sẵn vào firmware

#define AP_SSID           "ESP32-Audio-AP"
#define AP_PASSWORD       "12345678"
#define SERVER_IP         "192.168.4.1"
#define LED_PIN           2
#define CLIENT_HTTP_PORT  81
#define CLIENT_AUDIO_PORT 8081
#define SERVER_AUDIO_PORT 8080

WebServer  clientServer(CLIENT_HTTP_PORT);
WiFiServer audioServer(CLIENT_AUDIO_PORT);

// ── Audio buffer RAM (nhận từ Server hoặc từ PC) ─────────────────────────────
uint8_t* audioBuffer = nullptr;
size_t   audioSize   = 0;
bool     audioReady  = false;

// ── LED ──────────────────────────────────────────────────────────────────────
void blinkLED(int times, int ms = 100) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, LOW);  delay(ms);
    digitalWrite(LED_PIN, HIGH); delay(ms);
  }
}

// ── Push buffer lên Server (TCP thủ công) ────────────────────────────────────
bool uploadToServer(const uint8_t* buf, size_t size, const char* label = "") {
  WiFiClient tcp;
  Serial.printf("[Push%s] Connecting %s:%d ...\n", label, SERVER_IP, SERVER_AUDIO_PORT);
  if (!tcp.connect(SERVER_IP, SERVER_AUDIO_PORT)) {
    Serial.printf("[Push%s] FAILED to connect\n", label);
    return false;
  }
  tcp.printf("POST /upload HTTP/1.1\r\nHost: %s:%d\r\n"
             "Content-Type: audio/wav\r\nContent-Length: %d\r\n"
             "Connection: close\r\n\r\n",
             SERVER_IP, SERVER_AUDIO_PORT, size);
  size_t sent = 0;
  unsigned long t = millis();
  while (sent < size && tcp.connected() && (millis() - t) < 20000) {
    size_t chunk = min((size_t)1024, size - sent);
    tcp.write(buf + sent, chunk);
    sent += chunk; t = millis();
  }
  tcp.flush();
  String resp = ""; t = millis();
  while (tcp.connected() && (millis() - t) < 5000) {
    if (tcp.available()) { resp += (char)tcp.read(); t = millis(); }
  }
  tcp.stop();
  bool ok = (sent == size);
  Serial.printf("[Push%s] %s - Sent %d/%d bytes\n", label, ok ? "OK" : "FAIL", sent, size);
  if (resp.length() > 0) Serial.println("[Push] Resp: " + resp.substring(resp.lastIndexOf('\n') + 1));
  return ok;
}

// ── Fetch audio từ Server về RAM ─────────────────────────────────────────────
bool fetchFromServer() {
  WiFiClient tcp;
  Serial.printf("[Fetch] Connecting %s:%d ...\n", SERVER_IP, SERVER_AUDIO_PORT);
  if (!tcp.connect(SERVER_IP, SERVER_AUDIO_PORT)) {
    Serial.println("[Fetch] FAILED to connect");
    return false;
  }
  tcp.printf("GET /audio.wav HTTP/1.1\r\nHost: %s:%d\r\nConnection: close\r\n\r\n",
             SERVER_IP, SERVER_AUDIO_PORT);
  int contentLength = 0;
  unsigned long t = millis();
  while (tcp.connected() && (millis() - t) < 5000) {
    String line = tcp.readStringUntil('\n'); line.trim();
    if (line.length() == 0) break;
    String lower = line; lower.toLowerCase();
    if (lower.startsWith("content-length:"))
      contentLength = line.substring(line.indexOf(':') + 1).toInt();
  }
  if (contentLength <= 0 || contentLength > 200000) {
    tcp.stop();
    Serial.printf("[Fetch] Bad Content-Length: %d\n", contentLength);
    return false;
  }
  if (audioBuffer) { free(audioBuffer); audioBuffer = nullptr; audioSize = 0; }
  audioBuffer = (uint8_t*)malloc(contentLength);
  if (!audioBuffer) { tcp.stop(); Serial.println("[Fetch] OOM"); return false; }

  size_t received = 0; t = millis();
  while (received < (size_t)contentLength && tcp.connected() && (millis() - t) < 20000) {
    size_t avail = tcp.available();
    if (avail > 0) {
      size_t chunk = min(avail, (size_t)(contentLength - received));
      tcp.readBytes(audioBuffer + received, chunk);
      received += chunk; t = millis();
    } else { delay(1); }
  }
  tcp.stop();
  audioSize  = received;
  audioReady = (received >= 44);
  Serial.printf("[Fetch] %s - Got %d/%d bytes (%.1f KB)\n",
                audioReady ? "OK" : "FAIL", received, contentLength, received / 1024.0f);
  return audioReady;
}

// ── JSON API handlers (port 81) ───────────────────────────────────────────────
void handleStatus() {
  String ip = WiFi.localIP().toString();
  clientServer.send(200, "application/json",
    String("{\"mode\":\"STA\"") +
    ",\"ap_ssid\":\"" + AP_SSID + "\"" +
    ",\"ip\":\"" + ip + "\"" +
    ",\"server\":\"" + SERVER_IP + "\"" +
    ",\"free_heap\":" + String(ESP.getFreeHeap()) +
    ",\"ram_audio_ready\":" + (audioReady ? "true" : "false") +
    ",\"ram_audio_bytes\":" + String(audioSize) +
    ",\"builtin_wav_bytes\":" + String(TEST_WAV_SIZE) + "}");
}

void handleAudioInfo() {
  String ip = WiFi.localIP().toString();
  bool hasAudio = audioReady || (TEST_WAV_SIZE > 0);
  size_t sz = audioReady ? audioSize : TEST_WAV_SIZE;
  clientServer.send(200, "application/json",
    String("{\"ready\":") + (hasAudio ? "true" : "false") +
    ",\"source\":\"" + (audioReady ? "ram" : "builtin") + "\"" +
    ",\"size\":" + String(sz) +
    ",\"kb\":" + String((float)sz / 1024.0f, 1) + "}");
}

void handleAudioPush() {
  const uint8_t* buf = (audioReady && audioSize > 0) ? audioBuffer : TEST_WAV_DATA;
  size_t         sz  = (audioReady && audioSize > 0) ? audioSize   : TEST_WAV_SIZE;
  bool ok = uploadToServer(buf, sz, "");
  if (ok) blinkLED(5, 80); else blinkLED(2, 500);
  clientServer.send(200, "application/json",
    ok ? ("{\"status\":\"sent\",\"bytes\":" + String(sz) + "}") :
         "{\"status\":\"error\"}");
}

void handlePushBuiltin() {
  bool ok = uploadToServer(TEST_WAV_DATA, TEST_WAV_SIZE, "_builtin");
  if (ok) blinkLED(5, 80); else blinkLED(2, 500);
  clientServer.send(200, "application/json",
    ok ? ("{\"status\":\"sent\",\"bytes\":" + String(TEST_WAV_SIZE) + "}") :
         "{\"status\":\"error\"}");
}

void handleAudioFetch() {
  bool ok = fetchFromServer();
  if (ok) blinkLED(3, 150); else blinkLED(2, 500);
  clientServer.send(200, "application/json",
    ok ? ("{\"status\":\"ok\",\"bytes\":" + String(audioSize) + "}") :
         "{\"status\":\"error\"}");
}

void handleNotFound() {
  clientServer.send(404, "application/json", "{\"error\":\"not found\"}");
}

// ── Raw TCP Audio Server (port 8081): PC/thiết bị khác upload/download ────────
void handleAudioTCPClient(WiFiClient& client) {
  String reqLine = client.readStringUntil('\n'); reqLine.trim();
  Serial.println("[TCP] " + reqLine);
  int contentLength = 0;
  while (client.connected()) {
    String line = client.readStringUntil('\n'); line.trim();
    if (line.length() == 0) break;
    String lower = line; lower.toLowerCase();
    if (lower.startsWith("content-length:"))
      contentLength = line.substring(line.indexOf(':') + 1).toInt();
  }
  if (reqLine.startsWith("POST")) {
    if (contentLength <= 0 || contentLength > 200000) {
      client.print("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n{\"error\":\"bad length\"}");
      return;
    }
    if (audioBuffer) { free(audioBuffer); audioBuffer = nullptr; audioSize = 0; }
    audioBuffer = (uint8_t*)malloc(contentLength);
    if (!audioBuffer) {
      client.print("HTTP/1.1 507 Insufficient Storage\r\nConnection: close\r\n\r\n{\"error\":\"oom\"}");
      return;
    }
    size_t received = 0; unsigned long t = millis();
    while (received < (size_t)contentLength && client.connected() && (millis()-t) < 15000) {
      size_t avail = client.available();
      if (avail > 0) {
        size_t chunk = min(avail, (size_t)(contentLength - received));
        client.readBytes(audioBuffer + received, chunk);
        received += chunk; t = millis();
      } else { delay(1); }
    }
    audioSize = received; audioReady = (received >= 44);
    Serial.printf("[TCP] Uploaded %d/%d bytes\n", received, contentLength);
    String resp = "{\"status\":\"ok\",\"received\":" + String(received) + "}";
    client.printf("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s",
                  resp.length(), resp.c_str());
    blinkLED(3);
  } else if (reqLine.startsWith("GET")) {
    const uint8_t* buf = (audioReady && audioSize > 0) ? audioBuffer : TEST_WAV_DATA;
    size_t         sz  = (audioReady && audioSize > 0) ? audioSize   : TEST_WAV_SIZE;
    client.printf("HTTP/1.1 200 OK\r\nContent-Type: audio/wav\r\nContent-Length: %d\r\n"
                  "Content-Disposition: attachment; filename=audio.wav\r\nConnection: close\r\n\r\n", sz);
    size_t sent = 0;
    while (sent < sz && client.connected()) {
      size_t chunk = min((size_t)1024, sz - sent);
      client.write(buf + sent, chunk); sent += chunk;
    }
    client.flush();
    Serial.printf("[TCP] Served %d bytes\n", sz);
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.printf("\n[WiFi] Connecting to AP: %s\n", AP_SSID);
  Serial.printf("[Info] Built-in WAV: %d bytes (%.1f KB)\n", TEST_WAV_SIZE, TEST_WAV_SIZE / 1024.0f);

  WiFi.mode(WIFI_STA);
  WiFi.begin(AP_SSID, AP_PASSWORD);
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 40) {
    delay(500); Serial.print("."); retries++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[WiFi] FAILED!");
    while (true) { blinkLED(1, 200); }
  }
  String ip = WiFi.localIP().toString();
  Serial.printf("\n[WiFi] Connected! Client IP: %s\n", ip.c_str());
  Serial.printf("[WiFi] Free Heap: %d bytes\n", ESP.getFreeHeap());
  digitalWrite(LED_PIN, HIGH);
  delay(1000);  // Chờ Server sẵn sàng

  // ══════════════════════════════════════════════════════════════
  // BƯỚC 1: Client → Server  (push test.wav nhúng sẵn lên Server)
  // ══════════════════════════════════════════════════════════════
  Serial.println("\n[Auto] BUOC 1: Push test.wav len Server...");
  bool pushOk = uploadToServer(TEST_WAV_DATA, TEST_WAV_SIZE, "_builtin");
  if (pushOk) {
    Serial.printf("[Auto] Push OK! %d bytes sent\n", TEST_WAV_SIZE);
    blinkLED(5, 80);
  } else {
    Serial.println("[Auto] Push FAILED!");
    blinkLED(2, 500);
  }

  delay(500);

  // ══════════════════════════════════════════════════════════════
  // BƯỚC 2: Server → Client  (fetch audio từ Server về RAM)
  // ══════════════════════════════════════════════════════════════
  Serial.println("[Auto] BUOC 2: Fetch audio tu Server ve...");
  bool fetchOk = fetchFromServer();
  if (fetchOk) {
    Serial.printf("[Auto] Fetch OK! %d bytes received\n", audioSize);
    blinkLED(3, 150);
  } else {
    Serial.println("[Auto] Fetch FAILED!");
    blinkLED(2, 500);
  }

  // Kết quả tổng kết
  Serial.println("\n[Auto] ===== KET QUA =====");
  Serial.printf("  Push  Client->Server: %s (%d bytes)\n", pushOk  ? "OK" : "FAIL", TEST_WAV_SIZE);
  Serial.printf("  Fetch Server->Client: %s (%d bytes)\n", fetchOk ? "OK" : "FAIL", audioSize);
  Serial.println("[Auto] ====================");

  // JSON API port 81
  clientServer.on("/status",             HTTP_GET,  handleStatus);
  clientServer.on("/audio/info",         HTTP_GET,  handleAudioInfo);
  clientServer.on("/audio/push",         HTTP_POST, handleAudioPush);
  clientServer.on("/audio/push_builtin", HTTP_POST, handlePushBuiltin);
  clientServer.on("/audio/fetch",        HTTP_POST, handleAudioFetch);
  clientServer.onNotFound(handleNotFound);
  clientServer.begin();

  // Raw TCP port 8081
  audioServer.begin();

  Serial.println("\n[Ready] Client Endpoints:");
  Serial.printf("  GET  http://%s:%d/status              <- trang thai\n",        ip.c_str(), CLIENT_HTTP_PORT);
  Serial.printf("  POST http://%s:%d/audio/push          <- push audio len Server\n", ip.c_str(), CLIENT_HTTP_PORT);
  Serial.printf("  POST http://%s:%d/audio/push_builtin  <- push test.wav nhung san\n", ip.c_str(), CLIENT_HTTP_PORT);
  Serial.printf("  POST http://%s:%d/audio/fetch         <- fetch tu Server ve\n",ip.c_str(), CLIENT_HTTP_PORT);
  Serial.printf("  GET  http://%s:%d/audio.wav           <- download WAV\n",      ip.c_str(), CLIENT_AUDIO_PORT);
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  clientServer.handleClient();
  WiFiClient audioClient = audioServer.accept();
  if (audioClient) {
    unsigned long t = millis();
    while (!audioClient.available() && audioClient.connected() && (millis()-t) < 3000) delay(1);
    if (audioClient.available()) handleAudioTCPClient(audioClient);
    audioClient.stop();
  }
}
