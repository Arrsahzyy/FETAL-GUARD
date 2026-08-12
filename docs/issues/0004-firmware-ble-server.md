# Issue: [BLE] Setup GATT Server BLE di ESP32

## Roadmap Stage
- Tahap 2: Akuisisi Data & Dashboard Dasar

## Goal
- Menginisialisasi ESP32 sebagai BLE Peripheral Server dengan nama "FETAL-GUARD".
- Membuat custom Service dan setidaknya 3 Characteristics (Piezo/FSR array, SpO2 array, Battery status).

## Scope
- Boleh menyentuh: Firmware C++ ESP32 (`src/ble_manager.cpp`, `src/main.cpp`).
- Tidak boleh menyentuh: Konfigurasi Wi-Fi/MQTT (dihapus/dinonaktifkan).

## Files Likely Affected
- `firmware/src/main.cpp`
- `firmware/src/ble_manager.cpp`
- `firmware/src/ble_manager.h`

## Depends On
- Tidak ada (bisa dikembangkan secara paralel dengan hardware asal ada board ESP32).

## Acceptance Criteria
- [ ] Kode C++ berhasil dikompilasi.
- [ ] ESP32 memancarkan BLE *advertising* "FETAL-GUARD".
- [ ] Dapat dikoneksikan via aplikasi nRF Connect dari smartphone.
- [ ] UUID service dan UUID characteristics terbaca dengan benar (memiliki property `NOTIFY` atau `READ`).

## Test / Verification
```bash
# Build dan upload
pio run -t upload

# Pengecekan dengan nRF Connect App di Android/iOS
```

## Notes
- Gunakan library standar `BLEDevice.h` bawaan esp32 board package.
- Rencanakan format pengiriman (misalnya `uint8_t` array) untuk karakteristik agar ukurannya pas dengan MTU BLE (biasanya 20-512 bytes).
