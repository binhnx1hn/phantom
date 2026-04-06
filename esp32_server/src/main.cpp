/*
 * ESP32 #1 - SERVER / ACCESS POINT
 * ─────────────────────────────────────────────────────────────
 * - Phát WiFi AP: "ESP32-Audio-AP" / "12345678"
 * - IP cố định : 192.168.4.1
 * - Port 80    : JSON API (status, audio/info)
 * - Port 8080  : Raw TCP HTTP (upload WAV / download WAV)
 *
 * test.wav nhúng sẵn vào firmware → Server LUÔN có audio để gửi
 * Khi Client upload → ghi đè vào audioBuffer (RAM)
 * Download GET → ưu tiên RAM, fallback về test.wav nhúng sẵn
 *
 * Luồng 2 chiều:
 *   Client → POST :8080/upload  → Server lưu vào RAM
 *   Client ← GET  :8080/audio.wav ← Server trả về (RAM hoặc built-in)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "test_wav.h"   // test.wav nhúng sẵn

// ── Cấu hình AP ───────────────────────────────────────────────────────────────
#define AP_SSID     "ESP32-Audio-AP"
#define AP_PASSWORD "12345678"
#define AP_CHANNEL  1
#define AP_HIDDEN   false
#define AP_MAX_CON  4

// ── Cổng ──────────────────────────────────────────────────────────────────────
#define LED_PIN    2
#define HTTP_PORT  80
#define AUDIO_PORT 8080

WebServer  server(HTTP_PORT);
WiFiServer audioServer(AUDIO_PORT);

// ── Audio buffer (RAM - ghi đè khi Client upload) ────────────────────────────
uint8_t* audioBuffer = nullptr;
size_t   audioSize   = 0;
bool     audioReady  = false;   // true khi có audio trong RAM

// ── LED ──────────────────────────────────────────────────────────────────────
void blinkLED(int times, int ms = 100) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, LOW);  delay(ms);
    digitalWrite(LED_PIN, HIGH); delay(ms);
  }
}

// ── JSON API handlers (port 80) ───────────────────────────────────────────────
void handleStatus() {
  IPAddress ip = WiFi.softAPIP();
  server.send(200, "application/json",
    String("{\"mode\":\"AP\"") +
    ",\"ssid\":\"" + AP_SSID + "\"" +
    ",\"ip\":\"" + ip.toString() + "\"" +
    ",\"stations\":" + String(WiFi.softAPgetStationNum()) +
    ",\"free_heap\":" + String(ESP.getFreeHeap()) +
    ",\"ram_audio_ready\":" + (audioReady ? "true" : "false") +
    ",\"ram_audio_bytes\":" + String(audioSize) +
    ",\"builtin_wav_bytes\":" + String(TEST_WAV_SIZE) + "}");
}

void handleAudioInfo() {
  IPAddress ip = WiFi.softAPIP();
  bool hasAudio = audioReady || (TEST_WAV_SIZE > 0);
  size_t sz = audioReady ? audioSize : TEST_WAV_SIZE;
  server.send(200, "application/json",
    String("{\"ready\":") + (hasAudio ? "true" : "false") +
    ",\"source\":\"" + (audioReady ? "ram" : "builtin") + "\"" +
    ",\"size\":" + String(sz) +
    ",\"kb\":" + String((float)sz / 1024.0f, 1) +
    ",\"upload\":\"http://" + ip.toString() + ":" + String(AUDIO_PORT) + "/upload\"" +
    ",\"download\":\"http://" + ip.toString() + ":" + String(AUDIO_PORT) + "/audio.wav\"}");
}

void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"not found\"}");
}

// ── Raw TCP: upload / download WAV (port 8080) ────────────────────────────────
void handleAudioClient(WiFiClient& client) {
  String reqLine = client.readStringUntil('\n'); reqLine.trim();
  Serial.println("[Audio] " + reqLine + " from " + client.remoteIP().toString());

  int contentLength = 0;
  while (client.connected()) {
    String line = client.readStringUntil('\n'); line.trim();
    if (line.length() == 0) break;
    String lower = line; lower.toLowerCase();
    if (lower.startsWith("content-length:")) {
      contentLength = line.substring(line.indexOf(':') + 1).toInt();
    }
  }

  // ── POST /upload : Client gửi audio lên ──────────────────────────────────
  if (reqLine.startsWith("POST")) {
    if (contentLength <= 0 || contentLength > 200000) {
      client.print("HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"error\":\"bad content-length\"}");
      return;
    }
    if (audioBuffer) { free(audioBuffer); audioBuffer = nullptr; audioSize = 0; }
    audioBuffer = (uint8_t*)malloc(contentLength);
    if (!audioBuffer) {
      client.print("HTTP/1.1 507 Insufficient Storage\r\nConnection: close\r\n\r\n{\"error\":\"oom\"}");
      return;
    }
    size_t received = 0;
    unsigned long t = millis();
    while (received < (size_t)contentLength && client.connected() && (millis() - t) < 15000) {
      size_t avail = client.available();
      if (avail > 0) {
        size_t chunk = min(avail, (size_t)(contentLength - received));
        client.readBytes(audioBuffer + received, chunk);
        received += chunk; t = millis();
      } else { delay(1); }
    }
    audioSize  = received;
    audioReady = (received >= 44);
    Serial.printf("[Audio] Received %d/%d bytes (%.1f KB) from Client\n",
                  received, contentLength, received / 1024.0f);
    String resp = "{\"status\":\"ok\",\"received\":" + String(received) +
                  ",\"expected\":" + String(contentLength) + "}";
    client.printf("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s",
                  resp.length(), resp.c_str());
    blinkLED(5, 80);  // 5 nháy nhanh = nhận xong
  }
  // ── GET /audio.wav : Client tải audio từ Server ───────────────────────────
  else if (reqLine.startsWith("GET")) {
    // Ưu tiên RAM, fallback built-in test.wav
    const uint8_t* buf = (audioReady && audioSize > 0) ? audioBuffer : TEST_WAV_DATA;
    size_t         sz  = (audioReady && audioSize > 0) ? audioSize   : TEST_WAV_SIZE;
    const char*    src = (audioReady && audioSize > 0) ? "ram" : "builtin";

    if (sz == 0) {
      client.print("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n{\"error\":\"no audio\"}");
      return;
    }
    Serial.printf("[Audio] Sending %d bytes (%s) to Client\n", sz, src);
    client.printf("HTTP/1.1 200 OK\r\nContent-Type: audio/wav\r\nContent-Length: %d\r\n"
                  "Content-Disposition: attachment; filename=audio.wav\r\nConnection: close\r\n\r\n", sz);
    size_t sent = 0;
    while (sent < sz && client.connected()) {
      size_t chunk = min((size_t)1024, sz - sent);
      client.write(buf + sent, chunk);
      sent += chunk;
    }
    client.flush();
    Serial.printf("[Audio] Sent %d bytes OK\n", sz);
    blinkLED(3, 100);
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL, AP_HIDDEN, AP_MAX_CON);
  delay(200);

  IPAddress apIP = WiFi.softAPIP();
  Serial.printf("\n[AP] SSID     : %s\n", AP_SSID);
  Serial.printf("[AP] Password : %s\n", AP_PASSWORD);
  Serial.printf("[AP] IP       : %s\n", apIP.toString().c_str());
  Serial.printf("[AP] Heap     : %d bytes\n", ESP.getFreeHeap());
  Serial.printf("[AP] Built-in WAV: %d bytes (%.1f KB)\n", TEST_WAV_SIZE, TEST_WAV_SIZE / 1024.0f);
  digitalWrite(LED_PIN, HIGH);

  server.on("/status",     HTTP_GET, handleStatus);
  server.on("/audio/info", HTTP_GET, handleAudioInfo);
  server.onNotFound(handleNotFound);
  server.begin();

  audioServer.begin();

  Serial.println("\n[Ready] Server Endpoints:");
  Serial.printf("  GET  http://%s/status          <- trang thai\n",    apIP.toString().c_str());
  Serial.printf("  GET  http://%s/audio/info      <- info audio\n",    apIP.toString().c_str());
  Serial.printf("  POST http://%s:8080/upload     <- Client gui audio len\n", apIP.toString().c_str());
  Serial.printf("  GET  http://%s:8080/audio.wav  <- Client/PC tai audio ve\n", apIP.toString().c_str());
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();
  WiFiClient audioClient = audioServer.accept();
  if (audioClient) {
    unsigned long t = millis();
    while (!audioClient.available() && audioClient.connected() && (millis() - t) < 3000) delay(1);
    if (audioClient.available()) handleAudioClient(audioClient);
    audioClient.stop();
  }
}
