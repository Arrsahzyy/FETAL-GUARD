---
name: fetal-guard-prd
description: Use this to turn a clarified Fetal Guard feature idea into a PRD stored in docs/prd.
---

# Fetal Guard PRD Skill

Ubah requirement yang sudah jelas menjadi PRD praktis dan mendetail.

## Rules

- Tulis dalam bahasa Indonesia.
- Klaim medis harus konservatif — gunakan "skrining awal", "indikasi awal", "membantu pemantauan".
- Jika fitur menyentuh interpretasi kesehatan (FHR, kontraksi, vital ibu), wajib sebutkan kebutuhan validasi terhadap alat medis referensi (CTG/Doppler/toco).
- Jika fitur melibatkan sensor piezoelektrik, cantumkan channel yang digunakan dan SNR target.
- Jika fitur melibatkan koneksi, sebutkan protokol (BLE/WiFi/MQTT) dan format payload.
- Referensikan `fetal_guard_context_ai.md` section yang relevan.
- Simpan PRD di `docs/prd/`.
- Jangan implementasi kode sebelum diminta.

## PRD Structure

````md
# PRD: <Nama Fitur>

## 1. Latar Belakang
- [Konteks masalah yang ingin diselesaikan]
- [Referensi ke section mana di `fetal_guard_context_ai.md` yang relevan]

## 2. Tujuan
- [Tujuan fungsional fitur, misalnya "Mengirimkan data FHR ke cloud setiap 5 detik via MQTT"]

## 3. Non-Tujuan
- Fitur ini BUKAN untuk diagnosis definitif.
- Fitur ini BUKAN pengganti CTG/Doppler/toco.
- [Sebutkan secara eksplisit batasan lain yang spesifik untuk fitur ini]

## 4. Pengguna
- Pasien/ibu hamil
- Tenaga kesehatan (nakes)
- Tim pengembang/admin

## 5. Tahap Roadmap
- [Fitur ini termasuk di Tahap berapa? (1-6)]

## 6. Requirement Fungsional
- [Rincian frekuensi sampling sensor, format UUID BLE, struktur MQTT topic, payload JSON]
- [Interaksi UI di Mobile App atau Dashboard]
- [Input/output spesifik: contoh "ADC channel 0-3 untuk 4 piezo, sampling 500 Hz"]

## 7. Requirement Non-Fungsional
- [Latency maksimal end-to-end (sensor → dashboard)]
- [Target uptime, efisiensi baterai ESP32]
- [Batas memori flash/RAM ESP32 jika relevan]

## 8. Parameter Klinis (jika relevan)
- [Range normal FHR: 110-160 bpm]
- [Threshold bradikardia: < 110 bpm, takikardia: > 160 bpm]
- [Output AI yang aman: estimasi DJJ, kualitas sinyal, status risiko]
- [Jika tidak terkait parameter klinis, tulis "Tidak berlaku"]

## 9. Power & Safety (jika relevan)
- [Dampak pada konsumsi daya baterai]
- [Keamanan baterai, isolasi listrik, pemanasan casing]
- [Tekanan sensor pada abdomen]
- [Jika tidak terkait, tulis "Tidak berlaku"]

## 10. Data yang Dibutuhkan
- [Daftar endpoint API, variabel global, skema tabel database, MQTT topic]

## 11. Alur Sistem
- [Flowchart tekstual end-to-end: User → Sensor → LM324 → ESP32 → BLE/WiFi → Cloud → AI → App/Dashboard → Alert]

## 12. Risiko dan Batasan
- [Potensi delay, data loss, noise sensor, memori limit ESP32]
- [Risiko klaim medis yang terlalu kuat di UI]
- [Risiko safety: baterai, panas, tekanan]

## 13. Validasi
- [Cara memastikan fitur ini valid secara empiris]
- [Eksperimen: dummy data, simulasi mekanik, perbandingan dengan alat medis]
- [Metrik: MAE bpm, SNR, packet loss, confusion matrix]

## 14. Acceptance Criteria
- [ ] [Kriteria terkait hardware/sensor]
- [ ] [Kriteria terkait koneksi BLE/WiFi/MQTT]
- [ ] [Kriteria terkait UI/Dashboard]
- [ ] [Kriteria terkait AI output (jika relevan)]
- [ ] [Kriteria tidak melanggar "Medical Claim Guardrail"]
- [ ] Build sukses (`npm run build` atau `pio run`)
````

Setelah PRD selesai, rekomendasikan menjalankan `fetal-guard-issue-slicer`.
