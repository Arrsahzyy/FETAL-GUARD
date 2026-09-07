# Portal Admin — Roadmap Skala

**Tanggal:** 2026-09-07
**Konteks:** panel Perangkat (`src/screens/admin/AdminPortal/DevicesPanel.jsx`) sudah
menutup kebutuhan operasional dasar — daftar/registrasi/claim code/signing
key/assign/status alat lewat UI, tanpa shell. Dokumen ini mencatat pekerjaan
lanjutan agar portal tetap layak saat jumlah alat, pasien, dan nakes bertambah.

## Yang sudah kuat

- **Multi-tenant + RLS Postgres** — data tiap faskes terisolasi di level DB
  (`organization_id` + policy di `backend/core/database_security.py`).
- **Onboarding self-service by design** — pasien registrasi sendiri; tiap belt
  dikirim dengan **claim code tercetak**, pasien pairing sendiri (`POST /devices/claim`);
  nakes dibuat massal (`POST /admin/clinicians/bulk`).
- Audit log tiap aksi admin; pagination `limit`/`offset` di endpoint list.

## Backlog (urut prioritas)

### 1. Pecah portal jadi tab ber-route
`AdminPortal.jsx` ~1000 baris, semua section menumpuk. Pisah jadi rute anak
(`/admin/nakes`, `/admin/pasien`, `/admin/perangkat`, `/admin/audit`), lazy-load
per tab. `DevicesPanel` sudah jadi komponen mandiri — pola yang sama diterapkan ke
section lain.

### 2. Pencarian & pagination server-side penuh
- Semua filter sudah di server untuk devices/clinicians/patients; pastikan tidak
  ada filter sisa di klien.
- Ganti `offset` → **cursor pagination** (offset melambat di ribuan baris).
- Index DB pada kolom filter: `devices(organization_id, status)`,
  `devices(device_uid)`, `patients(organization_id, name)`.

### 3. Stasiun provisioning pabrik
Sekarang: terbitkan signing key di UI → tempel ke firmware → flash, satu-satu.
Skala produksi butuh skrip + jig yang per unit: `POST /devices` → ambil key →
flash firmware dengan UID+key → catat hasil ke CSV/DB. Bukan UI — alat ops
terpisah di `scripts/`.

### 4. Tampilan beban kerja nakes
Kolom "jumlah pasien aktif" per nakes di daftar nakes, plus filter "nakes tanpa
pasien" / "kelebihan beban". Opsional: saran auto-assign ke nakes paling ringan.

### 5. Siklus hidup pasien
- Admin belum bisa reset password pasien atau lihat kontak — perlu
  `POST /admin/patients/{id}/reset-password` + view detail pasien (email, telepon).
- Alur "selesai / arsip" pasca-persalinan supaya data pasien lama tidak menumpuk
  di daftar aktif selamanya (`status` pada `patients` atau tabel arsip).

### 6. Dashboard fleet health
Ringkasan alat per `last_seen_at` (mati > 7 hari), versi firmware (untuk rollout
OTA), status baterai terakhir. Endpoint agregasi baru di `backend/api/routes/devices.py`.

## Catatan implementasi panel Perangkat saat ini

- Kolom "Pasien" menampilkan `"Terpasang (pasien di luar halaman)"` bila alat
  ter-assign ke pasien yang tidak ada di halaman pasien yang sedang dimuat
  (`DeviceResponse` hanya bawa `patient_id`, bukan nama). Hilang sendiri setelah
  item #2 (device list ikut bawa nama pasien) atau #1.
- Rotasi signing key / ubah status / pindah pasien **ditolak backend (409)** bila
  ada sesi monitoring aktif — UI memunculkan pesannya, tidak mem-block di klien.
