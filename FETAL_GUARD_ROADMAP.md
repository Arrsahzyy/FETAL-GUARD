# FETAL-GUARD Roadmap, Milestones, and Execution Checklist

Dokumen ini adalah roadmap utama FETAL-GUARD. Gunakan bersama `AGENTS.md`.

Tujuan dokumen:

- Menentukan milestone teknis sampai sistem bekerja valid dan optimal.
- Menjaga prioritas agar tim tidak mengerjakan fitur di luar tahap.
- Menjadi checklist eksekusi untuk AI agent dan developer.
- Menyimpan acceptance criteria yang bisa diverifikasi.

## 1. North Star

FETAL-GUARD harus menjadi prototype wearable yang:

- Mengambil sinyal dari piezo, FSR408, dan MAX30102 secara stabil.
- Mengirim data ke backend secara aman dan dapat dilacak.
- Menampilkan data pasien dan nakes secara terpisah sesuai role.
- Menjalankan analisis awal hybrid rule + AI dengan bahasa skrining, bukan diagnosis.
- Memiliki jalur validasi teknis dan klinis yang jujur.
- Siap didemokan sebagai PKM-KC tanpa mengklaim sebagai alat medis final.

## 2. Roadmap 6 Tahap

| Tahap | Fokus | Output Utama | Status |
|---|---|---|---|
| 1 | PoC sensor dan power | ESP32 membaca piezo/FSR/MAX30102, serial plot, power aman | Belum lengkap |
| 2 | Akuisisi data dan dashboard dasar | Backend menerima sesi, dashboard pasien/nakes real contract | Berjalan |
| 3 | Preprocessing dan deteksi sinyal | Filter, estimasi FHR awal, signal quality index | Belum lengkap |
| 4 | Model AI awal | Rule layer + CNN-LSTM baseline dengan dataset publik | Belum lengkap |
| 5 | Validasi referensi klinis | Perbandingan dengan CTG/Doppler/toco, ethical clearance | Belum mulai |
| 6 | Integrasi wearable final | Sabuk V2, casing, PCB, demo end-to-end | Belum mulai |

Tahap aktif repository saat ini adalah Tahap 2 untuk software, dengan banyak pekerjaan Tahap 1 hardware yang masih harus dibuktikan.

## 3. Milestone 0 - Repository Foundation

Tujuan: memastikan repo stabil, dapat dijalankan lokal, dan tidak membingungkan AI/developer.

Checklist:

- [x] Root Markdown dikonsolidasikan menjadi `AGENTS.md` dan `FETAL_GUARD_ROADMAP.md`.
- [x] Frontend React/Vite dapat lint dan build.
- [x] Backend FastAPI memiliki test suite.
- [x] Role pasien/nakes/admin tidak diposisikan sebagai UI yang sama.
- [ ] Dokumentasi API disinkronkan ulang dengan source backend bila `api/openapi.yaml` tertinggal.
- [ ] Tambahkan visual QA workflow yang konsisten, idealnya Playwright atau Browser plugin.
- [ ] Pisahkan dokumen lama ke arsip non-root bila masih dibutuhkan.

Acceptance criteria:

- `Get-ChildItem -File -Filter *.md` di root hanya menampilkan dua file.
- `npm.cmd run lint` lulus.
- `npm.cmd run build` lulus.
- Backend pytest lulus dari folder `backend/`.

## 4. Milestone 1 - Auth, RBAC, and Admin Registration Flow

Tujuan: memastikan akses pasien, nakes, dan admin aman serta scalable.

Checklist:

- [x] Auth frontend memakai backend JWT.
- [x] Route guard memisahkan pasien dan nakes.
- [x] Pasien tidak bisa mengakses endpoint clinician.
- [x] Nakes login melalui portal nakes terpisah dari portal pasien.
- [x] Admin GUI untuk membuat, menonaktifkan, mengaktifkan ulang, dan mengelola akun nakes.
- [x] Admin action audit log untuk provisioning, aktivasi/nonaktivasi, dan reset password nakes.
- [x] Password onboarding/reset untuk nakes, bukan password statis di kode.
- [x] Akun nonaktif tidak dapat login dan token lama ditolak oleh backend.
- [x] Rate limit login berbasis database untuk membatasi percobaan password salah.
- [x] Frontend membersihkan session lokal ketika token ditolak atau akun dinonaktifkan.
- [x] Refresh token/session rotation policy.
- [x] Data access scoping dasar: nakes hanya melihat pasien dan alert yang di-assign oleh admin.
- [x] Supervisor fasilitas dapat melihat scope fasilitas tanpa membuka data fasilitas lain.

Acceptance criteria:

- Admin dapat mendaftarkan nakes tanpa edit kode.
- Patient role mendapat 403 untuk endpoint nakes/admin.
- Clinician role tidak mendapat akses admin.
- Admin audit event tersimpan untuk perubahan akun nakes.
- Tidak ada password atau secret tertulis di source/docs.

## 5. Milestone 2 - Patient App Readiness

Tujuan: aplikasi pasien informatif, aman, tidak alarmis, dan siap menerima hardware data.

Checklist:

- [x] Portal pasien terpisah dari portal nakes.
- [x] Monitoring screen tidak memakai kata "simulasi" sebagai label utama user-facing.
- [x] Hybrid AI analysis ditonjolkan sebagai fitur utama, tetapi tetap sebagai skrining awal.
- [x] History screen memiliki export PDF dan share flow yang tidak terhalang bottom navbar.
- [ ] Semua copy pasien parity ID/EN.
- [x] Empty state jujur untuk perangkat belum terhubung.
- [ ] Device pairing BLE/WiFi provisioning flow siap.
- [ ] Offline/poor connection state.
- [ ] Riwayat sesi memakai data backend real, bukan mock.
- [ ] PDF export menampilkan disclaimer medis dan sumber data.
- [ ] Notification severity tidak alarmis: rutin, perlu cek, segera hubungi nakes.

Acceptance criteria:

- Pasien dapat login/register, lengkapi profil, mulai/tutup sesi sesuai backend contract.
- Semua tombol utama dapat diakses di mobile dan laptop viewport.
- Tidak ada teks diagnosis atau klaim akurasi.
- Bahasa Indonesia dan English benar-benar mengganti seluruh copy user-facing.

## 6. Milestone 3 - Clinician Dashboard Readiness

Tujuan: dashboard nakes menjadi alat kerja operasional, bukan halaman demo.

Checklist:

- [x] Dashboard nakes fetch pasien dan alert dari backend.
- [x] FHR/signal quality yang belum tersedia ditampilkan sebagai "Belum tersedia dari sistem", bukan angka palsu.
- [x] Alert mapping memakai `patient_id`, bukan nama pasien.
- [x] Panel detail pasien hanya menampilkan alert pasien terpilih.
- [x] Dashboard nakes memiliki status kesegaran data dan refresh.
- [x] Copy dashboard nakes ID/EN parity untuk area utama.
- [x] Pagination server-side untuk daftar pasien.
- [x] Search server-side dasar untuk nama pasien.
- [x] Filter risiko/status server-side untuk skala production.
- [x] Patient-clinician assignment scope dikelola admin dan diterapkan pada patient list, alert list, dan alert acknowledgement.
- [x] Alert acknowledgement menyimpan actor, timestamp, dan note.
- [x] Alert lifecycle menyimpan status resolusi seperti in review, resolved, false positive, archived.
- [x] Patient detail menampilkan ringkasan sesi sensor saat backend menyediakan data.
- [x] Real-time update via polling event terkontrol dengan cursor, backoff, dan cleanup lifecycle.
- [ ] Report export terhubung ke data real dan audit log.
- [ ] QA responsive untuk desktop, tablet, dan mobile.

Acceptance criteria:

- Klik alert membuka pasien yang benar.
- Nakes melihat prioritas alert tanpa campur data pasien.
- Dashboard tetap usable saat data kosong, API error, atau data stale.
- Tidak ada debug/developer content di UI nakes.

## 7. Milestone 4 - Backend Data Contract and Production Hardening

Tujuan: backend siap menerima data perangkat dan mendukung UI real.

Checklist:

- [x] Auth dan role guard dasar.
- [x] Endpoint pasien dan clinician dasar.
- [x] Test backend berjalan.
- [x] Account status guard untuk akun nakes/admin yang dinonaktifkan.
- [x] Admin provisioning, reset password, aktivasi/nonaktivasi, dan audit log diuji.
- [x] Clinician patient list memiliki pagination/search contract.
- [x] Patient-clinician assignment table dan admin API/UI untuk membatasi scope data nakes.
- [x] Device registry: satu pasien dapat memiliki device yang terdaftar.
- [ ] Session raw data table atau time-series storage.
- [x] Sensor summary per session: FHR estimate, signal quality, contraction indicator, maternal HR.
- [x] Alert lifecycle: open, acknowledged, in review, resolved, false positive, archived.
- [x] Audit trail admin untuk lifecycle akun nakes.
- [ ] Audit trail nakes umum di luar acknowledgement alert.
- [x] Pagination/search untuk endpoint clinician patients.
- [x] Scoped clinician alerts berdasarkan assignment pasien-nakes.
- [x] Filter/sort klinis untuk endpoint clinician.
- [ ] MQTT ingestion service atau gateway API.
- [ ] Data retention policy.
- [ ] Export/report endpoint.
- [ ] API documentation disinkronkan otomatis atau semi-otomatis.

Acceptance criteria:

- Backend tidak mengandalkan mock untuk fitur utama.
- Contract frontend dan backend jelas, diuji, dan tidak berubah diam-diam.
- API error punya format konsisten.
- Role guard dan ownership diuji.

## 8. Milestone 5 - Hardware PoC and Firmware

Tujuan: membuktikan sensor dan power bekerja sebelum klaim software diperluas.

Checklist hardware:

- [ ] Rakit piezo + LM324 pre-amp di breadboard.
- [ ] Rakit FSR408 voltage divider.
- [ ] Integrasikan MAX30102 via I2C.
- [ ] Validasi semua channel ESP32.
- [ ] Evaluasi ADC internal ESP32 vs external ADC ADS1115.
- [ ] Proteksi ADC dari tegangan negatif dan noise.
- [ ] Uji power rail 3.3 V dan 5 V.
- [ ] Ukur arus idle, BLE, WiFi, dan transmisi.
- [ ] Uji pemanasan casing dan baterai.

Checklist firmware:

- [ ] Arduino/PlatformIO sketch membaca semua sensor.
- [ ] Serial output terstruktur.
- [ ] Timestamp dan device/session id.
- [ ] Buffering saat koneksi putus.
- [ ] Bandpass filter awal untuk piezo.
- [ ] Feature extraction ringan.
- [ ] MQTT publish atau BLE notify.
- [ ] Paket data dengan versi schema.

Acceptance criteria:

- Semua sensor terbaca stabil di serial monitor.
- Data satu sesi dapat direkam dan diplot.
- Tidak ada panas berlebih selama sesi uji.
- Format payload terdokumentasi dan dapat diparse backend.

## 9. Milestone 6 - Signal Processing and AI Pipeline

Tujuan: membuat analisis hybrid yang dapat diuji, bukan hanya visual.

Checklist:

- [x] Dataset publik dikurasi: CTU-UHB CTG, FPCGDB/PhysioNet, dan fetal ECG reference sesuai kebutuhan.
- [x] Preprocessing pipeline Python awal: cleaning, windowing, feature extraction, dan signal quality scaffold.
- [ ] Dataset publik diunduh lokal, provenance dicatat, dan metadata label diaudit.
- [ ] Baseline FHR estimation: peak detection dan/atau autocorrelation.
- [ ] Signal Quality Index untuk membedakan data valid vs noise.
- [ ] Rule-based layer untuk threshold klinis display.
- [x] CNN-LSTM multimodal implementation dan training runner dengan split berbasis subjek.
- [x] Safety layer untuk quality, uncertainty, technical output range, dan insufficient-signal gate.
- [ ] API inference yang deterministic untuk test mode.
- [x] Model artifact manifest, SHA-256 verification, versioning, dan validation/deployment gate.
- [ ] Evaluation script: MAE FHR, recall/precision, confusion matrix jika label tersedia.
- [x] Reason-code contract awal untuk signal quality, uncertainty, dan invalid technical output.

Acceptance criteria:

- Pipeline dapat dijalankan ulang dari data input ke output.
- Tidak ada klaim performa tanpa hasil evaluasi.
- Output AI memakai label aman: pemantauan rutin, perlu observasi, segera tinjau.
- UI menampilkan keterbatasan validasi dengan jujur.

## 10. Milestone 7 - Connectivity and Real-Time Flow

Tujuan: menghubungkan hardware, backend, dan UI secara end-to-end.

Checklist:

- [ ] MQTT broker dipilih: Mosquitto/HiveMQ/cloud lain.
- [ ] Topic convention: device raw, session summary, alert result.
- [ ] QoS policy: raw stream vs critical alert.
- [ ] Backend subscriber/gateway.
- [ ] Offline buffer pada ESP32 atau gateway mobile.
- [ ] BLE-to-phone gateway proof-of-concept.
- [ ] Secure pairing/provisioning plan.
- [ ] Latency measurement dari sensor ke dashboard.
- [ ] Data loss/packet loss measurement.
- [ ] Real-time UI update strategy.

Acceptance criteria:

- Satu sesi hardware dapat muncul di aplikasi pasien dan dashboard nakes.
- Sistem tetap aman saat koneksi putus.
- Latency dan packet loss terukur, bukan diasumsikan.

## 11. Milestone 8 - Wearable Integration

Tujuan: membuat sabuk yang nyaman dan repeatable untuk pengambilan data.

Checklist:

- [ ] Sabuk V1 untuk PoC sensor.
- [ ] Sabuk V2 dengan pocket sensor stabil.
- [ ] Posisi piezo P1-P4 konsisten.
- [ ] FSR di area fundus sebagai indikator tekanan mekanik.
- [ ] MAX30102 mudah dipakai dan tidak mengganggu.
- [ ] Casing main hub aman, tidak panas, tidak tajam.
- [ ] Cable routing dan strain relief.
- [ ] Material kontak kulit aman.
- [ ] Usability test internal 1-2 jam.

Acceptance criteria:

- Sensor tidak mudah bergeser.
- Pengguna dapat memasang sabuk dengan instruksi sederhana.
- Sinyal lebih stabil dibanding tanpa pocket/fixture.

## 12. Milestone 9 - Validation Ladder

Tujuan: memastikan klaim proyek tumbuh sesuai bukti.

Tahap validasi:

1. Bench testing:
   - Uji sensor, ADC, power, noise, filter.
   - Input dapat berupa signal generator atau speaker kecil.

2. Dataset/signal playback:
   - Putar sinyal fetal heart/audio dataset untuk menguji pipeline.
   - Cocok untuk membuktikan akuisisi dan preprocessing awal.

3. Phantom/manikin:
   - Media sederhana seperti balon air + speaker sebagai phantom awal.
   - Tujuan: repeatability, bukan klaim klinis.

4. Relawan non-klinis:
   - Hanya untuk ergonomi, koneksi, dan noise gerak.
   - Jangan klaim performa fetal monitoring dari tahap ini.

5. Uji terbatas klinis:
   - Wajib kolaborasi nakes dan ethical clearance.
   - Bandingkan dengan CTG/Doppler/tocotransducer.
   - Ground truth harus jelas.

Metrics yang boleh dipakai jika data tersedia:

- FHR MAE terhadap referensi.
- Signal quality valid/invalid rate.
- Latency sensor ke dashboard.
- Packet loss MQTT/BLE/WiFi.
- Battery runtime.
- Usability score.
- Precision/recall hanya jika label ground truth valid tersedia.

Acceptance criteria:

- Setiap klaim punya sumber data.
- Laporan validasi membedakan technical validation dan clinical validation.
- UI dan proposal tidak menyebut "terbukti klinis" sebelum uji klinis benar-benar selesai.

## 13. Production Readiness Checklist

Security and privacy:

- [ ] HTTPS/TLS untuk API.
- [ ] Secure MQTT/TLS jika digunakan.
- [x] Password hashing dan reset flow dasar untuk pasien/nakes/admin.
- [x] RBAC dasar pasien/nakes/admin.
- [x] Audit log admin untuk lifecycle akun nakes.
- [x] Rate limit login dan proteksi brute force dasar.
- [x] Token invalid/inactive-account cleanup di frontend.
- [x] Access token pendek, refresh token rotation, dan revoke refresh token saat logout.
- [x] Clinic/team scoped authorization dasar melalui patient-clinician assignment.
- [ ] Data minimization.
- [ ] Retention and deletion policy.
- [ ] No secrets in frontend bundle.

Scalability:

- [x] Server-side pagination dasar untuk admin clinicians dan clinician patients.
- [ ] Query indexing.
- [ ] Background worker untuk ingestion/AI.
- [ ] Queue atau stream untuk sensor data.
- [ ] Monitoring/logging.
- [ ] Backup and restore.

Reliability:

- [ ] Offline buffer.
- [ ] Retry strategy.
- [ ] Idempotent ingestion.
- [ ] Stale data indicators.
- [x] Device health status dasar melalui status registry dan `last_seen_at`.
- [ ] Alert deduplication.

UX:

- [ ] Pasien: simple, calm, guided.
- [x] Nakes: scan-friendly, operational, role-aware untuk dashboard dasar.
- [x] Admin: account management and audit untuk lifecycle akun nakes.
- [ ] Full ID/EN parity.
- [ ] Responsive desktop/mobile QA.

Regulatory and ethics:

- [ ] Medical disclaimer visible.
- [ ] Ethical clearance before clinical data collection.
- [ ] Consent flow.
- [ ] Data processing agreement if involving clinics.
- [ ] No clinical performance claims without validation.

## 14. Near-Term Priority Backlog

Urutan kerja yang direkomendasikan:

1. Complete BLE/WiFi provisioning with real hardware or gateway proof.
2. MQTT/BLE ingestion proof-of-concept.
3. Signal processing baseline and SQI.
4. Visual QA automation with desktop/mobile screenshots.
5. Documentation/API contract sync.

## 15. Verification Commands

Run this after software changes:

```powershell
npm.cmd run lint
npm.cmd run build
cd backend
.\venv\Scripts\pytest.exe -p no:cacheprovider
```

Useful local health checks:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/ -TimeoutSec 5
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/docs -TimeoutSec 5
```

Root docs check:

```powershell
Get-ChildItem -File -Filter *.md | Select-Object Name
```

Expected root docs:

```text
AGENTS.md
FETAL_GUARD_ROADMAP.md
```

## 16. Decision Log

- Root documentation is consolidated into two Markdown files to reduce AI/context drift.
- Backend source of truth is FastAPI in this repository, even if older proposal docs mention Node.js.
- Medical copy must use screening and indication language.
- Missing sensor values must be shown as unavailable, not mocked.
- Admin-managed clinician registration is the scalable production path.
- Admin can now provision, deactivate/reactivate, reset clinician passwords, and review audit logs without editing code.
- Clinician alerts now store acknowledgement actor, timestamp, and follow-up note, but not full resolution lifecycle yet.
- Login is now throttled after repeated failed attempts using a database-backed attempt table.
- Login now issues short-lived access tokens plus hashed refresh tokens stored in the database; refresh tokens rotate on use and are revoked on logout.
- Clinician dashboard data is now scoped by admin-managed patient-clinician assignments; unassigned patient records and alerts are hidden from nakes endpoints.
- Clinician patient and alert endpoints now support server-side filtering/sorting for search, risk, active session status, alert acknowledgement, patient scope, and priority ordering.
- Facility access now uses explicit organization context, time-bounded membership, and patient-clinician assignment records; clinicians see assigned patients while supervisors remain facility-scoped.
- PostgreSQL deployments require tenant RLS policies and restricted API-role table privileges to pass readiness checks before serving traffic.
- Patient and clinician screens use a scoped realtime event cursor with bounded polling/backoff; this is a software event channel and does not claim that hardware MQTT/BLE ingestion is complete.
- Alerts now have lifecycle status beyond acknowledgement: open, acknowledged, in_review, resolved, false_positive, and archived.
- Device registry now supports admin-managed device registration/assignment, patient-owned device listing, active-device enforcement on uploads, and `last_seen_at`.
- Session sensor summaries now store available FHR estimate, maternal HR, signal quality, contraction indicator, sample count, source, and simulation flag without inventing missing clinical values.
- Patient device UI now reads backend device registry, blocks unassigned device pairing, removes fallback sample telemetry from patient screens, and shows honest device-empty states before monitoring starts.
- Hybrid AI infrastructure now includes a real multi-branch CNN-LSTM builder, strict multimodal dataset contract, validity masks, subject-safe splits, training runner, artifact hash/manifest gates, conservative safety postprocessing, database job/result/review lifecycle, scoped patient/clinician APIs, audit, and realtime events. No trained or clinically validated artifact exists yet; hardware adapters, reviewed labels, an isolated worker, and analytical/clinical validation remain required.
- Patient monitoring now consumes patient-visible hybrid results as a safe, review-gated timeline; the clinician patient-detail panel consumes the corresponding clinician feed and records review decisions. A dedicated publication worker promotes only reviewed results from active `clinical_validated` clinician-slot models. This closes the display/publication path but does not complete hardware-v2 adaptation or inference execution.
- Local BLE gateway source path now exists: the ESP32-S3 sketch advertises the registered device UID and emits newline-framed telemetry v1, while Capacitor or Web Bluetooth forwards authenticated packets to FastAPI. A shared golden fixture verifies frontend parsing and exactly-once backend storage. Firmware compile/flash and physical end-to-end measurements remain required before the hardware/connectivity checkboxes can be completed.
- A reproducible `android-local` debug build now targets an explicit private-LAN FastAPI address, includes debug-only cleartext policy, keeps release HTTPS enforcement intact, and produces an installable APK for physical BLE-to-backend testing. This establishes the test artifact, not proof of physical sensor communication.
- Hardware validation must precede strong AI/clinical claims.
- Canonical production deployment blueprint lives in `docs/ops/digitalocean-production-blueprint.md`.
- Azure for Students deployment path lives in `docs/ops/azure-student-deployment-blueprint.md`.
