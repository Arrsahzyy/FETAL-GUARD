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
- [ ] Kode berhasil dikompilasi (build success).
