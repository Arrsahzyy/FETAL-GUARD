# Mobile App — Audit & Rencana Uji End-to-End (Hardware ↔ Apps ↔ Azure)

**Tanggal:** 2026-09-06 (diperbarui 2026-09-07)
**Cakupan:** aplikasi Capacitor Android (`com.fetalguard.app`), jalur BLE ESP32 → app → backend Azure → dashboard nakes
**Status backend/frontend:** staging live di `https://pkmkcfetalguard.app` / `https://api.pkmkcfetalguard.app`

> **Untuk eksekusi Fase C–E dengan ESP32-S3 asli + data sintetis, ikuti
> `docs/ops/esp32-synthetic-e2e-runbook.md`** — runbook itu menggabungkan
> Fase C–E + bench-connectivity-test.md jadi satu langkah-per-langkah yang
> memakai panel admin "Perangkat" (tanpa curl / tanpa `provision_devices.py`).
>
> **Sudah selesai sejak dokumen ini:** M1 (`build-android-staging.ps1`),
> M3 (provisioning perangkat kini lewat UI admin), M4 (`neverForLocation` +
> `androidNeverForLocation: true` → scan BLE tanpa prompt lokasi di Android 12+),
> M5 (izin notifikasi diminta sekali otomatis di `PatientNotificationBridge`).

---

## 1. Hasil audit kode

### 1.1 Yang sudah solid

| Area | Berkas | Catatan |
|---|---|---|
| BLE client | `src/hooks/useBluetooth.js` | scan (name prefix `FETAL-GUARD`), connect dengan generation guard, reconnect exponential-backoff (5×, cap 15 s), frame buffer newline-delimited JSON, transport queue 512 paket dengan overflow accounting, MTU-aware: kirim `T<ms>` (time sync) + `V2:<chunkBytes>` ke device saat connect |
| Web BLE fallback | `src/services/webBluetoothClient.js` | untuk uji di Chrome desktop tanpa APK |
| Antrian offline | `src/services/patientTelemetryQueue.js` | IndexedDB v2 + fallback memory, scoped `userId\|sessionId\|deviceId`, status pending/failed, retry `nextAttemptAt`/`attempts`, requeue failed |
| Verifikasi gateway | `src/context/PatientDeviceContext.jsx` | tolak `device_uid` ≠ device yang di-pair; boot_id tracking + retired boot-ids; sequence dedup (`seenSequences`), deteksi gap (`missingSequences`), reorder window — jaminan exactly-once di sisi gateway |
| Device claiming | `PatientDeviceContext.claimDevice()` → `api.devices.claim()` | pasien pair belt pakai claim code; endpoint `POST /devices/claim` sudah live di backend |
| Izin Android 12+ | manifest merge dari `@capacitor-community/bluetooth-le` | `BLUETOOTH_SCAN` + `BLUETOOTH_CONNECT` (tanpa maxSdk) + legacy `BLUETOOTH`/`BLUETOOTH_ADMIN` (maxSdk 30) + feature `bluetooth_le` — **APK final aman untuk Android 12–14** |
| Kontrak telemetri | `validateTelemetryEnvelope()` + `schemas/sensor_data.py` | app & backend sama-sama validasi schema v1/v2, `packet_signature` 64-hex HMAC diteruskan apa adanya (gateway tidak pernah verifikasi — hanya backend pegang kunci) |
| Test suite | `npm run test:frontend` | 62 test lulus (termasuk `useBluetooth.test.js`, `patientTelemetryQueue.test.js`, `webBluetoothClient.test.js`, `realtimeEventPoller.test.js`) |

### 1.2 Kualitas keseluruhan

Jalur BLE→gateway→antrian **direkayasa dengan baik** — exactly-once, fail-closed pada identity mismatch, offline durable queue, reconnect. Ini bukan prototipe kasar.

### 1.3 Gap & blocker sebelum uji on-device melawan Azure

| # | Gap | Dampak | Fix |
|---|-----|--------|-----|
| M1 | ~~Tidak ada build APK yang menunjuk ke Azure~~ — **SUDAH DIPERBAIKI**. `scripts/build-android-local.ps1` hanya menerima URL RFC1918; belum ada varian staging. Klarifikasi: `evaluateApiRuntimePolicy` **hanya memblokir `http://`** non-loopback — URL `https://` publik **lolos** di native production. | — | ✅ `scripts/build-android-staging.ps1` + `npm run build:android:staging` dibuat: default `VITE_API_BASE_URL=https://api.pkmkcfetalguard.app`, mode Vite production, tanpa flag cleartext/insecure. Masih `assembleDebug` (unsigned, cukup untuk sideload demo). |
| M2 | Firmware `FG_DEVICE_PACKET_SECRET = ""` (kosong) | Di production backend (`REQUIRE_DEVICE_PACKET_SIGNATURE=true`, sudah live di staging) **paket tanpa tanda tangan ditolak**. | Sebelum flash: `POST /devices/{id}/signing-key` (admin) → salin hex ke `fetalguard.ino` → flash ulang. |
| M3 | `FG_DEVICE_UID = "FETAL-GUARD-001"` hardcoded | Harus sama persis dengan `device_uid` yang didaftarkan admin, dan device harus di-*claim* pasien (atau di-assign admin) sebelum ingestion diterima. | Admin `POST /devices` dengan `device_uid=FETAL-GUARD-001` + set claim code; pasien claim di app. |
| M4 | Scan BLE meminta izin **lokasi** (`androidNeverForLocation: false`) | Prompt izin ekstra di HP Android 12+; kalau ditolak, scan gagal. | Opsional: set `androidNeverForLocation: true` + tambahkan flag `neverForLocation` ke `BLUETOOTH_SCAN` di manifest app. Untuk demo, cukup pandu tester memberi izin. |
| M5 | `POST_NOTIFICATIONS` diminta tapi belum tentu di-*request* runtime di Android 13+ | Alert nakes/pasien tidak muncul sebagai notifikasi OS. | Cek apakah ada `requestPermissions` untuk notifikasi; kalau tidak, tambah (di luar cakupan demo minimal). |
| M6 | Belum ada APK ter-*sign* untuk distribusi (hanya `app-debug.apk`) | Cukup untuk demo internal (sideload). Tidak untuk Play Store. | Tunda sampai pasca-lomba. |

---

## 2. Kontrak referensi (samakan hardware & app)

### 2.1 BLE

| Item | Nilai |
|---|---|
| Nama advertise | diawali `FETAL-GUARD` (app filter `namePrefix`) |
| Service UUID | `0000ffe0-0000-1000-8000-00805f9b34fb` |
| Characteristic UUID (notify + write) | `0000ffe1-0000-1000-8000-00805f9b34fb` |
| Framing | JSON per baris, dipisah `\n`; chunk 20–180 byte (MTU−3) |
| Command dari app → device | `T<unix_ms>` (time sync), `V2:<maxChunkBytes>` (minta telemetry v2) |

### 2.2 Envelope telemetri (device → app → backend)

```json
{
  "schema_version": 2,
  "device_uid": "FETAL-GUARD-001",
  "boot_id": "boot-<hex, >=8 char>",
  "sequence_number": 0,
  "captured_at": "2026-09-06T10:00:00.000Z",
  "packet_signature": "<64 hex = HMAC-SHA256, wajib di production>",
  "sample_rates_hz": { "p": 200, "fsr": 10, "hr_ir": 100, "hr_red": 100 },
  "channel_layout": { "p": 4 },
  "channels": {
    "p":      [/* int 0..4095, interleaved 4-kanal, kelipatan 4 */],
    "fsr":    [/* int 0..4095 */],
    "hr_ir":  [/* int 0..262143, panjang == hr_red */],
    "hr_red": [/* int 0..262143 */]
  },
  "telemetry": { "fhr": 142.0, "motherHR": 82.0, "signalQuality": 76.0, "contractionLevel": 28.0, "battery": 90, "charging": false }
}
```

- Backend **menolak** `summary`/`is_simulated` dari device (`enforce_production_ingestion_policy`); `telemetry.*` di-*ignore* untuk nilai klinis — FHR/MHR/SQI diturunkan server dari `channels`.
- `payload.t` (ms) di dalam chunk harus cocok dengan `captured_at` dalam ±5 detik.
- Tanda tangan menandatangani: `FGSIG1|uid|boot_id|sequence|captured_at_ms|schema|sha256(channels)` dengan `FG_DEVICE_PACKET_SECRET`.
- Golden fixture: `contracts/telemetry/v2/golden-esp32-window.json`.

---

## 3. Rencana uji E2E — bertahap

### Fase A — Siapkan artefak (tanpa hardware)

- [x] **A1** `scripts/build-android-staging.ps1` + `npm run build:android:staging` dibuat (fix M1). Butuh Android Studio JBR terinstall untuk dijalankan.
- [ ] **A2** `npm run test:frontend` hijau (regresi). ✅ sudah (62 pass).
- [ ] **A3** Admin daftarkan device di staging: `POST /devices` `{device_uid:"FETAL-GUARD-001"}` → set claim code → `POST /devices/{id}/signing-key` → simpan hex.
- [ ] **A4** `npm run simulate:belt -- --api https://api.pkmkcfetalguard.app --device FETAL-GUARD-001 --secret <hex>` → verifikasi: chunk masuk, `SessionSensorSummary.derivation_status` berubah, muncul di dashboard nakes. *(Ini menguji seluruh pipa backend tanpa app & tanpa hardware.)*

### Fase B — App-only (tanpa hardware, pakai Web Bluetooth mock atau APK + simulator BLE)

- [ ] **B1** APK staging ter-*install* di HP. Buka → login pasien → **tidak ada** error "API tidak tersedia".
- [ ] **B2** Pasien claim device (`FETAL-GUARD-001` + claim code). Status → `paired`.
- [ ] **B3** *(opsional)* jalankan ESP32 dengan firmware yang hanya BLE-advertise + kirim golden window berulang (tanpa sensor nyata) → app terima, tampilkan angka, mulai sesi, chunk sampai backend.
- [ ] **B4** Uji offline: matikan WiFi/data HP saat sesi jalan → antrian `pending` naik → nyalakan lagi → antrian flush ke backend, tidak ada duplikat (cek `sequence_number` di DB unik).

### Fase C — Hardware ↔ App (bench, LAN dulu kalau perlu)

- [ ] **C1** Flash `fetalguard.ino` dengan `FG_DEVICE_UID` + `FG_DEVICE_PACKET_SECRET` yang benar (fix M2/M3).
- [ ] **C2** ESP32 nyala → app scan → device `FETAL-GUARD-001` muncul dalam <10 s.
- [ ] **C3** Connect → app kirim `T…` + `V2:…` → device switch ke v2 → app terima frame v2 (`sensorPacketVersion` naik).
- [ ] **C4** Cek integritas: `transportDroppedPacketCount` & `sequenceDroppedPacketCount` ~0 pada sesi 5 menit diam; RSSI stabil; reconnect otomatis saat ESP32 di-*reset*.
- [ ] **C5** Uji identity mismatch: dekatkan device BLE lain bernama `FETAL-GUARD-XXX` → app tolak, `pairingError` identity mismatch.

### Fase D — Full chain: Hardware → App → Azure → Dashboard

- [ ] **D1** APK staging + ESP32 ter-provisioning + HP online.
- [ ] **D2** Pasien: connect device → **Mulai sesi monitoring**.
- [ ] **D3** Biarkan 3–5 menit dengan sensor menempel (fantom detak jantung / volunteer).
- [ ] **D4** Backend: chunk masuk (`POST /sessions/{id}/data` → 201), `packet_signature` diverifikasi (tidak ada 401/403), `sequence` unik.
- [ ] **D5** `SessionSensorSummary`: `derivation_status` = `derived` (kalau sinyal cukup) atau `insufficient_signal`; FHR/MHR/SQI terisi dari derivasi server.
- [ ] **D6** Kalau nilai di luar rentang rujukan + SQI cukup → `Notification` dibuat (`services/alerting.py`) → muncul di dashboard nakes + push realtime.
- [ ] **D7** Dashboard nakes (`https://pkmkcfetalguard.app`, login `mailani`): pasien "Adit" (atau pasien uji) → panel detail menampilkan sesi aktif + nilai + (kalau ada) tren.
- [ ] **D8** Pasien: **Tutup sesi** → `PATCH /sessions/{id}` status → `completed`; antrian flush habis; riwayat pasien menampilkan sesi.
- [ ] **D9** Export PDF dari dashboard nakes berisi sesi tadi.

### Fase E — Ketahanan

- [ ] **E1** App di-*background* saat sesi jalan → telemetri tetap masuk antrian (atau sesi pause bersih, tidak crash).
- [ ] **E2** HP low-battery / Doze mode → perilaku terdokumentasi.
- [ ] **E3** ESP32 kehilangan daya di tengah sesi → app deteksi disconnect, coba reconnect, sesi tetap `active` di backend sampai pasien menutup atau timeout.
- [ ] **E4** Dua HP mencoba claim device yang sama → yang kedua ditolak (`errorAlreadyPaired`).

---

## 4. Checklist ringkas untuk hari demo

| Prasyarat | Cek |
|---|---|
| APK staging ter-build & ter-install | ☐ |
| Device `FETAL-GUARD-001` terdaftar + signing key di firmware | ☐ |
| Firmware ter-flash dengan UID + secret benar | ☐ |
| Akun pasien demo + akun nakes demo siap | ☐ |
| HP: izin Bluetooth + Lokasi + Notifikasi diberikan | ☐ |
| WiFi/data HP stabil | ☐ |
| Fantom/volunteer untuk sinyal | ☐ |

**Jalur happy-path demo:** pasien buka app → connect belt → mulai sesi → (nakes di layar lain) lihat data masuk realtime → nakes tandai/aksi alert → pasien tutup sesi → export PDF.

---

## 5. Rekomendasi urutan kerja

1. **Fix M1** (`build-android-staging.ps1`) — tanpa ini tidak ada uji app↔Azure.
2. **Fase A** penuh — buktikan pipa backend + simulator, tanpa menunggu hardware.
3. **Fase B** — APK + login + claim, pakai simulator BLE.
4. **Fase C/D** begitu hardware + firmware siap (butuh M2/M3).
5. Fase E menjelang demo.
