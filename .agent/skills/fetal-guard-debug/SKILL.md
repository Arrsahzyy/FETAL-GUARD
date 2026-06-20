---
name: fetal-guard-debug
description: Use this to debug Fetal Guard build errors, runtime errors, BLE connection issues, API errors, Android/Capacitor errors, sensor data flow problems, or dashboard bugs.
---

# Fetal Guard Debug Skill

Gunakan alur diagnosis sistematis, bukan tebak-tebakan.

## Debugging Loop

1. Reproduce issue — pastikan bug bisa diulang.
2. Catat error message persis — copy-paste, bukan parafrase.
3. Minimalkan kasus gagal — isolasi ke satu subsystem.
4. Buat hipotesis berdasarkan layer (lihat tabel di bawah).
5. Tambahkan log jika perlu.
6. Fix penyebab paling kecil dan paling spesifik.
7. Jalankan regression check — pastikan fix tidak merusak hal lain.
8. Dokumentasikan root cause.

## Rules

- Jangan menebak tanpa log — selalu minta bukti error.
- Minta terminal output jika dibutuhkan.
- Jangan ubah banyak modul sekaligus — isolasi fix.
- Jika bug memengaruhi akurasi pembacaan sensor kesehatan, prioritaskan fix.
- Jangan mengubah threshold klinis saat debugging tanpa approval.

## Diagnostic Tools — Per Layer

| Layer | Tool | Cara Pakai |
|---|---|---|
| **Sensor/Hardware** | Multimeter, oscilloscope | Cek tegangan, sinyal analog |
| **ESP32 Firmware** | Serial Monitor / `pio device monitor` | Cek output `Serial.println()` |
| **Analog Front-End** | Serial Plotter / oscilloscope | Cek bentuk gelombang setelah LM324 |
| **BLE** | nRF Connect (Android) | Scan UUID, cek service/characteristic |
| **WiFi/MQTT** | MQTT Explorer / mosquitto_sub | Cek topic, payload, koneksi |
| **Mobile App** | Android Logcat (`adb logcat`) | Cek crash, exception, log |
| **API/Backend** | Postman / curl + server logs | Cek endpoint, response, error |
| **Dashboard/Frontend** | Chrome DevTools (Console + Network) | Cek JS error, API calls, WebSocket |
| **AI/ML** | Python debugger / notebook | Cek shape, NaN, training loss |
| **Power** | Multimeter + thermal camera | Cek voltase, arus, suhu |

## Common Fetal Guard Failure Modes

| Gejala | Kemungkinan Penyebab |
|---|---|
| ADC membaca 4095 terus | Tegangan input > 3.3V, proteksi ADC tidak ada |
| ADC membaca 0 terus | Sensor disconnected, kabel putus, pin salah |
| Data BLE tidak sampai | UUID mismatch, MTU terlalu kecil, jarak terlalu jauh |
| MQTT timeout | Broker unreachable, WiFi disconnect, payload terlalu besar |
| Dashboard data null | API error, CORS issue, WebSocket disconnect |
| FHR estimasi tidak masuk akal | Noise terlalu tinggi, filter salah, sampling rate terlalu rendah |
| Baterai cepat habis | WiFi selalu aktif, sleep mode tidak digunakan |
| ESP32 restart sendiri | Watchdog timeout, stack overflow, brownout voltage |

## Required Output

````md
## Gejala
- [Apa yang terjadi vs Apa yang seharusnya terjadi]
- [Subsystem mana yang terdampak]

## Bukti Error
- [Copy-paste dari Serial Monitor / Android Logcat / Network Tab / MQTT Explorer]
- [Screenshot jika relevan]

## Hipotesis (per Layer)
1. [Layer Fisik/Sensor: misal sensor lepas, baterai lemah, tegangan salah]
2. [Layer Komunikasi: misal packet BLE terpotong, MQTT topic salah, WiFi disconnect]
3. [Layer Logic/Software: misal salah parsing JSON, index out of bounds, NaN in model]

## Langkah Diagnosis
- [Langkah 1: Tool yang dipakai dan apa yang dicek]
- [Langkah 2: Hasil observasi]
- [Langkah 3: Narrowing down ke penyebab spesifik]

## Perubahan yang Dilakukan
- [File mana yang diubah dan perubahan apa]

## Verifikasi
- [Command yang dijalankan untuk membuktikan fix: `pio run`, `npm run build`, dll]
- [Hasil: "Serial Monitor sekarang menampilkan data piezo yang valid"]

## Root Cause Sementara / Final
- [Penjelasan teknis kenapa error itu terjadi]
- [Cara mencegahnya di masa depan]

## Impact Assessment
- [Apakah bug ini memengaruhi akurasi pembacaan sensor kesehatan?]
- [Apakah ada risiko keselamatan (baterai, panas, tekanan)?]
````
