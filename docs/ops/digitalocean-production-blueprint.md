# DigitalOcean Production Blueprint

Dokumen ini adalah blueprint canonical untuk deployment staging dan production FETAL-GUARD.

## 1. Keputusan Platform

Gunakan:

- DigitalOcean App Platform untuk frontend React/Vite.
- DigitalOcean App Platform untuk backend FastAPI sebagai web service.
- DigitalOcean Managed PostgreSQL untuk database produksi.
- Object storage atau queue hanya jika nanti benar-benar dibutuhkan.

Alasan keputusan ini:

- Operasional lebih ringan daripada raw VPS.
- Deploy, HTTPS, logs, dan scaling dasar lebih sederhana.
- Cocok untuk arsitektur kita yang memisahkan frontend, backend, database, dan role-based access.

## 2. Topologi Target

| Komponen | Domain | Fungsi |
|---|---|---|
| Frontend | `app.fetalguard.id` | Landing page, portal pasien, portal nakes, portal admin |
| Backend | `api.fetalguard.id` | Auth, session, device registry, clinician/admin APIs |
| Staging frontend | `staging-app.fetalguard.id` | Uji fitur sebelum rilis |
| Staging backend | `staging-api.fetalguard.id` | Uji integrasi dan smoke test |

Catatan penting:

- Backend saat ini mengekspor route pada origin root service, seperti `/auth`, `/patients`, dan `/sessions`.
- Karena itu `VITE_API_BASE_URL` harus diarahkan ke origin backend, bukan ke path `/api/v1`, sampai versioned prefix benar-benar diaktifkan.

## 3. Environment Matrix

| Environment | Frontend | Backend | Database | Catatan |
|---|---|---|---|---|
| Development | Vite localhost | FastAPI localhost | SQLite | Tetap ringan untuk coding lokal |
| Staging | App Platform static site | App Platform web service | Managed PostgreSQL | Validasi fitur end-to-end |
| Production | App Platform static site | App Platform web service | Managed PostgreSQL | Hanya config dan data produksi |

## 4. Wajib Siap Sebelum Deploy Pertama

- Backend memiliki driver PostgreSQL.
- Backend bisa connect ke PostgreSQL melalui `SQLALCHEMY_DATABASE_URI`.
- `AUTO_CREATE_DB=false` di production.
- `SECRET_KEY` production diset sebagai secret environment variable.
- `BACKEND_CORS_ORIGINS` diisi domain frontend staging/production.
- `VITE_API_BASE_URL` diarahkan ke domain backend.
- Migration Alembic sudah jalan di PostgreSQL.
- Seed admin hanya dipakai sebagai bootstrap awal.

## 5. Environment Variables

Backend:

| Variable | Contoh | Catatan |
|---|---|---|
| `ENVIRONMENT` | `production` | Fail-fast untuk config produksi |
| `SECRET_KEY` | secret acak panjang | Wajib untuk production |
| `SQLALCHEMY_DATABASE_URI` | `postgresql+psycopg://...` | Connection string PostgreSQL |
| `AUTO_CREATE_DB` | `false` | Hindari `create_all` di production |
| `BACKEND_CORS_ORIGINS` | `["https://app.fetalguard.id","https://staging-app.fetalguard.id"]` | Format JSON list |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Bisa disesuaikan |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Sesuai policy session |
| `AI_PIPELINE_MODE` | `disabled` | Gunakan `clinician` hanya setelah worker siap dan model clinical_validated aktif |
| `AI_ACTIVE_MODEL_VERSION_ID` | UUID model aktif | Wajib untuk mode aktif research/shadow/clinician |

Frontend:

| Variable | Contoh | Catatan |
|---|---|---|
| `VITE_API_BASE_URL` | `https://api.fetalguard.id` | Mengarah ke origin backend |

Bootstrap admin:

| Variable | Contoh | Catatan |
|---|---|---|
| `FG_ADMIN_EMAIL` | `admin@fetalguard.id` | Akun bootstrap awal |
| `FG_ADMIN_PASSWORD` | secret sementara | Hanya untuk seed awal, wajib diganti |

## 6. Urutan Deploy

1. Buat DigitalOcean project.
2. Buat Managed PostgreSQL.
3. Siapkan domain dan DNS records.
4. Deploy backend service terlebih dahulu.
5. Jalankan migration database.
6. Seed admin awal.
7. Deploy frontend static site.
8. Set `VITE_API_BASE_URL` ke backend production.
9. Jalankan smoke test auth, session, device registry, dan dashboard.
10. Baru lanjutkan koneksi hardware atau ingestion gateway.

### Database role untuk AI

Migration harus dijalankan oleh owner role yang tidak dipakai aplikasi. Web API dan AI worker wajib memakai login role berbeda, keduanya `NOSUPERUSER`, `NOBYPASSRLS`, dan bukan pemilik tabel.

Role API hanya memerlukan `SELECT, INSERT` pada `ai_inference_jobs`, `SELECT` pada `ai_analysis_results`/`ai_model_versions`, serta `SELECT, INSERT, UPDATE` pada `ai_analysis_reviews`. Role API tidak boleh mendapat `UPDATE` job atau `INSERT/UPDATE` result; readiness akan gagal jika privilege berlebih itu ditemukan.

Worker harus menggunakan database role bernama tepat `fetal_guard_ai_worker`. Berikan hanya privilege yang dibutuhkan: `SELECT, UPDATE` job; `SELECT, INSERT, UPDATE` result; `SELECT` model version, sensor chunk, dan AI review; `SELECT, INSERT` realtime event; serta `SELECT, INSERT, UPDATE` realtime cursor. Jangan berikan membership worker role kepada API role. Kredensial dan connection pool worker harus terpisah dari backend web.

Tambahkan publication worker sebagai App Platform background worker dengan source `backend/` dan run command:

```text
python run_ai_publication_worker.py
```

Komponen ini memakai `SQLALCHEMY_DATABASE_URI` milik role `fetal_guard_ai_worker`, bukan URI milik API. Publication worker merekonsiliasi hasil clinician yang sudah direview, termasuk mencabut hasil pasien jika review berubah menjadi `dismissed`; inference worker end-to-end tetap merupakan komponen terpisah yang harus diselesaikan sebelum mode `clinician` diaktifkan.

## 7. Smoke Test Minimum

- Landing page bisa dibuka dari domain publik.
- Login pasien berfungsi.
- Login nakes berfungsi.
- Login admin berfungsi.
- Admin bisa provision nakes tanpa edit kode.
- Pasien bisa membuat sesi monitoring.
- Session upload data diterima backend.
- Dashboard nakes membaca data dari backend production.
- CORS dari frontend ke backend tidak error.

## 8. Struktur Frontend

Satu frontend app cukup untuk semua role:

- Landing page.
- Portal pasien.
- Portal nakes.
- Portal admin.

Jangan pecah menjadi tiga frontend terpisah kecuali nanti skala dan organisasi memang menuntut itu.

## 9. Batasan Fase Ini

- Jangan hubungkan ESP32 langsung ke frontend production.
- Jangan pakai Firebase sebagai sumber data utama dashboard produksi.
- Jangan mengandalkan SQLite untuk multi-user production.
- Jangan rilis domain production sebelum backend dan database lulus smoke test.

## 10. Langkah Berikutnya

Setelah blueprint ini dipakai, langkah implementasi yang paling tepat adalah:

1. Tambahkan Dockerfile backend.
2. Tambahkan deployment config frontend.
3. Tambahkan environment docs yang siap dipakai di App Platform.
4. Uji migrasi PostgreSQL di staging.
5. Baru sambungkan ingestion hardware.
