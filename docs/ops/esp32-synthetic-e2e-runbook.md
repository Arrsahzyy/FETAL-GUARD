# Runbook — Uji End-to-End ESP32-S3 (Data Sintetis) → App → Azure → Dashboard

**Untuk:** membuktikan seluruh rantai FETAL-GUARD terintegrasi memakai **board
ESP32-S3 asli** yang menjalankan **firmware demo (gelombang sintetis)**, selagi
sensor fisik masih diproduksi.

**Yang diuji:** BLE transport, penautan perangkat, ingestion + tanda tangan
paket, derivasi vital di server, alerting, dan tampilan di aplikasi pasien +
dashboard nakes.
**Yang TIDAK diuji:** akuisisi sinyal. Angka yang dihasilkan bukan pengukuran
apa pun — jangan pernah disajikan sebagai data klinis.

Menggantikan bagian hardware dari `bench-connectivity-test.md` dan
`mobile-app-e2e-test-plan.md` Fase C–E. Backend/dashboard/pipa sudah terbukti
lewat `npm run simulate:belt` — kalau itu belum pernah kamu jalankan, lakukan
dulu (lihat `bench-connectivity-test.md` Tahap 0).

---

## 0. Prasyarat (verifikasi sekali)

| Item | Cara cek | Status |
|---|---|---|
| Android Studio JBR | `"C:\Program Files\Android\Android Studio\jbr\bin\java.exe" -version` → OpenJDK 21 | ✅ terverifikasi |
| Android SDK | `%LOCALAPPDATA%\Android\Sdk` ada `platform-tools`, `platforms`, `licenses` | ✅ terverifikasi |
| `android/local.properties` | berisi `sdk.dir=...` | ✅ terverifikasi |
| Arduino IDE 2.x | terpasang, + **esp32 board package** (Boards Manager → "esp32" by Espressif) | ☐ |
| ESP32-S3 dev board + kabel USB data | — | ☐ |
| HP Android 12+ dengan Bluetooth | — | ☐ |
| Login admin `admin@fetalguard.id` | — | ☐ |
| Login nakes (mis. `mailani@gmail.com`) | jika lupa: admin → Daftar nakes → **Reset password** | ☐ |

Board ESP32-S3 butuh library `MAX30105` **tidak** diperlukan untuk sketch demo —
demo tidak menyentuh sensor. Yang dipakai hanya library BLE + mbedtls bawaan core
esp32.

---

## 1. Buat pasien uji bench

Data sintetis akan masuk ke rekam pasien ini seolah nyata (`is_simulated: false`
memang disengaja supaya pipa produksi ikut teruji). Jadi **pakai pasien khusus,
bukan pasien nyata.**

1. Buka `https://pkmkcfetalguard.app` di browser → **Masuk sebagai Pasien** →
   daftar akun baru:
   - Email: `bench.test@pkmkc.local` (atau email apa pun yang belum dipakai)
   - Password: catat
2. Lengkapi profil onboarding (nama **"BENCH TEST — bukan pasien"**, usia,
   usia kehamilan, dll — isi seadanya).
3. Buka `https://pkmkcfetalguard.app/admin` → panel **Scope pasien-nakes** →
   assign "BENCH TEST" ke nakes uji (mis. `mailani@gmail.com`), peran **utama**.

---

## 2. Daftarkan perangkat `FETAL-GUARD-BENCH-02`

> Nama UID **harus diawali `FETAL-GUARD`** — aplikasi memindai BLE dengan filter
> `namePrefix "FETAL-GUARD"`, jadi perangkat bernama `FG-BENCH-02` tidak akan
> pernah muncul di hasil scan.

Di `https://pkmkcfetalguard.app/admin` → panel **Perangkat**:

1. **Daftarkan perangkat**
   - UID perangkat: `FETAL-GUARD-BENCH-02`
   - Nama tampilan: `Bench ESP32-S3 demo`
   - Tautkan ke pasien: **BENCH TEST**
   - Status awal: **Aktif**
   - klik **Daftarkan perangkat**
2. Pada baris `FETAL-GUARD-BENCH-02` → **Terbitkan claim code** → catat kode
   (mis. `AB3F-9KQ2`). Ini untuk aplikasi pasien.
3. Baris yang sama → **Rotasi signing key** → konfirmasi → catat kunci hex
   64 karakter. Ini untuk firmware. **Ditampilkan sekali.**

---

## 3. Flash firmware demo ke ESP32-S3

1. Buka `fetalguard-demo/fetalguard-demo.ino` di Arduino IDE.
2. Isi dua konstanta (baris ~44):
   ```cpp
   const char *FG_DEVICE_UID           = "FETAL-GUARD-BENCH-02";
   const char *FG_DEVICE_PACKET_SECRET = "<kunci hex dari langkah 2.3>";
   ```
3. Tools →
   - Board: **ESP32S3 Dev Module**
   - Port: port COM board (kalau ada dua, coba yang muncul saat board dicolok)
   - Sisanya biarkan default.
4. **Upload** (→). Selesai upload, buka **Serial Monitor @ 115200**.
   - Kalau Serial Monitor kosong: Tools → **USB CDC On Boot: Enabled**, upload
     ulang (beberapa devkit S3 pakai USB native, bukan chip UART terpisah).
5. Yang harus muncul:
   ```
   ==================================================
    FETAL-GUARD DEMO KONEKTIVITAS - TANPA SENSOR
    Gelombang sintetis. Bukan data pasien.
   ==================================================
   [i] Paket ditandatangani dengan kunci perangkat.
   [BLE] Advertising sebagai FETAL-GUARD-BENCH-02
   [BLE] Boot ID: boot-xxxxxxxx-xxxxxxxx
   ```
   Kalau muncul `[!] Kunci penandatanganan kosong` → `FG_DEVICE_PACKET_SECRET`
   belum terisi; backend staging akan menolak paketnya.

---

## 4. Build + pasang APK staging

Di root repo:

```powershell
npm run build:android:staging
```

Hasil: `artifacts\FETAL-GUARD-staging-debug.apk` (~5 MB). Script sudah
menetapkan `VITE_API_BASE_URL=https://api.pkmkcfetalguard.app` dan mode Vite
production (tanpa cleartext).

Pasang ke HP:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r artifacts\FETAL-GUARD-staging-debug.apk
```

atau salin APK ke HP dan buka (aktifkan "Install unknown apps" untuk file
manager). Buka aplikasi **FETAL-GUARD**.

---

## 5. Jalankan rantai lengkap

| # | Aksi | Yang diharapkan |
|---|---|---|
| 5.1 | Buka app → login pasien `bench.test@pkmkc.local` | Masuk ke Beranda. **Tidak ada** "Layanan tidak tersedia". |
| 5.2 | Beranda → area perangkat → **masukkan claim code** `AB3F-9KQ2` → kirim | Status → perangkat tertaut. |
| 5.3 | **Pindai perangkat** | `FETAL-GUARD-BENCH-02` muncul < 10 dtk, bertanda "terdaftar". *(Kalau HP minta izin — beri "Perangkat di sekitar". Bila scan kosong padahal ESP32 advertising: lihat §7.)* |
| 5.4 | **Hubungkan** | Serial: `[BLE] Gateway terhubung; menunggu sinkronisasi waktu.` → `[BLE] Waktu tersinkronisasi.` → `[BLE] Telemetry v2 aktif; fragment bytes: NNN` |
| 5.5 | **Mulai sesi monitoring** | Serial mulai mencetak `[TX] seq 1  bytes <bbbb>  fhr 140.0 bpm (sintetis)` tiap ~1 dtk (`bbbb` biasanya 6000–9000). App: sesi **aktif**, status data **Tersimpan** (bukan `awaiting_raw_channels` / `rejected`). |
| 5.6 | Admin → panel Perangkat → baris `FETAL-GUARD-BENCH-02` | Kolom **Terakhir terlihat** berubah jadi "baru saja" / beberapa detik lalu. |
| 5.7 | Login nakes di `https://pkmkcfetalguard.app` → pasien **BENCH TEST** | Panel detail: sesi aktif, DJJ ~140, nadi ibu ~82, kualitas sinyal terisi (setelah ~10 dtk data). |
| 5.8 | Tunggu ~90 dtk (drift firmware aktif: `DEMO_DRIFT_ENABLED`) | DJJ sintetis turun < 110 bpm → **alert** "Estimasi DJJ … di luar rentang rujukan (belum tervalidasi klinis)" muncul di dashboard nakes, dan notifikasi di HP pasien. Setelah cycle, DJJ balik ~140. |

Verifikasi di backend (opsional, kalau ada akses psql Cloud Shell):
```sql
SELECT sequence_number, schema_version, captured_at
FROM session_data_chunks
WHERE session_id = '<id sesi>' ORDER BY sequence_number DESC LIMIT 5;
-- sequence_number harus berurutan tanpa lompatan besar, tanpa duplikat
SELECT derivation_status, fhr_estimate_bpm, maternal_hr_bpm, signal_quality_index
FROM session_sensor_summaries WHERE session_id = '<id sesi>';
```

---

## 6. Uji ketahanan

| # | Aksi | Yang diharapkan |
|---|---|---|
| 6.1 | Tekan tombol **RESET** ESP32 di tengah sesi | Serial: advertising restart. App: `reconnecting` → reconnect otomatis < 15 dtk, sesi tetap jalan. Boot ID baru → sequence mulai dari 1 lagi; backend tidak menolaknya (boot_id beda). |
| 6.2 | HP → **mode pesawat** ~30 dtk selagi sesi jalan | App: antrian `pending` naik (data ditahan di IndexedDB). Matikan mode pesawat → antrian flush, status → **Tersimpan**. Di DB: `sequence_number` tetap unik, tidak ada duplikat. |
| 6.3 | Pasien → **Tutup sesi** | App: sesi → selesai, antrian kosong. Riwayat pasien menampilkan sesi tadi. Backend: `sessions.status = completed`. |
| 6.4 | Dashboard nakes → **Export PDF** sesi tadi | PDF berisi ringkasan sesi + alert. |
| 6.5 | *(opsional)* HP kedua coba claim `FETAL-GUARD-BENCH-02` | Ditolak — sudah tertaut ke pasien lain. |

---

## 7. Kalau ada yang gagal — pohon keputusan

| Gejala | Kemungkinan sebab | Tindakan |
|---|---|---|
| Scan kosong, ESP32 jelas advertising | filter `namePrefix "FETAL-GUARD"` — UID tidak diawali itu | pastikan UID `FETAL-GUARD-...`; daftar ulang + flash ulang |
| Scan kosong, izin BT sudah diberi, UID benar | flag `neverForLocation` belum termerge di HP itu | beri izin **Lokasi** juga; kalau masih kosong: `git revert` commit "drop BLE location requirement", rebuild APK |
| Serial stuck di "menunggu sinkronisasi waktu" | app tidak menulis `T<epoch_ms>` — izin `BLUETOOTH_CONNECT` ditolak | Setelan HP → Apps → FETAL-GUARD → Izin → aktifkan semua Bluetooth |
| v2 tidak pernah "aktif" | negosiasi `V2:<bytes>` ditolak karena sinkronisasi waktu belum selesai | sama seperti di atas |
| App: `rejected` / HTTP 401 di log | tanda tangan tidak cocok | salin ulang `FG_DEVICE_PACKET_SECRET` **persis** (64 hex, tanpa spasi), flash ulang. Kalau sempat rotasi key setelah flash → kunci lama batal, rotasi lagi & flash lagi. |
| App: `rejected` / HTTP 403 "Device is not active" | status perangkat bukan `active` | Admin → panel Perangkat → dropdown status → **Aktif** |
| App: `rejected` / HTTP 404 "Device not registered" | `device_uid` firmware ≠ yang terdaftar | samakan persis (case-insensitive, tapi samakan saja) |
| App: `awaiting_raw_channels` terus | frame tidak membawa channels mentah | seharusnya tidak terjadi dengan sketch demo; cek Serial `bytes` beberapa ribu, bukan ~200 |
| Dashboard: `derivation_status: insufficient_signal` | window sintetis kurang periodik / < 8 dtk terkumpul | tunggu lebih lama; sinyal demo cukup periodik, biasanya jadi `derived` setelah ~10–15 dtk |
| Dashboard: DJJ "belum tersedia" > 20 dtk | `derivation_status` = `unsupported_schema` (paket terkirim v1) | pastikan Serial mencetak `Telemetry v2 aktif` sebelum sesi mulai |

---

## 8. Metrik untuk dicatat

Roadmap meminta angka-angka ini; bench test adalah kesempatan pertama
mengukurnya. Tanpa angka, klaim latency/packet-loss tidak boleh dibuat.

| Metrik | Cara ukur |
|---|---|
| Latency sensor→dashboard | selisih `captured_at` paket vs waktu kemunculannya di dashboard nakes |
| Packet loss | `sequence_number` terakhir di Serial vs `MAX(sequence_number)` di `session_data_chunks` untuk boot_id itu |
| Jarak BLE | jarak maksimum sebelum `reconnecting` mulai sering |
| Perilaku reconnect | waktu pulih setelah RESET ESP32 |
| Drift sesi panjang | jalankan 1–2 jam, cek `captured_at` tidak melenceng > beberapa detik |
| Stabilitas heap ESP32 | tambahkan `Serial.println(ESP.getFreeHeap())` di `loop()` sementara; pantau setelah 1000+ frame — tidak boleh turun terus |

---

## 9. Batasan yang tetap harus disebut

- Sketch demo **tidak membaca sensor**. Ia membuktikan transport + tampilan,
  bukan akuisisi.
- Estimator DJJ **belum tervalidasi** terhadap CTG/Doppler. Demo mulus ≠ siap
  klinis.
- Belum ada BLE bonding/pairing. Tanda tangan paket menutup spoofing di batas
  API, bukan di lapisan radio.
- APK ini `assembleDebug` (unsigned) — cukup untuk sideload internal, bukan
  Play Store.
- Kecocokan byte firmware C++ ↔ backend baru terbukti **di test** (skema +
  ukuran frame penuh, `backend/tests/test_demo_firmware_frame.py`) dan **di
  runbook ini** (paket nyata dari hardware). Kalau §5.5 menghasilkan `[TX]` di
  Serial tapi backend menolak dengan 401, itulah titik ketidakcocokan yang
  belum pernah terlihat — laporkan Serial + response body.
