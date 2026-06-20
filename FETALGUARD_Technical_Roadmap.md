# FETAL-GUARD — Technical Roadmap & Engineering Brainstorm

**Dokumen Referensi Internal Tim**
Disusun untuk: Tim PKM-KC Institut Teknologi Sumatera
Versi: 1.0 | Status: Working Draft

---

## Daftar Isi

1. [Arsitektur Sistem Keseluruhan](#1-arsitektur-sistem-keseluruhan)
2. [Sistem Kelistrikan dan Power Management](#2-sistem-kelistrikan-dan-power-management)
3. [Akuisisi Data Sensor](#3-akuisisi-data-sensor)
4. [Desain IoT dan Dashboard](#4-desain-iot-dan-dashboard)
5. [Solusi Koneksi Internet untuk Alat Portabel](#5-solusi-koneksi-internet-untuk-alat-portabel)
6. [Alternatif Koneksi Bluetooth/BLE](#6-alternatif-koneksi-bluetoothble)
7. [Sistem AI Hybrid Deep Learning](#7-sistem-ai-hybrid-deep-learning)
8. [Ground Truth dan Strategi Validasi](#8-ground-truth-dan-strategi-validasi)
9. [Implementasi Bentuk Sabuk](#9-implementasi-bentuk-sabuk)
10. [Roadmap Realisasi Bertahap](#10-roadmap-realisasi-bertahap)
11. [Risiko Utama dan Mitigasi](#11-risiko-utama-dan-mitigasi)

---

## 1. Arsitektur Sistem Keseluruhan

### 1.1 Blok Diagram Sistem

```
LAYER SENSOR (On-Body)
┌──────────────────────────────────────────────────────────┐
│  [4x Piezoelektrik] [FSR 408] [MAX4466] [MAX30102]      │
│       ↓ analog          ↓ analog   ↓ analog   ↓ I2C     │
│  [LM324 Pre-Amp Array]  [Voltage Divider]  [direct]     │
└────────────────────────┬─────────────────────────────────┘
                         ↓
LAYER PEMROSESAN (Main Hub Control)
┌──────────────────────────────────────────────────────────┐
│  ESP32 DevKit V1 (Dual Core 240MHz, 520KB SRAM)         │
│  - ADC 12-bit multichannel                               │
│  - Signal conditioning & filtering awal                  │
│  - MQTT publish via WiFi / BLE proxy                    │
│  - LED status indicator                                  │
│  - Power management (sleep mode)                         │
└────────────────────────┬─────────────────────────────────┘
                         ↓
LAYER KOMUNIKASI
┌─────────────────┐   ┌──────────────────────────────────┐
│  WiFi 802.11n   │ OR│  BLE 4.2/5.0 → Smartphone App   │
│  MQTT over TLS  │   │  → Cloud via HTTPS               │
└────────┬────────┘   └──────────────┬───────────────────┘
         └──────────────┬────────────┘
                        ↓
LAYER CLOUD/SERVER
┌──────────────────────────────────────────────────────────┐
│  MQTT Broker (HiveMQ / Mosquitto / AWS IoT)             │
│  Backend API (Node.js/FastAPI)                          │
│  Database (PostgreSQL/TimescaleDB untuk time-series)    │
│  AI Inference Engine (CNN-LSTM model)                   │
│  Notifikasi Engine (FCM push notification)              │
└────────────────────────┬─────────────────────────────────┘
                         ↓
LAYER USER INTERFACE
┌──────────────────┐    ┌──────────────────────────────────┐
│  Aplikasi Mobile │    │  Dashboard Website               │
│  (Ibu Hamil)     │    │  (Tenaga Kesehatan)             │
└──────────────────┘    └──────────────────────────────────┘
```

### 1.2 Pembagian Sisi Sistem

**Sisi Pasien (Patient Side)**
- Sabuk pintar dengan sensor terpasang
- LED indikator (hijau = normal, merah = alert)
- Aplikasi mobile: tampilan ringkas, notifikasi peringatan
- Tidak perlu koneksi ke cloud secara langsung jika menggunakan BLE → smartphone

**Sisi Tenaga Kesehatan (Clinician Side)**
- Dashboard web: data waveform lengkap, tren historis, riwayat sesi
- Panel peringatan kritis dengan klasifikasi risiko
- Ekspor laporan PDF untuk rekam medis
- Akses multi-pasien dalam satu tampilan (ward monitoring)

**Sisi Cloud/Server**
- Menjalankan AI inference (CNN-LSTM) → lebih berat dari kapasitas ESP32
- Menyimpan data time-series mentah dan hasil analisis
- Mengelola notifikasi push ke mobile dan dashboard
- Sinkronisasi data dari mode offline (jika sinyal hilang)

---

## 2. Sistem Kelistrikan dan Power Management

### 2.1 Estimasi Konsumsi Daya

| Komponen | Mode Aktif | Mode Idle |
|---|---|---|
| ESP32 (WiFi aktif) | ~240 mA | ~10 mA (deep sleep) |
| ESP32 (BLE aktif) | ~130 mA | ~10 mA |
| 4x Piezoelektrik + LM324 | ~8–12 mA | ~2 mA |
| MAX30102 | ~1 mA | ~0.5 mA |
| MAX4466 | ~0.5 mA | ~0.1 mA |
| FSR408 | ~1–3 mA (tergantung divisor) | — |
| LED indikator | ~3–5 mA | 0 mA |
| **Total (WiFi mode)** | **~258–275 mA** | ~13 mA |
| **Total (BLE mode)** | **~145–160 mA** | ~13 mA |

**Kesimpulan kapasitas baterai:**
- Li-Po 2000mAh → ~7 jam (WiFi) atau ~12 jam (BLE)
- Li-Po 3000mAh → ~10 jam (WiFi) atau ~18 jam (BLE)
- **Rekomendasi: gunakan 3000mAh** agar cukup untuk sesi pemantauan harian 8–12 jam

### 2.2 Topologi Power Management

```
[Li-Po 3.7V, 3000mAh]
        ↓
[TP4056 — USB-C Charger Module]
    (proteksi overcharge, short circuit)
        ↓
[MT3608 — Step-Up ke 5V stabil]
    (input 3.0–4.2V → output 5V/2A)
        ↓
[AMS1117-3.3 atau LDO ke 3.3V] ─── untuk ESP32 (3.3V), MAX30102 (3.3V), MAX4466 (2.7–5.5V)
[5V rail] ────────────────────────── untuk LM324 Op-Amp (dual supply atau 5V single)

[Dioda Schottky 1N5819] — Isolasi antara USB power dan baterai power
```

**Hal kritis yang harus diimplementasikan:**
- Tambahkan kapasitor decoupling 100nF di setiap pin VCC sensor
- Tambahkan kapasitor 100µF pada output MT3608 untuk mengurangi ripple
- Gunakan jalur PCB terpisah untuk ground analog dan digital
- Pasang fuse polyfuse 500mA antara baterai dan sirkuit utama

### 2.3 Strategi Power Saving

Implementasikan duty-cycle pada ESP32:
```
Mode operasi:
  - Akuisisi data: 30 detik ON
  - Transmisi data: 5 detik WiFi burst
  - Deep sleep: 25 detik (opsional untuk hemat daya)

Atau mode continuous (disarankan untuk prototype):
  - ESP32 selalu aktif
  - WiFi modem sleep saat tidak transmit
  - ADC sampling dengan timer interrupt (bukan polling)
```

Untuk prototype mahasiswa: mulai dengan mode continuous yang sederhana, power saving dapat dioptimasi di iterasi berikutnya.

---

## 3. Akuisisi Data Sensor

### 3.1 Sensor Piezoelektrik — Deteksi DJJ

**Prinsip kerja:** Piezoelektrik mendeteksi vibrasi mekanik katup jantung janin (Phonocardiography/PCG). Sinyal ini sangat lemah (mV range) dan bercampur noise.

**Sampling rate yang diperlukan:**
- Sinyal DJJ mengandung komponen frekuensi 20–150 Hz
- Berdasarkan teorema Nyquist: sampling rate minimum 300 Hz
- **Rekomendasi praktis: 1000–2000 Hz** untuk memberikan resolusi temporal yang cukup

**Masalah kritis ADC ESP32:**
ESP32 ADC bawaan memiliki karakteristik non-linear dan noise yang signifikan (terutama di dekat WiFi transmisi). Solusi:

| Opsi | ADC Eksternal | Kelebihan | Kekurangan |
|---|---|---|---|
| **Opsi A (Disarankan)** | ADS1115 (I2C, 16-bit, 860 SPS) | Murah (~Rp 30rb), mudah | Hanya 860 SPS per channel |
| **Opsi B (Lebih Baik)** | ADS1256 (SPI, 24-bit, 30kSPS) | Kualitas tinggi | Lebih mahal (~Rp 150rb) |
| **Opsi C (Minimal)** | ESP32 ADC bawaan + software averaging | Tidak perlu komponen tambahan | Noise tinggi, non-linear |

Untuk prototype awal, **mulai dengan ESP32 ADC + averaging** dahulu untuk validasi sistem. Upgrade ke ADS1115 jika SNR tidak cukup.

**Rangkaian kondisioning sinyal piezoelektrik:**
```
[Piezo] ──── [R_bias 1MΩ ke GND] ──── [LM324 Stage 1: Gain x100]
                                         ↓
                                    [High-pass filter 20 Hz]
                                         ↓
                                    [LM324 Stage 2: Gain x10]
                                         ↓
                                    [Low-pass filter 150 Hz]
                                         ↓
                                    [DC offset: VCC/2 = 1.65V]
                                         ↓
                                    [ADC ESP32 atau ADS1115]
```

Total gain target: ~1000x. Tanpa gain ini, sinyal piezo terlalu kecil untuk ADC.

**Fusi 4 sensor piezoelektrik:**
Dari 4 sensor, ambil nilai dengan SNR tertinggi secara real-time (algorithm smart switching). Dapat juga dilakukan averaging dengan bobot berdasarkan kualitas sinyal.

### 3.2 Sensor FSR 408 — Deteksi Kontraksi

- Sampling rate: 10–50 Hz cukup (kontraksi berlangsung 30–90 detik)
- Rangkaian: voltage divider dengan R_ref = 10kΩ → ADC ESP32
- Kalibrasi: rekam baseline tanpa tekanan, tentukan threshold kontraksi secara adaptif
- Output: intensitas tekanan (0–1023 raw ADC), bukan tekanan absolut (mmHg)

**Catatan penting:** FSR 408 mengukur tekanan mekanik relatif pada area fundus uteri, bukan intrauterine pressure seperti pada tocotransducer medis. Dalam proposal harus dinyatakan secara eksplisit bahwa ini adalah estimasi indikator kontraksi, bukan pengganti tocometry klinis.

### 3.3 Sensor MAX30102 — Denyut Jantung Ibu

- Protokol: I2C (SDA, SCL → GPIO 21, 22 pada ESP32)
- Sampling: 50–100 Hz (atur via register MAX30102)
- Library: Sparkfun MAX3010x library (Arduino/ESP32)
- Output: nilai raw IR dan Red → algoritma SpO2 dan BPM
- Rekomendasi: gunakan library PulseSensor.com atau HeartRate calculation dari peak detection

### 3.4 Mikrofon MAX4466 — Referensi Noise untuk ANC

- Sampling rate: sama dengan piezoelektrik (1000–2000 Hz) agar algoritma ANC bekerja
- Output analog → ADC ESP32 (channel terpisah dari piezo)
- Gunakan sebagai sinyal referensi pada algoritma LMS (Least Mean Squares) Adaptive Filter di server

### 3.5 Data Tambahan yang Harus Dicatat

Setiap sesi pemantauan, simpan metadata berikut:
```json
{
  "session_id": "uuid",
  "timestamp_start": "ISO8601",
  "gestational_age_weeks": 32,
  "maternal_position": "supine/left-lateral/standing",
  "sensor_placement_quality": "good/fair/poor",
  "noise_level_dB": 45.2,
  "belt_tightness": "tight/normal/loose",
  "maternal_activity": "resting/walking/eating",
  "signal_snr_db": [12.3, 8.1, 15.2, 9.4],
  "notes": "teks bebas dari pengguna"
}
```

### 3.6 Pipeline Akuisisi Data di ESP32

```
Timer interrupt (1000 Hz)
  ↓
ADC read (4 piezo, 1 mikrofon, 1 FSR) — maks ~6 channel ADC
  ↓
Circular buffer (ukuran 2 detik = 2000 sampel per channel)
  ↓
Basic pre-processing di ESP32:
  - DC removal (moving average subtraction)
  - Simple bandpass FIR filter (untuk hemat memori, gunakan IIR 2nd-order biquad)
  ↓
MAX30102 polling via I2C (50 Hz, interrupt-based)
  ↓
Paketkan data setiap 1 detik → transmit via WiFi/BLE

Format paket data (JSON atau MessagePack untuk efisiensi):
{
  "t": 1718123456789,        // Unix timestamp ms
  "p": [1024, 980, 1100, 995, 1023, 980, ...], // piezo raw (1 detik x 1000 Hz x 4 ch)
  "m": [500, 480, 510, ...], // mikrofon raw
  "fsr": [320, 325, ...],    // FSR readings (50 Hz)
  "hr_ir": [...],            // MAX30102 IR
  "hr_red": [...]            // MAX30102 Red
}
```

**PENTING:** 1 detik data piezo 4 channel @ 1000 Hz = 4000 nilai int16 = 8KB. Jika WiFi bandwidth tidak cukup, pertimbangkan:
- Kompresi data (gzip, MessagePack bukan JSON)
- Downsampling setelah pre-filtering di ESP32
- Mode BLE yang hanya kirim features (bukan raw data)

---

## 4. Desain IoT dan Dashboard

### 4.1 Stack Teknologi yang Direkomendasikan

**Backend:**
- Python FastAPI atau Node.js Express
- MQTT Broker: HiveMQ Cloud (gratis tier) atau Mosquitto self-hosted
- Database: PostgreSQL + TimescaleDB extension (optimized untuk time-series)
- AI inference: TensorFlow Serving atau endpoint Python

**Frontend Mobile:**
- Flutter (cross-platform iOS & Android, satu codebase)
- Alternatif: React Native

**Frontend Web Dashboard:**
- React.js + Chart.js/Recharts untuk visualisasi sinyal
- Alternatif sederhana: Grafana (open source, cocok untuk prototype)

**Hosting awal yang murah:**
- Railway.app atau Render.com (free tier cukup untuk prototype)
- MQTT: HiveMQ Cloud free (10 koneksi, cukup untuk demo)

### 4.2 Apa yang Ditampilkan ke Pasien vs Tenaga Kesehatan

**Aplikasi Ibu Hamil (Patient App) — prinsip: simple, tidak menimbulkan klaim diagnosis:**

| Informasi | Boleh ditampilkan | Tidak boleh |
|---|---|---|
| Status koneksi perangkat | ✅ | — |
| Durasi sesi pemantauan | ✅ | — |
| Indikator kualitas sinyal | ✅ | Raw SNR dalam angka |
| Status umum: Normal / Perlu Perhatian / Darurat | ✅ | "FHR = 185 bpm (ABNORMAL)" |
| Estimasi DJJ (bpm) | ✅ dengan catatan "estimasi" | Tanpa disclaimer |
| Grafik aktivitas kontraksi | ✅ sebagai indikator, bukan diagnosa | Nilai mmHg absolut |
| Notifikasi push | ✅ dengan bahasa non-medis | Terminologi klinis teknis |
| Tombol "Hubungi Dokter" / "Darurat" | ✅ | — |
| Saran posisi tubuh | ✅ | — |

**Dashboard Tenaga Kesehatan (Clinician Web Portal):**
- Waveform sinyal DJJ real-time (mirip CTG strip)
- Grafik variabilitas DJJ (FHRV)
- Estimasi kontraksi (relative intensity, bukan mmHg)
- Klasifikasi risiko AI: Normal / Watchful / Alert + confidence score
- Riwayat sesi lengkap dengan metadata
- Ekspor PDF atau CSV per pasien
- Notifikasi alert ke email/SMS (opsional, via Twilio/SendGrid)

### 4.3 Alur Data dari Perangkat ke Server

```
ESP32 → MQTT Publish (topic: fetalguard/{device_id}/raw)
         ↓
MQTT Broker (HiveMQ)
         ↓
Backend Service Subscribe → proses & simpan ke DB
         ↓
AI Inference (setiap 5–30 detik window)
         ↓
MQTT Publish hasil AI (topic: fetalguard/{device_id}/result)
         ↓
Aplikasi Mobile & Web Subscribe → update UI real-time
```

**QoS MQTT:** Gunakan QoS 1 (at least once delivery) untuk data penting, QoS 0 untuk raw sensor stream (tidak perlu dijamin, mengurangi overhead).

---

## 5. Solusi Koneksi Internet untuk Alat Portabel

### 5.1 Masalah: Multi-User WiFi Configuration

Jika alat digunakan oleh banyak pasien di berbagai rumah, setiap rumah punya SSID dan password berbeda. Hardcoding SSID tidak mungkin.

### 5.2 Perbandingan Opsi Koneksi

| Metode | Cara Kerja | Untuk Prototype | Untuk Produk |
|---|---|---|---|
| **WiFi Manager (Captive Portal)** | ESP32 buat access point sementara → user connect dari HP → buka halaman web → input SSID+password → disimpan di EEPROM/NVS | ⭐⭐⭐ **Terbaik untuk prototype** | ⭐⭐ Kurang user-friendly |
| **ESP SmartConfig (Espressif)** | Smartphone broadcast SSID+password ke ESP32 via WiFi packet | ⭐⭐ Perlu app khusus | ⭐⭐ Tergantung SDK |
| **BLE Provisioning** | Kirim SSID+password via BLE dari aplikasi mobile → ESP32 simpan & connect WiFi | ⭐⭐ Perlu BLE setup lebih dulu | ⭐⭐⭐ **Terbaik untuk produk** |
| **Hotspot Smartphone** | Ibu aktifkan hotspot HP → ESP32 connect ke hotspot | ⭐⭐⭐ Sangat mudah untuk prototype | ⭐ Baterai HP cepat habis |
| **SIM800L / SIM7600 (GSM)** | Modul 4G/LTE langsung di perangkat | ⭐ Terlalu kompleks | ⭐⭐ Mahal, butuh SIM card |
| **Mode Offline + SD Card Sync** | Simpan lokal ke micro-SD → sync saat ada WiFi | ⭐⭐ Perlu komponen tambahan | ⭐⭐⭐ Fallback yang baik |

### 5.3 Rekomendasi Arsitektur Koneksi

**Fase Prototype (Mahasiswa PKM):**
```
Gunakan WiFi Manager Library (tzapu/WiFiManager) + Hotspot HP sebagai fallback
  
  1. Pertama kali dinyalakan: ESP32 buat AP "FETALGUARD-SETUP"
  2. User connect HP ke AP tersebut
  3. Browser otomatis buka 192.168.4.1 (captive portal)
  4. User pilih WiFi rumah dari list yang terscan + input password
  5. ESP32 simpan credential di NVS (Non-Volatile Storage)
  6. Jika gagal connect: aktifkan mode hotspot HP sebagai backup
```

**Fase Produk:**
```
BLE Provisioning via Aplikasi Mobile
  
  1. User install aplikasi FETAL-GUARD di HP
  2. Tap "Pasangkan Perangkat" → scan BLE
  3. Aplikasi connect ke ESP32 via BLE
  4. Kirim SSID + password via BLE (encrypted)
  5. ESP32 connect ke WiFi → konfirmasi via BLE ke aplikasi
  6. Selanjutnya, ESP32 kirim data via WiFi (lebih hemat baterai HP)
```

**Implementasi WiFi Manager (kode ringkas):**
```cpp
#include <WiFiManager.h>

void setup() {
  WiFiManager wm;
  // Timeout 180 detik untuk setup
  wm.setConfigPortalTimeout(180);
  
  if (!wm.autoConnect("FETALGUARD-SETUP")) {
    ESP.restart(); // restart jika gagal connect
  }
  // Jika sampai sini, WiFi sudah terhubung
}
```

---

## 6. Alternatif Koneksi Bluetooth/BLE

### 6.1 Arsitektur BLE Hybrid

Alur data: `ESP32 BLE → Smartphone App → Cloud (HTTPS/MQTT)`

```
Keuntungan:
✅ Tidak perlu WiFi provisioning yang rumit
✅ Konsumsi daya ESP32 lebih rendah (BLE vs WiFi)
✅ Pairing sekali, tidak perlu konfigurasi ulang di lokasi baru
✅ Smartphone sebagai gateway → data forwarding ke cloud
✅ Tetap bisa kirim notifikasi ke ibu via app meski tidak ada WiFi di perangkat

Kekurangan:
❌ Jika HP mati / jauh, data tidak terkirim ke cloud
❌ Throughput BLE terbatas (~100 KB/s praktis vs ~1 MB/s WiFi)
❌ Latensi lebih tinggi (~20-50ms vs <10ms WiFi)
❌ Butuh HP aktif dan dalam jangkauan BLE (~10 meter)
```

### 6.2 Throughput BLE vs Kebutuhan Data

- BLE 4.2: ~7 Mbps teoritis, ~20–50 KB/s praktis
- BLE 5.0: ~2 Mbps teoritis, ~100–250 KB/s praktis
- Data sensor 1 detik: ~8–16 KB/s (tergantung resolusi)

**Solusi jika BLE bandwidth tidak cukup:**
- Kirim compressed features dari ESP32 (bukan raw data)
- Buffer di ESP32 selama 5 detik, kirim burst setiap 5 detik
- Gunakan MessagePack (binary) bukan JSON (text) → 2-3x lebih kecil

### 6.3 Implementasi BLE di ESP32

```cpp
// ESP32 sebagai BLE Server (Peripheral)
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define SERVICE_UUID        "12345678-1234-1234-1234-123456789abc"
#define CHARACTERISTIC_UUID "abcd1234-abcd-abcd-abcd-abcdef012345"

BLECharacteristic* pCharacteristic;

void sendSensorData(uint8_t* data, size_t len) {
  pCharacteristic->setValue(data, len);
  pCharacteristic->notify(); // push ke aplikasi tanpa diminta
}
```

Aplikasi mobile (Flutter) bertindak sebagai BLE Central yang subscribe ke notifikasi, lalu forward ke cloud via HTTPS.

### 6.4 Keamanan BLE

- Gunakan BLE Bonding (pairing dengan PIN atau numerik perbandingan)
- Data yang dikirim via BLE: enkripsi di layer BLE (BLE 4.2+ support LE Secure Connections)
- Data yang dikirim ke cloud via HP: gunakan HTTPS (TLS 1.3)
- Tambahkan app-level encryption (AES-128) untuk data sensitif medis

### 6.5 Mode Hybrid (Rekomendasi Terbaik untuk Prototype)

```
Primary: BLE → HP → Cloud
Fallback: WiFi langsung → Cloud (jika HP tidak tersedia)

Prioritas otomatis:
  1. Cek apakah BLE terhubung ke aplikasi HP → gunakan BLE
  2. Jika tidak → coba WiFi dengan credential tersimpan
  3. Jika WiFi gagal → simpan ke buffer memori / SD card
  4. Sync saat koneksi tersedia kembali
```

---

## 7. Sistem AI Hybrid Deep Learning

### 7.1 Data yang Dibutuhkan

**Dataset Publik yang Tersedia (Gratis):**

| Dataset | Sumber | Isi | Ukuran |
|---|---|---|---|
| CTU-CHB Intrapartum CTG Database | PhysioNet.org | 552 rekaman CTG (FHR + kontraksi) berlabel | ~1.6 GB |
| NI-FECG Synthetic DB | PhysioNet.org | Sinyal ECG janin sintetis dan campuran | Kecil |
| Physionet/CinC Challenge 2013 | PhysioNet.org | Fetal ECG dari elektroda abdominal | Sedang |
| FPCGDB | PhysioNet.org | Sinyal PCG janin dari perangkat piezo | Relevan! |
| CTG Dataset | Kaggle/UCI | 2126 rekaman CTG dengan label Normal/Suspect/Pathological | ~50KB CSV |

**Dataset yang Relevan dengan FETAL-GUARD (prioritaskan ini):**
- FPCGDB (Fetal Phonocardiography Database) — sangat relevan karena dari piezoelektrik
- Kaggle CTG Dataset — relevan untuk label classification

**Data Primer yang Perlu Dikumpulkan:**
Rekam data dari perangkat FETAL-GUARD secara bersamaan dengan CTG klinis (ground truth). Bahkan 10–20 rekaman sudah bisa digunakan untuk fine-tuning.

### 7.2 Pipeline Pemrosesan dan Pelatihan Model

```
RAW SIGNAL (dari piezo + mikrofon)
         ↓
1. Pre-processing:
   - Bandpass filter 20–150 Hz (FIR atau IIR)
   - Normalisasi amplitudo (Z-score atau Min-Max)
   - Segmentasi window (5 detik, overlap 50%)
         ↓
2. Feature Extraction (pilih salah satu sebagai input CNN):
   - Spektrogram STFT (Short-Time Fourier Transform)
   - Mel-frequency spectrogram
   - ATAU raw time series (untuk 1D CNN)
         ↓
3. CNN Layer (Ekstraksi Fitur Spasial/Lokal):
   - Input: (window_size, 1) untuk 1D CNN, atau (freq_bins, time_bins, 1) untuk 2D CNN
   - Conv1D x 3 layers (filters: 32, 64, 128), kernel_size=7, activation=ReLU
   - MaxPooling1D x 3
   - Dropout 0.3
         ↓
4. LSTM Layer (Pola Temporal):
   - Reshape output CNN → sequence
   - LSTM 128 units (2 layers, bidirectional)
   - Dropout 0.3
         ↓
5. Fully Connected + Output:
   - Dense 64, ReLU
   - Output Dense 3: Normal / Watchful / Alert (Softmax)
   - Tambahan head: estimasi DJJ (regresi, output 1 neuron)
```

### 7.3 Arsitektur Model yang Direkomendasikan

**Pendekatan Hybrid: Rule-Based + Deep Learning**

```python
# Pseudocode arsitektur hybrid

def classify_fetal_status(fhr_estimate, fhrv, contraction_indicator, dl_prediction):
    
    # Layer 1: Hard Rules (clinical thresholds — tidak bisa di-override AI)
    if fhr_estimate < 100:
        return "ALERT", "Bradikardia berat — segera hubungi tenaga kesehatan"
    if fhr_estimate > 180:
        return "ALERT", "Takikardia berat — segera hubungi tenaga kesehatan"
    
    # Layer 2: Soft Rules (clinical guidelines)
    if fhr_estimate < 110 or fhr_estimate > 160:
        soft_alert = True
    else:
        soft_alert = False
    
    # Layer 3: AI Model prediction
    ai_class = dl_prediction["class"]  # Normal/Watchful/Alert
    ai_confidence = dl_prediction["confidence"]
    
    # Kombinasi rule + AI
    if soft_alert and ai_class == "Alert":
        return "ALERT", confidence=high
    elif soft_alert or ai_class in ["Alert", "Watchful"]:
        return "WATCHFUL", confidence=medium
    else:
        return "NORMAL", confidence=ai_confidence
```

Keuntungan hybrid: bahkan jika model AI salah (underfitting karena data terbatas), rule-based tetap menangkap anomali klinis yang jelas.

### 7.4 Estimasi DJJ dari Sinyal Piezoelektrik

Ini adalah tantangan teknis terbesar. Metode yang bisa dicoba secara bertahap:

**Tahap 1 (Paling Sederhana):** Peak Detection pada sinyal yang sudah difilter
```python
from scipy.signal import find_peaks

def estimate_fhr(signal, fs=1000):
    # Bandpass 20-50 Hz untuk isolasi S1 (komponen dominan DJJ)
    filtered = bandpass_filter(signal, 20, 50, fs)
    # Cari puncak dengan minimum interval 300ms (max 200 bpm)
    peaks, _ = find_peaks(filtered, distance=fs*0.3, height=threshold)
    # Hitung BPM dari interval antar puncak
    intervals = np.diff(peaks) / fs  # dalam detik
    bpm = 60 / np.mean(intervals)
    return bpm
```

**Tahap 2:** Autocorrelation-based period estimation (lebih robust terhadap noise)

**Tahap 3:** Deep learning regression (CNN-LSTM untuk estimasi FHR dari raw signal)

### 7.5 Strategi Pelatihan dengan Data Terbatas

- Transfer learning: gunakan pre-trained model dari CTG dataset (CTU-CHB), fine-tune dengan data primer Anda
- Data augmentation: time stretching, amplitude scaling, synthetic noise injection
- K-fold cross validation: minimal 5-fold untuk evaluasi yang lebih reliable
- Gunakan class weighting: dataset biasanya imbalanced (lebih banyak normal)

**Framework yang disarankan:**
- TensorFlow/Keras (lebih banyak referensi untuk deploy ke embedded)
- Untuk ESP32 inference: TensorFlow Lite Micro (namun memori sangat terbatas)
- **Rekomendasi: jalankan inference di cloud server**, bukan di ESP32

---

## 8. Ground Truth dan Strategi Validasi

### 8.1 Apa itu Ground Truth dalam Konteks FETAL-GUARD

Ground truth adalah data referensi dari alat medis yang sudah tervalidasi secara klinis:
- **DJJ (FHR):** dari CTG konvensional (elektronik fetal monitoring)
- **Kontraksi:** dari tocotransducer atau IUPC (intrauterine pressure catheter)
- **SpO2/HR ibu:** dari pulse oximeter klinis

### 8.2 Tahapan Validasi (dari Mudah ke Susah)

**Tahap 0 — Bench Testing (Tanpa Akses Rumah Sakit)**
```
Validasi piezoelektrik:
  - Gunakan speaker kecil yang diputar sinyal jantung simulasi (sine wave 80-150 Hz)
  - Tempel piezo di atas speaker → lihat apakah sistem bisa deteksi frekuensi
  - Bandingkan estimasi BPM dari sistem vs frekuensi input yang diketahui

Validasi FSR:
  - Tekan dengan tangan, bandingkan output terhadap skala tekanan yang diketahui
  
Validasi MAX30102:
  - Tempelkan di jari, bandingkan BPM dengan manual count atau pulse oximeter komersial
```

**Tahap 1 — Simulasi Sinyal (Signal Generator)**
```
- Gunakan audio playback sinyal FHR dari dataset PhysioNet (FPCGDB)
- Putar melalui speaker kecil yang ditempel di permukaan simulasi perut
- Catat sinyal dari piezo → bandingkan estimasi FHR dengan ground truth dataset
- Ini bisa dilakukan di lab tanpa melibatkan manusia
```

**Tahap 2 — Phantom/Manikin Simulasi**
```
- Buat phantom sederhana: balon berisi air (simulasi janin) di dalam media gelatin/gel ultrasound
- Speaker mini di dalam "janin" memutar sinyal PCG jantung dari dataset
- Sabuk dipasang di sekitar phantom
- Lebih realistis dari signal generator murni
```

**Tahap 3 — Uji Non-Klinis pada Manusia (Non-Pregnant Volunteer)**
```
- Pasang sabuk di perut sukarelawan dewasa yang tidak hamil
- Validasi bahwa sistem bisa membedakan DJJ dari sinyal tubuh lain
- Ukur kenyamanan ergonomis, distribusi beban, dan stabilitas sensor
- Tidak melibatkan data medis → tidak perlu ethical clearance medis
```

**Tahap 4 — Uji Terbatas Klinis (Membutuhkan Kolaborasi Klinis + Ethical Clearance)**
```
- Kolaborasi dengan bidan/dokter di klinik KIA atau puskesmas
- Pasang FETAL-GUARD bersamaan dengan CTG (simultan)
- Rekam data keduanya → korelasi hasil estimasi vs CTG
- Harus ada ethical clearance dari komite etik institusi
- Bahkan 5–10 subjek sudah cukup untuk uji awal
```

### 8.3 Jika Akses Rumah Sakit Sangat Terbatas

Langkah yang realistis untuk tim mahasiswa:
1. **Prioritaskan Tahap 0–2** untuk proof-of-concept teknis
2. Hubungi **Puskesmas terdekat atau BPS (Bidan Praktek Swasta)** — lebih mudah dari RSUD
3. Minta izin **observasi (bukan intervensi)** — pasang alat secara bersamaan, tanpa mengubah penanganan pasien
4. Siapkan **surat izin dari dosen + institusi** (bukan surat penelitian penuh, cukup surat pengantar)
5. Manfaatkan **koneksi dosen pendamping (Rudi Setiawan, S.T., M.T.)** yang sudah punya pengalaman riset medis

### 8.4 Metrik Evaluasi

**Untuk estimasi DJJ:**
- MAE (Mean Absolute Error) dalam bpm → target: MAE < 5 bpm
- RMSE (Root Mean Square Error) → target: < 10 bpm
- Bland-Altman plot untuk visualisasi agreement dengan CTG

**Untuk klasifikasi kondisi janin:**
- Sensitivitas (Recall) untuk kelas Alert → prioritas tinggi, target > 85%
- Spesifisitas → target > 70% (boleh ada false positive, asal tidak banyak)
- F1-Score per kelas
- Confusion matrix

**Untuk sistem secara keseluruhan:**
- Latensi end-to-end (dari sensor ke notifikasi) → target: < 5 detik
- Reliabilitas koneksi (uptime %) → target: > 95% selama sesi 30 menit
- Durasi baterai → target: > 8 jam per charge
- SNR sinyal piezoelektrik → target: > 10 dB

---

## 9. Implementasi Bentuk Sabuk

### 9.1 Desain Mekanik yang Direkomendasikan

```
TAMPAK DEPAN ABDOMEN:

  ┌──────────────────────────────────────────────────────┐
  │  [STRAP ATAS — FSR 408 Strip di area fundus uteri]  │
  │              ↑ sekitar 3-4 jari di bawah pusar       │
  │                                                      │
  │  Panel Abdomen (kain elastis tebal):                │
  │    [P1] ───── [MIKROFON] ───── [P2]                 │
  │         \         |           /                      │
  │          \      Formasi     /                        │
  │           \    Belah       /                         │
  │         [P3] ─── ─── ─ [P4]                         │
  │    P1-P4 = Sensor Piezoelektrik                     │
  │                                                      │
  │  [MAIN HUB CONTROL] ← di sisi lateral abdomen       │
  │  (casing, ESP32, baterai)                           │
  └──────────────────────────────────────────────────────┘
  
  ┌─────────────────────────────────┐
  │  STRAP BELAKANG + PINGGANG      │
  │  [MAX30102] di sayap pinggang   │
  │  (finger touch pad format)      │
  └─────────────────────────────────┘
```

### 9.2 Material dan Konstruksi

| Bagian | Material | Pertimbangan |
|---|---|---|
| Panel abdomen utama | Cotton Lycra 4-way stretch | Breathable, elastis, tidak iritasi |
| Lapisan sensor piezo | Foam EVA 5mm + fabric pocket | Memastikan kontak penuh, reduksi noise gesekan |
| Enclosure sensor | PLA 3D print + lapisan karet tipis | Rigid tapi tidak keras pada kulit |
| Main Hub Control casing | PLA 3D print (Gyroid infill untuk cushioning) | Ringan, kuat |
| Kabel penghubung | Kabel silikon AWG 26 (flexible) | Tidak kaku, tahan tekukan berulang |
| Manajemen kabel | Kanal kain dijahit langsung di strap | Tidak terlihat, tidak tersangkut |
| Velcro penutup | Velcro high-grade 5cm | Adjustable untuk berbagai ukuran perut |

### 9.3 Posisi Sensor yang Kritis

**Sensor Piezoelektrik:**
- Letakkan di tengah abdomen (antara pusar dan simfisis pubis)
- Formasi belah ketupat: jarak antar sensor ~5–8 cm
- Pastikan kontak langsung dengan kulit (bukan di atas pakaian)
- Tambahkan gel akustik atau pad foam yang sudah dikompresi untuk kontak optimal

**FSR 408:**
- Area fundus uteri: sekitar 3-4 cm di atas pusar (bervariasi per usia kehamilan)
- Pasang dalam strip horizontal agar merata menangkap tekanan kontraksi

**MAX30102:**
- Di sayap pinggang (lateral), format "finger touch pad" — ibu menekan jarinya ke sensor
- Hindari area abdomen karena lapisan lemak mengurangi kualitas sinyal PPG

**Main Hub Control:**
- Di sisi lateral bawah perut, TIDAK di atas rahim
- Ini mengurangi tekanan langsung pada janin dan memastikan distribusi berat merata

### 9.4 Menjaga Konsistensi Posisi Sensor

Problem terbesar: sensor bergeser saat ibu bergerak → noise tinggi dan data tidak konsisten.

**Solusi:**
1. Gunakan sistem elastic pocket yang menekan sensor ke abdomen (bukan hanya ditempel)
2. Tandai posisi sensor dengan jahitan guide atau dot berbeda warna pada sabuk
3. Tambahkan sticker skin-safe (seperti sticker elektroda ECG) di bawah setiap sensor piezo
4. Pada aplikasi: tampilkan signal quality indicator → beri tahu ibu saat sensor bergeser
5. Sistem kalibrasi otomatis saat mulai sesi: 30 detik diam untuk baseline

---

## 10. Roadmap Realisasi Bertahap

### Bulan 1 — MVP Signal Acquisition (Proof-of-Concept Teknis)

**Target:** Bisa baca data dari semua sensor dan tampilkan di Serial Monitor / laptop.

**Tugas Hardware:**
- [ ] Rakit rangkaian piezoelektrik + LM324 pre-amp di breadboard
- [ ] Uji gain dan frekuensi response dengan signal generator (atau speaker + function generator app)
- [ ] Rakit FSR408 + voltage divider
- [ ] Integrasikan MAX30102 via I2C
- [ ] Integrasikan MAX4466 (analog)
- [ ] Sambungkan semua ke ESP32, validasi tidak ada konflik ADC channel
- [ ] Buat sabuk prototype pertama dari kain elastis sederhana (tidak perlu rapi)

**Tugas Software:**
- [ ] Arduino sketch: baca semua sensor, output ke Serial pada 115200 baud
- [ ] Python script di laptop: terima data Serial, plot real-time (gunakan matplotlib/pyserial)
- [ ] Implementasi simple bandpass filter (IIR biquad) di ESP32
- [ ] Validasi bench test: apakah bisa detect simulasi sinyal jantung dari speaker?

**Deliverable Bulan 1:**
- Grafik sinyal real-time dari semua sensor yang terlihat berkorelasi dengan sumber sinyal
- Estimasi BPM sederhana dari sinyal piezo (meski akurasi masih rendah)

### Bulan 2–3 — Sistem Komunikasi dan Dashboard Awal

**Target:** Data terkirim ke cloud, tersimpan di database, bisa dilihat di web browser.

**Tugas:**
- [ ] Setup MQTT broker (HiveMQ Cloud free tier)
- [ ] Implementasi WiFi Manager di ESP32
- [ ] Backend sederhana: FastAPI Python, subscribe MQTT, simpan ke PostgreSQL
- [ ] TimescaleDB extension untuk data time-series
- [ ] Dashboard web minimal: tabel data + grafik sinyal (gunakan Grafana atau Chart.js)
- [ ] Aplikasi mobile prototype (Flutter): tampilkan status koneksi + BPM sederhana
- [ ] Setup BLE alternatif (opsional di bulan ini, bisa di bulan 3)

**Sabuk:**
- [ ] Pola sabuk v1: jahit pocket sensor, pasang velcro, test kenyamanan
- [ ] Cetak casing Main Hub Control dengan 3D printer
- [ ] Desain PCB versi pertama (bisa gunakan perfboard/protoboard dahulu)

### Bulan 4–6 — AI Integration dan Validasi Awal

**Target:** Model AI running, validasi Tahap 0–2 selesai.

**Tugas AI:**
- [ ] Download dan preprocess CTU-CHB CTG dataset + FPCGDB dari PhysioNet
- [ ] Implementasi feature extraction (bandpass filter, STFT/spectrogram)
- [ ] Training model CNN-LSTM pada dataset publik
- [ ] Deploy model sebagai endpoint REST API di server (TensorFlow Serving atau FastAPI)
- [ ] Integrasikan endpoint AI ke pipeline backend
- [ ] Implementasi rule-based layer (hard thresholds DJJ)
- [ ] Tampilkan klasifikasi di dashboard

**Validasi:**
- [ ] Tahap 0: bench test dengan signal generator
- [ ] Tahap 1: simulasi sinyal dari dataset PhysioNet
- [ ] Tahap 2: phantom test (opsional, bergantung waktu)
- [ ] Dokumentasi metrik: MAE FHR estimation, sensitivitas/spesifisitas klasifikasi

**Sabuk:**
- [ ] PCB final (cetak atau etching)
- [ ] Sabuk v2: lebih rapi, material production-quality
- [ ] Uji kenyamanan 1–2 jam pada relawan

### Bulan 7–12 — Validasi Klinis Terbatas dan Penyempurnaan

**Target:** Uji terbatas dengan ibu hamil (Tahap 3–4), evaluasi komprehensif.

**Tugas:**
- [ ] Siapkan ethical clearance (melalui institusi)
- [ ] Kolaborasi dengan klinik/puskesmas untuk pilot study
- [ ] Rekam data bersamaan dengan CTG (10–20 subjek minimal)
- [ ] Fine-tuning model AI dengan data primer
- [ ] Evaluasi metrik lengkap (Bland-Altman, ROC AUC, dll)
- [ ] Usability test: kuesioner kenyamanan, ease of use
- [ ] Penyesuaian desain sabuk berdasarkan feedback pengguna
- [ ] Laporan akhir, paper publikasi (opsional)

### Prioritas Fitur

**Harus dibuat dulu (core):**
1. Akuisisi sinyal piezo yang bisa menghasilkan estimasi BPM
2. Transmisi data via WiFi ke server
3. Penyimpanan data di database
4. Dashboard minimal untuk tampilan sinyal
5. Hard-rule alert (FHR di luar range)

**Bisa ditunda:**
- BLE provisioning (ganti dengan WiFi Manager dulu)
- AI deep learning (mulai dengan rule-based + simple peak detection)
- Mobile app lengkap (mulai dengan web dashboard)
- Ekspor PDF
- GPS geolocation

---

## 11. Risiko Utama dan Mitigasi

| Risiko | Dampak | Kemungkinan | Mitigasi |
|---|---|---|---|
| Sinyal piezo terlalu noise, DJJ tidak terdeteksi | Sangat tinggi | Tinggi | Benchmark early (bulan 1), siapkan opsi sensor alternatif (contact microphone medis/stetoskop digital) |
| ESP32 ADC terlalu noisy saat WiFi aktif | Tinggi | Sedang | Gunakan external ADC (ADS1115), atau gunakan BLE (tidak mengganggu ADC saat transmit) |
| Model AI akurasi rendah karena data terbatas | Tinggi | Sedang | Mulai dengan rule-based, gunakan transfer learning, prioritaskan data augmentation |
| Tidak dapat akses RS untuk validasi | Sedang | Tinggi | Validasi Tahap 0–2 cukup untuk PKM, hubungi puskesmas/BPS untuk Tahap 3–4 |
| Baterai tidak cukup untuk sesi panjang | Sedang | Sedang | Upgrade ke 3000mAh, implementasi power saving mode |
| Sensor bergeser, data tidak konsisten | Tinggi | Tinggi | Desain pocket khusus, skin-safe sticker, signal quality indicator |
| Ethical clearance terlambat | Sedang | Sedang | Mulai proses ethical clearance dari bulan 1–2, jadikan parallel track |
| Koneksi WiFi tidak stabil di rumah pasien | Sedang | Sedang | Implementasi offline buffer + mode BLE sebagai fallback |

---

## Catatan Penting: Disclaimer Medis

**WAJIB diimplementasikan dalam semua output sistem:**

1. Setiap tampilan kepada pengguna HARUS menyertakan kalimat: *"Hasil dari FETAL-GUARD bersifat indikatif dan bukan pengganti pemeriksaan medis profesional. Selalu konsultasikan kondisi janin dengan tenaga kesehatan."*

2. Klasifikasi AI hanya menggunakan terminologi risiko awal (low risk / watchful / alert), BUKAN terminologi diagnostik (normal / abnormal / fetal distress).

3. Sistem harus memiliki tombol darurat yang mengarahkan ke kontak tenaga kesehatan, dan tidak boleh mendorong pengguna untuk menunda pemeriksaan medis jika ada indikasi alert.

4. Dokumentasikan keterbatasan sistem secara eksplisit dalam laporan akhir.

---

*Dokumen ini bersifat living document. Update setiap kali ada keputusan desain baru.*
*Terakhir diperbarui: Juni 2026*
