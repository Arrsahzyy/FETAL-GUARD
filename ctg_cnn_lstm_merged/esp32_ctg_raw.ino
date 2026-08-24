/*
  esp32_ctg_raw.ino — baca 4 piezo (FHR) + MAX30102 (MHR) + FSR408 (UC),
  kumpulkan WINDOW_SEC detik, kirim array mentah ke /api/ingest-raw.
  Server yang mengolah jadi bpm (SQI seleksi piezo, dsb) — lihat
  app/services/sensor_pipeline.py.

  BUTUH LIBRARY: SparkFun MAX3010x (Library Manager Arduino IDE, cari
  "SparkFun MAX3010x Pulse and Proximity Sensor Library").
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include "MAX30105.h"

const char* WIFI_SSID     = "NAMA_WIFI_ANDA";
const char* WIFI_PASSWORD = "PASSWORD_WIFI_ANDA";
const char* API_URL       = "http://ALAMAT_VPS_ANDA:8000/api/ingest-raw";
const char* DEVICE_ID     = "esp32-ctg-01";

// Pin analog piezo (sesuaikan wiring Anda) & FSR
const int PIEZO_PINS[4] = {32, 33, 34, 35};
const int FSR_PIN = 36;

const float FS_PIEZO = 50.0;    // Hz
const float FS_MAX30102 = 50.0; // Hz
const float FS_FSR = 10.0;      // Hz
const int WINDOW_SEC = 4;

const int N_PIEZO = (int)(FS_PIEZO * WINDOW_SEC);
const int N_MAX = (int)(FS_MAX30102 * WINDOW_SEC);
const int N_FSR = (int)(FS_FSR * WINDOW_SEC);

float bufPiezo[4][200];  // pastikan >= N_PIEZO
float bufMax[200];
float bufFsr[40];

MAX30105 maxSensor;

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(400); }
  Serial.println("WiFi tersambung: " + WiFi.localIP().toString());
}

void setup() {
  Serial.begin(115200);
  connectWiFi();

  if (!maxSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 tidak terdeteksi — cek wiring I2C (SDA/SCL)!");
  } else {
    maxSensor.setup();  // konfigurasi default: LED brightness, sample rate, dst
  }
}

// Kumpulkan 1 window penuh (blocking, sesuai WINDOW_SEC)
void collectWindow() {
  unsigned long tPiezoNext = millis(), tMaxNext = millis(), tFsrNext = millis();
  int iPiezo = 0, iMax = 0, iFsr = 0;
  unsigned long start = millis();

  while (millis() - start < (unsigned long)(WINDOW_SEC * 1000)) {
    unsigned long now = millis();

    if (iPiezo < N_PIEZO && now >= tPiezoNext) {
      for (int p = 0; p < 4; p++) bufPiezo[p][iPiezo] = analogRead(PIEZO_PINS[p]) / 4095.0;
      iPiezo++;
      tPiezoNext += (unsigned long)(1000.0 / FS_PIEZO);
    }
    if (iMax < N_MAX && now >= tMaxNext) {
      bufMax[iMax] = (float)maxSensor.getIR();  // sinyal IR ~ dipakai utk deteksi pulsa
      iMax++;
      tMaxNext += (unsigned long)(1000.0 / FS_MAX30102);
    }
    if (iFsr < N_FSR && now >= tFsrNext) {
      bufFsr[iFsr] = analogRead(FSR_PIN) / 4095.0 * 1000.0;  // skala ke ~0-1000 spt di training
      iFsr++;
      tFsrNext += (unsigned long)(1000.0 / FS_FSR);
    }
  }
}

String arrayToJson(float* arr, int n) {
  String s = "[";
  for (int i = 0; i < n; i++) { s += String(arr[i], 3); if (i < n - 1) s += ","; }
  return s + "]";
}

void sendWindow() {
  if (WiFi.status() != WL_CONNECTED) { connectWiFi(); return; }

  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  payload += "\"piezo_1\":" + arrayToJson(bufPiezo[0], N_PIEZO) + ",";
  payload += "\"piezo_2\":" + arrayToJson(bufPiezo[1], N_PIEZO) + ",";
  payload += "\"piezo_3\":" + arrayToJson(bufPiezo[2], N_PIEZO) + ",";
  payload += "\"piezo_4\":" + arrayToJson(bufPiezo[3], N_PIEZO) + ",";
  payload += "\"max30102\":" + arrayToJson(bufMax, N_MAX) + ",";
  payload += "\"fsr\":" + arrayToJson(bufFsr, N_FSR);
  payload += "}";

  int code = http.POST(payload);
  if (code > 0) {
    Serial.println("(" + String(code) + ") " + http.getString());
  } else {
    Serial.println("Gagal kirim: " + http.errorToString(code));
  }
  http.end();
}

void loop() {
  collectWindow();
  sendWindow();
}
