# AGENTS.md — Fetal Guard PKM-KC

## Project Overview

Fetal Guard adalah prototype PKM-KC (Karsa Cipta) berupa sabuk pintar wearable untuk skrining awal risiko feto-maternal pada ibu hamil. Sistem memantau DJJ/FHR, indikator kontraksi rahim, dan parameter vital ibu secara non-invasif.

Project ini **bukan** alat diagnosis medis dan **tidak menggantikan** CTG, tocotransducer, Doppler, USG, dokter, bidan, atau fasilitas rumah sakit.

## Technology Stack

### Hardware
ESP32 DevKit V1, 4x piezoelektrik, FSR408, MAX30102, LM324 (pre-amp), Li-Po 3.7V 2000mAh, TP4056, MT3608.

### Software
- **Frontend/Dashboard**: Web-based (React/Vite)
- **Mobile App**: Capacitor/Android
- **Backend/API**: Node.js + MQTT broker
- **AI/ML**: Python, CNN-LSTM (TensorFlow/PyTorch)
- **Embedded**: Arduino/PlatformIO C++

## Required Context Files

Sebelum mengedit file, agent WAJIB membaca file berikut jika relevan dengan subsystem yang akan diubah:

| File | Kapan Dibaca |
|---|---|
| `docs/ai/CONTEXT.md` | Selalu — setiap sesi baru |
| `fetal_guard_context_ai.md` | Saat butuh detail proposal (sensor, parameter klinis, arsitektur lengkap) |
| `FETALGUARD_Technical_Roadmap.md` | Saat merencanakan fitur baru atau mengubah arsitektur |
| `package.json` | Saat mengubah dependencies atau scripts |

## Agent Workflow

Sebelum mengedit file, agent wajib:

1. Membaca konteks project (`docs/ai/CONTEXT.md`).
2. Menjelaskan ulang permintaan user.
3. Mengidentifikasi subsystem terdampak.
4. Bertanya jika requirement belum jelas.
5. Membuat implementation plan.
6. Menunggu approval untuk perubahan besar.

## Roadmap Awareness

Project mengikuti 6 tahap roadmap:

1. PoC Sensor & Power
2. Akuisisi Data & Dashboard Dasar
3. Preprocessing & Deteksi Sinyal
4. Model AI Awal
5. Validasi dengan Referensi Klinis
6. Integrasi Wearable Final

Agent harus mengetahui tahap aktif saat ini dan tidak mengerjakan fitur di luar tahap tanpa approval.

## Subsystem

- Embedded/ESP32 (sensor, ADC, preprocessing, BLE/WiFi)
- Analog front-end (LM324, filter, proteksi ADC)
- Power management (baterai, charger, regulator)
- Wearable/belt design (sabuk, sensor placement, casing)
- Mobile/Android/Capacitor
- API/backend (MQTT, database, REST API)
- Dashboard/frontend (monitoring nakes, analytics)
- AI/ML pipeline (CNN-LSTM, preprocessing sinyal, dataset)
- BLE/WiFi/cloud connectivity
- Dokumentasi dan proposal
- Validasi dan testing

## Safety Rules

- Jangan membuat klaim medis berlebihan. Gunakan "indikasi awal", "skrining awal", "membantu pemantauan".
- Jangan mengarang akurasi, sensitivitas, spesifisitas, atau hasil validasi.
- Jangan mengubah threshold klinis (FHR 110-160 bpm) tanpa approval eksplisit.
- Jangan menghapus sensor dari arsitektur tanpa diskusi.
- Jangan menampilkan API key, token, password, atau isi `.env`.
- Jangan menjalankan command destruktif seperti `git reset --hard` tanpa izin.
- Jangan install dependency baru tanpa menjelaskan alasannya.

## Development Commands

Gunakan command berikut jika relevan:

```bash
# Frontend / Dashboard
npm install
npm run dev
npm run build
npm run lint

# Embedded (jika menggunakan PlatformIO)
pio run
pio run --target upload
pio device monitor
```
