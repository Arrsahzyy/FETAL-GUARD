---
name: fetal-guard-grill
description: Use this before changing Fetal Guard requirements, architecture, BLE/WiFi/cloud flow, sensor flow, dashboard, AI/ML roadmap, or medical-risk wording.
---

# Fetal Guard Grill Skill

Sebelum menulis kode atau mengubah file, lakukan sesi klarifikasi mendalam.

## Context yang Wajib Dibaca Dulu

- `docs/ai/CONTEXT.md` — hardware stack, parameter klinis, roadmap
- `fetal_guard_context_ai.md` — detail proposal jika diperlukan

## Required Behavior

1. Jelaskan ulang permintaan user dalam bahasa Indonesia sederhana.
2. Identifikasi subsystem terdampak (lihat daftar lengkap di bawah).
3. Pisahkan: fakta, asumsi, pertanyaan terbuka, risiko.
4. Jika fitur terkait parameter klinis (FHR 110-160 bpm, kontraksi, vital ibu), sebutkan batasan klaim secara eksplisit.
5. Referensikan tahap roadmap yang relevan (Tahap 1-6).
6. Akhiri dengan rekomendasi langkah berikutnya.

## Daftar Subsystem Lengkap

- **Embedded/ESP32**: ADC, I2C, preprocessing, BLE/WiFi, firmware C++
- **Analog Front-End**: LM324 pre-amp, filter analog, proteksi ADC 3.3V, bias tengah
- **Power Management**: Li-Po, TP4056, MT3608, estimasi daya, switching noise
- **Wearable/Belt**: sensor placement, kenyamanan, casing, kabel shielded
- **BLE/Mobile App**: UUID, parser data, UI pasien, BLE central
- **WiFi/Cloud/MQTT**: topic structure, payload JSON, offline buffer, keamanan
- **API/Backend**: database, REST API, sesi, manajemen device
- **Dashboard/Frontend**: chart real-time, tabel monitoring, clinical alerts, analytics
- **AI/ML Pipeline**: CNN-LSTM, preprocessing sinyal, dataset, ground truth, inference
- **Documentation/Proposal**: PRD, roadmap, laporan PKM-KC
- **Validation/Testing**: SNR, MAE bpm, korelasi CTG/toco, usability

## Output Format

````md
## Pemahaman Awal
- [Jelaskan fitur dari sudut pandang alur data end-to-end: Sensor → LM324 → ESP32 ADC → BLE/WiFi → Cloud → AI → App/Dashboard]
- [Jelaskan batasan utama fitur ini secara fungsional]

## Tahap Roadmap Terkait
- [Tahap 1/2/3/4/5/6 — sebutkan target tahap tersebut]

## Subsystem Terdampak
- **Embedded/ESP32**: [Dampak pada firmware, sampling rate, pin mapping]
- **Analog Front-End**: [Dampak pada rangkaian LM324, filter, proteksi ADC]
- **Power Management**: [Dampak pada konsumsi daya, charging, thermal]
- **Wearable/Belt**: [Dampak pada posisi sensor, kenyamanan, kabel]
- **BLE/Mobile App**: [Dampak UUID, parser data, UI pasien]
- **Cloud/API**: [Dampak skema database, format payload JSON, MQTT topic]
- **Dashboard**: [Dampak chart, indikator nakes, clinical alerts]
- **AI/ML**: [Dampak pada feature extraction, model, dataset, inference]

## Parameter Klinis yang Terpengaruh
- [Jika fitur menyentuh FHR, kontraksi, atau vital ibu — sebutkan range normal dan batasan klaim]
- [Jika tidak terkait parameter klinis, tulis "Tidak ada"]

## Fakta yang Sudah Ada
- [Sebutkan teknologi/modul/hasil yang sudah dikonfirmasi berjalan]

## Asumsi
- [Sebutkan hal yang belum diverifikasi, misalnya "Diasumsikan sampling rate 500 Hz cukup untuk menangkap vibrasi DJJ"]

## Pertanyaan Klarifikasi
1. [Pertanyaan terkait hardware/sensor/rangkaian]
2. [Pertanyaan terkait limitasi mobile/cloud/koneksi]
3. [Pertanyaan terkait batasan medis/klaim/validasi]

## Risiko
- [Risiko hardware: sensor disconnected, ADC overflow, switching noise MT3608]
- [Risiko komunikasi: packet loss BLE/MQTT, latency, offline sync]
- [Risiko AI: overfitting, data leakage, ground truth tidak tersedia]
- [Risiko medis: "fitur ini berisiko terlihat seperti alat diagnosis" — sebutkan guardrail]

## Rekomendasi Langkah Berikutnya
- [Saran langkah logis berikutnya, termasuk skill mana yang harus dijalankan selanjutnya]
````