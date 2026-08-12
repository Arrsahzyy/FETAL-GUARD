# PRD: Backend API (FastAPI + Python)

## 1. Latar Belakang
- Sistem FETAL-GUARD membutuhkan server backend untuk menerima data sensor dari aplikasi mobile (yang bertindak sebagai gateway BLE), menyimpan data sesi monitoring, dan menyajikan data ke dashboard tenaga kesehatan (nakes).
- Saat ini aplikasi mobile sudah memiliki MockSensorService yang menghasilkan data realistis. Data ini perlu disimpan di server agar bisa diakses oleh dashboard nakes dan diolah oleh model AI.
- Referensi canonical: `AGENTS.md` untuk data flow/core subsystem, `FETAL_GUARD_ROADMAP.md` untuk milestone backend, dan source backend/API aktual sebagai kontrak utama.

## 2. Tujuan
- Membangun REST API menggunakan FastAPI (Python) yang mampu:
  1. Menerima registrasi dan autentikasi pengguna (pasien + nakes) via JWT.
  2. Menerima POST data batch sensor dari aplikasi mobile.
  3. Menyimpan sesi monitoring lengkap (metadata + chunk data sensor).
  4. Menyajikan endpoint GET untuk dashboard nakes (daftar pasien, sesi aktif, alerts).
  5. Menyediakan endpoint inferensi AI (stub) yang akan diisi model CNN-LSTM nantinya.

## 3. Non-Tujuan
- Fitur ini BUKAN untuk diagnosis medis definitif.
- Backend ini BUKAN pengganti rekam medis elektronik rumah sakit.
- Backend ini BELUM mencakup fitur real-time WebSocket/SSE push — polling REST cukup untuk fase prototipe.
- Enkripsi end-to-end dan compliance HIPAA/PDP belum ditargetkan di fase ini.

## 4. Pengguna
- **Pasien/ibu hamil** — via mobile app: mengirim data sensor, melihat riwayat.
- **Tenaga kesehatan (nakes)** — via web dashboard: memantau pasien, menerima alerts.
- **Tim pengembang/admin** — via API docs (Swagger): debugging dan integrasi.

## 5. Tahap Roadmap
- Tahap 2: Akuisisi Data & Dashboard Dasar.

## 6. Requirement Fungsional

### 6.1 Autentikasi
- `POST /auth/register` — Registrasi user baru (role: patient | clinician).
- `POST /auth/login` — Login, return JWT access + refresh token.
- `POST /auth/refresh` — Refresh expired access token.
- Password di-hash menggunakan bcrypt.

### 6.2 Manajemen Pasien
- `GET /patients/me` — Profil pasien saat ini (dari JWT).
- `PATCH /patients/me` — Update profil (usia kehamilan, berat badan, riwayat medis).
- `GET /patients` — (khusus nakes) Daftar semua pasien dengan filter risiko.

### 6.3 Sesi Monitoring
- `POST /sessions` — Mulai sesi baru (kirim device_id).
- `POST /sessions/{id}/data` — Upload batch data sensor (JSON array: piezo channels, FSR, HR, SpO2).
- `PATCH /sessions/{id}` — Stop/complete sesi.
- `GET /sessions` — Daftar sesi (filter by patient, tanggal).
- `GET /sessions/{id}` — Detail sesi lengkap termasuk FHR summary.

### 6.4 Stub Inferensi AI
- `POST /ai/predict` — Menerima window data time-series, mengembalikan prediksi (stub: random normal/waspada/bahaya).

### 6.5 Dashboard Nakes
- `GET /clinician/patients` — Daftar pasien dengan status risiko terkini.
- `GET /clinician/alerts` — Antrian alert aktif.

## 7. Requirement Non-Fungsional
- Latency API response < 500ms untuk operasi CRUD.
- Database: SQLite untuk development lokal, migrasi ke PostgreSQL saat deploy ke production platform.
- Menggunakan SQLAlchemy ORM + Alembic untuk migrasi skema.
- Auto-generated API docs via Swagger UI bawaan FastAPI (`/docs`).

## 8. Parameter Klinis (jika relevan)
- FHR normal: 110-160 bpm.
- Threshold bradikardia: < 110 bpm, takikardia: > 160 bpm.
- Output AI stub yang aman: "normal" / "waspada" / "segera konsultasi".
- Risk score 0-100 (computed dari data FHR, variabilitas, deselerasi).

## 9. Power & Safety (jika relevan)
- Tidak berlaku (backend berjalan di server/VPS).

## 10. Data yang Dibutuhkan

### Tabel Database

| Tabel | Kolom Utama |
|---|---|
| `users` | id, email, hashed_password, role (patient/clinician), created_at |
| `patients` | id, user_id (FK), name, birth_date, gestational_age_weeks, lmp_date, medical_history_json |
| `sessions` | id, patient_id (FK), device_id, start_time, end_time, status, fhr_mean, fhr_min, fhr_max, risk_level |
| `session_data_chunks` | id, session_id (FK), chunk_index, timestamp, raw_channels_json |
| `notifications` | id, patient_id, session_id, type, title, message, acknowledged |

## 11. Alur Sistem

```
Mobile App (React/Capacitor)
  → BLE menerima data dari sabuk (atau MockSensorService)
  → App batch data per 5 detik
  → POST /sessions/{id}/data ke Backend API
  → Backend simpan ke database
  → (Opsional) Backend panggil AI model → hasilkan risk score
  → Dashboard Nakes polling GET /clinician/patients → tampilkan status
  → Jika ada anomali → POST /notifications → push alert
```

## 12. Risiko dan Batasan
- **Data loss jika koneksi putus**: Mobile app perlu buffer lokal (belum di-scope fase ini).
- **Skalabilitas SQLite**: Cukup untuk prototipe (<100 pasien simultan), migrasi ke PostgreSQL untuk produksi.
- **Keamanan JWT**: Secret key harus disimpan di .env, jangan di-hardcode.
- **Klaim medis di API response**: Harus menggunakan frasa aman ("indikasi awal", "skrining awal").

## 13. Validasi
- Unit test endpoint dengan `pytest` + `httpx` (TestClient bawaan FastAPI).
- Test skenario: registrasi → login → buat sesi → upload 3 batch data → stop sesi → get summary.
- Metrik: semua endpoint return status code yang benar (201, 200, 401, 404).
- Swagger UI bisa diakses tanpa error di `http://localhost:8000/docs`.

## 14. Acceptance Criteria
- [ ] `pip install -r requirements.txt` berhasil tanpa error.
- [ ] `python -m pytest` semua test lulus.
- [ ] Swagger UI bisa diakses di `localhost:8000/docs`.
- [ ] Endpoint auth (register, login, refresh) berfungsi.
- [ ] Endpoint sessions (create, upload data, stop) berfungsi.
- [ ] Endpoint clinician (patients, alerts) berfungsi.
- [ ] Tidak ada API key, password, atau secret yang di-hardcode.
- [ ] Tidak melanggar Medical Claim Guardrail.
