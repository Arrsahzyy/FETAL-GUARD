# Issue: [UI] Visualisasi Raw Data Sensor dari BLE

## Roadmap Stage
- Tahap 2: Akuisisi Data & Dashboard Dasar

## Goal
- Mem-parsing raw payload BLE (array data) menjadi nilai yang bisa digambarkan.
- Menggambarkan data piezo, FSR, dan SpO2/HR dalam bentuk grafik dinamis secara real-time di UI mobile app.

## Scope
- Boleh menyentuh: Source code `mobile-app/`.
- Tidak boleh menyentuh: ESP32.

## Files Likely Affected
- `mobile-app/src/pages/Dashboard.tsx`
- `mobile-app/src/components/SignalChart.tsx`

## Depends On
- `0005-firmware-adc-batching.md`
- `0006-mobile-app-ble-client.md`

## Acceptance Criteria
- [ ] Payload byte array berhasil di-parsing menjadi integer/float.
- [ ] Terdapat 3 grafik utama (Piezo, Kontraksi/FSR, SpO2).
- [ ] Grafik ter-update dengan *frame rate* mulus (memanfaatkan *Canvas* atau library charting berperforma tinggi seperti `uPlot` atau `Chart.js` / `Recharts`).
- [ ] Tidak ada delay penumpukan data yang membuat aplikasi *freeze*.

## Test / Verification
```bash
cd mobile-app
npm run dev
# Bisa di-mock terlebih dahulu dengan setInterval jika ESP32 sedang offline.
```

## Notes
- Wajib menggunakan library charting yang kuat untuk data time-series berfrekuensi tinggi. *React-chartjs-2* bisa menjadi awal yang baik.
