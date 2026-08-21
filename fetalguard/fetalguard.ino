#include <Wire.h>
#include <SPI.h>
#include <math.h>
#include <time.h>
#include <esp_system.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "MAX30105.h"
#include "spo2_algorithm.h"

// =====================================================
// FETAL-GUARD
// MAX30102 (STABIL) + FSR408 (STABIL) + 4 PIEZO ADS1256 (V12 V6 MINIMAL-REFINED)
// ESP32-S3
// =====================================================

MAX30105 max30102;

// =====================================================
// PIN
// =====================================================
#define SDA_PIN 8
#define SCL_PIN 9
#define FSR_PIN 4

// ADS1256 module:
// CS->GPIO10, DIN->GPIO11, SCLK->GPIO12,
// DOUT->GPIO13, DRDY->GPIO14, RST->GPIO15.
// Modul yang dipakai TIDAK mengekspos pin SYNC;
// sinkronisasi dilakukan dengan command SPI.
#define ADS_CS_PIN    10
#define ADS_MOSI_PIN  11
#define ADS_SCLK_PIN  12
#define ADS_MISO_PIN  13
#define ADS_DRDY_PIN  14
#define ADS_RESET_PIN 15

// =====================================================
// IDENTITAS + BLE GATEWAY
// =====================================================
// Nilai ini harus sama persis dengan device_uid yang didaftarkan admin.
// Tidak mengandung password, token pasien, atau secret backend.
const char *FG_DEVICE_UID = "FETAL-GUARD-001";
const char *FG_BLE_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb";
const char *FG_BLE_CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb";

// Paket JSON dikirim satu kali per detik. Potongan 20 byte aman untuk
// koneksi yang masih memakai ATT MTU minimum dan dirakit kembali oleh app.
const unsigned long BLE_TELEMETRY_INTERVAL_MS = 1000;
const size_t BLE_NOTIFY_CHUNK_BYTES = 20;

// =====================================================
// MAX30102 - SETTING DIFREEZE / TIDAK DIUBAH
// =====================================================
const int FG_BUFFER_SIZE = 100;
const int FG_UPDATE_SAMPLES = 25;
const int FG_KEEP_SAMPLES = FG_BUFFER_SIZE - FG_UPDATE_SAMPLES;
const int FG_STABILIZE_SAMPLES = 50;

const uint32_t FINGER_THRESHOLD = 10000;
const unsigned long SAMPLE_TIMEOUT_MS = 1500;

const byte LED_BRIGHTNESS = 0x1F;
const byte SAMPLE_AVERAGE = 4;
const byte LED_MODE = 2;
const int SAMPLE_RATE = 100;
const int PULSE_WIDTH = 411;
const int ADC_RANGE = 4096;

const uint32_t RAW_SATURATION_WARNING = 240000;

// =====================================================
// FILTER HASIL MAX30102 - TIDAK DIUBAH
// =====================================================
const byte HR_HISTORY_SIZE = 7;
const byte SPO2_HISTORY_SIZE = 5;

const byte MIN_HR_VALID_FOR_OUTPUT = 3;
const byte MIN_SPO2_VALID_FOR_OUTPUT = 3;

const int HR_MIN_VALID = 40;
const int HR_MAX_VALID = 180;
const int SPO2_MIN_VALID = 70;
const int SPO2_MAX_VALID = 100;

const float HR_ALPHA = 0.30f;
const float SPO2_ALPHA = 0.25f;
const byte MAX_INVALID_STREAK = 2;

// =====================================================
// BUFFER MAX30102
// =====================================================
uint32_t irBuffer[FG_BUFFER_SIZE];
uint32_t redBuffer[FG_BUFFER_SIZE];

int32_t spo2Raw = 0;
int8_t validSPO2Raw = 0;

int32_t heartRateRaw = 0;
int8_t validHeartRateRaw = 0;

int hrHistory[HR_HISTORY_SIZE];
byte hrHistoryCount = 0;
byte hrHistoryIndex = 0;

float hrFiltered = 0.0f;
bool hrFilteredReady = false;
byte hrInvalidStreak = 0;

int spo2History[SPO2_HISTORY_SIZE];
byte spo2HistoryCount = 0;
byte spo2HistoryIndex = 0;

float spo2Filtered = 0.0f;
bool spo2FilteredReady = false;
byte spo2InvalidStreak = 0;

bool maxBufferReady = false;
bool fingerPresent = false;

float maxActualFs = 0.0f;

// =====================================================
// FSR408 - FILTER DAN BASELINE BARU
// =====================================================

// FSR dibaca setiap 20 ms = 50 Hz
const unsigned long FSR_SAMPLE_INTERVAL_MS = 20;
unsigned long lastFSRSample = 0;

// Ambil median 5 kali ADC untuk mengurangi spike
const byte FSR_MEDIAN_SAMPLES = 5;

// EMA dibuat cukup halus tetapi masih responsif
const float FSR_ALPHA = 0.12f;

bool fsrFilterInitialized = false;

int fsrRawADC = 0;
float fsrFilteredADC = 0.0f;
float fsrVoltage = 0.0f;

// Baseline 5 detik
bool fsrBaselineReady = false;
unsigned long fsrCalibrationStart = 0;
const unsigned long FSR_CALIBRATION_TIME_MS = 5000;

float fsrBaselineSum = 0.0f;
uint32_t fsrBaselineSamples = 0;
float fsrBaseline = 0.0f;

// Rekam noise baseline untuk threshold adaptif
float fsrBaselineMin = 4095.0f;
float fsrBaselineMax = 0.0f;
float fsrBaselineNoise = 0.0f;

// Nilai perubahan aktual
float fsrDeltaADC = 0.0f;
float fsrDeltaVoltage = 0.0f;

// Threshold minimum.
// Threshold final akan dibuat lebih besar bila noise baseline besar.
const float FSR_MIN_ON_DELTA_ADC = 60.0f;
const float FSR_MIN_OFF_DELTA_ADC = 30.0f;

float fsrOnThresholdADC = FSR_MIN_ON_DELTA_ADC;
float fsrOffThresholdADC = FSR_MIN_OFF_DELTA_ADC;

bool pressureActive = false;
unsigned long pressureStartTime = 0;
unsigned long pressureDuration = 0;

// =====================================================
// ADS1256 + 4 PIEZO - LOGIKA PIEZO DIADAPTASI DARI V3 LAMA
// =====================================================
// Hardware analog yang dipakai sekarang:
// P1 -> AN0, P2 -> AN1, P3 -> AN2, P4 -> AN3
// VCM 2.5 V -> ACOM
//
// Berbeda dari ADS1115 lama, ADS1256 membaca DIFFERENTIAL:
// ANx - ACOM. Karena output op-amp idle berada dekat VCM,
// nilai DC differential memang seharusnya dekat 0 mV.

const uint8_t ADS_REG_STATUS = 0x00;
const uint8_t ADS_REG_MUX    = 0x01;
const uint8_t ADS_REG_ADCON  = 0x02;
const uint8_t ADS_REG_DRATE  = 0x03;

const uint8_t ADS_CMD_WAKEUP  = 0x00;
const uint8_t ADS_CMD_RDATA   = 0x01;
const uint8_t ADS_CMD_SDATAC  = 0x0F;
const uint8_t ADS_CMD_RREG    = 0x10;
const uint8_t ADS_CMD_WREG    = 0x50;
const uint8_t ADS_CMD_SELFCAL = 0xF0;
const uint8_t ADS_CMD_SYNC    = 0xFC;

// 7500 SPS @ 7.68 MHz.
const uint8_t ADS_DRATE_7500 = 0xD0;

// Modul ADS1256 orange board menggunakan reference 2.5 V onboard.
const float ADS_VREF = 2.5f;

// Mulai dari PGA=1 agar ketukan/gerakan besar tidak mudah clipping.
const uint8_t ADS_PGA_CODE = 0x00;
const float ADS_PGA = 1.0f;

SPISettings adsSPISettings(1000000, MSBFIRST, SPI_MODE1);

const byte PIEZO_COUNT = 4;

// 0=P1, 1=P2, 2=P3, 3=P4.
// Pada V4 semua channel tetap dibaca, lalu sistem memilih channel dengan
// rasio signal/noise terbaik secara perlahan agar tidak pindah-pindah tiap sampel.
const uint8_t FHR_PIEZO_CHANNEL = 3; // fallback

// -1=AUTO, 0=P1, 1=P2, 2=P3, 3=P4.
// Untuk mengecek satu piezo secara individual boleh dipaksa sementara.
// Untuk monitoring sebenarnya biarkan -1.
const int8_t MANUAL_PIEZO_CHANNEL = -1;
const bool AUTO_SELECT_FHR_PIEZO = true;

// Pertahankan 200 sample/s/channel agar pembacaan ADS1256 + MAX30102 + FSR
// tetap stabil pada hardware yang sudah diuji.
const unsigned long PIEZO_SAMPLE_INTERVAL_US = 5000;
unsigned long lastPiezoSampleUs = 0;

bool adsReady = false;
bool adsDRDYTimeout = false;
bool adsRegisterError = false;

uint8_t adsStatusReadback = 0;
uint8_t adsMuxReadback = 0;
uint8_t adsAdconReadback = 0;
uint8_t adsDrateReadback = 0;

int32_t piezoRaw[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoDiffmV[PIEZO_COUNT] = {0, 0, 0, 0};

// Baseline differential ANx-ACOM, dalam mV.
float piezoBaselineMv[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoACmV[PIEZO_COUNT] = {0, 0, 0, 0};

// Filter digital untuk komponen mekanik denyut jantung.
// Dengan fs ~200 Hz/channel, koefisien ini mengarahkan respons utama kira-kira
// ke band belasan Hz sampai puluhan Hz, bukan drift/gerakan sangat lambat.
float piezoHighPass[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoPreviousInput[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoBandPass[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoWindowPeak[PIEZO_COUNT] = {0, 0, 0, 0};

float piezoNoiseStdMv[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoThresholdMv[PIEZO_COUNT] = {0, 0, 0, 0};

// V5 lebih sensitif pada sinyal mekanik kecil.
// Pada fs sekitar 200 Hz/channel, ini kira-kira HPF 8 Hz dan LPF 90 Hz.
const float HP_ALPHA = 0.800f;
const float LP_ALPHA = 0.740f;

const float BASELINE_TRACK_ALPHA = 0.00025f;
const float THRESHOLD_NOISE_MULTIPLIER = 2.5f;
const float MIN_THRESHOLD_MV = 0.08f;
const float MAX_THRESHOLD_MV = 3.0f;

// Threshold dinamis + normalisasi per-channel.
float piezoNoiseAbsEMA[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoDynamicThresholdMv[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoNormalized[PIEZO_COUNT] = {0, 0, 0, 0};

const float RUNNING_NOISE_ALPHA = 0.0020f;
const float RUNNING_NOISE_MULTIPLIER = 2.8f;

float piezoEnvelopeEMA[PIEZO_COUNT] = {0, 0, 0, 0};
float piezoQuality[PIEZO_COUNT] = {0, 0, 0, 0};
const float PIEZO_ENVELOPE_ALPHA = 0.025f;

// =====================================================
// AUTO SELECT 2 FASE
// =====================================================
// FASE SEARCH:
// sebelum FHR valid, sistem harus cepat mencari kanal terbaik.
//
// FASE LOCK:
// setelah FHR valid, perpindahan kanal dibuat lebih ketat agar FHR
// tidak putus hanya karena satu transient.
//
// Active Piezo = kanal yang dipakai DETEKTOR FHR.
// Strongest Now = kanal dengan |Norm| terbesar pada frame saat ini.
// Best Quality  = kanal dengan quality EMA terbesar.
//
// Karena getaran dapat merambat antarpiezo, Strongest Now tidak selalu sama
// dengan sensor yang secara fisik sedang disentuh/diketuk.

const unsigned long SEARCH_SELECT_INTERVAL_MS = 500;
const float SEARCH_SWITCH_HYSTERESIS = 1.10f;
const byte SEARCH_WIN_REQUIRED = 2;
const unsigned long SEARCH_MIN_HOLD_MS = 800;

const unsigned long LOCK_SELECT_INTERVAL_MS = 1000;
const float LOCK_SWITCH_HYSTERESIS = 1.35f;
const byte LOCK_WIN_REQUIRED = 3;
const unsigned long LOCK_MIN_HOLD_MS = 4000;

unsigned long lastChannelSelectMs = 0;
unsigned long activePiezoSinceMs = 0;

int candidatePiezo = FHR_PIEZO_CHANNEL;
byte candidatePiezoWins = 0;

bool activePiezoInitialized = false;

int strongestPiezoNow = 0;
int bestQualityPiezo = 0;

int activePiezo = FHR_PIEZO_CHANNEL;
float selectedPiezoRaw = 0.0f;
float selectedPiezo = 0.0f;
float selectedPiezoNorm = 0.0f;

// FHR detector.
// Satu siklus jantung menghasilkan S1 dan S2, jadi peak tidak langsung
// dianggap satu denyut. Refractory + interval-valid + konsistensi beberapa
// denyut dipakai sebelum FHR dinyatakan siap.
float prePreviousAbsPiezo = 0.0f;
float previousAbsPiezo = 0.0f;
unsigned long lastPeakTime = 0;
unsigned long lastPeakIntervalMs = 0;
unsigned long lastValidFHRTime = 0;
float lastPeakAmplitude = 0.0f;
uint32_t detectedPeakCount = 0;
float fetalBPM = 0.0f;
float fetalBPMFiltered = 0.0f;

const unsigned long REFRACTORY_TIME_MS = 250;

// Untuk validasi sinyal kecil (mis. nadi pergelangan), tampilkan mechanical BPM
// tanpa melabelinya sebagai FHR.
const float MIN_MECHANICAL_BPM = 45.0f;
const float MAX_MECHANICAL_BPM = 240.0f;

const float MIN_FETAL_BPM = 80.0f;
const float MAX_FETAL_BPM = 220.0f;
const float BPM_FILTER_ALPHA = 0.35f;

// Lebih responsif dari V4: cukup 2 interval konsisten.
const byte MIN_CONSISTENT_FHR_BEATS = 2;
const float MAX_FHR_JUMP_FRACTION = 0.30f;

byte consistentFHRBeats = 0;
float previousCandidateBPM = 0.0f;
float mechanicalBPM = 0.0f;
bool fetalHRReady = false;
bool fetalNearMaternal = false;

// =====================================================
// V12 - HANYA REFINEMENT VALIDASI FHR
// =====================================================
// Tidak mengubah filter, threshold, sampling, ADS, MAX30102, atau FSR.
//
// Problem V6:
//   kandidat valid 1 -> satu interval jelek -> balik valid 1 / 0.
// V12:
//   satu interval jelek hanya diberi toleransi; dua mismatch berturut-turut
//   baru memulai kandidat baru.
//
// Selama Valid=1 masih fresh, Active Piezo juga ditahan agar selector tidak
// mereset detector di tengah proses.
unsigned long lastFHRValidationMs = 0;
const unsigned long FHR_VALIDATION_HOLD_MS = 2200;

byte fhrMismatchStreak = 0;
const byte MAX_FHR_MISMATCH_STREAK = 2;

// Bersihkan angka Mechanical/FHR Candidate bila sinyal sudah hilang,
// tetapi jangan membuat detector terlalu ketat.
const unsigned long BPM_DISPLAY_STALE_MS = 1600;

// Sampling rate aktual.
uint32_t piezoFramesInRateWindow = 0;
unsigned long piezoRateWindowStartMs = 0;
float piezoActualFsPerChannel = 0.0f;

// Diagnostik khusus bila seluruh data ADS terus persis nol.
uint16_t adsAllZeroStreak = 0;
bool adsAllZeroWarning = false;

// =====================================================
// OUTPUT SERIAL INDEPENDEN
// =====================================================
unsigned long lastSystemPrint = 0;
const unsigned long SYSTEM_PRINT_INTERVAL_MS = 1000;

BLECharacteristic *bleTelemetryCharacteristic = nullptr;
bool bleClientConnected = false;
bool bleClockSynchronized = false;
uint64_t bleEpochAtSyncMs = 0;
uint32_t bleMillisAtSync = 0;
uint64_t bleSequenceNumber = 0;
unsigned long lastBleTelemetryMs = 0;
char bleBootId[40] = {0};

// =====================================================
// FORWARD DECLARATION
// =====================================================
void updateFSR();
void updatePiezos();
void calculateFHR();
void calibratePiezos();
void printSystemStatus();
void updatePiezoSelector();
void setupBLEGateway();
void sendTelemetryIfDue();

// =====================================================
// UTILITAS SORT
// =====================================================
void sortIntArray(int *data, byte count)
{
  for (byte i = 0; i < count; i++)
  {
    for (byte j = i + 1; j < count; j++)
    {
      if (data[j] < data[i])
      {
        int temp = data[i];
        data[i] = data[j];
        data[j] = temp;
      }
    }
  }
}

int medianFromHistory(const int *history, byte count)
{
  if (count == 0)
    return 0;

  int temp[HR_HISTORY_SIZE];

  for (byte i = 0; i < count; i++)
    temp[i] = history[i];

  sortIntArray(temp, count);

  if (count % 2 == 1)
    return temp[count / 2];

  return (temp[count / 2 - 1] + temp[count / 2]) / 2;
}

// =====================================================
// MEDIAN ADC FSR
// =====================================================
int readFSRMedianADC()
{
  int samples[FSR_MEDIAN_SAMPLES];

  for (byte i = 0; i < FSR_MEDIAN_SAMPLES; i++)
  {
    samples[i] = analogRead(FSR_PIN);
  }

  sortIntArray(samples, FSR_MEDIAN_SAMPLES);

  return samples[FSR_MEDIAN_SAMPLES / 2];
}

// =====================================================
// RESET FILTER MAX30102
// =====================================================
void resetMAXResultFilters()
{
  hrHistoryCount = 0;
  hrHistoryIndex = 0;
  hrFiltered = 0.0f;
  hrFilteredReady = false;
  hrInvalidStreak = 0;

  spo2HistoryCount = 0;
  spo2HistoryIndex = 0;
  spo2Filtered = 0.0f;
  spo2FilteredReady = false;
  spo2InvalidStreak = 0;
}

// =====================================================
// FILTER HR MAX30102
// =====================================================
void updateHRFilter()
{
  bool rawValid =
    validHeartRateRaw &&
    heartRateRaw >= HR_MIN_VALID &&
    heartRateRaw <= HR_MAX_VALID;

  if (!rawValid)
  {
    if (hrInvalidStreak < 255)
      hrInvalidStreak++;

    if (hrInvalidStreak > MAX_INVALID_STREAK)
      hrFilteredReady = false;

    return;
  }

  hrInvalidStreak = 0;

  hrHistory[hrHistoryIndex] = heartRateRaw;
  hrHistoryIndex++;
  hrHistoryIndex %= HR_HISTORY_SIZE;

  if (hrHistoryCount < HR_HISTORY_SIZE)
    hrHistoryCount++;

  int hrMedian = medianFromHistory(hrHistory, hrHistoryCount);

  if (!hrFilteredReady)
  {
    hrFiltered = hrMedian;

    if (hrHistoryCount >= MIN_HR_VALID_FOR_OUTPUT)
      hrFilteredReady = true;
  }
  else
  {
    hrFiltered =
      HR_ALPHA * hrMedian +
      (1.0f - HR_ALPHA) * hrFiltered;
  }
}

// =====================================================
// FILTER SPO2 MAX30102
// =====================================================
void updateSpO2Filter()
{
  bool rawValid =
    validSPO2Raw &&
    spo2Raw >= SPO2_MIN_VALID &&
    spo2Raw <= SPO2_MAX_VALID;

  if (!rawValid)
  {
    if (spo2InvalidStreak < 255)
      spo2InvalidStreak++;

    if (spo2InvalidStreak > MAX_INVALID_STREAK)
      spo2FilteredReady = false;

    return;
  }

  spo2InvalidStreak = 0;

  spo2History[spo2HistoryIndex] = spo2Raw;
  spo2HistoryIndex++;
  spo2HistoryIndex %= SPO2_HISTORY_SIZE;

  if (spo2HistoryCount < SPO2_HISTORY_SIZE)
    spo2HistoryCount++;

  int spo2Median =
    medianFromHistory(spo2History, spo2HistoryCount);

  if (!spo2FilteredReady)
  {
    spo2Filtered = spo2Median;

    if (spo2HistoryCount >= MIN_SPO2_VALID_FOR_OUTPUT)
      spo2FilteredReady = true;
  }
  else
  {
    spo2Filtered =
      SPO2_ALPHA * spo2Median +
      (1.0f - SPO2_ALPHA) * spo2Filtered;
  }
}

// =====================================================
// UPDATE FSR408
// =====================================================
void updateFSR()
{
  unsigned long now = millis();

  if (now - lastFSRSample < FSR_SAMPLE_INTERVAL_MS)
    return;

  lastFSRSample = now;

  // 1. Median filter 5 pembacaan ADC
  fsrRawADC = readFSRMedianADC();

  // 2. EMA
  if (!fsrFilterInitialized)
  {
    fsrFilteredADC = fsrRawADC;
    fsrFilterInitialized = true;
  }
  else
  {
    fsrFilteredADC =
      (FSR_ALPHA * fsrRawADC) +
      ((1.0f - FSR_ALPHA) * fsrFilteredADC);
  }

  // Tegangan estimasi dari ADC 12-bit
  fsrVoltage =
    fsrFilteredADC *
    (3.3f / 4095.0f);

  // ===================================================
  // KALIBRASI BASELINE
  // ===================================================
  if (!fsrBaselineReady)
  {
    fsrBaselineSum += fsrFilteredADC;
    fsrBaselineSamples++;

    if (fsrFilteredADC < fsrBaselineMin)
      fsrBaselineMin = fsrFilteredADC;

    if (fsrFilteredADC > fsrBaselineMax)
      fsrBaselineMax = fsrFilteredADC;

    if (
      now - fsrCalibrationStart >=
      FSR_CALIBRATION_TIME_MS
    )
    {
      if (fsrBaselineSamples > 0)
      {
        fsrBaseline =
          fsrBaselineSum /
          (float)fsrBaselineSamples;
      }
      else
      {
        fsrBaseline = fsrFilteredADC;
      }

      fsrBaselineNoise =
        fsrBaselineMax -
        fsrBaselineMin;

      // Threshold adaptif berdasarkan noise baseline
      fsrOnThresholdADC =
        fsrBaselineNoise * 4.0f;

      fsrOffThresholdADC =
        fsrBaselineNoise * 2.0f;

      if (fsrOnThresholdADC < FSR_MIN_ON_DELTA_ADC)
        fsrOnThresholdADC = FSR_MIN_ON_DELTA_ADC;

      if (fsrOffThresholdADC < FSR_MIN_OFF_DELTA_ADC)
        fsrOffThresholdADC = FSR_MIN_OFF_DELTA_ADC;

      // Pastikan OFF selalu lebih kecil dari ON
      if (fsrOffThresholdADC >= fsrOnThresholdADC)
        fsrOffThresholdADC = fsrOnThresholdADC * 0.5f;

      fsrBaselineReady = true;

      Serial.println();
      Serial.print(">>> Baseline FSR selesai: ");
      Serial.println(fsrBaseline, 1);

      Serial.print(">>> Noise baseline FSR  : ");
      Serial.println(fsrBaselineNoise, 1);

      Serial.print(">>> Threshold ON        : +");
      Serial.print(fsrOnThresholdADC, 1);
      Serial.println(" ADC");

      Serial.print(">>> Threshold OFF       : +");
      Serial.print(fsrOffThresholdADC, 1);
      Serial.println(" ADC");
    }

    return;
  }

  // ===================================================
  // DELTA FSR
  // ===================================================
  fsrDeltaADC =
    fsrFilteredADC -
    fsrBaseline;

  // Untuk tekanan, kita hanya melihat kenaikan dari baseline
  if (fsrDeltaADC < 0.0f)
    fsrDeltaADC = 0.0f;

  fsrDeltaVoltage =
    fsrDeltaADC *
    (3.3f / 4095.0f);

  // ===================================================
  // DETEKSI PENINGKATAN TEKANAN
  // Hysteresis agar status tidak berkedip
  // ===================================================
  if (!pressureActive)
  {
    if (fsrDeltaADC >= fsrOnThresholdADC)
    {
      pressureActive = true;
      pressureStartTime = now;
      pressureDuration = 0;
    }
  }
  else
  {
    pressureDuration =
      now -
      pressureStartTime;

    if (fsrDeltaADC <= fsrOffThresholdADC)
    {
      pressureActive = false;
      pressureDuration = 0;
    }
  }
}

// =====================================================
// ADS1256 - LOW LEVEL
// =====================================================
void adsSelect()
{
  SPI.beginTransaction(adsSPISettings);
  digitalWrite(ADS_CS_PIN, LOW);
}

void adsDeselect()
{
  digitalWrite(ADS_CS_PIN, HIGH);
  SPI.endTransaction();
}

void adsCommand(uint8_t command)
{
  adsSelect();
  SPI.transfer(command);
  adsDeselect();
  delayMicroseconds(4);
}

bool adsWaitDRDYLow(unsigned long timeoutUs)
{
  unsigned long start = micros();
  while (digitalRead(ADS_DRDY_PIN) == HIGH)
  {
    if ((unsigned long)(micros() - start) >= timeoutUs)
      return false;
  }
  return true;
}

// Setelah SYNC + WAKEUP, ADS1256 memaksa DRDY HIGH lalu LOW
// ketika data baru valid. Fungsi ini mencegah kita membaca status LOW lama
// dari konversi sebelumnya.
bool adsWaitNewConversion(unsigned long timeoutUs)
{
  unsigned long start = micros();

  // Tunggu DRDY benar-benar menjadi HIGH terlebih dahulu.
  while (digitalRead(ADS_DRDY_PIN) == LOW)
  {
    if ((unsigned long)(micros() - start) >= timeoutUs)
      return false;
  }

  // Lalu tunggu data baru: DRDY LOW.
  while (digitalRead(ADS_DRDY_PIN) == HIGH)
  {
    if ((unsigned long)(micros() - start) >= timeoutUs)
      return false;
  }

  return true;
}

void adsWriteRegister(uint8_t reg, uint8_t value)
{
  adsSelect();
  SPI.transfer(ADS_CMD_WREG | (reg & 0x0F));
  SPI.transfer(0x00); // satu register
  SPI.transfer(value);
  adsDeselect();
  delayMicroseconds(4);
}

uint8_t adsReadRegister(uint8_t reg)
{
  adsSelect();
  SPI.transfer(ADS_CMD_RREG | (reg & 0x0F));
  SPI.transfer(0x00);

  // t6 >= 50 * tauCLKIN. Pada 7.68 MHz sekitar 6.5 us.
  delayMicroseconds(10);

  uint8_t value = SPI.transfer(0xFF);
  adsDeselect();
  delayMicroseconds(4);
  return value;
}

void adsHardwareReset()
{
  digitalWrite(ADS_RESET_PIN, HIGH);
  delay(1);
  digitalWrite(ADS_RESET_PIN, LOW);
  delayMicroseconds(20);
  digitalWrite(ADS_RESET_PIN, HIGH);
  delay(10);
}

bool adsInit()
{
  pinMode(ADS_CS_PIN, OUTPUT);
  pinMode(ADS_DRDY_PIN, INPUT);
  pinMode(ADS_RESET_PIN, OUTPUT);

  digitalWrite(ADS_CS_PIN, HIGH);
  digitalWrite(ADS_RESET_PIN, HIGH);

  SPI.begin(ADS_SCLK_PIN, ADS_MISO_PIN, ADS_MOSI_PIN, ADS_CS_PIN);

  adsHardwareReset();

  if (!adsWaitDRDYLow(150000))
    return false;

  adsCommand(ADS_CMD_SDATAC);

  // STATUS: MSB first, ACAL off, buffer off.
  adsWriteRegister(ADS_REG_STATUS, 0x00);
  // ADCON: clock out off, sensor detect off, PGA1.
  adsWriteRegister(ADS_REG_ADCON, ADS_PGA_CODE);
  // 7500 SPS.
  adsWriteRegister(ADS_REG_DRATE, ADS_DRATE_7500);
  // AN0 - ACOM.
  adsWriteRegister(ADS_REG_MUX, 0x08);

  adsCommand(ADS_CMD_SELFCAL);
  if (!adsWaitDRDYLow(150000))
    return false;

  // PENTING: read-back register. Kalau DOUT/MISO tidak benar, kode lama
  // bisa terlihat "OK" tetapi semua data 0. Sekarang kondisi itu ditolak.
  adsStatusReadback = adsReadRegister(ADS_REG_STATUS);
  adsMuxReadback    = adsReadRegister(ADS_REG_MUX);
  adsAdconReadback  = adsReadRegister(ADS_REG_ADCON);
  adsDrateReadback  = adsReadRegister(ADS_REG_DRATE);

  adsRegisterError =
    ((adsMuxReadback & 0xFF) != 0x08) ||
    ((adsAdconReadback & 0x07) != ADS_PGA_CODE) ||
    (adsDrateReadback != ADS_DRATE_7500);

  if (adsRegisterError)
    return false;

  return true;
}

// =====================================================
// ADS1256 - READ ANx - ACOM
// =====================================================
bool adsReadPiezoChannel(uint8_t channel, int32_t &raw)
{
  if (channel >= PIEZO_COUNT)
    return false;

  const uint8_t mux = (uint8_t)((channel << 4) | 0x08);
  adsWriteRegister(ADS_REG_MUX, mux);

  // Sequence multiplexing: WREG MUX -> SYNC -> WAKEUP -> tunggu data baru.
  adsCommand(ADS_CMD_SYNC);
  delayMicroseconds(4);
  adsCommand(ADS_CMD_WAKEUP);

  if (!adsWaitNewConversion(4000))
  {
    adsDRDYTimeout = true;
    return false;
  }

  adsSelect();
  SPI.transfer(ADS_CMD_RDATA);
  delayMicroseconds(10);

  uint32_t value = 0;
  value |= ((uint32_t)SPI.transfer(0xFF) << 16);
  value |= ((uint32_t)SPI.transfer(0xFF) << 8);
  value |= ((uint32_t)SPI.transfer(0xFF));
  adsDeselect();

  if (value & 0x800000UL)
    value |= 0xFF000000UL;

  raw = (int32_t)value;
  return true;
}

float adsCountsToMilliVolts(int32_t raw)
{
  const float fullScaleVolts = (2.0f * ADS_VREF) / ADS_PGA;
  return ((float)raw / 8388607.0f) * fullScaleVolts * 1000.0f;
}

float clampFloat(float value, float minimum, float maximum)
{
  if (value < minimum) return minimum;
  if (value > maximum) return maximum;
  return value;
}


// =====================================================
// RESET DETEKTOR FHR SAAT CHANNEL BERPINDAH
// =====================================================
void resetFHRDetectorOnly()
{
  prePreviousAbsPiezo = 0.0f;
  previousAbsPiezo = 0.0f;
  lastPeakTime = 0;
  lastPeakIntervalMs = 0;
  lastValidFHRTime = 0;
  lastPeakAmplitude = 0.0f;
  fetalBPM = 0.0f;
  fetalBPMFiltered = 0.0f;
  mechanicalBPM = 0.0f;
  consistentFHRBeats = 0;
  previousCandidateBPM = 0.0f;
  fetalHRReady = false;
  fetalNearMaternal = false;

  lastFHRValidationMs = 0;
  fhrMismatchStreak = 0;
}

// =====================================================
// PIEZO CALIBRATION - DIADAPTASI DARI KODE V3 LAMA
// =====================================================
void calibratePiezos()
{
  if (!adsReady)
    return;

  Serial.println();
  Serial.println("PIEZO CALIBRATION:");
  Serial.println("DIAMKAN SABUK/SENSOR SELAMA KALIBRASI; JANGAN DIGERAKKAN...");
  Serial.println("Tahap 1: baseline ANx-ACOM");

  // ---------------------------------------------------
  // TAHAP 1 - baseline differential masing-masing kanal
  // ---------------------------------------------------
  const int BASELINE_SAMPLES = 200;

  for (uint8_t ch = 0; ch < PIEZO_COUNT; ch++)
  {
    double meanMv = 0.0;
    int validSamples = 0;

    for (int i = 0; i < BASELINE_SAMPLES; i++)
    {
      int32_t raw = 0;
      if (!adsReadPiezoChannel(ch, raw))
        continue;

      float mv = adsCountsToMilliVolts(raw);
      validSamples++;
      meanMv += ((double)mv - meanMv) / (double)validSamples;
      updateFSR();
    }

    if (validSamples < 10)
    {
      Serial.print("Piezo ");
      Serial.print(ch + 1);
      Serial.println(" baseline GAGAL");
      continue;
    }

    piezoBaselineMv[ch] = (float)meanMv;
  }

  // Reset filter sebelum mengukur noise BAND-PASS.
  for (uint8_t ch = 0; ch < PIEZO_COUNT; ch++)
  {
    piezoACmV[ch] = 0.0f;
    piezoHighPass[ch] = 0.0f;
    piezoPreviousInput[ch] = 0.0f;
    piezoBandPass[ch] = 0.0f;
    piezoWindowPeak[ch] = 0.0f;
  }

  Serial.println("Tahap 2: estimasi noise setelah filter fetal-heart pada 200 Hz/channel");

  // ---------------------------------------------------
  // TAHAP 2 - noise dihitung SETELAH band-pass.
  // Ini penting untuk ADS1256: threshold FHR harus berada pada domain
  // sinyal yang benar-benar dipakai peak detector, bukan noise RAW ADC.
  // ---------------------------------------------------
  const int FILTER_WARMUP_FRAMES = 60;
  const int NOISE_FRAMES = 300;

  double meanBP[PIEZO_COUNT] = {0, 0, 0, 0};
  double m2BP[PIEZO_COUNT] = {0, 0, 0, 0};
  int nBP[PIEZO_COUNT] = {0, 0, 0, 0};

  unsigned long nextFrameUs = micros();

  for (int frame = 0; frame < FILTER_WARMUP_FRAMES + NOISE_FRAMES; frame++)
  {
    // Pertahankan kondisi sampling sama dengan runtime: ~200 Hz/channel.
    while ((long)(micros() - nextFrameUs) < 0)
    {
      updateFSR();
    }
    nextFrameUs += PIEZO_SAMPLE_INTERVAL_US;

    for (uint8_t ch = 0; ch < PIEZO_COUNT; ch++)
    {
      int32_t raw = 0;
      if (!adsReadPiezoChannel(ch, raw))
        continue;

      float diffMv = adsCountsToMilliVolts(raw);
      float acMv = diffMv - piezoBaselineMv[ch];

      piezoHighPass[ch] =
        HP_ALPHA *
        (piezoHighPass[ch] + acMv - piezoPreviousInput[ch]);

      piezoPreviousInput[ch] = acMv;

      piezoBandPass[ch] =
        LP_ALPHA * piezoHighPass[ch] +
        (1.0f - LP_ALPHA) * piezoBandPass[ch];

      if (frame >= FILTER_WARMUP_FRAMES)
      {
        nBP[ch]++;
        double x = piezoBandPass[ch];
        double delta = x - meanBP[ch];
        meanBP[ch] += delta / (double)nBP[ch];
        double delta2 = x - meanBP[ch];
        m2BP[ch] += delta * delta2;
      }
    }
  }

  for (uint8_t ch = 0; ch < PIEZO_COUNT; ch++)
  {
    double varianceBP =
      (nBP[ch] > 1) ? m2BP[ch] / (double)(nBP[ch] - 1) : 0.0;

    piezoNoiseStdMv[ch] = (float)sqrt(varianceBP);

    float threshold =
      piezoNoiseStdMv[ch] * THRESHOLD_NOISE_MULTIPLIER;

    piezoThresholdMv[ch] =
      clampFloat(threshold, MIN_THRESHOLD_MV, MAX_THRESHOLD_MV);

    piezoNoiseAbsEMA[ch] =
      (piezoNoiseStdMv[ch] > 0.03f) ? piezoNoiseStdMv[ch] : 0.03f;

    piezoDynamicThresholdMv[ch] = piezoThresholdMv[ch];
    piezoNormalized[ch] = 0.0f;

    Serial.print("Piezo ");
    Serial.print(ch + 1);
    Serial.print(" | Baseline diff = ");
    Serial.print(piezoBaselineMv[ch], 4);
    Serial.print(" mV | BP Noise = ");
    Serial.print(piezoNoiseStdMv[ch], 4);
    Serial.print(" mV | Threshold = ");
    Serial.print(piezoThresholdMv[ch], 4);
    Serial.println(" mV");
  }

  // Reset filter/FHR setelah calibration agar transient calibration
  // tidak dianggap sebagai denyut pertama.
  for (uint8_t ch = 0; ch < PIEZO_COUNT; ch++)
  {
    piezoACmV[ch] = 0.0f;
    piezoHighPass[ch] = 0.0f;
    piezoPreviousInput[ch] = 0.0f;
    piezoBandPass[ch] = 0.0f;
    piezoWindowPeak[ch] = 0.0f;
    piezoEnvelopeEMA[ch] = 0.0f;
    piezoQuality[ch] = 0.0f;
    piezoNormalized[ch] = 0.0f;
  }

  prePreviousAbsPiezo = 0.0f;
  previousAbsPiezo = 0.0f;
  lastPeakTime = 0;
  lastPeakIntervalMs = 0;
  lastValidFHRTime = 0;
  lastPeakAmplitude = 0.0f;
  detectedPeakCount = 0;
  fetalBPM = 0.0f;
  fetalBPMFiltered = 0.0f;
  consistentFHRBeats = 0;
  previousCandidateBPM = 0.0f;
  fetalHRReady = false;
  fetalNearMaternal = false;
  lastChannelSelectMs = millis();
  activePiezoSinceMs = millis();
  candidatePiezo = activePiezo;
  candidatePiezoWins = 0;
  activePiezoInitialized = false;
  strongestPiezoNow = 0;
  bestQualityPiezo = 0;

  Serial.println("PIEZO CALIBRATION FINISH");
  Serial.println("Mode AUTO: sebelum FHR valid, pencarian channel dibuat cepat.");
  Serial.println("Setelah FHR valid, channel dikunci lebih kuat agar hasil stabil.");
  Serial.println("Mechanical BPM tampil cepat untuk validasi sinyal mekanik kecil.");
  Serial.println();

  lastPiezoSampleUs = micros();
  piezoRateWindowStartMs = millis();
}

// =====================================================
// PROCESS PIEZO - SAMA KONSEP DENGAN V3 LAMA
// =====================================================
void processPiezoChannel(uint8_t ch, int32_t raw)
{
  piezoRaw[ch] = raw;
  piezoDiffmV[ch] = adsCountsToMilliVolts(raw);

  piezoACmV[ch] = piezoDiffmV[ch] - piezoBaselineMv[ch];

  if (fabsf(piezoACmV[ch]) > fabsf(piezoWindowPeak[ch]))
    piezoWindowPeak[ch] = piezoACmV[ch];

  // Baseline hanya mengikuti drift ketika sinyal tenang.
  if (fabsf(piezoACmV[ch]) < piezoThresholdMv[ch] * 0.50f)
  {
    piezoBaselineMv[ch] +=
      BASELINE_TRACK_ALPHA *
      (piezoDiffmV[ch] - piezoBaselineMv[ch]);
  }

  piezoHighPass[ch] =
    HP_ALPHA *
    (piezoHighPass[ch] + piezoACmV[ch] - piezoPreviousInput[ch]);

  piezoPreviousInput[ch] = piezoACmV[ch];

  piezoBandPass[ch] =
    LP_ALPHA * piezoHighPass[ch] +
    (1.0f - LP_ALPHA) * piezoBandPass[ch];

  const float absBP = fabsf(piezoBandPass[ch]);

  float currentThreshold = piezoDynamicThresholdMv[ch];
  if (currentThreshold < MIN_THRESHOLD_MV)
    currentThreshold = MIN_THRESHOLD_MV;

  // Noise hanya diikuti saat sinyal masih dekat noise floor.
  if (absBP < currentThreshold * 1.5f)
  {
    piezoNoiseAbsEMA[ch] =
      RUNNING_NOISE_ALPHA * absBP +
      (1.0f - RUNNING_NOISE_ALPHA) * piezoNoiseAbsEMA[ch];
  }

  float dynamicThreshold =
    piezoNoiseAbsEMA[ch] * RUNNING_NOISE_MULTIPLIER;

  const float calibrationFloor =
    piezoThresholdMv[ch] * 0.65f;

  if (dynamicThreshold < calibrationFloor)
    dynamicThreshold = calibrationFloor;

  piezoDynamicThresholdMv[ch] =
    clampFloat(dynamicThreshold, MIN_THRESHOLD_MV, MAX_THRESHOLD_MV);

  piezoNormalized[ch] =
    piezoBandPass[ch] / piezoDynamicThresholdMv[ch];

  const float absNorm = fabsf(piezoNormalized[ch]);

  piezoEnvelopeEMA[ch] =
    PIEZO_ENVELOPE_ALPHA * absNorm +
    (1.0f - PIEZO_ENVELOPE_ALPHA) * piezoEnvelopeEMA[ch];

  // Dimensionless score; lebih adil untuk channel dengan sensitivitas berbeda.
  piezoQuality[ch] = piezoEnvelopeEMA[ch];
}


// =====================================================
// UPDATE PIEZO SELECTOR
// =====================================================
void updatePiezoSelector()
{
  // ---------------------------------------------------
  // DIAGNOSTIK INSTANT:
  // strongestPiezoNow = |Norm| terbesar saat frame ini.
  // ---------------------------------------------------
  strongestPiezoNow = 0;

  for (uint8_t ch = 1; ch < PIEZO_COUNT; ch++)
  {
    if (fabsf(piezoNormalized[ch]) >
        fabsf(piezoNormalized[strongestPiezoNow]))
    {
      strongestPiezoNow = ch;
    }
  }

  // ---------------------------------------------------
  // QUALITY:
  // quality adalah envelope ternormalisasi yang lebih lambat.
  // ---------------------------------------------------
  bestQualityPiezo = 0;

  for (uint8_t ch = 1; ch < PIEZO_COUNT; ch++)
  {
    if (piezoQuality[ch] > piezoQuality[bestQualityPiezo])
      bestQualityPiezo = ch;
  }

  // ---------------------------------------------------
  // MODE MANUAL
  // ---------------------------------------------------
  if (
    MANUAL_PIEZO_CHANNEL >= 0 &&
    MANUAL_PIEZO_CHANNEL < PIEZO_COUNT
  )
  {
    const int forcedPiezo = MANUAL_PIEZO_CHANNEL;

    if (!activePiezoInitialized ||
        activePiezo != forcedPiezo)
    {
      activePiezo = forcedPiezo;
      activePiezoInitialized = true;

      activePiezoSinceMs = millis();
      candidatePiezo = activePiezo;
      candidatePiezoWins = 0;

      resetFHRDetectorOnly();
    }

    return;
  }

  // ---------------------------------------------------
  // AUTO SELECT
  // ---------------------------------------------------
  if (!AUTO_SELECT_FHR_PIEZO)
  {
    if (!activePiezoInitialized)
    {
      activePiezo = FHR_PIEZO_CHANNEL;
      activePiezoInitialized = true;
      activePiezoSinceMs = millis();
    }

    return;
  }

  const unsigned long nowMs = millis();

  // ---------------------------------------------------
  // V12 - VALIDATION HOLD
  // ---------------------------------------------------
  // HANYA ketika sudah ada kandidat pertama.
  // Tidak mengganggu SEARCH normal dan tidak membuat detector susah aktif.
  const bool validationInProgress =
    !fetalHRReady &&
    consistentFHRBeats > 0 &&
    lastFHRValidationMs != 0 &&
    (nowMs - lastFHRValidationMs) <= FHR_VALIDATION_HOLD_MS;

  if (validationInProgress)
  {
    return;
  }

  // Sebelum ada Active Piezo yang benar-benar dipilih dari data,
  // beri waktu singkat supaya envelope quality terbentuk.
  if (!activePiezoInitialized)
  {
    if (nowMs - lastChannelSelectMs < 800)
      return;

    activePiezo = bestQualityPiezo;
    activePiezoInitialized = true;

    activePiezoSinceMs = nowMs;
    lastChannelSelectMs = nowMs;

    candidatePiezo = activePiezo;
    candidatePiezoWins = 0;

    resetFHRDetectorOnly();
    return;
  }

  // Dua setting berbeda:
  // belum dapat FHR -> SEARCH cepat
  // sudah dapat FHR  -> LOCK lebih ketat
  const bool lockedMode = fetalHRReady;

  const unsigned long selectInterval =
    lockedMode ?
    LOCK_SELECT_INTERVAL_MS :
    SEARCH_SELECT_INTERVAL_MS;

  const unsigned long minHold =
    lockedMode ?
    LOCK_MIN_HOLD_MS :
    SEARCH_MIN_HOLD_MS;

  const float switchRatio =
    lockedMode ?
    LOCK_SWITCH_HYSTERESIS :
    SEARCH_SWITCH_HYSTERESIS;

  const byte winsRequired =
    lockedMode ?
    LOCK_WIN_REQUIRED :
    SEARCH_WIN_REQUIRED;

  if (nowMs - lastChannelSelectMs < selectInterval)
    return;

  lastChannelSelectMs = nowMs;

  const int best = bestQualityPiezo;

  if (best == activePiezo)
  {
    candidatePiezo = activePiezo;
    candidatePiezoWins = 0;
    return;
  }

  const float activeQ = piezoQuality[activePiezo];
  const float bestQ = piezoQuality[best];

  // Saat SEARCH dan channel aktif hampir tidak punya sinyal,
  // izinkan pindah tanpa menuntut rasio yang terlalu besar.
  const bool activeVeryWeak =
    (!lockedMode && activeQ < 0.75f);

  const bool clearlyBetter =
    activeVeryWeak ||
    (bestQ > activeQ * switchRatio);

  if (!clearlyBetter)
  {
    candidatePiezo = activePiezo;
    candidatePiezoWins = 0;
    return;
  }

  if (candidatePiezo == best)
  {
    if (candidatePiezoWins < 255)
      candidatePiezoWins++;
  }
  else
  {
    candidatePiezo = best;
    candidatePiezoWins = 1;
  }

  const bool holdExpired =
    (nowMs - activePiezoSinceMs) >= minHold;

  if (
    holdExpired &&
    candidatePiezoWins >= winsRequired
  )
  {
    activePiezo = candidatePiezo;

    activePiezoSinceMs = nowMs;
    candidatePiezoWins = 0;

    // Detector harus dimulai ulang karena sumber waveform berubah.
    resetFHRDetectorOnly();
  }
}

void updatePiezos()
{
  if (!adsReady)
    return;

  const unsigned long nowUs = micros();
  if ((unsigned long)(nowUs - lastPiezoSampleUs) < PIEZO_SAMPLE_INTERVAL_US)
    return;

  lastPiezoSampleUs += PIEZO_SAMPLE_INTERVAL_US;
  if ((unsigned long)(nowUs - lastPiezoSampleUs) > PIEZO_SAMPLE_INTERVAL_US * 2UL)
    lastPiezoSampleUs = nowUs;

  bool allZero = true;

  for (uint8_t ch = 0; ch < PIEZO_COUNT; ch++)
  {
    int32_t raw = 0;
    if (!adsReadPiezoChannel(ch, raw))
      return;

    if (raw != 0)
      allZero = false;

    processPiezoChannel(ch, raw);
  }

  adsDRDYTimeout = false;

  if (allZero)
  {
    if (adsAllZeroStreak < 65535)
      adsAllZeroStreak++;
  }
  else
  {
    adsAllZeroStreak = 0;
    adsAllZeroWarning = false;
  }

  if (adsAllZeroStreak >= 20)
    adsAllZeroWarning = true;

  updatePiezoSelector();

  selectedPiezoRaw = piezoACmV[activePiezo];
  selectedPiezo = piezoBandPass[activePiezo];
  selectedPiezoNorm = piezoNormalized[activePiezo];

  calculateFHR();

  piezoFramesInRateWindow++;
  const unsigned long nowMs = millis();
  if (piezoRateWindowStartMs == 0)
    piezoRateWindowStartMs = nowMs;

  unsigned long elapsed = nowMs - piezoRateWindowStartMs;
  if (elapsed >= 1000)
  {
    piezoActualFsPerChannel =
      (piezoFramesInRateWindow * 1000.0f) / (float)elapsed;
    piezoFramesInRateWindow = 0;
    piezoRateWindowStartMs = nowMs;
  }
}

// =====================================================
// FHR - DETEKSI DENYUT FETAL KONTINU
// =====================================================
void calculateFHR()
{
  const unsigned long now = millis();

  // SAMA seperti V6:
  // |Norm| = 1 berarti tepat di dynamic threshold.
  const float currentAbs =
    fabsf(selectedPiezoNorm);

  const float threshold = 1.0f;

  const bool localMaximum =
    previousAbsPiezo >
      prePreviousAbsPiezo &&
    previousAbsPiezo >=
      currentAbs;

  if (
    localMaximum &&
    previousAbsPiezo >= threshold &&
    (
      lastPeakTime == 0 ||
      now - lastPeakTime >=
        REFRACTORY_TIME_MS
    )
  )
  {
    unsigned long peakTime = now;

    if (peakTime >= 5)
      peakTime -= 5;

    lastPeakAmplitude =
      fabsf(selectedPiezo);

    detectedPeakCount++;

    if (lastPeakTime != 0)
    {
      lastPeakIntervalMs =
        peakTime - lastPeakTime;

      const float candidateBPM =
        60000.0f /
        (float)lastPeakIntervalMs;

      // =================================================
      // MECHANICAL BPM
      // =================================================
      // Tetap responsif seperti V6.
      if (
        candidateBPM >=
          MIN_MECHANICAL_BPM &&
        candidateBPM <=
          MAX_MECHANICAL_BPM
      )
      {
        mechanicalBPM =
          candidateBPM;
      }
      else
      {
        mechanicalBPM = 0.0f;
      }

      // =================================================
      // FHR CANDIDATE
      // =================================================
      if (
        candidateBPM >=
          MIN_FETAL_BPM &&
        candidateBPM <=
          MAX_FETAL_BPM
      )
      {
        fetalBPM =
          candidateBPM;

        // Kandidat pertama.
        if (
          previousCandidateBPM <=
          0.0f
        )
        {
          previousCandidateBPM =
            candidateBPM;

          consistentFHRBeats = 1;
          fhrMismatchStreak = 0;

          lastFHRValidationMs =
            now;
        }
        else
        {
          const float allowedJump =
            previousCandidateBPM *
            MAX_FHR_JUMP_FRACTION;

          const bool consistent =
            fabsf(
              candidateBPM -
              previousCandidateBPM
            ) <=
            allowedJump;

          if (consistent)
          {
            // Kandidat kedua cocok.
            previousCandidateBPM =
              candidateBPM;

            fhrMismatchStreak = 0;

            lastFHRValidationMs =
              now;

            if (
              consistentFHRBeats <
              255
            )
            {
              consistentFHRBeats++;
            }
          }
          else
          {
            // -------------------------------------------
            // PERBAIKAN UTAMA V12
            // -------------------------------------------
            // SATU mismatch tidak langsung membuat Valid 1 hilang.
            if (
              fhrMismatchStreak <
              255
            )
            {
              fhrMismatchStreak++;
            }

            // Baru setelah 2 mismatch berturut-turut,
            // kandidat lama dianggap memang tidak cocok.
            if (
              fhrMismatchStreak >=
              MAX_FHR_MISMATCH_STREAK
            )
            {
              previousCandidateBPM =
                candidateBPM;

              consistentFHRBeats = 1;
              fhrMismatchStreak = 0;

              lastFHRValidationMs =
                now;
            }

            // Kalau baru mismatch pertama:
            // previousCandidateBPM dan Valid=1 DIPERTAHANKAN.
          }
        }

        // =================================================
        // FHR FILTERED
        // =================================================
        if (
          consistentFHRBeats >=
          MIN_CONSISTENT_FHR_BEATS
        )
        {
          if (
            !fetalHRReady ||
            fetalBPMFiltered <=
              0.0f
          )
          {
            // Gunakan candidate terbaru yang sudah lolos validasi.
            fetalBPMFiltered =
              previousCandidateBPM;
          }
          else
          {
            fetalBPMFiltered =
              BPM_FILTER_ALPHA *
                previousCandidateBPM +
              (1.0f -
               BPM_FILTER_ALPHA) *
                fetalBPMFiltered;
          }

          fetalHRReady = true;
          lastValidFHRTime =
            peakTime;

          fetalNearMaternal =
            false;

          if (
            hrFilteredReady &&
            fabsf(
              fetalBPMFiltered -
              hrFiltered
            ) <=
              10.0f
          )
          {
            fetalNearMaternal =
              true;
          }
        }
      }
      else
      {
        // =================================================
        // INTERVAL BUKAN FHR
        // =================================================
        // Mechanical tetap boleh terbaca.
        // Yang penting: JANGAN langsung hapus Valid=1 hanya karena
        // satu interval berada di luar 80..220 BPM.
        fetalBPM = 0.0f;

        if (
          consistentFHRBeats > 0 &&
          lastFHRValidationMs != 0 &&
          (now - lastFHRValidationMs) >
            FHR_VALIDATION_HOLD_MS
        )
        {
          // Kandidat memang sudah terlalu lama tidak mendapat pasangan.
          consistentFHRBeats = 0;
          previousCandidateBPM = 0.0f;
          fhrMismatchStreak = 0;
          lastFHRValidationMs = 0;
          fetalHRReady = false;
        }
      }
    }

    // Tetap sama seperti V6:
    // peak yang lolos refractory menjadi reference interval berikutnya.
    lastPeakTime =
      peakTime;
  }

  // ===================================================
  // DISPLAY STALE
  // ===================================================
  // Angka lama jangan menggantung saat sudah tidak ada aktivitas.
  if (
    lastPeakTime != 0 &&
    now - lastPeakTime >
      BPM_DISPLAY_STALE_MS
  )
  {
    mechanicalBPM = 0.0f;
    fetalBPM = 0.0f;
  }

  // ===================================================
  // VALIDATION TIMEOUT
  // ===================================================
  // Kalau Valid=1 tidak pernah mendapat pasangan cukup lama,
  // barulah kembali ke pencarian dari nol.
  if (
    !fetalHRReady &&
    consistentFHRBeats > 0 &&
    lastFHRValidationMs != 0 &&
    now - lastFHRValidationMs >
      FHR_VALIDATION_HOLD_MS
  )
  {
    consistentFHRBeats = 0;
    previousCandidateBPM = 0.0f;
    fhrMismatchStreak = 0;
    lastFHRValidationMs = 0;
  }

  // ===================================================
  // FULL RESET
  // ===================================================
  if (
    lastPeakTime != 0 &&
    now - lastPeakTime >
      3000
  )
  {
    resetFHRDetectorOnly();
  }
  else
  {
    prePreviousAbsPiezo =
      previousAbsPiezo;

    previousAbsPiezo =
      currentAbs;
  }
}

// =====================================================
// BACA MAX30102 DARI FIFO
// FSR dan 4 Piezo tetap di-update selama menunggu MAX30102.
// =====================================================
bool readMAXSample(uint32_t &ir, uint32_t &red)
{
  unsigned long startWait = millis();

  while (!max30102.available())
  {
    max30102.check();

    updateFSR();
    updatePiezos();

    if (millis() - startWait >= SAMPLE_TIMEOUT_MS)
      return false;
  }

  red = max30102.getFIFORed();
  ir  = max30102.getFIFOIR();

  max30102.nextSample();

  updateFSR();
  updatePiezos();

  return true;
}

// =====================================================
// FIFO MAX30102
// =====================================================
void flushMAXFIFO()
{
  while (max30102.available())
    max30102.nextSample();

  max30102.clearFIFO();
}

// =====================================================
// RESET MAX30102 SAJA
// FSR TIDAK IKUT RESET
// =====================================================
void resetMAXMeasurement()
{
  maxBufferReady = false;
  fingerPresent = false;
  maxActualFs = 0.0f;

  heartRateRaw = 0;
  validHeartRateRaw = 0;

  spo2Raw = 0;
  validSPO2Raw = 0;

  resetMAXResultFilters();
  flushMAXFIFO();
}

// =====================================================
// ACTUAL FS MAX30102
// =====================================================
float calculateActualFs(
  int numberOfSamples,
  unsigned long elapsedMs
)
{
  if (elapsedMs == 0)
    return 0.0f;

  return
    (numberOfSamples * 1000.0f) /
    elapsedMs;
}

// =====================================================
// RAW MIN/MAX MAX30102
// =====================================================
void getMAXRawMinMax(
  uint32_t &irMin,
  uint32_t &irMax,
  uint32_t &redMin,
  uint32_t &redMax
)
{
  irMin = irBuffer[0];
  irMax = irBuffer[0];

  redMin = redBuffer[0];
  redMax = redBuffer[0];

  for (int i = 1; i < FG_BUFFER_SIZE; i++)
  {
    if (irBuffer[i] < irMin) irMin = irBuffer[i];
    if (irBuffer[i] > irMax) irMax = irBuffer[i];

    if (redBuffer[i] < redMin) redMin = redBuffer[i];
    if (redBuffer[i] > redMax) redMax = redBuffer[i];
  }
}

// =====================================================
// HITUNG HR + SPO2 MAX30102
// =====================================================
void calculateMAXResults()
{
  maxim_heart_rate_and_oxygen_saturation(
    irBuffer,
    FG_BUFFER_SIZE,
    redBuffer,
    &spo2Raw,
    &validSPO2Raw,
    &heartRateRaw,
    &validHeartRateRaw
  );

  updateHRFilter();
  updateSpO2Filter();
}

// =====================================================
// BLE GATEWAY + SINKRONISASI WAKTU DARI APP
// =====================================================
// ESP32 tidak menyimpan kredensial pasien/backend. App mengirim waktu saat
// koneksi terbentuk, menerima telemetry, lalu melakukan upload terautentikasi.
class FGBleServerCallbacks : public BLEServerCallbacks
{
  void onConnect(BLEServer *server) override
  {
    (void)server;
    bleClientConnected = true;
    bleClockSynchronized = false;
    lastBleTelemetryMs = 0;
    Serial.println("[BLE] Gateway terhubung; menunggu sinkronisasi waktu.");
  }

  void onDisconnect(BLEServer *server) override
  {
    (void)server;
    bleClientConnected = false;
    bleClockSynchronized = false;
    BLEDevice::startAdvertising();
    Serial.println("[BLE] Gateway terputus; advertising dimulai kembali.");
  }
};

class FGBleTimeSyncCallbacks : public BLECharacteristicCallbacks
{
  void onWrite(BLECharacteristic *characteristic) override
  {
    String command = characteristic->getValue().c_str();
    command.trim();
    if (!command.startsWith("T") || command.length() < 14)
    {
      Serial.println("[BLE] Perintah gateway tidak dikenali.");
      return;
    }

    char *parseEnd = nullptr;
    const uint64_t unixMs = strtoull(command.c_str() + 1, &parseEnd, 10);
    const bool parsedAll = parseEnd != nullptr && *parseEnd == '\0';
    // Tolak waktu sebelum 2024 dan angka yang tidak lengkap.
    if (!parsedAll || unixMs < 1704067200000ULL)
    {
      Serial.println("[BLE] Sinkronisasi waktu ditolak.");
      return;
    }

    bleEpochAtSyncMs = unixMs;
    bleMillisAtSync = millis();
    bleClockSynchronized = true;
    lastBleTelemetryMs = 0;
    Serial.println("[BLE] Waktu gateway tersinkronisasi.");
  }
};

uint64_t currentGatewayEpochMs()
{
  const uint32_t elapsedMs = millis() - bleMillisAtSync;
  return bleEpochAtSyncMs + (uint64_t)elapsedMs;
}

bool formatGatewayTimestamp(char *output, size_t outputSize, uint64_t epochMs)
{
  const time_t epochSeconds = (time_t)(epochMs / 1000ULL);
  struct tm utcTime;
  if (gmtime_r(&epochSeconds, &utcTime) == nullptr)
    return false;

  const unsigned int milliseconds = (unsigned int)(epochMs % 1000ULL);
  const int written = snprintf(
    output,
    outputSize,
    "%04d-%02d-%02dT%02d:%02d:%02d.%03uZ",
    utcTime.tm_year + 1900,
    utcTime.tm_mon + 1,
    utcTime.tm_mday,
    utcTime.tm_hour,
    utcTime.tm_min,
    utcTime.tm_sec,
    milliseconds
  );
  return written > 0 && (size_t)written < outputSize;
}

uint16_t quantizeADS1256To12Bit(int32_t raw)
{
  int64_t bounded = raw;
  if (bounded < -8388608LL) bounded = -8388608LL;
  if (bounded > 8388607LL) bounded = 8388607LL;
  return (uint16_t)(((bounded + 8388608LL) * 4095LL) / 16777215LL);
}

void appendJsonNumberField(
  String &json,
  bool &hasField,
  const char *name,
  float value,
  unsigned int decimals
)
{
  if (!isfinite(value)) return;
  if (hasField) json += ',';
  json += '\"';
  json += name;
  json += "\":";
  json += String(value, decimals);
  hasField = true;
}

String buildTelemetryFrame()
{
  char capturedAt[32];
  const uint64_t capturedAtMs = currentGatewayEpochMs();
  if (!formatGatewayTimestamp(capturedAt, sizeof(capturedAt), capturedAtMs))
    return String();

  String json;
  json.reserve(640);
  json += "{\"schema_version\":1,\"device_uid\":\"";
  json += FG_DEVICE_UID;
  json += "\",\"boot_id\":\"";
  json += bleBootId;
  json += "\",\"sequence_number\":";
  json += String((unsigned long)bleSequenceNumber);
  json += ",\"captured_at\":\"";
  json += capturedAt;
  json += "\",\"sample_rate_hz\":1,\"telemetry\":{";

  bool hasTelemetryField = false;
  if (fetalHRReady && !fetalNearMaternal)
    appendJsonNumberField(json, hasTelemetryField, "fhr", fetalBPMFiltered, 1);
  if (hrFilteredReady)
    appendJsonNumberField(json, hasTelemetryField, "motherHR", hrFiltered, 1);
  if (spo2FilteredReady)
    appendJsonNumberField(json, hasTelemetryField, "spo2", spo2Filtered, 1);
  json += "},\"channels\":{";

  bool hasChannel = false;
  if (adsReady && !adsDRDYTimeout)
  {
    json += "\"p\":[";
    for (byte channel = 0; channel < PIEZO_COUNT; channel++)
    {
      if (channel > 0) json += ',';
      json += String(quantizeADS1256To12Bit(piezoRaw[channel]));
    }
    json += ']';
    hasChannel = true;
  }

  if (hasChannel) json += ',';
  json += "\"fsr\":[";
  json += String(constrain(fsrRawADC, 0, 4095));
  json += ']';
  hasChannel = true;

  if (fingerPresent && maxBufferReady)
  {
    json += ",\"hr_ir\":[";
    json += String(irBuffer[FG_BUFFER_SIZE - 1]);
    json += "],\"hr_red\":[";
    json += String(redBuffer[FG_BUFFER_SIZE - 1]);
    json += ']';
  }

  json += "}}\n";
  return json;
}

void notifyTelemetryFrame(const String &frame)
{
  if (bleTelemetryCharacteristic == nullptr || frame.length() == 0)
    return;

  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(frame.c_str());
  for (size_t offset = 0; offset < frame.length(); offset += BLE_NOTIFY_CHUNK_BYTES)
  {
    const size_t remaining = frame.length() - offset;
    const size_t chunkSize = remaining < BLE_NOTIFY_CHUNK_BYTES
      ? remaining
      : BLE_NOTIFY_CHUNK_BYTES;
    bleTelemetryCharacteristic->setValue((uint8_t *)(bytes + offset), chunkSize);
    bleTelemetryCharacteristic->notify();
    // Beri waktu stack BLE mengirim setiap fragmen pada ATT MTU minimum.
    // Pada interval frame 1 Hz, jeda ini lebih mengutamakan keutuhan frame.
    delay(8);
  }
}

void setupBLEGateway()
{
  const uint64_t chipId = ESP.getEfuseMac();
  snprintf(
    bleBootId,
    sizeof(bleBootId),
    "boot-%08lx-%08lx",
    (unsigned long)(chipId & 0xFFFFFFFFULL),
    (unsigned long)esp_random()
  );

  BLEDevice::init(FG_DEVICE_UID);
  BLEDevice::setMTU(185);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new FGBleServerCallbacks());

  BLEService *service = server->createService(FG_BLE_SERVICE_UUID);
  bleTelemetryCharacteristic = service->createCharacteristic(
    FG_BLE_CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_NOTIFY |
    BLECharacteristic::PROPERTY_WRITE |
    BLECharacteristic::PROPERTY_WRITE_NR
  );
  bleTelemetryCharacteristic->addDescriptor(new BLE2902());
  bleTelemetryCharacteristic->setCallbacks(new FGBleTimeSyncCallbacks());
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

void sendTelemetryIfDue()
{
  if (!bleClientConnected || !bleClockSynchronized)
    return;

  const unsigned long now = millis();
  if (lastBleTelemetryMs != 0 && now - lastBleTelemetryMs < BLE_TELEMETRY_INTERVAL_MS)
    return;
  lastBleTelemetryMs = now;

  const String frame = buildTelemetryFrame();
  if (frame.length() == 0)
    return;

  notifyTelemetryFrame(frame);
  bleSequenceNumber++;
}

// =====================================================
// TAMPILAN SISTEM - SENSOR INDEPENDEN
// =====================================================
void printSystemStatus()
{
  sendTelemetryIfDue();
  unsigned long now = millis();

  if (
    now - lastSystemPrint <
    SYSTEM_PRINT_INTERVAL_MS
  )
    return;

  lastSystemPrint = now;

  Serial.println();
  Serial.println("======================================");
  Serial.println("FETAL-GUARD - MAX30102 + FSR408 + 4 PIEZO V12-V6-MINIMAL");

  // ===================================================
  // MAX30102
  // ===================================================
  Serial.println("[MAX30102]");

  if (!fingerPresent)
  {
    Serial.println("Status        : Tidak ada jari");
    Serial.println("Maternal HR   : --");
    Serial.println("Maternal SpO2 : --");
  }
  else if (!maxBufferReady)
  {
    Serial.println("Status        : Mengumpulkan data");
    Serial.println("Maternal HR   : Menghitung...");
    Serial.println("Maternal SpO2 : Menghitung...");
  }
  else
  {
    bool samplingOK =
      maxActualFs >= 22.0f &&
      maxActualFs <= 28.0f;

    uint32_t irMin, irMax, redMin, redMax;

    getMAXRawMinMax(
      irMin,
      irMax,
      redMin,
      redMax
    );

    bool rawTooHigh =
      irMax >= RAW_SATURATION_WARNING ||
      redMax >= RAW_SATURATION_WARNING;

    Serial.print("Status        : ");

    if (!samplingOK)
      Serial.println("Periksa sampling");
    else if (rawTooHigh)
      Serial.println("Raw terlalu tinggi");
    else if (!hrFilteredReady || !spo2FilteredReady)
      Serial.println("Stabilisasi hasil...");
    else
      Serial.println("Sinyal stabil");

    Serial.print("Maternal HR   : ");

    if (hrFilteredReady)
    {
      Serial.print((int)(hrFiltered + 0.5f));
      Serial.println(" BPM");
    }
    else
    {
      Serial.println("Menghitung...");
    }

    Serial.print("Maternal SpO2 : ");

    if (spo2FilteredReady)
    {
      Serial.print((int)(spo2Filtered + 0.5f));
      Serial.println(" %");
    }
    else
    {
      Serial.println("Menghitung...");
    }

    Serial.print("IR Raw        : ");
    Serial.println(
      irBuffer[FG_BUFFER_SIZE - 1]
    );

    Serial.print("RED Raw       : ");
    Serial.println(
      redBuffer[FG_BUFFER_SIZE - 1]
    );

    Serial.print("Actual Fs     : ");
    Serial.print(maxActualFs, 2);
    Serial.println(" Hz");
  }

  // ===================================================
  // FSR408 - SELALU DITAMPILKAN
  // ===================================================
  Serial.println();
  Serial.println("[FSR408]");

  Serial.print("FSR Raw ADC   : ");
  Serial.println(fsrRawADC);

  Serial.print("FSR Filtered  : ");
  Serial.println(fsrFilteredADC, 1);

  Serial.print("FSR Voltage   : ");
  Serial.print(fsrVoltage, 3);
  Serial.println(" V");

  if (!fsrBaselineReady)
  {
    Serial.println("FSR Baseline  : Kalibrasi 5 detik...");
    Serial.println("FSR Delta ADC : --");
    Serial.println("Tekanan       : Menunggu baseline");
  }
  else
  {
    Serial.print("FSR Baseline  : ");
    Serial.println(fsrBaseline, 1);

    Serial.print("FSR Delta ADC : +");
    Serial.println(fsrDeltaADC, 1);

    Serial.print("Delta Voltage : +");
    Serial.print(fsrDeltaVoltage, 3);
    Serial.println(" V");

    Serial.print("Threshold ON  : +");
    Serial.print(fsrOnThresholdADC, 1);
    Serial.println(" ADC");

    if (pressureActive)
    {
      Serial.print("Tekanan       : MENINGKAT");

      Serial.print(" | Durasi = ");
      Serial.print(
        pressureDuration / 1000.0f,
        1
      );
      Serial.println(" s");
    }
    else
    {
      Serial.println("Tekanan       : BASELINE");
    }
  }

  // ===================================================
  // 4 PIEZO / ADS1256
  // ===================================================
  Serial.println();
  Serial.println("[4 PIEZO / ADS1256]");

  if (!adsReady)
  {
    Serial.println("ADS1256       : TIDAK SIAP / REGISTER SPI GAGAL");
  }
  else
  {
    Serial.print("ADS1256       : ");
    if (adsDRDYTimeout)
      Serial.println("DRDY TIMEOUT");
    else if (adsAllZeroWarning)
      Serial.println("WARNING - SEMUA RAW TERUS 0");
    else
      Serial.println("OK");

    Serial.print("Sample/ch     : ");
    Serial.print(piezoActualFsPerChannel, 1);
    Serial.println(" Hz");

    for (byte ch = 0; ch < PIEZO_COUNT; ch++)
    {
      Serial.print("Piezo ");
      Serial.print(ch + 1);
      Serial.print(" AN");
      Serial.print(ch);
      Serial.print("-ACOM | Raw=");
      Serial.print(piezoRaw[ch]);
      Serial.print(" | Diff=");
      Serial.print(piezoDiffmV[ch], 4);
      Serial.print(" mV | AC=");
      Serial.print(piezoACmV[ch], 4);
      Serial.print(" mV | Peak=");
      Serial.print(piezoWindowPeak[ch], 4);
      Serial.print(" mV | BP=");
      Serial.print(piezoBandPass[ch], 4);
      Serial.print(" mV | DynThr=");
      Serial.print(piezoDynamicThresholdMv[ch], 4);
      Serial.print(" | Norm=");
      Serial.print(piezoNormalized[ch], 2);
      Serial.print(" | Q=");
      Serial.println(piezoQuality[ch], 2);
    }

    Serial.print("Strongest Now  : Piezo ");
    Serial.println(strongestPiezoNow + 1);

    Serial.print("Best Quality   : Piezo ");
    Serial.println(bestQualityPiezo + 1);

    Serial.print("Active FHR Piezo: Piezo ");
    Serial.println(activePiezo + 1);

    Serial.print("Selector Phase : ");
    if (MANUAL_PIEZO_CHANNEL >= 0)
      Serial.println("MANUAL");
    else if (fetalHRReady)
      Serial.println("LOCK");
    else if (
      consistentFHRBeats > 0 &&
      lastFHRValidationMs != 0 &&
      (millis() - lastFHRValidationMs) <= FHR_VALIDATION_HOLD_MS
    )
      Serial.println("VALIDATION HOLD");
    else
      Serial.println("SEARCH");

    Serial.print("Select Mode    : ");
    if (MANUAL_PIEZO_CHANNEL >= 0)
    {
      Serial.print("MANUAL P");
      Serial.println(MANUAL_PIEZO_CHANNEL + 1);
    }
    else
    {
      Serial.println("AUTO-SNR LOCK");
    }
    Serial.print("Selected Raw   : ");
    Serial.print(selectedPiezoRaw, 4);
    Serial.println(" mV");
    Serial.print("Selected BP    : ");
    Serial.print(selectedPiezo, 4);
    Serial.println(" mV");

    Serial.print("Selected Norm  : ");
    Serial.println(selectedPiezoNorm, 2);
    Serial.print("Threshold      : ");
    Serial.print(piezoDynamicThresholdMv[activePiezo], 4);
    Serial.println(" mV");
    Serial.print("Peak Count     : ");
    Serial.println(detectedPeakCount);
    Serial.print("Last Peak Amp  : ");
    Serial.print(lastPeakAmplitude, 4);
    Serial.println(" mV");
    Serial.print("Last Interval  : ");
    if (lastPeakIntervalMs > 0)
    {
      Serial.print(lastPeakIntervalMs);
      Serial.println(" ms");
    }
    else
    {
      Serial.println("--");
    }
    Serial.print("Mechanical BPM : ");
    if (mechanicalBPM > 0.0f)
    {
      Serial.print(mechanicalBPM, 1);
      Serial.println(" BPM");
    }
    else
    {
      Serial.println("--");
    }

    Serial.print("FHR Candidate  : ");
    if (fetalBPM > 0.0f)
    {
      Serial.print(fetalBPM, 1);
      Serial.println(" BPM");
    }
    else
    {
      Serial.println("--");
    }
    Serial.print("FHR Status     : ");
    if (fetalHRReady)
      Serial.println("TERDETEKSI");
    else
      Serial.println("MENCARI / VALIDASI 2 INTERVAL");

    Serial.print("Consistent Beat: ");
    Serial.println(consistentFHRBeats);

    Serial.print("Mismatch       : ");
    Serial.print(fhrMismatchStreak);
    Serial.print("/");
    Serial.println(MAX_FHR_MISMATCH_STREAK);

    Serial.print("Validation Hold: ");
    if (
      !fetalHRReady &&
      consistentFHRBeats > 0 &&
      lastFHRValidationMs != 0 &&
      (millis() - lastFHRValidationMs) <= FHR_VALIDATION_HOLD_MS
    )
      Serial.println("AKTIF");
    else
      Serial.println("TIDAK");

    Serial.print("FHR Filtered   : ");
    if (fetalHRReady)
    {
      Serial.print(fetalBPMFiltered, 1);
      Serial.println(" BPM");
    }
    else
    {
      Serial.println("--");
    }

    if (fetalHRReady && fetalNearMaternal)
      Serial.println("Catatan        : FHR dekat HR ibu; verifikasi kualitas sinyal.");

    if (adsAllZeroWarning)
    {
      Serial.println("!!! Semua channel persis 0. Ini BUKAN masalah filter FHR.");
      Serial.println("!!! Ukur dengan multimeter: AN0 dan ACOM harus sekitar 2.5V absolut.");
      Serial.println("!!! Ketuk P1: tegangan AN0 harus berubah sesaat terhadap ACOM.");
      Serial.println("!!! Jika AN0 berubah tetapi Raw tetap 0 -> periksa DOUT/MISO/SPI ADS1256.");
    }

    for (byte ch = 0; ch < PIEZO_COUNT; ch++)
      piezoWindowPeak[ch] = 0.0f;
  }

  Serial.println("======================================");
}

// =====================================================
// SETUP
// =====================================================
void setup()
{
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("======================================");
  Serial.println("FETAL-GUARD");
  Serial.println("MAX30102 + FSR408 + 4 PIEZO");
  Serial.println("======================================");

  // ===================================================
  // FSR408
  // ===================================================
  analogReadResolution(12);
  pinMode(FSR_PIN, INPUT);

  fsrCalibrationStart = millis();

  Serial.println();
  Serial.println("FSR408:");
  Serial.println("- Kalibrasi baseline 5 detik.");
  Serial.println("- Jangan tekan FSR saat kalibrasi.");
  Serial.println("- Setelah kalibrasi, tekan AREA AKTIF FSR.");

  // ===================================================
  // ADS1256 + 4 PIEZO
  // ===================================================
  Serial.println();
  Serial.print("Mencari ADS1256... ");

  adsReady = adsInit();

  if (!adsReady)
  {
    Serial.println("GAGAL: DRDY atau REGISTER SPI tidak valid");
    Serial.println(
      "Periksa 5V, GND, SCLK GPIO12, DIN GPIO11, "
      "DOUT GPIO13, DRDY GPIO14, CS GPIO10, RST GPIO15."
    );
    Serial.println(
      "MAX30102 dan FSR tetap dapat berjalan, tetapi Piezo tidak dibaca."
    );
  }
  else
  {
    Serial.println("TERDETEKSI + REGISTER READBACK OK");

    Serial.print("STATUS = 0x");
    if (adsStatusReadback < 0x10) Serial.print("0");
    Serial.println(adsStatusReadback, HEX);

    Serial.print("MUX    = 0x");
    if (adsMuxReadback < 0x10) Serial.print("0");
    Serial.println(adsMuxReadback, HEX);

    Serial.print("ADCON  = 0x");
    if (adsAdconReadback < 0x10) Serial.print("0");
    Serial.println(adsAdconReadback, HEX);

    Serial.print("DRATE  = 0x");
    if (adsDrateReadback < 0x10) Serial.print("0");
    Serial.println(adsDrateReadback, HEX);

    Serial.println("- P1=AN0, P2=AN1, P3=AN2, P4=AN3.");
    Serial.println("- ACOM = VCM 2.5 V dari MCP6002 #1 pin 1.");
    Serial.println("- BUFEN OFF, PGA 1, DRATE 7500 SPS.");
    Serial.println("- Algoritma piezo: baseline + band filter + normalisasi per-channel.");
    Serial.println("- Selector: SEARCH cepat sebelum FHR, LOCK setelah FHR stabil.");

    calibratePiezos();
  }

  // ===================================================
  // MAX30102
  // ===================================================
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  Serial.println();
  Serial.print("Mencari MAX30102... ");

  if (!max30102.begin(Wire, I2C_SPEED_FAST))
  {
    Serial.println("GAGAL");
    Serial.println(
      "Periksa VCC, GND, SDA GPIO8, dan SCL GPIO9."
    );

    while (1)
      delay(1000);
  }

  Serial.println("TERDETEKSI");

  max30102.setup(
    LED_BRIGHTNESS,
    SAMPLE_AVERAGE,
    LED_MODE,
    SAMPLE_RATE,
    PULSE_WIDTH,
    ADC_RANGE
  );

  max30102.setPulseAmplitudeRed(
    LED_BRIGHTNESS
  );

  max30102.setPulseAmplitudeIR(
    LED_BRIGHTNESS
  );

  max30102.setPulseAmplitudeGreen(0);

  flushMAXFIFO();
  resetMAXResultFilters();

  Serial.println();
  Serial.println("MAX30102:");
  Serial.println("- Setting final tetap 0x1F.");
  Serial.println("- Bisa digunakan atau dibiarkan tanpa jari.");
  Serial.println("- FSR tetap bekerja walau MAX30102 tidak dipakai.");

  // BLE dimulai setelah sensor siap agar aplikasi tidak menerima paket
  // sebelum akuisisi hardware berhasil diinisialisasi.
  setupBLEGateway();
}

// =====================================================
// LOOP
// =====================================================
void loop()
{
  // FSR selalu berjalan independen
  updateFSR();

  // Empat Piezo juga berjalan independen melalui ADS1256.
  updatePiezos();

  uint32_t ir = 0;
  uint32_t red = 0;

  // ===================================================
  // MAX30102 BELUM PUNYA BUFFER
  // ===================================================
  if (!maxBufferReady)
  {
    if (!readMAXSample(ir, red))
    {
      resetMAXMeasurement();
      printSystemStatus();
      return;
    }

    // -----------------------------------------------
    // Tidak ada jari:
    // MAX berhenti di status "--", FSR tetap jalan.
    // -----------------------------------------------
    if (ir < FINGER_THRESHOLD)
    {
      fingerPresent = false;

      printSystemStatus();
      return;
    }

    // -----------------------------------------------
    // Jari baru terdeteksi
    // -----------------------------------------------
    if (!fingerPresent)
    {
      fingerPresent = true;
      resetMAXResultFilters();

      Serial.println();
      Serial.println(">>> Jari MAX30102 terdeteksi");
      Serial.println(">>> Stabilisasi sekitar 2 detik...");

      for (
        int i = 0;
        i < FG_STABILIZE_SAMPLES;
        i++
      )
      {
        if (!readMAXSample(ir, red))
        {
          resetMAXMeasurement();
          return;
        }

        if (ir < FINGER_THRESHOLD)
        {
          resetMAXMeasurement();
          return;
        }
      }

      flushMAXFIFO();

      Serial.println(
        ">>> Mengumpulkan 100 sample MAX30102..."
      );
    }

    // -----------------------------------------------
    // 100 sample awal MAX30102
    // -----------------------------------------------
    unsigned long startSampling =
      millis();

    for (
      int i = 0;
      i < FG_BUFFER_SIZE;
      i++
    )
    {
      if (!readMAXSample(ir, red))
      {
        resetMAXMeasurement();
        return;
      }

      if (ir < FINGER_THRESHOLD)
      {
        resetMAXMeasurement();
        return;
      }

      irBuffer[i] = ir;
      redBuffer[i] = red;
    }

    unsigned long elapsed =
      millis() -
      startSampling;

    maxActualFs =
      calculateActualFs(
        FG_BUFFER_SIZE,
        elapsed
      );

    maxBufferReady = true;

    calculateMAXResults();
    printSystemStatus();

    return;
  }

  // ===================================================
  // MAX30102 ROLLING BUFFER 75 + 25
  // ===================================================
  for (
    int i = FG_UPDATE_SAMPLES;
    i < FG_BUFFER_SIZE;
    i++
  )
  {
    irBuffer[
      i - FG_UPDATE_SAMPLES
    ] = irBuffer[i];

    redBuffer[
      i - FG_UPDATE_SAMPLES
    ] = redBuffer[i];
  }

  unsigned long startSampling =
    millis();

  for (
    int i = FG_KEEP_SAMPLES;
    i < FG_BUFFER_SIZE;
    i++
  )
  {
    if (!readMAXSample(ir, red))
    {
      resetMAXMeasurement();
      printSystemStatus();
      return;
    }

    if (ir < FINGER_THRESHOLD)
    {
      resetMAXMeasurement();
      printSystemStatus();
      return;
    }

    irBuffer[i] = ir;
    redBuffer[i] = red;
  }

  unsigned long elapsed =
    millis() -
    startSampling;

  maxActualFs =
    calculateActualFs(
      FG_UPDATE_SAMPLES,
      elapsed
    );

  calculateMAXResults();
  printSystemStatus();
}
