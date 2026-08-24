/*
  esp32_ctg.ino — kirim FHR/MHR/UC ke /api/ingest tiap SEND_INTERVAL_MS.
  Ganti readFHR()/readMHR()/readUC() dengan pembacaan sensor asli Anda.
*/
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID     = "NAMA_WIFI_ANDA";
const char* WIFI_PASSWORD = "PASSWORD_WIFI_ANDA";
const char* API_URL       = "http://ALAMAT_VPS_ANDA:8000/api/ingest"; // ganti https://... setelah setup nginx (langkah 11)
const char* DEVICE_ID     = "esp32-ctg-01";
const unsigned long SEND_INTERVAL_MS = 2000; // samakan konsepnya dgn asumsi window SEQ_LEN di training

unsigned long lastSend = 0;

void connectWiFi() {
  Serial.print("Menghubungkan WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.println("\nTersambung, IP: " + WiFi.localIP().toString());
}

void setup() {
  Serial.begin(115200);
  connectWiFi();
}

// GANTI dengan pembacaan sensor asli
float readFHR() { return 130.0 + random(-8, 8); }
float readMHR() { return 85.0 + random(-4, 4); }
float readUC()  { return 3.0 + random(-1, 2) * 0.5; }

void sendReading(float fhr, float mhr, float uc) {
  if (WiFi.status() != WL_CONNECTED) { connectWiFi(); return; }

  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = String("{") +
    "\"device_id\":\"" + DEVICE_ID + "\"," +
    "\"fhr_bpm\":" + String(fhr, 1) + "," +
    "\"mhr_bpm\":" + String(mhr, 1) + "," +
    "\"uc_per_10min\":" + String(uc, 1) + "}";

  int code = http.POST(payload);
  if (code > 0) {
    // response berisi status "collecting" (buffer_count/buffer_needed)
    // atau "predicted" (prediction.fhr.status, dst — sesuai schema baru)
    Serial.println("(" + String(code) + ") " + http.getString());
  } else {
    Serial.println("Gagal kirim: " + http.errorToString(code));
  }
  http.end();
}

void loop() {
  unsigned long now = millis();
  if (now - lastSend >= SEND_INTERVAL_MS) {
    lastSend = now;
    sendReading(readFHR(), readMHR(), readUC());
  }
}
