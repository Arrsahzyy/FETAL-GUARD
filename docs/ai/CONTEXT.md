# Fetal Guard — AI Agent Context

> File ini adalah referensi utama yang WAJIB dibaca AI agent setiap memulai sesi.
> Sumber: [fetal_guard_context_ai.md](file:///e:/PROJECT/PKM%20KC%20ACA/fetal_guard_context_ai.md)

---

## Identitas Proyek

| Field | Detail |
|---|---|
| Nama alat | FETAL-GUARD |
| Jenis program | PKM-KC (Karsa Cipta) |
| Bentuk inovasi | Sabuk pintar / wearable maternity belt |
| Target pengguna | Ibu hamil & tenaga kesehatan (nakes) |
| Durasi proyek | ~4 bulan |
| Anggaran | Rp 8.745.000 |
| Tim | 5 orang (Mailani, Fitriah, Tasya, Arris, Aditya) |

---

## What This Project Is

- Prototype PKM-KC untuk skrining awal risiko feto-maternal.
- Riset rekayasa mahasiswa.
- Sistem wearable non-invasif portabel.
- Sistem yang membutuhkan validasi terhadap ground truth medis.

## What This Project Is NOT

- Bukan pengganti CTG, tocotransducer, Doppler, USG, dokter, bidan, atau fasilitas RS.
- Bukan alat diagnosis medis definitif.
- Belum tervalidasi klinis kecuali dibuktikan oleh data uji.

---

## Hardware Stack

| Komponen | Qty | Fungsi |
|---|---:|---|
| ESP32 DevKit V1 | 1 | MCU utama: baca ADC, I2C, WiFi/BLE, preprocessing |
| Sensor piezoelektrik | 4 | Array terdistribusi untuk vibrasi mekanik DJJ |
| FSR408 | 1 strip | Indikator kontraksi rahim (tekanan mekanik) |
| MAX30102 | 1 | PPG maternal: denyut jantung ibu |
| LM324 | 2 IC | Pre-amplifier analog sinyal piezo |
| Li-Po 3.7V 2000mAh | 1 | Sumber daya utama |
| TP4056 | 1 | Modul charger baterai |
| MT3608 | 1 | Step-up 5V untuk sensor/op-amp |
| LED merah + hijau | 1+1 | Indikator alarm dan status |

> **Catatan**: Mikrofon MAX4466 yang ada di proposal asli **TIDAK digunakan** dalam implementasi. Strategi noise cancellation menggunakan multi-channel piezo selection (SNR terbaik), adaptive filtering, bandpass filtering, dan signal quality index.

### Analog Front-End

Sinyal piezo → LM324 pre-amp → filter analog (LPF/BPF) → ADC ESP32 (maks 3.3V, perlu proteksi tegangan negatif). Isu kritis: impedansi tinggi, bias tengah AC, shielding kabel, ground layout, switching noise dari MT3608.

### Power Architecture

Li-Po 3.7V → TP4056 charger → MT3608 step-up 5V → sensor/op-amp. ESP32 via VIN 5V. Perlu: proteksi baterai, load sharing, estimasi daya (ESP32 boros saat WiFi aktif), isolasi jalur analog-digital.

---

## Parameter Klinis Rujukan

| Parameter | Bradikardia | Normal | Takikardia |
|---|---:|---:|---:|
| HR Ibu | < 60 bpm | 60-100 bpm | > 100 bpm |
| FHR Janin | < 110 bpm | 110-160 bpm | > 160 bpm |

Parameter FHR yang dipantau: baseline, variabilitas, akselerasi, deselerasi, pola abnormal.

Kontraksi rahim: frekuensi, durasi, intensitas (diukur via FSR sebagai proksi tekanan mekanik). FSR bukan pengganti tocotransducer — validasi terhadap toco klinis diperlukan.

---

## Data Flow

```
Sensor pada sabuk
  → Analog front-end (LM324 pre-amp + filter)
  → ESP32 ADC
  → WiFi + MQTT (atau BLE ke smartphone)
  → Server/Cloud
  → AI hybrid CNN-LSTM
  → Mobile App ibu hamil
  → Dashboard website nakes
  → Alert / notifikasi / rekomendasi
```

---

## Core Subsystems

### 1. Embedded Device (ESP32)
Baca sensor via ADC (piezo) dan I2C (MAX30102), preprocessing awal, buffering, kirim data via WiFi/MQTT atau BLE. Fallback: simpan lokal jika koneksi putus.

### 2. Analog Front-End
LM324 pre-amplifier, filter analog, proteksi ADC. Kritis untuk SNR sinyal piezo.

### 3. Power Management
Li-Po + TP4056 + MT3608. Keamanan baterai, isolasi, pemanasan, load sharing.

### 4. Wearable / Belt Design
Maternity support belt 80-117 cm, Cotton Lycra + mesh + Velcro. Sensor placement: piezo di panel tengah abdomen, FSR di area fundus, MAX30102 di sayap pinggang. Casing PLA 3D-printed.

### 5. Mobile App (Ibu Hamil)
Home (status DJJ, koneksi, baterai), History (rekam medis digital, ekspor PDF), Monitoring (grafik real-time menyerupai CTG), Notifikasi (alert merah/kuning/biru + rekomendasi tindakan), Settings (profil, dark mode, AI lokal).

### 6. Cloud / API
MQTT broker, penyimpanan sesi, manajemen user/device, API untuk dashboard dan AI pipeline. Isu: struktur topic MQTT, format payload JSON, keamanan koneksi, offline buffer.

### 7. AI/ML Pipeline
Hybrid CNN-LSTM. CNN: ekstraksi fitur lokal sinyal. LSTM: pola temporal DJJ. Input: raw signal 1D atau spectrogram. Output: estimasi DJJ, kualitas sinyal, status risiko (normal/waspada/konsultasi). Dataset: PhysioNet + data primer. Ground truth: CTG/Doppler/toco + label nakes.

### 8. Dashboard Nakes
Overview (total pasien, distribusi risiko), Active Monitoring (tabel real-time + filter risiko/gestasi), Clinical Alerts (GPS pasien, tren DJJ 5 menit, Call Patient/Ambulance), Staff Schedules, System Analytics (KPI, export report), Settings (threshold FHR, eskalasi 3-tier).

---

## Roadmap 6 Tahap

| Tahap | Target Utama |
|---|---|
| 1. PoC Sensor & Power | ESP32 baca piezo/FSR/MAX30102, serial monitor, MQTT sederhana |
| 2. Akuisisi & Dashboard Dasar | Data masuk cloud, dashboard real-time, simpan riwayat |
| 3. Preprocessing & Deteksi | Filter sinyal, estimasi FHR, signal quality index |
| 4. Model AI Awal | CNN-LSTM baseline, training dataset publik, klasifikasi normal/warning |
| 5. Validasi Klinis | Perbandingan dengan Doppler/CTG/toco, dataset primer |
| 6. Integrasi Wearable Final | PCB, casing, sabuk ergonomis, demo end-to-end |

---

## Konektivitas — Opsi Bertahap

| Tahap | Metode | Catatan |
|---|---|---|
| MVP mahasiswa | WiFi + MQTT via hotspot HP/lab | Paling sederhana |
| Prototipe lanjut | WiFi provisioning via app | Lebih user-friendly |
| Produk portabel | BLE ke smartphone sebagai gateway | Mirip smartwatch |

---

## Medical Claim Guardrail

### Frasa yang AMAN digunakan
- "indikasi awal"
- "skrining awal"
- "membantu pemantauan"
- "perlu validasi lanjutan"
- "tidak menggantikan pemeriksaan tenaga kesehatan"
- "risiko rendah / perlu pemantauan / segera konsultasi"

### Frasa yang DILARANG
- "mendiagnosis"
- "akurasi menyamai alat medis"
- "menggantikan CTG"
- "terbukti klinis" (kecuali didukung data validasi nyata)

### Output AI yang Aman
- Estimasi DJJ (bpm)
- Estimasi kualitas sinyal
- Status risiko: normal / waspada / konsultasi
- Rekomendasi: ulang pemasangan sensor, hubungi nakes
- Alert bila nilai melewati threshold

---

## Critical Open Questions (dari Proposal)

1. **Validasi Klinis**: Siapa pemberi label ground truth? Izin etik? Metrik evaluasi?
2. **Rangkaian Piezo**: Konfigurasi LM324, nilai R/C, bias ADC, frekuensi target, proteksi 3.3V?
3. **FSR sebagai Proksi Kontraksi**: Validasi terhadap toco klinis? Pengaruh kencang sabuk/gerakan?
4. **AI Input**: Raw 1D vs spectrogram? Window length? Sampling rate? Label target?
5. **Koneksi IoT**: WiFi provisioning vs BLE gateway vs hotspot?
6. **Keamanan Data**: Enkripsi, autentikasi, RBAC, audit log, kebijakan hapus data?
7. **Keselamatan Wearable**: Keamanan baterai, pemanasan, tekanan abdomen, material kontak kulit?

---

## File Konteks Utama — Wajib Baca

Sebelum mengubah project, baca file berikut jika relevan:

| File | Isi |
|---|---|
| `fetal_guard_context_ai.md` | Master context 1200+ baris dari proposal PKM-KC |
| `AGENTS.md` | Rules dan workflow agent |
| `docs/ai/CONTEXT.md` | File ini — ringkasan operasional |
| `FETALGUARD_Technical_Roadmap.md` | Roadmap teknis detail |
| `package.json` | Dependencies dan scripts |
| `README.md` | Overview project |

---

## Preferred Workflow With AI Agent

1. **Grill** requirement (skill: `fetal-guard-grill`).
2. **Produce PRD** (skill: `fetal-guard-prd`, simpan di `docs/prd/`).
3. **Split** into local issues (skill: `fetal-guard-issue-slicer`, simpan di `docs/issues/`).
4. **Implement** one issue at a time (skill: `fetal-guard-tdd`).
5. **Debug** jika ada error (skill: `fetal-guard-debug`).
6. **Review** sebelum commit (skill: `fetal-guard-review`).
7. **Update** documentation dan CONTEXT.md jika arsitektur berubah.