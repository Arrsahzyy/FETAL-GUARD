# Issue: [API] Sesi Monitoring dan Upload Data Sensor

## Roadmap Stage
- Tahap 2: Akuisisi & Dashboard Dasar

## Goal
- Membuat tabel `patients`, `sessions`, dan `session_data_chunks`.
- Membuat endpoint untuk memulai sesi, mengirim batch data sensor, dan mengakhiri sesi.

## Scope
- Hanya folder `backend/`.
- Tabel: `patients`, `sessions`, `session_data_chunks`.
- Endpoint: `POST /sessions`, `POST /sessions/{id}/data`, `PATCH /sessions/{id}`.

## Files Likely Affected
- `backend/models/patient.py`
- `backend/models/session.py`
- `backend/schemas/session.py`
- `backend/api/routes/sessions.py`

## Depends On
- 0008-backend-setup-auth.md (Butuh JWT Auth)

## Acceptance Criteria
- [ ] Pasien dapat memulai sesi baru (membuat record di tabel `sessions`).
- [ ] Pasien dapat mengirim batch data sensor (array FHR, SpO2, dll) ke `/sessions/{id}/data`.
- [ ] Data sensor tersimpan dalam bentuk JSON di tabel `session_data_chunks` agar efisien.
- [ ] Pasien dapat mengakhiri sesi, mengubah status menjadi `completed`.
- [ ] Semua endpoint ini dilindungi oleh JWT (hanya user dengan role valid yang bisa akses).

## Test / Verification
```bash
cd backend
python -m pytest tests/test_sessions.py
```

## Notes
- Karena data sensor direkam dengan frekuensi tinggi (misal 50Hz/100Hz), menyimpan setiap baris di DB akan membebani I/O. Simpan per "chunk" (misalnya setiap 5 detik) dalam satu field JSON/JSONB.
