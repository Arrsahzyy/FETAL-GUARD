# PRD: Fase 1 - Akuisisi Sinyal, Manajemen Daya 2S, dan Komunikasi BLE

## 1. Latar Belakang
- Prototipe awal FETAL-GUARD memerlukan pondasi hardware dan konektivitas yang solid sebelum masuk ke tahap analisis AI.
- Berdasarkan kesepakatan terbaru, arsitektur daya menggunakan baterai Li-ion 18650 2S (7.4V) untuk stabilitas sistem, dan arsitektur komunikasi menggunakan Bluetooth Low Energy (BLE) agar perangkat wearable dapat berkomunikasi langsung dengan smartphone pasien layaknya *smartwatch*, tanpa perlu melakukan setup koneksi Wi-Fi pada ESP32.
- Referensi canonical: `AGENTS.md` untuk konteks sistem dan `FETAL_GUARD_ROADMAP.md` untuk milestone hardware/konektivitas.

## 2. Tujuan
- Membangun sirkuit daya yang stabil untuk menyuplai ESP32 (3.3V) dan LM324 (5V) dari baterai 2S (7.4V).
- Mengakuisisi data dari 4 sensor piezoelektrik, 1 FSR408, dan MAX30102 secara simultan.
- Mentransmisikan data sensor secara nirkabel dari ESP32 (sebagai BLE Peripheral) ke aplikasi mobile Android (sebagai BLE Central) dengan latency rendah.

## 3. Non-Tujuan
- Fitur ini BUKAN untuk diagnosis definitif.
- Fitur ini BUKAN pengganti CTG/Doppler/toco.
- Fitur ini belum mencakup pemrosesan AI (CNN-LSTM) di sisi cloud. Hanya sebatas pengiriman data mentah (raw data) ke aplikasi mobile.

## 4. Pengguna
- Pasien/ibu hamil (memakai sabuk dan aplikasi mobile untuk pairing BLE).
- Tim pengembang/admin (fokus pada perakitan dan validasi hardware).

## 5. Tahap Roadmap
- Fitur ini termasuk di **Tahap 1 (PoC Sensor & Power)** dan awal **Tahap 2 (Akuisisi Data)**.

## 6. Requirement Fungsional
- **Sensor Sampling:**
  - 4 channel ADC internal ESP32 (atau ADS1115 jika noise tinggi) untuk membaca 4 piezoelektrik (frekuensi sampling target ~500-1000 Hz).
  - 1 channel ADC untuk membaca FSR408 (frekuensi sampling ~50 Hz).
  - Interupsi I2C untuk MAX30102.
- **BLE GATT Server (ESP32):**
  - Custom Service UUID untuk FETAL-GUARD.
  - Characteristic 1 (Notify): Payload data Piezo & FSR (dibatch per sekian ms untuk efisiensi MTU BLE).
  - Characteristic 2 (Notify): Payload data SpO2/HR dari MAX30102.
  - Characteristic 3 (Read/Notify): Status baterai (pembacaan tegangan baterai via pembagi tegangan).
- **Aplikasi Mobile (Gateway):**
  - Aplikasi dapat melakukan pemindaian (scan) perangkat BLE dengan nama "FETAL-GUARD".
  - Aplikasi dapat terhubung (connect) dan subscribe ke notifikasi (notify) untuk menerima stream data secara kontinyu.

## 7. Requirement Non-Fungsional
- **Latency:** Keterlambatan penerimaan data di aplikasi mobile maksimal 1 detik dari waktu aktual di sabuk.
- **Efisiensi:** Payload BLE harus dipadatkan (contoh: mengirim array integer dalam format byte) agar tidak melebihi batasan bandwidth BLE dan menghemat daya.
- **Uptime:** Sistem harus dapat menyala dan mentransmisikan data setidaknya selama 2-4 jam pemantauan nonstop.

## 8. Parameter Klinis
- Tidak berlaku secara langsung. Saat ini hanya mengambil raw data. (Namun data raw ini nantinya akan digunakan untuk mendeteksi FHR 110-160 bpm).

## 9. Power & Safety
- **Baterai 2S (7.4V, 1500 mAh):** Wajib menggunakan modul charger 2S (misal TP5100 atau BMS) untuk mencegah *overcharge/overdischarge*.
- **Isolasi Panas & Listrik:** Buck converter (penurun 7.4V ke 5V) dan LDO (5V ke 3.3V) bisa menghasilkan panas. Penempatan di dalam *casing 3D printed* harus memperhatikan sirkulasi udara dan dijauhkan dari kontak langsung dengan kulit abdomen pasien.
- **Tekanan:** Sabuk harus dipasang secara ergonomis agar tekanan 4 sensor piezoelektrik cukup kuat untuk membaca vibrasi tanpa menyakiti ibu.

## 10. Data yang Dibutuhkan
- Format Payload BLE (JSON/Byte Array):
  `{ "p": [p1, p2, p3, p4], "f": fsr_val, "h": [hr_ir, hr_red] }`
  *(Catatan: Mengingat batasan MTU BLE (biasanya 20-512 bytes), payload mungkin dikirim sebagai struktur byte alih-alih string JSON murni).*

## 11. Alur Sistem
1. Sabuk dinyalakan → ESP32 menginisiasi BLE Server dan mulai *advertising*.
2. Ibu hamil membuka aplikasi mobile Android → klik "Connect".
3. Aplikasi melakukan *pairing/connect* via BLE.
4. Timer interrupt di ESP32 membaca 4x Piezo + 1x FSR + MAX30102.
5. ESP32 mengemas data dalam buffer kecil (batch).
6. ESP32 mengirim notifikasi GATT berisi buffer data ke aplikasi mobile.
7. Aplikasi mobile menerima byte array, mem-parsing, dan menampilkannya di grafik *real-time* layar HP.

## 12. Risiko dan Batasan
- **Noise ADC Internal ESP32:** Sinyal piezo berada di orde milivolt. Modul Wi-Fi/BLE bawaan ESP32 sering menginterferensi ADC internal (noise paku/spikes). *Mitigasi: Mengaktifkan opsi penggunaan ADS1115.*
- **Limitasi Bandwidth BLE:** Sampling 4 piezo pada 1000 Hz memakan bandwidth besar. *Mitigasi: Data batching dan downsampling jika diperlukan.*
- **Risiko Safety:** Baterai Li-ion tanpa BMS yang memadai rawan rusak atau terbakar. *Mitigasi: Pemilihan modul charging 2S yang tepat dan enclosure aman.*

## 13. Validasi
- **Power Validation:** Multimeter pada pin input ESP32 (harus stabil 3.3V) dan LM324 (harus stabil 5V) saat baterai di bawah beban penuh transmisi BLE.
- **Connectivity Validation:** Menggunakan aplikasi *nRF Connect* di smartphone untuk memastikan layanan BLE muncul dan data mengalir dengan lancar.
- **Signal Quality (SNR):** Mengecek Serial Plotter (kabel USB) vs visualisasi di aplikasi HP untuk memastikan data tidak terpotong (packet loss) selama transmisi BLE.

## 14. Acceptance Criteria
- [ ] Hardware terpasang dengan sumber daya Li-ion 2S, *Buck Converter* stabil 5V, LDO stabil 3.3V.
- [ ] ESP32 memancarkan BLE dengan nama "FETAL-GUARD".
- [ ] Aplikasi (atau nRF Connect) bisa subscribe ke GATT characteristic dan mendapat stream data yang masuk akal (berubah saat sensor disentuh).
- [ ] Tidak ada klaim diagnostik medis yang tercantum pada antarmuka aplikasi.
- [ ] Suhu casing tidak panas saat beroperasi terus menerus selama 1 jam.
- [ ] Firmware telemetry v2 dikompilasi ulang untuk `esp32:esp32:esp32s3` setelah perubahan buffer multi-rate.

## 15. Implementasi Gateway Lokal v1

Alur uji lokal yang diimplementasikan adalah:

```text
Sensor -> ESP32-S3 (BLE peripheral) -> browser/aplikasi pasien
-> FastAPI lokal terautentikasi -> database -> tampilan pasien/nakes
```

ESP32 tidak menyimpan JWT, password pasien, atau secret backend. Identitas perangkat pada
`FG_DEVICE_UID` di `fetalguard.ino` harus sama persis dengan `device_uid` yang didaftarkan
dan ditugaskan kepada pasien oleh admin. Nilai bawaan untuk smoke test adalah
`FETAL-GUARD-001`.

Kontrak paket canonical berada di `contracts/telemetry/v1/golden-esp32.json`. Firmware
mengirim satu frame JSON berakhiran newline setiap satu detik melalui service `FFE0` dan
characteristic `FFE1`. Frame dipecah menjadi fragmen 20 byte agar tetap aman pada ATT MTU
minimum, lalu dirakit kembali oleh aplikasi. Sesudah subscribe, aplikasi menulis perintah
`T<unix_epoch_ms>` ke characteristic yang sama agar timestamp ESP32 berasal dari jam gateway.

Bagian `telemetry` membawa nilai live yang sudah tersedia dari firmware (`fhr`, `motherHR`,
`spo2`, `contractionLevel`, dan `signalQuality`). `contractionLevel` adalah perubahan tekanan
FSR relatif terhadap baseline/threshold perangkat, sedangkan `signalQuality` adalah indikator
teknis envelope piezo terhadap noise floor. Keduanya bernilai 0-100 dan bukan pengukuran
kontraksi atau SQI klinis. Aplikasi mengosongkan semua nilai live ketika sesi berhenti atau
paket melewati batas freshness; angka terakhir tidak dipertahankan seolah-olah masih berjalan.

Payload 1 Hz v1 ini tetap menjadi snapshot kompatibilitas untuk browser. Pada aplikasi Android
native, gateway membaca ATT MTU yang sudah dinegosiasikan lalu mengirim perintah
`V2:<fragment_bytes>`. Firmware kemudian mengirim jendela JSON v2 berakhiran newline dengan:

- `sample_rates_hz.p` untuk frame piezo empat kanal;
- `sample_rates_hz.fsr`, `hr_ir`, dan `hr_red` untuk laju native masing-masing sensor;
- `channel_layout.p=4` untuk merekonstruksi array piezo interleaved;
- raw ADC di `channels`, sementara nilai live tetap berada di `telemetry`.

Kontrak dan fixture canonical v2 berada di
`contracts/telemetry/v2/golden-esp32-window.json`. Fragmen native dibatasi maksimal 180 byte;
browser yang tidak dapat membaca negotiated MTU tetap memakai snapshot v1 20 byte. Pengiriman
v2 mempersiapkan penyimpanan window AI, tetapi latency, packet loss, dan kestabilan sampling
selama notify tetap harus diukur pada ESP32 dan ponsel fisik.

## 16. Prosedur Uji Lokal End-to-End

Prasyarat firmware:

- Arduino ESP32 core dengan target `ESP32S3 Dev Module`.
- Library SparkFun MAX3010x yang menyediakan `MAX30105.h` dan `spo2_algorithm.h`.
- ESP32-S3 dan rangkaian sensor sesuai pin pada `fetalguard.ino`.

Langkah uji:

1. Pastikan `FG_DEVICE_UID` di sketch bernilai `FETAL-GUARD-001`, atau gunakan UID lain yang konsisten di firmware dan registry backend.
2. Compile dan upload `fetalguard.ino`, lalu buka Serial Monitor pada 115200 baud.
3. Jalankan backend dan frontend lokal dari root repository:

   ```powershell
   npm.cmd run local
   ```

4. Jika perangkat belum ditugaskan ke akun pasien, buka terminal kedua dan jalankan shortcut
   interaktif berikut. UID bawaannya sama dengan firmware, yaitu `FETAL-GUARD-001`:

   ```powershell
   npm.cmd run local:device
   ```

5. Buka `http://127.0.0.1:5173` memakai Chrome atau Edge di komputer yang memiliki Bluetooth, lalu login sebagai pasien tersebut.
6. Pada Beranda atau halaman Monitoring, lakukan scan, pilih `FETAL-GUARD-001`, tekan **Hubungkan**, kemudian mulai sesi monitoring.
7. Pastikan Serial Monitor menampilkan `[BLE] Waktu gateway tersinkronisasi.` dan UI menerima data tanpa status stale.
8. Pastikan upload berubah menjadi tersinkronisasi dan satu `boot_id + sequence_number` hanya membuat satu record walaupun paket dikirim ulang.

Web Bluetooth membutuhkan secure context. `localhost` diterima untuk uji desktop, tetapi alamat
HTTP LAN seperti `http://192.168.x.x:5173` pada browser HP umumnya tidak. Untuk uji Android,
gunakan build Capacitor yang sudah memakai plugin BLE native atau layani frontend melalui HTTPS.
Selain itu, `127.0.0.1` di HP menunjuk ke HP itu sendiri, bukan komputer backend.

## 17. Kriteria Lulus Smoke Test Gateway

- ESP32 advertising dengan UID yang terdaftar dan dapat dipilih dari aplikasi.
- Sinkronisasi waktu diterima sebelum frame telemetry dikirim.
- Fixture v1 dan v2 lolos parser frontend dan contract ingestion backend.
- Android mencatat telemetry `schema_version=2`, empat kanal piezo, dan laju native per modalitas.
- Paket retry tersimpan tepat satu kali berdasarkan ingestion id.
- Nilai yang tidak tersedia tetap kosong; sistem tidak membuat angka klinis pengganti.
- Compile, flash, perubahan sensor fisik, latency, dan packet loss dibuktikan dengan perangkat nyata sebelum checklist hardware dinyatakan selesai.

## 18. Jalur Backend dan AI Fail-Closed

Aplikasi menyimpan paket BLE ke antrean lokal terlebih dahulu, membentuk ingestion ID deterministik
dari device UID, boot ID, dan sequence number, lalu mengunggahnya ke endpoint sesi. Backend
menolak rate yang hilang, layout piezo selain empat kanal, PPG IR/red yang tidak berpasangan,
timestamp yang tidak konsisten, perangkat yang bukan milik pasien, dan paket out-of-order. Retry
dengan identitas yang sama tidak membuat record kedua.

Adapter `ai/src/fetal_guard_ai/telemetry.py` hanya menerima data hardware schema v2 non-simulasi.
Adapter menolak boot ID campuran atau sequence gap, melakukan resampling eksplisit ke kontrak
model (piezo 250 Hz, FSR 50 Hz, PPG ibu 100 Hz), dan membuat validity mask untuk cakupan yang
hilang. Worker `backend/run_ai_inference_worker.py` memverifikasi SHA-256 manifest, kecocokan
record model aktif, validation/deployment gate, lalu menjalankan CNN-LSTM dan safety layer.

AI tetap nonaktif secara default. Untuk riset internal, siapkan environment terpisah dari
`ai/requirements-ai.txt`, daftarkan manifest model yang sudah direview pada tabel model, dan
gunakan mode `research` atau `shadow`. Jangan mengaktifkan mode `clinician` tanpa model
`clinical_validated`; hasil pasien tetap memerlukan review nakes dan publication worker.

```powershell
cd backend
python run_ai_inference_worker.py --once
```

Nama/path virtual environment di atas adalah contoh; interpreter wajib memiliki dependency AI
dan backend. Worker PostgreSQL production wajib memakai role `fetal_guard_ai_worker`.

## 19. Build APK Android untuk Backend Lokal

APK debug lokal mempertahankan BLE native dan mengizinkan HTTP hanya ketika build memakai mode
`android-local`, flag eksplisit, dan alamat API berada pada rentang IPv4 privat. Manifest
cleartext berada di source set `debug`, sehingga kebijakan tersebut tidak masuk ke APK release.

Contoh untuk laptop dengan IP `192.168.1.22`:

```powershell
npm.cmd run build:android:local -- -ApiBaseUrl http://192.168.1.22:8000
```

Hasil build berada di `artifacts/FETAL-GUARD-local-debug.apk`. Jalankan backend dengan host dan
CORS khusus aplikasi mobile lokal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-backend-local-mobile.ps1 -LaptopIp 192.168.1.22
```

HP dan laptop harus berada pada Wi-Fi yang sama untuk jalur aplikasi ke backend. Hubungan ESP32
ke HP tetap menggunakan BLE dan tidak bergantung pada Wi-Fi tersebut. Jika IP laptop berubah,
APK harus dibangun ulang menggunakan IP baru. Pastikan Windows Firewall mengizinkan TCP 8000
hanya pada jaringan privat yang dipercaya.

Launcher icon Android memakai simbol ibu-janin dan jantung FETAL-GUARD tanpa teks agar tetap
terbaca pada ukuran kecil. Master foreground berada di
`src/assets/fetal-guard-app-icon-foreground.png`; seluruh varian legacy, round, dan adaptive
dibuat ulang otomatis oleh `scripts/generate-android-icons.ps1` saat build APK lokal.
