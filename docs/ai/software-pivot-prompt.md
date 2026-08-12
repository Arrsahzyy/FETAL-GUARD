# Prompt Eksekusi Perangkat Lunak & AI (FETAL-GUARD)

Gunakan *prompt* di bawah ini untuk menginstruksikan AI lain (atau agent ini di sesi terpisah) agar dapat langsung mengeksekusi rencana tanpa perlu mengulang konteks dari awal. Anda tinggal menyalin teks di dalam blok kode di bawah ini.

```text
Kamu adalah Senior Software & AI Engineer yang bertugas membangun sistem perangkat lunak untuk proyek FETAL-GUARD (Sabuk pintar pemantau detak jantung janin dan kontraksi ibu).

## KONTEKS & BATASAN SAAT INI
1. Hardware (ESP32, Piezo, FSR, Baterai 2S) sedang dipegang rekan tim lain. KITA TIDAK AKAN MENYENTUH KODE HARDWARE SAMA SEKALI.
2. Tenggat waktu proyek kurang dari 2 bulan untuk presentasi (demo-able).
3. Karena tidak ada hardware, aplikasi harus memiliki "Mock Hardware Mode" yang men-generate data palsu/simulasi yang realistis (110-160 bpm untuk detak jantung janin) agar aplikasi tetap bisa didemokan 100%.

## ARSITEKTUR YANG DISEPAKATI
Kita membagi pengembangan menjadi 3 pilar utama:

1. **Frontend Mobile/Web (React + Vite + Capacitor)**
   - Berada di folder `/src/`.
   - Tugas: Buat `src/services/MockSensorService.ts` yang mensimulasikan koneksi BLE dan menghasilkan array data raw (Piezo, FSR, SpO2) secara real-time (sekitar 100Hz).
   - Tugas: Hubungkan data mock ini ke `MonitoringScreen` agar grafik bergerak layaknya membaca EKG/CTG asli.

2. **Backend API (FastAPI + Python + SQLite)**
   - Buat folder `/backend/`.
   - Tugas: Buat REST API menggunakan FastAPI untuk menerima POST data *batch* sensor dari aplikasi Mobile, dan endpoint GET untuk Web Dashboard tenaga kesehatan.
   - Mengapa FastAPI? Agar mudah diintegrasikan dengan model AI Python kita nantinya.

3. **Infrastruktur AI Hybrid Deep Learning (CNN-LSTM)**
   - Buat folder `/ai-pipeline/`.
   - Tugas: Buat arsitektur CNN-LSTM dasar menggunakan PyTorch (atau TensorFlow).
   - Tugas: Buat script `download_dataset.py` untuk mengunduh dataset CTG publik dari PhysioNet (misalnya CTU-UHB Intrapartum Cardiotocography Database) sebagai data *training* awal.

## INSTRUKSI EKSEKUSI
Pilih salah satu dari 3 tugas di bawah ini untuk kamu kerjakan SEKARANG:

**TUGAS A (Frontend UI & Mocking):**
Buatkan struktur kode lengkap untuk `MockSensorService.ts` dan panduan cara mengintegrasikannya dengan React Hooks agar `MonitoringScreen` bisa menampilkan grafik dinamis berkecepatan tinggi.

**TUGAS B (Backend FastAPI):**
Buatkan file `backend/main.py`, skema Pydantic, dan konfigurasi database SQLite menggunakan SQLAlchemy untuk endpoint pendaftaran pasien dan penerimaan data sensor (raw array).

**TUGAS C (AI Pipeline):**
Buatkan kerangka Python lengkap (`model.py` dan `train.py`) yang mendefinisikan kelas PyTorch CNN-LSTM untuk menerima input time-series (1 dimensi x N channels) dan mengeluarkan klasifikasi 3 kelas (Normal, Waspada, Bahaya).

Jawablah dengan menanyakan Tugas mana yang ingin saya eksekusi terlebih dahulu, atau langsung kerjakan Tugas A jika menurutmu itu yang terbaik untuk melihat hasil visual pertama kali!
```
