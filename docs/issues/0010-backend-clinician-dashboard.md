# Issue: [API] Dashboard Nakes dan AI Stub

## Roadmap Stage
- Tahap 2: Akuisisi & Dashboard Dasar
- Tahap 4: Model AI Awal (Stub)

## Goal
- Membuat endpoint untuk nakes (clinician) guna melihat daftar pasien dan sesi aktif.
- Membuat endpoint stub untuk prediksi AI (sementara me-return nilai acak normal/waspada/bahaya).

## Scope
- Hanya folder `backend/`.
- Tabel: `notifications` (jika diperlukan untuk alerts).
- Endpoint: `GET /clinician/patients`, `GET /clinician/alerts`, `POST /ai/predict`.

## Files Likely Affected
- `backend/api/routes/clinician.py`
- `backend/api/routes/ai.py`
- `backend/services/ai_stub.py`

## Depends On
- 0009-backend-sessions-data.md (Butuh data sesi untuk ditampilkan)

## Acceptance Criteria
- [ ] Nakes dapat mengambil daftar pasien dengan resume data terakhir.
- [ ] Nakes dapat melihat status pasien yang sesinya sedang aktif.
- [ ] Stub AI dapat menerima payload data dan me-return probabilitas risiko simulasi.
- [ ] Endpoint dilindungi (hanya user dengan role `clinician` yang dapat melihat daftar pasien lengkap).
- [ ] Tidak melanggar klaim medis (gunakan "indikasi awal").

## Test / Verification
```bash
cd backend
python -m pytest tests/test_clinician.py
```

## Notes
- Endpoint `POST /ai/predict` nantinya akan diganti dengan pemanggilan ke model CNN-LSTM (PyTorch) sungguhan di Tahap 4. Saat ini cukup return dummy JSON.
