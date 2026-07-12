# Azure Student Deployment Blueprint

Dokumen ini adalah panduan setup staging FETAL-GUARD menggunakan kredit Azure for Students.

## 1. Prinsip Biaya

- Gunakan satu resource group khusus staging.
- Buat budget alert sebelum membuat database atau App Service.
- Mulai dari tier termurah yang masih bisa menjalankan FastAPI dan PostgreSQL.
- Jangan aktifkan AKS, GPU, Azure Machine Learning compute, Application Gateway, NAT Gateway, atau VM besar.
- Jangan masukkan secret asli ke source code, chat, screenshot publik, atau dokumen.

## 2. Target Resource

| Kebutuhan | Azure Service | Nama Disarankan |
|---|---|---|
| Resource group | Resource Group | `rg-fetalguard-staging-sea` |
| Frontend | Static Web Apps | `swa-fetalguard-staging` |
| Backend | App Service Linux | `app-fetalguard-api-staging` |
| Backend plan | App Service Plan | `asp-fetalguard-staging-b1` |
| Database | Azure Database for PostgreSQL Flexible Server | `pg-fetalguard-staging` |
| Database name | PostgreSQL database | `fetalguard_staging` |

Region yang disarankan: `Southeast Asia`.

## 3. Urutan Setup Manual di Azure Portal

1. Pastikan subscription yang aktif adalah Azure for Students.
2. Buat resource group `rg-fetalguard-staging-sea`.
3. Buat budget alert untuk subscription atau resource group.
4. Buat PostgreSQL Flexible Server.
5. Buat App Service Linux untuk backend.
6. Set environment variables backend.
7. Deploy backend dari folder `backend/`.
8. Jalankan migration melalui startup script atau console.
9. Seed admin awal satu kali.
10. Buat Static Web App untuk frontend.
11. Set `VITE_API_BASE_URL` ke URL backend.
12. Jalankan smoke test.

## 4. Backend Configuration

Runtime:

- Python 3.12 jika tersedia.
- Source folder: `backend`.
- GitHub Actions workflow: `.github/workflows/azure-backend-staging.yml`.
- Startup command:

```bash
bash startup.sh
```

Environment variables:

```env
ENVIRONMENT=production
SECRET_KEY=<generated-secret-min-32-chars>
SQLALCHEMY_DATABASE_URI=postgresql+psycopg://<user>:<password>@<host>:5432/fetalguard_staging
AUTO_CREATE_DB=false
BACKEND_CORS_ORIGINS=["https://swa-fetalguard-staging.azurestaticapps.net"]
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
SCM_DO_BUILD_DURING_DEPLOYMENT=true
ENABLE_ORYX_BUILD=true
```

Admin bootstrap variables, hanya saat seed awal:

```env
FG_ADMIN_EMAIL=admin@fetalguard.id
FG_ADMIN_PASSWORD=<temporary-password>
```

Setelah admin berhasil login dan mengganti password, hapus atau rotasi password bootstrap.

## 5. Frontend Configuration

Static Web Apps:

- App location: `/`
- Output location: `dist`
- Build command: `npm run build`

Environment variable:

```env
VITE_API_BASE_URL=https://app-fetalguard-api-staging.azurewebsites.net
```

## 6. PostgreSQL Notes

- Gunakan PostgreSQL Flexible Server, bukan SQLite.
- Pastikan firewall/network mengizinkan App Service backend mengakses database.
- Gunakan SSL/TLS default dari Azure.
- Jangan memakai `AUTO_CREATE_DB=true` untuk staging cloud.
- Schema harus dibuat melalui Alembic migration.

## 7. Smoke Test Minimum

- `GET /` backend mengembalikan pesan API.
- Frontend bisa terbuka dari URL Static Web Apps.
- Frontend bisa memanggil backend tanpa CORS error.
- Pasien bisa register dan login.
- Admin bisa login setelah seed awal.
- Admin bisa membuat akun nakes.
- Nakes bisa login lewat portal nakes.
- Pasien bisa membuat sesi monitoring.
- Backend menerima upload sensor chunk ke sesi aktif.
- Dashboard nakes membaca data dari backend.

## 8. Backend Deployment via GitHub Actions

Workflow backend staging sudah disiapkan di `.github/workflows/azure-backend-staging.yml`.

Prasyarat:

- Repository sudah dipush ke GitHub.
- App Service bernama `app-fetalguard-api-staging` sudah dibuat.
- App Service app settings sudah diisi.
- Publish profile App Service disimpan sebagai GitHub repository secret bernama `AZURE_WEBAPP_PUBLISH_PROFILE_STAGING`.

Langkah:

1. Buka Azure App Service `app-fetalguard-api-staging`.
2. Masuk ke `Overview`.
3. Klik `Download publish profile`.
4. Buka GitHub repository.
5. Masuk ke `Settings` -> `Secrets and variables` -> `Actions`.
6. Tambahkan repository secret `AZURE_WEBAPP_PUBLISH_PROFILE_STAGING`.
7. Isi value secret dengan isi file publish profile.
8. Buka tab `Actions`.
9. Pilih workflow `Deploy backend to Azure App Service staging`.
10. Klik `Run workflow`.

Jika tombol download publish profile tidak tersedia karena publishing credentials dimatikan, aktifkan sementara App Service publishing credentials untuk deployment staging, simpan publish profile ke GitHub secret, lalu evaluasi lagi setelah deployment stabil. Untuk production final, lebih baik pakai federated identity/OIDC daripada publish profile.

## 9. Stop Criteria

Hentikan setup dan evaluasi biaya jika:

- Azure Portal memperkirakan biaya bulanan jauh di atas kredit yang tersedia.
- App Service atau PostgreSQL meminta tier yang tidak bisa ditanggung kredit student.
- Backend gagal connect ke PostgreSQL karena network/firewall.
- Migration gagal karena schema drift.

## 10. Prompt untuk AI Pendamping Cloud

```text
Kamu adalah cloud deployment engineer untuk FETAL-GUARD.

Target:
- Azure for Students, kredit terbatas.
- Region Southeast Asia.
- Resource group rg-fetalguard-staging-sea.
- Frontend React/Vite via Azure Static Web Apps.
- Backend FastAPI dari folder backend via Azure App Service Linux.
- Database Azure PostgreSQL Flexible Server.

Batasan:
- Jangan membuat AKS, GPU, Azure ML compute, Application Gateway, NAT Gateway, atau VM besar.
- Jangan menampilkan secret asli di chat.
- Gunakan placeholder untuk password, SECRET_KEY, dan database URI.
- Jangan mengubah arsitektur auth/RBAC.
- Jangan pakai SQLite untuk staging cloud.

Tugas:
1. Bantu saya membuat resource Azure satu per satu.
2. Pastikan budget alert dibuat sebelum App Service dan PostgreSQL.
3. Pastikan env var backend dan frontend sesuai repo.
4. Pastikan Alembic migration berjalan ke PostgreSQL.
5. Bantu smoke test frontend, backend, auth, admin provisioning, sesi pasien, dan dashboard nakes.
```
