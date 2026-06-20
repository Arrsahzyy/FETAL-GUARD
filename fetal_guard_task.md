# FETAL-GUARD: Execution Task Tracker

Daftar ini melacak kemajuan realisasi pengembangan sistem FETAL-GUARD. Kita akan menandai progres seiring berjalannya proyek.

## Fase 1: MVP Signal Acquisition & Basic IoT
- [ ] **Hardware Setup**
  - [ ] Merangkai sirkuit *Analog Front-End* (LM324 + Piezo)
  - [ ] Mengintegrasikan sensor tekanan (FSR408) dan sensor *Pulse Oximetry* (MAX30102)
  - [ ] Mengganti ADC internal ESP32 dengan ADS1115 untuk akurasi sinyal piezo
  - [ ] Mencetak 3D *casing Main Hub Control*
- [ ] **Firmware & IoT Setup**
  - [ ] Membuat kode program di ESP32 untuk pembacaan semua sensor
  - [ ] Mengimplementasikan *Bandpass Filter* sederhana
  - [ ] Konfigurasi MQTT Broker (Misal: HiveMQ)
  - [ ] Mengatur transmisi data dari ESP32 ke MQTT
- [ ] **Validasi Awal (Tahap 0)**
  - [ ] Pembuatan *setup* manekin simulasi (balon + speaker)
  - [ ] Memutar dataset audio jantung janin (FPCGDB) untuk menguji respons sensor

## Fase 2: Pembuatan Sabuk V2 & Pengembangan AI
- [ ] **Desain Fisik Sabuk V2**
  - [ ] Memilih dan menjahit kain *Cotton Lycra*
  - [ ] Mendesain *pocket* untuk mengunci posisi sensor di perut
- [ ] **Pengembangan Model AI (Pre-Trained)**
  - [ ] Mengunduh dataset CTU-CHB Intrapartum CTG Database
  - [ ] Mengembangkan *pipeline preprocessing* (Spectrogram/STFT) di Python
  - [ ] Melatih model dasar berbasis CNN-LSTM
- [ ] **Pengembangan Backend/Dashboard**
  - [ ] Membuat API (misal dengan FastAPI) untuk menerima data MQTT
  - [ ] Menyediakan *endpoint inference* model AI
  - [ ] Membuat *dashboard* visualisasi sinyal layaknya UI CTG

## Fase 3: Validasi Klinis Terbatas (Pre-Klinis)
- [ ] **Administrasi Medis**
  - [ ] Menyusun protokol penelitian untuk uji observasional
  - [ ] Mengajukan *Ethical Clearance* (Persetujuan Etik)
- [ ] **Pengumpulan Data Primer (Ground Truth)**
  - [ ] Uji coba sistem pada pasien sesungguhnya (bersamaan dengan alat CTG klinis)
  - [ ] Anotasi data (Memberi label *Normal, Watchful, Alert* dari alat medis standar)
- [ ] **Penyempurnaan Model AI**
  - [ ] Melakukan *fine-tuning* model CNN-LSTM dengan data primer
  - [ ] Evaluasi performa (Target MAE < 5 bpm, *Recall* anomali > 85%)

## Fase Jangka Panjang (Komersialisasi & Regulasi)
- [ ] Lulus uji Standar Keselamatan Elektrik Medis (IEC 60601-1)
- [ ] Lulus uji Biokompatibilitas (ISO 10993)
- [ ] Pendaftaran Izin Edar AKD Kelas B ke Kemenkes RI
