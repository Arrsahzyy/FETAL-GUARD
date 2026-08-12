# Prompt for Execution Agent

Kamu adalah Execution Agent untuk project Fetal Guard di `E:\PROJECT\PKM KC ACA`.

Tugasmu adalah memperbaiki masalah yang ditemukan dalam `docs/ai-discovery-report.md`. Jangan mengulang discovery dari nol, tetapi tetap baca file terkait sebelum mengubahnya.

## Aturan Utama

1. Ikuti `AGENTS.md` dan `docs/ai/CONTEXT.md` sebelum mengubah source code.
2. Kerjakan batch secara berurutan. Jangan lompat batch kecuali user meminta.
3. Buat perubahan kecil, terverifikasi, dan mudah direview.
4. Jangan membuat klaim medis berlebihan. Gunakan wording "skrining awal", "indikasi", "membantu pemantauan", "perlu observasi".
5. Jangan mengubah threshold klinis FHR 110-160 bpm tanpa approval eksplisit.
6. Jangan menambahkan dependency baru tanpa menjelaskan alasan dan meminta approval.
7. Jangan menghapus sensor dari arsitektur.
8. Jangan mengubah AI stub menjadi klaim model real. Endpoint AI saat ini masih stub dan harus tetap jelas sebagai stub/simulasi sampai pipeline validasi ada.
9. Jangan menampilkan password/token/isi `.env`.
10. Gunakan command Windows yang sesuai: `npm.cmd`, bukan `npm`, bila terkena PowerShell ExecutionPolicy.

## Konteks Project

- Frontend: React + Vite + Tailwind + React Router + Capacitor.
- Backend aktual: FastAPI + SQLAlchemy + SQLite + Alembic + JWT.
- API client utama: `src/services/api.js`.
- Auth state utama: `src/context/AuthContext.jsx`.
- Patient/mobile screens: `src/screens/mobile/`.
- Clinician dashboard: `src/screens/clinician/ClinicianDashboard/`.
- Backend entry: `backend/main.py`.
- Backend routes: `backend/api/routes/`.
- API documentation `api/openapi.yaml` saat ini tidak sinkron dengan backend aktual. Jangan menganggap file itu source of truth tanpa verifikasi route FastAPI.

## Definition of Done Global

- `npm.cmd run lint` lulus.
- `npm.cmd run build` lulus, kecuali ada blocker yang harus dilaporkan jelas.
- Dari folder `backend`, `.\venv\Scripts\pytest.exe -p no:cacheprovider` lulus.
- Tidak ada source mock data yang tampil sebagai data klinis real tanpa label simulasi.
- Patient dan clinician domain tetap terpisah.
- Wording klinis tetap konservatif dan tidak diagnostik.

## Batch 1: Security dan Runtime Blocker

Tujuan: tutup risiko auth/role dan jalur mock auth.

File utama:

- `backend/api/routes/auth.py`
- `backend/schemas/user.py`
- `backend/tests/test_auth.py`
- `src/App.jsx`
- `src/screens/mobile/LoginScreen/LoginScreen.jsx`
- `src/screens/mobile/index.js`
- `capacitor.config.ts`
- `api/openapi.yaml`

Instruksi:

1. Restrict public registration agar hanya dapat membuat role patient.
2. Jika request register mengirim `role=clinician`, backend harus menolak dengan status code yang jelas atau mengabaikan role dan tetap membuat patient. Pilih pendekatan yang paling aman dan testable; rekomendasi: reject dengan 400/403.
3. Tambahkan regression test backend untuk memastikan public register tidak bisa membuat clinician.
4. Pastikan clinician account dibuat lewat seed/admin flow, bukan public register.
5. Hapus atau deprecate `LoginScreen` lama yang memakai `setTimeout` mock auth. Jika dihapus, bersihkan export dan import yang terkait.
6. Pastikan route `/login` tetap memakai `AuthScreen` dan real `AuthContext`.
7. Review `capacitor.config.ts`: production build tidak boleh default ke `allowMixedContent` dan debugging enabled tanpa environment guard.
8. Update status `api/openapi.yaml`: regenerate dari FastAPI atau beri catatan jelas bahwa file itu aspirational/roadmap, bukan implemented contract. Jangan membuat frontend baru berdasarkan endpoint yang belum ada.

Verifikasi batch:

- Test auth backend lulus.
- Search repo memastikan tidak ada jalur login user-facing yang masih memakai mock credential/setTimeout sebagai auth real.
- Lint frontend lulus.

## Batch 2: Frontend-Backend Contract Fix

Tujuan: sinkronkan fitur user-facing dengan endpoint real.

File utama:

- `src/services/api.js`
- `src/context/AuthContext.jsx`
- `src/screens/mobile/ProfileScreen.jsx`
- `src/screens/mobile/HomeScreen/HomeScreen.jsx`
- `src/screens/mobile/HistoryScreen/HistoryScreen.jsx`
- `src/screens/mobile/NotificationsScreen.jsx`
- `src/screens/mobile/SettingsScreen.jsx`
- `backend/api/routes/patients.py`
- `backend/api/routes/sessions.py`
- `backend/api/routes/clinician.py`
- `backend/models/notification.py`
- `backend/schemas/clinician.py`

Instruksi:

1. Tambahkan endpoint update patient profile jika belum ada, misalnya `PATCH /patients/me`.
2. Hubungkan `ProfileScreen` save action ke endpoint real. Hapus `setTimeout` sebagai save palsu.
3. Hapus hardcoded fallback patient/device/recent history dari `HomeScreen`. Ganti dengan loading, empty, atau unavailable state.
4. Hubungkan `HistoryScreen` ke data session real bila endpoint sudah cukup. Jika belum cukup, disable filter/export/share yang belum real dengan state UI yang jujur.
5. Jangan biarkan date filter terlihat aktif bila logic belum memfilter tanggal.
6. Buat notification contract real bila notifikasi akan dipakai: list notifications dan acknowledge/read endpoint.
7. Tambahkan field ack/read di model notification bila ack persist diperlukan.
8. Perluas `/clinician/alerts` agar membawa patient identity yang cukup: minimal `patient_id`, `patient_name`, `session_id`, `risk`, `message`, `created_at`, dan ack state bila ada.
9. Untuk `SettingsScreen`, sembunyikan atau labeli jelas device/MQTT actions yang belum punya backend/device real.
10. Centralize response normalization di API layer atau utility supaya snake_case/camelCase mapping tidak tersebar.

Verifikasi batch:

- Profile update persist setelah refresh/login ulang.
- History tidak menampilkan kontrol palsu.
- Notifications tidak hanya ack local bila UI mengatakan ack berhasil.
- Clinician alerts tidak mengarang patient identity.

## Batch 3: Backend Validation dan Data Integrity

Tujuan: backend lebih aman untuk data monitoring.

File utama:

- `backend/api/routes/sessions.py`
- `backend/schemas/sensor_data.py`
- `backend/models/session.py`
- `backend/models/sensor_data.py`
- `backend/models/notification.py`
- `backend/api/routes/clinician.py`
- `backend/core/config.py`
- `backend/main.py`

Instruksi:

1. Tambahkan guard di `POST /sessions` agar satu patient tidak memiliki multiple active sessions tanpa keputusan eksplisit.
2. Jika active session sudah ada, return 409 dengan pesan jelas atau reuse session. Rekomendasi awal: 409 supaya state machine eksplisit.
3. Perketat schema sensor upload. Minimal field yang perlu divalidasi: timestamp, fhr, contraction/uterine activity, maternal_hr, spo2, imu/movement bila dipakai, dan `source`.
4. Tambahkan `source` atau `is_simulated` agar data mock tidak bercampur sebagai data real.
5. Standardize error response agar frontend bisa menampilkan pesan konsisten.
6. Pindahkan CORS origins ke config/env.
7. Pastikan production secret key fail-fast bila tidak ada.
8. Review penggunaan `Base.metadata.create_all`; gate untuk dev/test atau pastikan Alembic menjadi sumber migration.
9. Tambahkan pagination dan query yang lebih efisien untuk `/clinician/patients`. Jangan load seluruh histori session untuk semua pasien bila dataset mulai besar.

Verifikasi batch:

- Tests backend baru mencakup active session conflict, invalid sensor payload, source simulation, dan clinician pagination/role guard.
- Existing 25 tests tetap lulus.

## Batch 4: Frontend State, Loading, Error, Empty

Tujuan: UI tidak lagi terlihat seperti prototype yang memalsukan data.

File utama:

- `src/screens/mobile/HomeScreen/HomeScreen.jsx`
- `src/screens/mobile/MonitoringScreen/MonitoringScreen.jsx`
- `src/screens/mobile/HistoryScreen/HistoryScreen.jsx`
- `src/screens/mobile/NotificationsScreen.jsx`
- `src/screens/mobile/ProfileScreen.jsx`
- `src/screens/mobile/SettingsScreen.jsx`
- `src/services/api.js`
- `src/App.jsx`
- `src/context/AuthContext.jsx`

Instruksi:

1. Buat pola loading/error/empty state konsisten.
2. Tambahkan global toast atau notification context ringan untuk API/network error.
3. Pakai `getApiErrorMessage` dari `src/services/api.js` di UI, bukan hanya console/error local yang diam.
4. Jangan tampilkan angka klinis dummy saat data belum tersedia.
5. Untuk data mock yang memang dibutuhkan pada dev, tampilkan label mode simulasi yang jelas.
6. Pastikan loading state selesai juga ketika request gagal.
7. Audit semua `console.log`, `alert()`, dan placeholder action. Ganti dengan feedback UI yang sesuai atau hapus bila debug-only.

Verifikasi batch:

- Matikan backend dan buka frontend: UI harus menampilkan error state yang jelas, bukan data palsu.
- Empty state tidak menampilkan nama pasien/angka vital dummy.
- Lint lulus.

## Batch 5: UI/UX dan Accessibility

Tujuan: polish pengalaman pasien dan nakes tanpa mengubah scope klinis.

File utama:

- `src/components/AuthScreen/AuthScreen.jsx`
- `src/components/EmergencyButton.jsx`
- `src/components/FeedbackModal.jsx`
- `src/screens/mobile/HomeScreen/HomeScreen.jsx`
- `src/screens/mobile/SettingsScreen.jsx`
- `src/screens/mobile/ProfileScreen.jsx`
- `src/index.css`
- `src/styles/design-tokens.css`

Instruksi:

1. Tambahkan `aria-label` untuk icon-only buttons.
2. Perbaiki tab semantics di auth screen: `role=tablist`, `role=tab`, `aria-selected`, dan `aria-controls`.
3. Tambahkan modal focus management untuk emergency dan feedback modal: initial focus, Escape close, focus return, `aria-modal`.
4. Review toggle/switch settings agar punya semantic button/switch, visible focus, disabled/loading state.
5. Review wording medis. Hindari "diagnosis", "abnormal", "gawat janin", "penyakit", dan klaim "lebih akurat" kecuali user memberi approval eksplisit.
6. Gunakan copy konservatif: "riwayat kesehatan", "indikasi awal", "perlu observasi", "membantu pemantauan".
7. Stabilkan typography global; hindari body text yang bergantung ke `vw`.
8. Pastikan responsive layout tidak overlap dan tetap usable di mobile.

Verifikasi batch:

- Keyboard-only navigation untuk login, modal, settings toggle bisa digunakan.
- Tidak ada wording diagnostik berlebihan.
- Lint lulus.

## Batch 6: Animation dan Performance Polish

Tujuan: animasi halus tetapi tidak menipu data.

File utama:

- `src/components/FHRDisplay.jsx`
- `src/components/WaveformChart.jsx`
- `src/screens/mobile/HomeScreen/HomeScreen.jsx`
- `src/screens/mobile/MonitoringScreen/MonitoringScreen.jsx`
- CSS terkait animation/reduced motion.

Instruksi:

1. Tambahkan cleanup `requestAnimationFrame` di `FHRDisplay`.
2. Tambahkan cleanup/gating animation loop di `WaveformChart`.
3. Jangan generate random waveform saat data kosong. Tampilkan empty chart state.
4. Pastikan semua animasi menghormati `prefers-reduced-motion`.
5. Jika membuat pulse FHR dinamis, ikat durasi ke BPM tetapi tetap jelas bahwa angka berasal dari data real atau simulasi.
6. Jangan menambah dependency animasi baru tanpa approval.

Verifikasi batch:

- Route berpindah tidak meninggalkan animation loop.
- Chart kosong tidak terlihat seperti sinyal real.
- Reduced motion user tidak mendapat animasi intens.

## Batch 7: Cleanup, Tests, dan Documentation

Tujuan: tutup technical debt dan pastikan agent berikutnya tidak mengulang kesalahan.

Instruksi:

1. Hapus dead code yang sudah tidak dipakai setelah auth/profile/history/notification real.
2. Tandai dev-only mock fixtures dengan nama folder/file yang jelas.
3. Tambahkan tests backend untuk:
   - public register tidak bisa membuat clinician,
   - patient tidak bisa akses clinician endpoints,
   - active session conflict,
   - invalid sensor payload ditolak,
   - notification ack persist bila fitur ack dibuat.
4. Tambahkan dokumentasi env minimal:
   - `VITE_API_BASE_URL`,
   - backend `SECRET_KEY`,
   - CORS origins,
   - dev vs production mode.
5. Update `docs/ai/CONTEXT.md` atau dokumentasi project hanya jika user menyetujui update dokumentasi tambahan.
6. Jalankan full verification:
   - `npm.cmd run lint`
   - `npm.cmd run build`
   - dari `backend`: `.\venv\Scripts\pytest.exe -p no:cacheprovider`

## Catatan Penting

- Jangan mengerjakan fitur AI real/CNN-LSTM dalam batch ini.
- Jangan mengubah threshold klinis tanpa approval.
- Jangan mengisi data clinician dashboard dengan estimasi palsu. Jika backend belum menyediakan FHR/signal quality, tampilkan `Belum tersedia` atau placeholder jujur.
- Jangan menampilkan istilah developer seperti API endpoint/base URL/prototype di layar nakes/pasien kecuali berada di mode admin/developer yang eksplisit.
- Patient dan clinician domain harus tetap bersih: patient registration bukan clinician provisioning, dan clinician dashboard tidak boleh mengarang data patient.
