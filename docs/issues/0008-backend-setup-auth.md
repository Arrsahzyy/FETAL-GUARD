# Issue: [API] Setup FastAPI, SQLite, dan JWT Auth

## Roadmap Stage
- Tahap 2: Akuisisi & Dashboard Dasar

## Goal
- Inisialisasi proyek FastAPI di folder `backend/`.
- Setup database SQLite dengan SQLAlchemy dan Alembic untuk migrasi.
- Membuat tabel `users` dan implementasi endpoint register/login menggunakan JWT.

## Scope
- Hanya folder `backend/`.
- Tabel: `users` dengan kolom dasar (email, hashed_password, role).
- Endpoint: `POST /auth/register`, `POST /auth/login`.

## Files Likely Affected
- `backend/requirements.txt`
- `backend/main.py`
- `backend/core/config.py`
- `backend/core/security.py`
- `backend/db/database.py`
- `backend/models/user.py`
- `backend/api/routes/auth.py`

## Depends On
- Tidak ada.

## Acceptance Criteria
- [ ] Folder backend terbentuk dan `pip install -r requirements.txt` sukses.
- [ ] Swagger UI muncul di `http://localhost:8000/docs`.
- [ ] Bisa mendaftar user baru (password di-hash dengan bcrypt).
- [ ] Login mengembalikan token JWT yang valid.
- [ ] Endpoint yang butuh auth menolak request tanpa token.
- [ ] Build/Run sukses (`uvicorn main:app --reload`).

## Test / Verification
```bash
cd backend
python -m pytest tests/test_auth.py
```

## Notes
- Gunakan `passlib` untuk hashing.
- Jangan hardcode JWT secret, gunakan `python-dotenv`.
