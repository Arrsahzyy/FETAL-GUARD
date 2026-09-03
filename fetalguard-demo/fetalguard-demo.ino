// =====================================================
// FETAL-GUARD - SKETCH DEMO KONEKTIVITAS (TANPA SENSOR)
// =====================================================
//
// Tujuan: membuktikan jalur ESP32-S3 -> BLE -> aplikasi pasien -> backend ->
// dashboard nakes, tanpa menunggu sensor fisik selesai dirancang.
//
// Sketch ini TIDAK membaca sensor apa pun. Ia membangkitkan gelombang sintetis
// dan mengirimkannya memakai protokol, framing, dan skema penandatanganan yang
// sama persis dengan firmware asli (fetalguard/fetalguard.ino). Jadi yang diuji
// adalah transport dan tampilan, BUKAN akuisisi sinyal.
//
// PERINGATAN: angka yang dihasilkan bukan pengukuran apa pun. Jangan pernah
// menampilkannya sebagai data klinis, dan jangan jalankan ini terhadap
// deployment production. Pakai pasien uji dan perangkat yang terdaftar sebagai
// hardware bench.
//
// Board: ESP32-S3 (Arduino core). Tidak perlu sensor terpasang.
//
// Langkah pakai:
//   1. Provision perangkat:  python backend/provision_devices.py --count 1 \
//        --prefix FG-BENCH --hardware bench-demo --out batch.csv
//   2. Salin device_uid dan packet_secret dari CSV ke dua konstanta di bawah.
//   3. Flash sketch ini.
//   4. Di aplikasi pasien: scan, tautkan dengan claim code dari CSV, mulai sesi.
//
// =====================================================

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <esp_system.h>
#include <mbedtls/md.h>
#include <math.h>
#include <time.h>

// ===== WAJIB DIISI SEBELUM FLASH =====================
// Harus sama persis dengan device_uid yang terdaftar di backend.
const char *FG_DEVICE_UID = "FG-BENCH-001";
// Kunci penandatanganan dari provision_devices.py. Biarkan kosong hanya jika
// perangkat belum diprovisikan dan backend belum mewajibkan tanda tangan.
const char *FG_DEVICE_PACKET_SECRET = "";
// =====================================================

// Kontrak BLE, identik dengan firmware asli.
const char *FG_BLE_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb";
const char *FG_BLE_CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb";

const unsigned long BLE_TELEMETRY_INTERVAL_MS = 1000;
const size_t BLE_MIN_NOTIFY_CHUNK_BYTES = 20;
const size_t BLE_MAX_NOTIFY_CHUNK_BYTES = 180;

// Laju per kanal, dilaporkan apa adanya di sample_rates_hz.
const uint16_t DEMO_PIEZO_RATE_HZ = 200;
const uint8_t DEMO_PIEZO_CHANNELS = 4;
const uint16_t DEMO_FSR_RATE_HZ = 50;
const uint16_t DEMO_PPG_RATE_HZ = 100;

// Profil sinyal sintetis.
const float DEMO_BASE_FHR_BPM = 140.0f;
const float DEMO_MATERNAL_HR_BPM = 82.0f;
// Setelah sekian detik, DJJ digeser keluar rentang rujukan 110-160 supaya jalur
// alert nakes bisa dilihat benar-benar terpicu, lalu dikembalikan normal.
const bool DEMO_DRIFT_ENABLED = true;
const unsigned long DEMO_DRIFT_CYCLE_S = 180;

BLECharacteristic *bleTelemetryCharacteristic = nullptr;
bool bleClientConnected = false;
bool bleClockSynchronized = false;
bool bleTelemetryV2Enabled = false;
size_t bleNotifyChunkBytes = BLE_MIN_NOTIFY_CHUNK_BYTES;
uint64_t bleEpochAtSyncMs = 0;
unsigned long bleMillisAtSync = 0;
unsigned long lastBleTelemetryMs = 0;
uint64_t bleSequenceNumber = 0;
char bleBootId[40] = {0};

// Indeks sampel global; menjaga fase gelombang tetap kontinu antar frame supaya
// jendela yang disambung backend tetap terbaca oleh autokorelasi.
uint32_t demoPiezoSampleIndex = 0;
uint32_t demoPpgSampleIndex = 0;
unsigned long demoStartedAtMs = 0;

// ===== WAKTU ==========================================

uint64_t currentGatewayEpochMs()
{
  if (!bleClockSynchronized)
    return 0;
  return bleEpochAtSyncMs + (uint64_t)(millis() - bleMillisAtSync);
}

bool formatGatewayTimestamp(char *output, size_t outputSize, uint64_t epochMs)
{
  if (epochMs == 0)
    return false;
  const time_t seconds = (time_t)(epochMs / 1000ULL);
  const unsigned int milliseconds = (unsigned int)(epochMs % 1000ULL);
  struct tm utcTime;
  if (gmtime_r(&seconds, &utcTime) == nullptr)
    return false;
  const int written = snprintf(
      output, outputSize, "%04d-%02d-%02dT%02d:%02d:%02d.%03uZ",
      utcTime.tm_year + 1900, utcTime.tm_mon + 1, utcTime.tm_mday,
      utcTime.tm_hour, utcTime.tm_min, utcTime.tm_sec, milliseconds);
  return written > 0 && (size_t)written < outputSize;
}

// ===== TANDA TANGAN PAKET =============================
// Skema identik dengan backend/core/device_auth.py dan firmware asli:
//   FGSIG1|<uid>|<boot_id>|<seq>|<captured_at_ms>|<schema>|<digest>
// digest = SHA-256 atas "p:<v,..>|fsr:<v,..>|hr_ir:<v,..>|hr_red:<v,..>",
// selalu memuat keempat kanal agar kanal yang hilang mengubah digest.

// Arduino's String gained an unsigned-long-long constructor only in newer cores,
// so 64-bit values are formatted explicitly to keep this sketch portable.
String uint64ToString(uint64_t value)
{
  char buffer[21];
  snprintf(buffer, sizeof(buffer), "%llu", (unsigned long long)value);
  return String(buffer);
}

String toHexString(const unsigned char *bytes, size_t length)
{
  static const char digits[] = "0123456789abcdef";
  String hex;
  hex.reserve(length * 2);
  for (size_t index = 0; index < length; index++)
  {
    hex += digits[(bytes[index] >> 4) & 0x0F];
    hex += digits[bytes[index] & 0x0F];
  }
  return hex;
}

String sha256Hex(const String &input)
{
  unsigned char digest[32];
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr)
    return String();
  mbedtls_md_context_t context;
  mbedtls_md_init(&context);
  const bool ok = mbedtls_md_setup(&context, info, 0) == 0 &&
                  mbedtls_md_starts(&context) == 0 &&
                  mbedtls_md_update(&context, (const unsigned char *)input.c_str(), input.length()) == 0 &&
                  mbedtls_md_finish(&context, digest) == 0;
  mbedtls_md_free(&context);
  return ok ? toHexString(digest, sizeof(digest)) : String();
}

String hmacSha256Hex(const char *key, const String &message)
{
  unsigned char digest[32];
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr || key == nullptr)
    return String();
  mbedtls_md_context_t context;
  mbedtls_md_init(&context);
  const bool ok = mbedtls_md_setup(&context, info, 1) == 0 &&
                  mbedtls_md_hmac_starts(&context, (const unsigned char *)key, strlen(key)) == 0 &&
                  mbedtls_md_hmac_update(&context, (const unsigned char *)message.c_str(), message.length()) == 0 &&
                  mbedtls_md_hmac_finish(&context, digest) == 0;
  mbedtls_md_free(&context);
  return ok ? toHexString(digest, sizeof(digest)) : String();
}

void appendPacketSignature(String &json, const String &canonicalChannels, uint64_t capturedAtMs)
{
  if (FG_DEVICE_PACKET_SECRET == nullptr || strlen(FG_DEVICE_PACKET_SECRET) == 0)
    return;
  const String digest = sha256Hex(canonicalChannels);
  if (digest.length() == 0)
    return;

  String message;
  message.reserve(160);
  message += "FGSIG1|";
  message += FG_DEVICE_UID;
  message += '|';
  message += bleBootId;
  message += '|';
  message += uint64ToString(bleSequenceNumber);
  message += '|';
  message += uint64ToString(capturedAtMs);
  message += "|2|";
  message += digest;

  const String signature = hmacSha256Hex(FG_DEVICE_PACKET_SECRET, message);
  if (signature.length() == 0)
    return;
  json += ",\"packet_signature\":\"";
  json += signature;
  json += '\"';
}

// ===== GELOMBANG SINTETIS =============================

// Denyut sebagai burst amplitudo sempit di awal tiap periode, dibawa osilasi
// yang lebih cepat - bentuk yang menyerupai getaran mekanik yang dilihat piezo.
int demoBeatSample(float bpm, uint16_t sampleRateHz, uint32_t index, float amplitude, float baseline)
{
  const float period = (sampleRateHz * 60.0f) / bpm;
  const float phase = fmodf((float)index, period) / period;
  const float envelope = expf(-powf(phase * 8.0f, 2.0f));
  const float carrier = sinf((2.0f * PI * 12.0f * index) / sampleRateHz);
  return (int)lroundf(baseline + amplitude * envelope * carrier);
}

float demoCurrentFhrBpm()
{
  if (!DEMO_DRIFT_ENABLED)
    return DEMO_BASE_FHR_BPM;
  const unsigned long elapsedS = (millis() - demoStartedAtMs) / 1000UL;
  const unsigned long cycle = elapsedS % DEMO_DRIFT_CYCLE_S;
  if (cycle < 60)
    return DEMO_BASE_FHR_BPM;
  if (cycle < 120)
  {
    // Turun perlahan hingga di bawah 110 bpm supaya alert terpicu.
    const float drop = (float)(cycle - 60) * 0.9f;
    return fmaxf(70.0f, DEMO_BASE_FHR_BPM - drop);
  }
  return DEMO_BASE_FHR_BPM;
}

String buildDemoTelemetryV2Frame()
{
  char capturedAt[32];
  const uint64_t capturedAtMs = currentGatewayEpochMs();
  if (!formatGatewayTimestamp(capturedAt, sizeof(capturedAt), capturedAtMs))
    return String();

  const float fhrBpm = demoCurrentFhrBpm();
  const uint16_t piezoFrames = DEMO_PIEZO_RATE_HZ;
  const uint16_t fsrSamples = DEMO_FSR_RATE_HZ;
  const uint16_t ppgSamples = DEMO_PPG_RATE_HZ;

  String json;
  json.reserve(14000);
  json += "{\"schema_version\":2,\"device_uid\":\"";
  json += FG_DEVICE_UID;
  json += "\",\"boot_id\":\"";
  json += bleBootId;
  json += "\",\"sequence_number\":";
  json += uint64ToString(bleSequenceNumber);
  json += ",\"captured_at\":\"";
  json += capturedAt;
  json += "\",\"sample_rates_hz\":{\"p\":";
  json += String(DEMO_PIEZO_RATE_HZ);
  json += ",\"fsr\":";
  json += String(DEMO_FSR_RATE_HZ);
  json += ",\"hr_ir\":";
  json += String(DEMO_PPG_RATE_HZ);
  json += ",\"hr_red\":";
  json += String(DEMO_PPG_RATE_HZ);
  json += "},\"channel_layout\":{\"p\":4},\"channels\":{";

  String canonical;
  canonical.reserve(6000);

  // Kanal piezo: hanya satu posisi yang "melihat" denyut, tiga lainnya tenang.
  // Ini sengaja, supaya backend benar-benar harus memilih kanal paling periodik.
  json += "\"p\":[";
  canonical += "p:";
  for (uint16_t frame = 0; frame < piezoFrames; frame++)
  {
    const uint32_t index = demoPiezoSampleIndex + frame;
    for (uint8_t channel = 0; channel < DEMO_PIEZO_CHANNELS; channel++)
    {
      if (frame > 0 || channel > 0)
      {
        json += ',';
        canonical += ',';
      }
      const int value = (channel == 2)
        ? demoBeatSample(fhrBpm, DEMO_PIEZO_RATE_HZ, index, 800.0f, 2048.0f)
        : 2048;
      const String sample = String(constrain(value, 0, 4095));
      json += sample;
      canonical += sample;
    }
  }
  json += "],\"fsr\":[";
  canonical += "|fsr:";
  for (uint16_t index = 0; index < fsrSamples; index++)
  {
    if (index > 0)
    {
      json += ',';
      canonical += ',';
    }
    const String sample = String(700);
    json += sample;
    canonical += sample;
  }
  json += "],\"hr_ir\":[";
  canonical += "|hr_ir:";
  String redChannel;
  String redCanonical;
  redChannel.reserve(1200);
  redCanonical.reserve(1200);
  for (uint16_t index = 0; index < ppgSamples; index++)
  {
    if (index > 0)
    {
      json += ',';
      canonical += ',';
      redChannel += ',';
      redCanonical += ',';
    }
    const int value = demoBeatSample(
        DEMO_MATERNAL_HR_BPM, DEMO_PPG_RATE_HZ, demoPpgSampleIndex + index, 6000.0f, 50000.0f);
    const String sample = String(constrain(value, 0, 262143));
    json += sample;
    canonical += sample;
    redChannel += sample;
    redCanonical += sample;
  }
  json += "],\"hr_red\":[";
  json += redChannel;
  json += "]}";
  canonical += "|hr_red:";
  canonical += redCanonical;

  appendPacketSignature(json, canonical, capturedAtMs);
  json += "}\n";

  demoPiezoSampleIndex += piezoFrames;
  demoPpgSampleIndex += ppgSamples;
  return json;
}

// ===== BLE ============================================

void notifyTelemetryFrame(const String &frame)
{
  if (bleTelemetryCharacteristic == nullptr || frame.length() == 0)
    return;
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(frame.c_str());
  for (size_t offset = 0; offset < frame.length(); offset += bleNotifyChunkBytes)
  {
    const size_t remaining = frame.length() - offset;
    const size_t chunkSize = remaining < bleNotifyChunkBytes ? remaining : bleNotifyChunkBytes;
    bleTelemetryCharacteristic->setValue((uint8_t *)(bytes + offset), chunkSize);
    bleTelemetryCharacteristic->notify();
    delay(bleNotifyChunkBytes == BLE_MIN_NOTIFY_CHUNK_BYTES ? 8 : 2);
  }
}

class FGDemoServerCallbacks : public BLEServerCallbacks
{
  void onConnect(BLEServer *server) override
  {
    (void)server;
    bleClientConnected = true;
    bleClockSynchronized = false;
    bleTelemetryV2Enabled = false;
    bleNotifyChunkBytes = BLE_MIN_NOTIFY_CHUNK_BYTES;
    lastBleTelemetryMs = 0;
    Serial.println("[BLE] Gateway terhubung; menunggu sinkronisasi waktu.");
  }

  void onDisconnect(BLEServer *server) override
  {
    (void)server;
    bleClientConnected = false;
    bleClockSynchronized = false;
    bleTelemetryV2Enabled = false;
    BLEDevice::startAdvertising();
    Serial.println("[BLE] Gateway terputus; advertising dimulai kembali.");
  }
};

class FGDemoTimeSyncCallbacks : public BLECharacteristicCallbacks
{
  void onWrite(BLECharacteristic *characteristic) override
  {
    String command = characteristic->getValue().c_str();
    command.trim();

    if (command.startsWith("V2:"))
    {
      const long requestedChunkBytes = command.substring(3).toInt();
      if (!bleClockSynchronized ||
          requestedChunkBytes < (long)BLE_MIN_NOTIFY_CHUNK_BYTES ||
          requestedChunkBytes > (long)BLE_MAX_NOTIFY_CHUNK_BYTES)
      {
        Serial.println("[BLE] Negosiasi telemetry v2 ditolak.");
        return;
      }
      bleNotifyChunkBytes = (size_t)requestedChunkBytes;
      bleTelemetryV2Enabled = true;
      lastBleTelemetryMs = millis();
      Serial.print("[BLE] Telemetry v2 aktif; fragment bytes: ");
      Serial.println((unsigned int)bleNotifyChunkBytes);
      return;
    }

    if (!command.startsWith("T") || command.length() < 14)
    {
      Serial.println("[BLE] Perintah gateway tidak dikenali.");
      return;
    }
    char *parseEnd = nullptr;
    const uint64_t unixMs = strtoull(command.c_str() + 1, &parseEnd, 10);
    const bool parsedAll = parseEnd != nullptr && *parseEnd == '\0';
    if (!parsedAll || unixMs < 1704067200000ULL)
    {
      Serial.println("[BLE] Sinkronisasi waktu ditolak.");
      return;
    }

    bleEpochAtSyncMs = unixMs;
    bleMillisAtSync = millis();
    bleClockSynchronized = true;
    bleTelemetryV2Enabled = false;
    bleNotifyChunkBytes = BLE_MIN_NOTIFY_CHUNK_BYTES;
    lastBleTelemetryMs = 0;
    Serial.println("[BLE] Waktu tersinkronisasi.");
  }
};

void setupBLEGateway()
{
  const uint64_t chipId = ESP.getEfuseMac();
  snprintf(bleBootId, sizeof(bleBootId), "boot-%08lx-%08lx",
           (unsigned long)(chipId & 0xFFFFFFFFULL), (unsigned long)esp_random());

  BLEDevice::init(FG_DEVICE_UID);
  BLEDevice::setMTU(185);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new FGDemoServerCallbacks());

  BLEService *service = server->createService(FG_BLE_SERVICE_UUID);
  bleTelemetryCharacteristic = service->createCharacteristic(
      FG_BLE_CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_NOTIFY |
          BLECharacteristic::PROPERTY_WRITE |
          BLECharacteristic::PROPERTY_WRITE_NR);
  bleTelemetryCharacteristic->addDescriptor(new BLE2902());
  bleTelemetryCharacteristic->setCallbacks(new FGDemoTimeSyncCallbacks());
  service->start();

  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(FG_BLE_SERVICE_UUID);
  advertising->setScanResponse(true);
  advertising->start();

  Serial.print("[BLE] Advertising sebagai ");
  Serial.println(FG_DEVICE_UID);
  Serial.print("[BLE] Boot ID: ");
  Serial.println(bleBootId);
}

// ===== SETUP / LOOP ===================================

void setup()
{
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("==================================================");
  Serial.println(" FETAL-GUARD DEMO KONEKTIVITAS - TANPA SENSOR");
  Serial.println(" Gelombang sintetis. Bukan data pasien.");
  Serial.println("==================================================");
  if (strlen(FG_DEVICE_PACKET_SECRET) == 0)
    Serial.println("[!] Kunci penandatanganan kosong: hanya untuk backend yang belum mewajibkan tanda tangan.");
  else
    Serial.println("[i] Paket ditandatangani dengan kunci perangkat.");

  demoStartedAtMs = millis();
  setupBLEGateway();
}

void loop()
{
  if (!bleClientConnected || !bleClockSynchronized || !bleTelemetryV2Enabled)
  {
    delay(50);
    return;
  }

  const unsigned long now = millis();
  if (now - lastBleTelemetryMs < BLE_TELEMETRY_INTERVAL_MS)
  {
    delay(5);
    return;
  }
  lastBleTelemetryMs = now;

  const String frame = buildDemoTelemetryV2Frame();
  if (frame.length() == 0)
    return;

  notifyTelemetryFrame(frame);
  bleSequenceNumber++;

  Serial.print("[TX] seq ");
  Serial.print((unsigned long)bleSequenceNumber);
  Serial.print("  bytes ");
  Serial.print(frame.length());
  Serial.print("  fhr ");
  Serial.print(demoCurrentFhrBpm(), 1);
  Serial.println(" bpm (sintetis)");
}
