# FETAL-GUARD: Final Technical & Implementation Roadmap

Menggabungkan konteks proposal awal dan analisis arsitektur teknis mendalam dari referensi dokumen tambahan, berikut adalah roadmap final dan komprehensif untuk merealisasikan FETAL-GUARD. Roadmap ini disusun dengan pendekatan *Engineering & Medical Validation*, memastikan prototipe kalian dapat berkembang menjadi produk medis yang *viable*.

> [!IMPORTANT]
> **User Review Required**
> Silakan tinjau roadmap final yang telah disempurnakan ini. Roadmap ini disusun menjadi tahapan teknis terperinci (Bulan 1-12) dan tahapan klinis jangka panjang. Mohon berikan *feedback* pada bagian **Open Questions** di akhir dokumen.

## 1. Arsitektur Teknis yang Direkomendasikan
Berdasarkan tinjauan terbaru, ada beberapa modifikasi sistem yang direkomendasikan agar FETAL-GUARD benar-benar berfungsi:

* **Hardware & Sensor:**
  * Baterai: Tingkatkan ke **Li-Po 3000mAh** untuk memastikan daya tahan operasional 8-12 jam.
  * *Critical Upgrade:* Gunakan **External ADC (misal ADS1115 via I2C)** alih-alih ADC bawaan ESP32. Sinyal piezoelektrik dari getaran jantung janin sangat kecil dan rentan terhadap *noise* transmisi WiFi dari ESP32 itu sendiri.
  * Penempatan Sensor: FSR408 diposisikan horizontal di area *fundus uteri* (puncak rahim), 4 buah Piezo di *abdomen* (tengah perut formasi belah ketupat), dan MAX30102 sebagai sensor *finger-touch* di sayap pinggang.
* **Komunikasi (IoT):**
  * Terapkan arsitektur komunikasi **Hybrid**. Untuk prototipe awal (PKM), *WiFi Manager* + *Hotspot HP* sudah cukup. Namun desain *software*-nya harus diarahkan ke **BLE Provisioning** di mana HP ibu hamil bertindak sebagai *gateway* pengirim data ke *Cloud* (menghemat baterai perangkat).
* **AI & Pemrosesan:**
  * Model AI (CNN-LSTM) sangat berat untuk dijalankan di *edge* (ESP32). Eksekusi model dilakukan di **Cloud/Server/Backend**.
  * Gunakan arsitektur *Hybrid AI*: Kombinasikan *Hard Rules* (batas takikardia/bradikardia klinis) dengan *Soft Rules* dan klasifikasi *Deep Learning*.

---

## 2. Roadmap Pelaksanaan Bertahap (Tahun Pertama)

### Bulan 1-3: MVP Signal Acquisition & Basic IoT (Proof-of-Concept)
* **Hardware:** Merakit rangkaian Analog Front-End (AFE) dengan LM324 + piezo + ADS1115 di *breadboard* atau PCB *prototype*.
* **Filter Dasar:** Mengimplementasikan *Bandpass filter* (20-150Hz) secara digital atau analog untuk membersihkan sinyal *phonocardiography*.
* **Validasi Tahap 0-2 (Bench Testing):** Menggunakan *signal generator* atau memutar dataset audio jantung janin (seperti **FPCGDB** dari PhysioNet) melalui *speaker* kecil yang ditempelkan langsung ke piezoelektrik untuk memverifikasi ADC dan transmisi data.
* **IoT:** Mengirimkan data via MQTT ke *broker* (seperti HiveMQ free tier) dan menyimpannya di *database* *time-series* sederhana.

### Bulan 4-6: Sabuk V2 & Pengembangan AI (Pre-trained)
* **Sabuk Ergonomis:** Menjahit *maternity belt* versi 2 menggunakan *Cotton Lycra*. Penambahan *pocket* (kantung sabuk) ketat agar piezo tidak bergeser (mengurangi artefak gerak/ *noise*).
* **Pengembangan AI Awal:** Mengunduh dataset publik (seperti **CTU-CHB Intrapartum CTG Database**) untuk melatih model CNN-LSTM awal (Pre-trained model). 
* **Backend:** Menyediakan *endpoint* API (misalnya menggunakan FastAPI) untuk menerima data mentah, memproses ekstraksi fitur (misal STFT/*Spectrogram*), dan mengembalikan klasifikasi: *Normal*, *Watchful*, atau *Alert*.

### Bulan 7-12: Validasi Klinis Terbatas (Ground Truth)
* **Ethical Clearance:** Menyusun protokol uji observasional dan mendapatkan izin etik (KEPK).
* **Pengambilan Data Klinis:** Membawa prototipe alat (Sabuk V2) ke klinik bersalin/Puskesmas. Pasien yang sedang menggunakan CTG Klinis atau diperiksa *Doppler* dipakaikan FETAL-GUARD secara bersamaan.
* **Model Fine-Tuning:** Rekaman *Ground Truth* CTG tersebut digunakan untuk melatih ulang (fine-tuning) AI agar mengenali karakteristik perangkat FETAL-GUARD itu sendiri.
* **Metrik Evaluasi Pokok:** MAE (Mean Absolute Error) di bawah 5 bpm untuk taksiran DJJ, dan *Recall* (Sensitivitas) di atas 85% untuk deteksi kondisi bahaya.

---

## 3. Fase Jangka Panjang: Standarisasi Medis & Hilirisasi

### Uji Keamanan Fisik (Safety Testing)
Sebagai alat elektronik *wearable* ibu hamil, alat ini wajib diuji:
* **Keamanan Kelistrikan (IEC 60601-1):** Memastikan tidak ada panas berlebih dari ESP32 atau *short-circuit* pada kulit perut pasien.
* **Biokompatibilitas (ISO 10993):** Material 3D print (PLA/ABS) dan sabuk tidak menimbulkan reaksi iritasi atau alergi.

### Izin Edar Alat Kesehatan
* Sistem akan didaftarkan sebagai **AKD (Alat Kesehatan Dalam Negeri) Kelas B** (Alat skrining non-invasif).
* **Mandatory Disclaimer:** Secara legal, baik dalam aplikasi ibu dan *dashboard* Nakes, hasil AI hanya menggunakan istilah *"Risk Level"* (Tingkat Risiko), bukan *"Diagnosis"*.

---

## Open Questions untuk Diskusi Tim

> [!CAUTION]
> 1. **Eksternal ADC (ADS1115):** Dari evaluasi teknis, membaca sinyal piezoelektrik yang amat lemah dengan ADC internal ESP32 biasanya gagal karena terlalu *noisy* apalagi saat transmisi WiFi. Apakah kalian setuju untuk segera menambahkan **ADS1115** ke dalam BoM (*Bill of Materials*) dan prototipe awal?
> 2. **Metode Validasi Awal (Tanpa RS):** Di Bulan ke-1, mampukah tim membuat "Manekin Janin" sederhana (contoh: balon air yang di dalamnya ada *speaker* yang memutar file audio DJJ dari PhysioNet)? Ini *hack* terbaik sebelum alat dipakaikan ke relawan manusia.
> 3. **Komputasi AI:** Rencana kalian untuk implementasi *backend* AI di Bulan 4-6 akan *hosting* di mana? Apakah mau mencoba AWS Educate, Google Cloud, atau platform murah/gratis seperti Render/Railway untuk *endpoint* FastAPI-nya?
