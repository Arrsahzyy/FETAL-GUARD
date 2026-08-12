# Issue: [UI] Setup Capacitor App dan BLE Client

## Roadmap Stage
- Tahap 2: Akuisisi Data & Dashboard Dasar

## Goal
- Membuat kerangka project mobile app (Android) menggunakan Capacitor (misalnya dengan React/Vite/Ionic).
- Mengintegrasikan plugin Bluetooth Low Energy (misal `@capacitor-community/bluetooth-le`).
- Aplikasi dapat memindai (scan) device bernama "FETAL-GUARD", melakukan koneksi, dan meng-subscribe (notify) data yang masuk.

## Scope
- Boleh menyentuh: Source code di folder `mobile-app/` (jika belum ada, inisialisasi).
- Tidak boleh menyentuh: Firmware ESP32.

## Files Likely Affected
- `mobile-app/package.json`
- `mobile-app/src/services/BleService.ts`
- `mobile-app/src/pages/Home.tsx`

## Depends On
- `0004-firmware-ble-server.md` (Untuk pengujian end-to-end, minimal ESP32 sudah memancarkan nama BLE).

## Acceptance Criteria
- [ ] Project Capacitor/Android berhasil di-build tanpa error.
- [ ] Terdapat tombol UI untuk "Scan Device".
- [ ] Aplikasi bisa menemukan "FETAL-GUARD" dan menampilkan status "Connected".
- [ ] Data raw array byte/integer dari karakteristik BLE tercetak di `console.log` aplikasi.

## Test / Verification
```bash
cd mobile-app
npm install
npm run build
npx cap sync android
npx cap open android
# Lalu jalankan via Android Studio ke perangkat HP asli (Emulator tidak support BLE).
```

## Notes
- Referensi dokumentasi `@capacitor-community/bluetooth-le`.
- Membutuhkan izin *Location* dan *Bluetooth Connect* (Android 12+) di `AndroidManifest.xml`.
