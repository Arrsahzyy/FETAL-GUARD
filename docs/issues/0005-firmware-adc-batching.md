# Issue: [HW] Sampling ADC Sensor dan Batching via BLE

## Roadmap Stage
- Tahap 2: Akuisisi Data & Dashboard Dasar

## Goal
- Membaca 4 ADC channel (Piezo), 1 ADC channel (FSR), dan I2C (MAX30102) secara simultan menggunakan *timer interrupt* atau non-blocking loop.
- Mengemas data (batching) untuk dikirim melalui notifikasi BLE setiap sekian milidetik untuk menghindari bottleneck BLE.

## Scope
- Boleh menyentuh: Firmware C++ ESP32 (`src/sensor_reader.cpp`, `src/main.cpp`).
- Tidak boleh menyentuh: Struktur dasar koneksi BLE (sudah di Issue 0004).

## Files Likely Affected
- `firmware/src/main.cpp`
- `firmware/src/sensor_reader.cpp`
- `firmware/src/sensor_reader.h`

## Depends On
- `0002-sensor-piezo-lm324.md`
- `0003-sensor-fsr-max30102.md`
- `0004-firmware-ble-server.md`

## Acceptance Criteria
- [ ] ESP32 dapat membaca data dari seluruh sensor tanpa lag parah (loop freq > 100 Hz).
- [ ] ESP32 berhasil mengirimkan data buffer secara stabil via BLE `notify()`.
- [ ] Noise yang dihasilkan radio BLE terhadap ADC (spike internal) diminimalisir. Jika tak bisa diatasi, pertimbangkan transisi ke ADS1115 (luar scope issue ini, buat issue baru jika perlu).

## Test / Verification
```bash
pio run -t upload
pio device monitor
# Cek throughput data di nRF Connect
```

## Notes
- Jangan gunakan `delay()` dalam loop utama. Gunakan `millis()` atau hardware timer.
- Pertimbangkan ukuran buffer. Misal: kumpulkan 10 sample tiap piezo sebelum di-`notify()`.
