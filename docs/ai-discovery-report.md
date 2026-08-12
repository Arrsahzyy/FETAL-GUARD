# Discovery Report

Audit ini dilakukan sebagai discovery-only. Tidak ada source code aplikasi yang diubah. Fokus audit mengikuti urutan yang diminta: frontend/UI, backend/API, lalu integrasi frontend-backend.

## 1. Project Summary

### Stack

- Frontend: React 19.2, Vite 7.2, React Router 7.18, Tailwind CSS 3.4, Axios, MQTT client, Capacitor 8.
- Backend aktual di repository: FastAPI, SQLAlchemy, SQLite, Alembic, JWT, bcrypt/passlib, pytest.
- Dokumentasi `AGENTS.md` menyebut Backend/API sebagai Node.js + MQTT broker, tetapi kode aktual memiliki backend FastAPI di `backend/`. Ini adalah mismatch dokumentasi yang perlu dirapikan.
- Mobile target: Capacitor Android dengan `webDir: dist`.
- API client utama: `src/services/api.js`.

### Struktur Folder Penting

- `src/main.jsx`: entry point frontend.
- `src/App.jsx`: router utama dan role-based layout.
- `src/context/AuthContext.jsx`: auth state, login/register/logout, profile hydration.
- `src/services/api.js`: Axios instance, token persistence, endpoint wrapper.
- `src/screens/mobile/`: layar pasien/mobile.
- `src/screens/clinician/ClinicianDashboard/`: dashboard nakes/clinician.
- `src/components/`: reusable UI dan visual monitoring.
- `src/hooks/`: mock sensor, Bluetooth, MQTT.
- `src/services/MockSensorService.js`: simulasi sensor dan sinkronisasi session ke backend.
- `backend/main.py`: FastAPI app entry point.
- `backend/api/routes/`: route `auth`, `patients`, `sessions`, `clinician`, `ai`.
- `backend/models/` dan `backend/schemas/`: SQLAlchemy models dan Pydantic schemas.
- `api/openapi.yaml`: API spec, tetapi saat ini tidak sinkron dengan FastAPI aktual.

### Cara Menjalankan Project

- Frontend dev: `npm.cmd run dev`
- Frontend lint: `npm.cmd run lint`
- Frontend build: `npm.cmd run build`
- Backend tests: dari folder `backend`, jalankan `.\venv\Scripts\pytest.exe -p no:cacheprovider`
- Backend server kemungkinan: `uvicorn main:app --reload` dari folder `backend`, berdasarkan struktur FastAPI.

### Verifikasi Discovery

- `npm.cmd run lint`: lulus.
- `backend\venv\Scripts\pytest.exe -p no:cacheprovider`: 25 passed, 1 deprecation warning dari Starlette/TestClient.
- `npm run lint` via PowerShell shim gagal karena ExecutionPolicy, sehingga command yang aman di environment ini adalah `npm.cmd`.
- Build frontend tidak dijalankan karena akan menulis `dist/`, sementara tahap ini discovery-only.
- Playwright/browser visual QA tidak dijalankan karena Playwright tidak tersedia di `node_modules`.

### Area Audit Utama

- Konsistensi role `patient` dan `clinician`.
- Penggunaan mock data pada layar pasien dan sensor service.
- API contract antara frontend wrapper dan backend FastAPI aktual.
- Stale API documentation di `api/openapi.yaml`.
- State loading/error/empty di layar mobile.
- Aksesibilitas modal, tab, button icon, dan toggle.
- Security dasar backend: role registration, CORS, secret key, active session guard.
- Bahasa medis: harus tetap konservatif sebagai skrining awal, bukan diagnosis.

### Data Flow Overview

1. User login/register lewat `AuthContext` dan `api.auth`.
2. Token JWT disimpan di localStorage via `src/services/api.js`.
3. Patient mobile flow menggunakan `PatientLayout` dan screens di `src/screens/mobile`.
4. Monitoring memakai `useMockSensor` dan `MockSensorService` untuk membuat session backend, mengunggah sensor chunk, dan mengakhiri session.
5. Clinician dashboard mengambil data dari endpoint `/clinician/patients` dan `/clinician/alerts`.
6. Backend menyimpan user, patient, monitoring session, sensor data, dan notification di SQLite.

## 2. Frontend Findings

| ID | Priority | File | Component/Page | Issue | Evidence | Impact | Root Cause Sementara | Recommendation |
|---|---|---|---|---|---|---|---|---|
| FE-01 | High | `src/App.jsx` | Routing | Terdapat dua login UI: route aktif memakai `AuthScreen`, sementara `LoginScreen` masih diekspor tetapi tidak diroute. | `src/App.jsx:123` memakai `AuthScreen`; `src/screens/mobile/index.js:7` masih export `LoginScreen`; `LoginScreen.jsx:54-65` masih simulasi login dengan `setTimeout`. | Risiko agent/developer berikutnya memperbaiki layar login yang salah dan meninggalkan mock auth hidup. | Migrasi auth belum membersihkan screen lama. | Hapus/deprecate `LoginScreen` atau dokumentasikan jelas bahwa `AuthScreen` adalah satu-satunya entry auth. |
| FE-02 | Critical | `src/screens/mobile/LoginScreen/LoginScreen.jsx` | Dead login screen | Login screen lama melakukan simulasi API dan tidak memakai backend auth. | `LoginScreen.jsx:54-65` memakai `setTimeout`, user dummy, dan tidak memanggil `api.auth.login`. | Jika screen ini dipakai kembali, auth real backend ter-bypass dan data user palsu muncul. | Dead code tidak dibersihkan setelah auth real dipasang. | Hapus file jika tidak dipakai, atau rewrite agar memakai `AuthContext`. Prioritas tinggi karena ini auth surface. |
| FE-03 | High | `src/screens/mobile/HomeScreen/HomeScreen.jsx` | Home patient | Fallback patient/device data di-hardcode. | `HomeScreen.jsx:28-34` membuat fallback device; `HomeScreen.jsx:40-44` fallback label; `HomeScreen.jsx:92-96` mock recent history. | User bisa melihat data palsu saat backend belum siap/gagal, berbahaya untuk konteks monitoring kesehatan. | UI mencoba tetap terisi tanpa membedakan mock vs real. | Ganti dengan loading, empty, atau unavailable state yang eksplisit. Jangan tampilkan data klinis palsu. |
| FE-04 | High | `src/screens/mobile/MonitoringScreen/MonitoringScreen.jsx` | Monitoring | Monitoring utama masih berbasis mock sensor dan auto-sync ke backend. | Import `useMockSensor` di `MonitoringScreen.jsx:6`; sensor state dari mock di `MonitoringScreen.jsx:58-67`; auto-start/stop session di `MonitoringScreen.jsx:74-82`. | Sulit membedakan data simulasi dan data device real. Bisa menyesatkan validasi. | Mock service menjadi jalur utama UI, bukan mode eksplisit. | Tambahkan mode/source indicator yang jelas, pisahkan mock/dev mode dari real device mode, dan jangan upload mock sebagai real tanpa flag kuat. |
| FE-05 | Medium | `src/screens/mobile/MonitoringScreen/MonitoringScreen.jsx` | Monitoring | Parameter dan label sensor belum konsisten dengan domain klinis yang disepakati. | Risk thresholds lokal `MonitoringScreen.jsx:114-116`; komentar SpO2 sebagai BP replacement `MonitoringScreen.jsx:126`; IMU hardcoded "Normal" di `MonitoringScreen.jsx:207`. | UI bisa memberi kesan interpretasi klinis lebih matang daripada data aktual. | Transformasi view model dibuat lokal tanpa kontrak backend/domain yang jelas. | Centralize mapping sensor display dan gunakan wording konservatif: skrining awal, observasi, belum tersedia. |
| FE-06 | Medium | `src/hooks/useMockSensor.js` | Sensor hook | Risk score dihitung lokal dengan rule sederhana dan random-ish stream. | `useMockSensor.js:179-190` risk rule; `useMockSensor.js:63` dan `useMockSensor.js:201` sync/error flags. | Risk UI bisa berubah tanpa backend/AI authority. | Logic demo tertanam di hook presentasi. | Tandai sebagai demo-only, pindahkan rule ke service simulasi, dan pastikan backend payload membawa `source=mock`. |
| FE-07 | Medium | `src/services/MockSensorService.js` | Mock sensor service | Service membuat session backend dan upload chunk secara periodik dari data simulasi. | Start interval di `MockSensorService.js:353`; create/upload/end session di `MockSensorService.js:325`, `392`, `564`; data source mock sekitar payload generation. | Database bisa tercampur data simulasi yang terlihat real di dashboard. | Tidak ada pemisahan environment atau mode simulasi yang kuat. | Tambahkan `source`, `is_simulated`, atau environment guard; tampilkan indikator simulasi di dashboard. |
| FE-08 | Medium | `src/screens/mobile/HistoryScreen/HistoryScreen.jsx` | History | Filter tanggal ada di state/UI tetapi logic filter hanya memfilter risk. | `dateRange` state di `HistoryScreen.jsx:11`; `getFilteredSessions` hanya cek risk di `HistoryScreen.jsx:91-93`; select UI di `HistoryScreen.jsx:225-233`. | User memilih rentang tanggal tetapi hasil tidak berubah sesuai ekspektasi. | UI kontrol dibuat lebih dulu dari logic. | Implementasikan date filtering atau sembunyikan kontrol sampai backend history siap. |
| FE-09 | Medium | `src/screens/mobile/HistoryScreen/HistoryScreen.jsx` | History export/share | Export dan share masih mock/logging. | Mock data di `HistoryScreen.jsx:18`; export/share di `HistoryScreen.jsx:287-305`. | User mengira export medis tersedia, padahal belum menghasilkan file/aksi real. | Prototype action belum diberi state disabled/coming soon. | Implementasikan export real dari backend atau disable dengan copy yang jujur. |
| FE-10 | Medium | `src/screens/mobile/NotificationsScreen.jsx` | Notifications | Notifications sepenuhnya static/local, ack tidak sinkron backend. | Static array di `NotificationsScreen.jsx:11`; local ack di `NotificationsScreen.jsx:76-90`; clear button tanpa handler jelas di `NotificationsScreen.jsx:105-106`. | Status notifikasi berbeda antara frontend dan backend; notifikasi bisa muncul lagi atau hilang lokal saja. | Backend notification model belum punya ack/read contract. | Tambah endpoint notification list/ack atau ubah UI menjadi local-only demo yang eksplisit. |
| FE-11 | Medium | `src/screens/mobile/ProfileScreen.jsx` | Profile | Save profile hanya `setTimeout`, tidak memanggil backend. | Save mock di `ProfileScreen.jsx:67-70`; pregnancy week memakai `Math.abs` di `ProfileScreen.jsx:80-84`. | Perubahan profil tidak persist. Usia kehamilan bisa salah karena `Math.abs` menyembunyikan tanggal invalid/future. | Form profile belum terhubung ke `api.patients`. | Hubungkan ke `PATCH /patients/me` atau endpoint update baru; validasi tanggal HPHT/EDD secara eksplisit. |
| FE-12 | Medium | `src/screens/mobile/ProfileScreen.jsx` | Medical wording | Ada wording yang cenderung klinis/diagnostik dan perlu konservatif. | Label "Riwayat Penyakit" di `ProfileScreen.jsx:397`; "Penyakit Jantung" di `ProfileScreen.jsx:430`; "analisis lebih akurat" di `ProfileScreen.jsx:494`. | Bertentangan dengan safety rule: bukan diagnosis dan jangan klaim akurasi. | Copy belum diselaraskan dengan guideline Fetal Guard. | Ubah ke wording skrining/riwayat kesehatan, hindari klaim akurasi. |
| FE-13 | Medium | `src/screens/mobile/SettingsScreen.jsx` | Settings | Settings menampilkan hardcoded broker/topic/device/user dan beberapa aksi mock. | MQTT broker/topic di `SettingsScreen.jsx:31-32`; test disconnect `setTimeout` di `SettingsScreen.jsx:57`; hardcoded device/user di `SettingsScreen.jsx:67-80`; unpair/delete mock di `SettingsScreen.jsx:165`, `302`. | UI terasa seperti prototype dan bisa membocorkan detail teknis yang tidak relevan bagi pasien. | Settings belum dipisah antara patient settings, device settings, dan developer diagnostics. | Pisahkan user-facing settings dari developer diagnostics; hubungkan aksi penting ke backend/device layer. |
| FE-14 | Medium | `src/services/api.js` | API client | Base URL default hardcoded ke localhost dan token disimpan di localStorage. | `api.js:3` default `http://localhost:8000`; token/user localStorage di `api.js:4-5`, `16-44`; interceptor di `api.js:74-77`. | Build mobile/Capacitor dapat gagal connect ke device/emulator/backend; localStorage token rentan XSS. | Config env belum dibuat per target runtime; auth storage belum risk-reviewed. | Gunakan env per platform, dokumentasikan `VITE_API_BASE_URL`, pertimbangkan secure storage untuk mobile. |
| FE-15 | Low | `src/components/FHRDisplay.jsx` | FHR animation | RAF animation tidak memiliki cleanup yang jelas. | `requestAnimationFrame` dipakai di `FHRDisplay.jsx:31`, `38`. | Potensi animation loop tetap hidup saat unmount, terutama saat route berpindah. | Effect lifecycle belum rapih. | Simpan RAF id dan cancel di cleanup. |
| FE-16 | Low | `src/components/WaveformChart.jsx` | Chart canvas | Chart membuat fallback random data jika `data` kosong dan animasi live loop terus berjalan. | Random fallback `WaveformChart.jsx:23-36`; live RAF `WaveformChart.jsx:170`; wheel preventDefault `WaveformChart.jsx:185`; canvas render `WaveformChart.jsx:223-225`. | Empty state chart terlihat seperti sinyal real; scroll/wheel behavior bisa mengganggu. | Chart mengutamakan visual demo daripada data truth. | Untuk empty data tampilkan empty chart state; gate live animation; review wheel handler accessibility. |
| FE-17 | Medium | `src/components/AuthScreen/AuthScreen.jsx` | Auth accessibility | Tab login/register tidak memakai `aria-selected`/tab semantics lengkap. | Tablist di `AuthScreen.jsx:59-68`; validation local di `AuthScreen.jsx:97`, `122-136`. | Keyboard/screen reader UX kurang baik. | Custom tabs dibuat dengan button biasa tanpa semantic lengkap. | Gunakan `role=tablist`, `role=tab`, `aria-selected`, dan id/aria-controls. |
| FE-18 | Medium | `src/components/EmergencyButton.jsx` | Emergency modal | Modal confirmation tidak memiliki focus trap dan emergency call memakai `window.location.href`. | Confirm state di `EmergencyButton.jsx:11-22`; `tel:` call di `EmergencyButton.jsx:28`, `40`; dialog role di `EmergencyButton.jsx:66`. | Modal sulit untuk keyboard user; accidental call flow perlu UX yang lebih aman. | Modal custom belum memakai dialog/focus management. | Tambahkan focus trap, Escape close, initial focus, dan wording tindakan darurat yang jelas. |
| FE-19 | Low | `src/components/FeedbackModal.jsx` | Feedback modal | Modal tidak memiliki role/aria/focus management. | Overlay/content di `FeedbackModal.jsx:8-9`. | Aksesibilitas modal rendah. | Custom modal minimal. | Tambahkan `role=dialog`, `aria-modal`, title id, focus return. |
| FE-20 | Low | CSS global | Typography/responsive | Font size memakai viewport scaling. | `src/index.css:8` memakai `2vw`; `src/styles/design-tokens.css:88-99` memakai responsive clamp; reduced motion ada di `src/index.css:62-68`. | Teks bisa terlalu kecil/besar di viewport tertentu dan kurang stabil. | Global responsive type belum diuji visual lint. | Gunakan token type scale yang stabil, bukan viewport-width scaling untuk body text. |

## 3. Backend Findings

| ID | Priority | File/Endpoint | Module | Issue | Evidence | Impact | Root Cause Sementara | Recommendation |
|---|---|---|---|---|---|---|---|---|
| BE-01 | Critical | `backend/api/routes/auth.py` | Auth register | Public register menerima role dari request, termasuk clinician. | `backend/schemas/user.py:9-16` enum memiliki `clinician`; `auth.py:28` menyimpan `role=user_in.role.value`. | Siapa pun dapat membuat akun clinician via API langsung. | Role creation belum dipisah dari public patient registration. | Public register hanya boleh patient. Clinician dibuat via seed/admin-only flow. Tambah regression test. |
| BE-02 | High | `backend/api/routes/sessions.py` | Session lifecycle | Tidak ada guard yang mencegah lebih dari satu active session per patient. | Create active session di `sessions.py:48-56`; upload mensyaratkan active session di `sessions.py:85-100`. | Data monitoring bisa terpecah/duplikat jika user start beberapa session. | State machine session belum lengkap. | Saat create, cek existing active session; return 409 atau reuse active session sesuai keputusan produk. |
| BE-03 | High | `backend/core/config.py` | Security config | Development secret random fallback dan production secret optional sampai runtime validation. | `_DEV_SECRET_KEY` random di `config.py:11`; `SECRET_KEY` optional di `config.py:21`; fallback di `jwt_secret_key` `config.py:49-50`. | Token invalid setelah restart dev; risiko misconfig environment. | Config dibuat fleksibel untuk dev, tetapi belum terdokumentasi kuat. | Document `.env`, fail-fast untuk non-dev, dan gunakan stable dev secret via `.env.example`. |
| BE-04 | Medium | `backend/main.py` | CORS | CORS origin hardcoded. | CORS middleware di `main.py:27-37`. | Mobile/Capacitor atau deployment domain mudah gagal tanpa config. | Origin belum masuk environment config. | Pindahkan allowed origins ke env/config list. |
| BE-05 | Medium | `backend/db/database.py` | DB init | `Base.metadata.create_all` otomatis saat import/start. | `database.py:30`. | Bisa konflik dengan Alembic dan menyamarkan migration drift. | Prototype convenience masih aktif. | Di production/test serius, gunakan Alembic migration; gate `create_all` untuk dev/test saja. |
| BE-06 | High | `backend/api/routes/clinician.py` | Clinician list patients | Endpoint list patients memuat patients + sessions dan dapat membesar tanpa pagination. | `clinician.py:41-51` memakai joinedload/list all; memory sebelumnya juga menunjukkan joinedload dipakai untuk dashboard. | Data besar membuat dashboard lambat dan response berat. | Endpoint dirancang untuk demo dataset kecil. | Tambah pagination, filter search server-side, dan query latest/active session secara efisien. |
| BE-07 | Medium | `backend/api/routes/clinician.py` | Clinician alerts | Alert list hanya filter medium/high, tidak menyertakan patient identity yang cukup. | `clinician.py:57-70`; `NotificationResponse` hanya fields `id/session/message/risk/created` di `schemas/clinician.py:25-32`. | Frontend harus menebak/memap alert ke patient sendiri; rawan data salah. | Notification schema terlalu tipis. | Include `patient_id`, `patient_name`, `session_id`, risk, timestamp, ack status. |
| BE-08 | Medium | `backend/models/notification.py` | Notifications | Notification tidak punya acknowledged/read fields. | `notification.py:10-20`. | Frontend ack local tidak bisa persist. | Notification lifecycle belum dibuat. | Tambah `acknowledged_at`, `acknowledged_by`, atau `read_at`; endpoint ack. |
| BE-09 | Medium | `backend/schemas/sensor_data.py` | Sensor upload validation | Sensor chunk payload masih generic dict/list dengan limit ukuran, belum typed domain validation. | `sensor_data.py:7-26`. | Payload invalid bisa tersimpan dan merusak analitik/AI pipeline. | Prototype fleksibel untuk berbagai sensor. | Buat schema typed minimal: timestamp, fhr, contraction, maternal_hr, spo2, imu, source. |
| BE-10 | Medium | `backend/services/ai_stub.py` dan `backend/api/routes/ai.py` | AI stub | AI endpoint memakai random stub. | `ai_stub.py:1`, `6-7`; `ai.py:49-59` return `is_stub=True`. | Output tidak deterministik dan tidak cocok untuk test klinis. | AI pipeline belum masuk tahap validasi. | Pertahankan sebagai stub, tetapi pastikan UI menampilkan sebagai simulasi/skrining awal dan test tidak menganggapnya real. |
| BE-11 | Low | `backend/api/dependencies.py` | Auth dependencies | Ada helper `get_current_clinician` tetapi route memakai helper role sendiri. | `dependencies.py:33`; route clinician punya dependency sendiri. | Duplikasi auth role logic. | Refactor sebagian belum selesai. | Satukan role dependency agar policy konsisten. |
| BE-12 | Medium | `api/openapi.yaml` | API docs | OpenAPI spec tidak sinkron dengan backend aktual. | Spec mencantumkan `/auth/refresh`, `/auth/logout`, `/devices/*`, `/notifications/*/acknowledge`, `/audit/logs`, `/data/retention`, `/sessions/{id}/export`, dll. Banyak tidak ada di FastAPI. | Execution agent bisa membangun frontend terhadap endpoint yang tidak ada. | Spec aspirational tidak dipisah dari implemented contract. | Tandai spec sebagai roadmap atau regenerate dari FastAPI; buat contract docs implemented-only. |

## 4. Frontend-Backend Contract Findings

| ID | Priority | Frontend Caller | Function/API Client | Backend Endpoint | Method | Request | Expected Response di Frontend | Actual Response Backend | Status | Issue | Recommendation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| API-01 | High | `AuthContext.jsx` | `api.auth.register` | `/auth/register` | POST | email, password, role/name/profile-ish payload | Patient user dibuat aman | Backend bisa menerima role clinician | Mismatch/Risky | Public endpoint bisa create clinician. | Batasi role public register ke patient; clinician via seed/admin. |
| API-02 | Medium | `AuthContext.jsx` | `api.auth.me` + `api.patients.me` | `/auth/me`, `/patients/me` | GET | Bearer token | User + patient profile untuk hydrate app | Ada real endpoint, tetapi field snake_case harus dimapping | Risky | Mapping tersebar di frontend. | Buat normalizer tunggal atau ubah response ke contract yang disepakati. |
| API-03 | High | `ProfileScreen.jsx` | Tidak ada API call real | Butuh `/patients/me` update | PATCH/PUT missing | Profile form fields | Save profile persist | Backend saat ini tidak terlihat menyediakan update profile | Missing | UI save hanya setTimeout. | Tambah endpoint update patient profile dan hubungkan form. |
| API-04 | Medium | `HomeScreen.jsx` | props dari layout/context | `/patients/me`, session summary missing | GET | token | Home menampilkan patient/device/recent history | Backend hanya menyediakan profile/session endpoints terpisah | Risky | Home membuat fallback hardcoded saat data tidak lengkap. | Tambah endpoint summary atau compose data dengan loading/empty state. |
| API-05 | High | `MonitoringScreen.jsx` / `MockSensorService.js` | session create/upload/end | `/sessions`, `/sessions/{id}/data`, `/sessions/{id}/end` | POST | sensor chunks | Active monitoring session sinkron | Backend menerima generic payload dan active session | OK/Risky | Data mock bisa tersimpan seperti real; no active-session guard. | Tambahkan source flag, typed validation, active-session uniqueness. |
| API-06 | Medium | `HistoryScreen.jsx` | Tidak ada API real jelas | `/sessions` atau history endpoint | GET | date/risk filters | Array sessions sesuai filter | Backend punya session routes, tetapi UI memakai mock data | Missing | History tidak memakai backend. | Buat `api.sessions.listHistory(filters)` dan server-side/client-side filter yang benar. |
| API-07 | Medium | `NotificationsScreen.jsx` | Tidak ada API real | `/notifications`, `/notifications/{id}/acknowledge` | GET/PATCH missing | ack/read action | Notifikasi real + ack persist | Backend notification model tidak punya ack; OpenAPI mencantumkan endpoint yang tidak ada | Missing | UI notification local-only. | Implement list/ack contract atau ubah UI menjadi jelas demo-only. |
| API-08 | Medium | `SettingsScreen.jsx` | Tidak ada API/device real | `/devices/*` di OpenAPI | GET/POST/PATCH missing | device pairing/settings | Pair/unpair/test connection real | Backend tidak mengimplementasikan devices endpoints | Missing | Settings menampilkan device actions mock. | Implement device config contract atau hide actions sampai tersedia. |
| API-09 | Medium | `ClinicianDashboard.jsx` | `api.clinician.listPatients` | `/clinician/patients` | GET | token clinician | Patient rows dengan active/latest session | Endpoint ada tetapi detail FHR/signal quality terbatas | Risky | Frontend harus memakai placeholder, bukan invent data. | Perluas schema dengan latest metrics atau tampilkan "belum tersedia". |
| API-10 | Medium | `ClinicianDashboard.jsx` | `api.clinician.listAlerts` | `/clinician/alerts` | GET | token clinician | Alerts dengan patient identity | Actual alert schema tidak menyertakan patient name/id cukup | Mismatch | Dashboard sulit mengaitkan alert ke pasien. | Include patient identity di response atau endpoint detail join. |
| API-11 | Low | `src/services/api.js` | base client | All endpoints | All | `VITE_API_BASE_URL` fallback localhost | Connect di web/mobile | Default `http://localhost:8000` | Risky | Capacitor/mobile environment tidak sama dengan browser localhost. | Dokumentasikan env dan gunakan config per platform. |
| API-12 | Medium | `api/openapi.yaml` consumers | OpenAPI spec | Banyak endpoint | Various | Spec sebagai source of truth | Backend aktual tidak sesuai spec | Mismatch | Contract docs misleading. | Regenerate spec dari FastAPI atau pindah file aspirational ke roadmap. |
| API-13 | Medium | Error handling UI | `getApiErrorMessage` | All endpoints | All | Error response konsisten | UI bisa menampilkan pesan error | Backend error format bervariasi; frontend tidak punya global toast | Risky | Request gagal dapat diam atau hanya console. | Standardize error response dan global toast/error boundary. |
| API-14 | Medium | Auth role guard | route guards di `App.jsx` | `/clinician/*` | GET | clinician token only | Patient dilarang akses clinician | Backend punya role guard, frontend punya guard, tetapi public register bisa buat clinician | Risky | Authorization backend bagus sebagian, provisioning role lemah. | Fix provisioning role, tambah tests patient 403 dan public role rejection. |

## 5. UI/UX & Animation Findings

| ID | Priority | Location | Issue | Impact | Recommendation |
|---|---|---|---|---|---|
| UX-01 | High | Patient home, history, notifications, settings | Banyak data fallback/mock tidak diberi label simulasi. | User bisa percaya data palsu sebagai kondisi real. | Semua data simulasi harus diberi status "mode simulasi" atau diganti empty/loading state. |
| UX-02 | Medium | `HomeScreen.jsx` | Icon-only buttons profile/notification kurang label aksesibilitas. | Screen reader user tidak tahu fungsi button. | Tambah `aria-label` pada button icon. |
| UX-03 | Medium | `AuthScreen.jsx` | Tab login/register belum semantic lengkap. | Keyboard/screen reader UX kurang baik. | Gunakan tab semantics lengkap. |
| UX-04 | Medium | `EmergencyButton.jsx`, `FeedbackModal.jsx` | Modal custom tanpa focus trap/focus return. | Navigasi keyboard dapat terjebak atau hilang konteks. | Implement dialog behavior lengkap atau gunakan modal primitive yang sudah teruji. |
| UX-05 | Medium | `SettingsScreen.jsx` | Toggle dibuat dari div/button custom dan beberapa state action mock. | Feedback aksi kurang meyakinkan; UI terasa belum selesai. | Gunakan switch semantics, loading/disabled states, dan toast hasil aksi. |
| UX-06 | Medium | `MonitoringScreen.jsx` | Risk display dan alert visual dapat terasa seperti diagnosis. | Risiko klaim medis berlebihan. | Copy harus konsisten sebagai skrining awal/indikasi pemantauan, bukan diagnosis. |
| UX-07 | Medium | `HistoryScreen.jsx` | Filter tanggal tidak bekerja, export/share mock. | User kehilangan trust pada fitur history. | Implement filter/export real atau disable sampai siap. |
| UX-08 | Low | Route transitions | Pergantian route mendadak. | UX terasa kaku. | Tambah transition ringan CSS, hormati `prefers-reduced-motion`. |
| UX-09 | Low | `FHRDisplay.jsx`, `WaveformChart.jsx` | Animasi loop perlu cleanup dan empty data tidak boleh random. | Potensi performance issue dan false signal. | Cleanup RAF, tampilkan empty chart state. |
| UX-10 | Low | Global typography | Body font scaling memakai viewport width. | Layout teks bisa tidak konsisten antar device. | Pakai token type scale stabil dan uji responsive. |
| UX-11 | Medium | Clinician dashboard | Data terbatas harus tetap jujur sebagai belum tersedia, bukan diisi estimasi. | Nakes bisa salah membaca status pasien. | Pertahankan placeholder yang jujur; perluas backend schema jika ingin data real. |

## 6. Technical Debt

- Duplicated/dead auth UI: `AuthScreen` aktif, `LoginScreen` lama masih ada.
- Banyak mock data berada di screen user-facing, bukan di fixture/dev-only layer.
- API docs tidak sinkron dengan backend aktual.
- Sensor payload schema terlalu generic untuk kebutuhan analytics dan AI pipeline.
- Error handling belum menjadi cross-cutting UI system.
- Modal, tab, dan toggle belum punya accessibility contract kuat.
- Backend role provisioning lemah karena public register dapat menerima role clinician.
- Session lifecycle belum menjadi state machine yang eksplisit.
- OpenAPI aspirational bercampur dengan implemented API.
- Build/mobile config memiliki dev flags yang berisiko (`allowMixedContent`, debugging enabled) dan perlu gating environment.
- Frontend field normalization tersebar; belum ada view-model/API normalizer yang konsisten.
- Tests backend sudah ada dan lulus, tetapi belum menutup public clinician registration, active session duplication, notification ack, dan typed sensor validation.

## 7. Risk Ranking

### Critical

- FE-02: Dead `LoginScreen` masih menyimpan mock auth dan dapat meng-bypass real auth jika dipakai lagi.
- BE-01/API-01: Public register dapat membuat role clinician.

### High

- FE-03: Home screen menampilkan hardcoded patient/device data.
- FE-04/FE-07/API-05: Mock sensor bisa membuat/upload session seperti data real tanpa guard kuat.
- BE-02: Multiple active session belum dicegah.
- BE-06: Clinician patients endpoint belum punya pagination/query strategy yang scalable.

### Medium

- FE-08/FE-09/API-06: History filter/export tidak sesuai UI.
- FE-10/API-07/BE-08: Notification ack tidak persist dan contract belum ada.
- FE-11/API-03: Profile save belum persist.
- FE-13/API-08: Settings device actions masih mock.
- FE-14/API-11: API base URL hardcoded fallback dan storage token risk.
- BE-09: Sensor payload belum typed.
- BE-12/API-12: OpenAPI stale.
- UX-03/UX-04/UX-05: Accessibility gaps pada tab/modal/toggle.

### Low

- FE-15/FE-16/UX-09: Animation cleanup dan chart empty state.
- FE-20/UX-10: Typography scaling perlu polish.
- UX-08: Route transition polish.

## 8. Suggested Execution Order

### Batch 1: App/build/runtime blocker

- Restrict public registration agar hanya patient.
- Tambah tests untuk menolak public clinician registration.
- Cleanup/deprecate `LoginScreen` mock auth agar tidak menjadi jalur auth alternatif.
- Review Capacitor dev flags dan pastikan production config tidak memakai mixed content/debugging.
- Regenerate atau tandai `api/openapi.yaml` agar tidak dianggap implemented contract.

### Batch 2: Frontend-backend mismatch

- Tambahkan atau sepakati endpoint update `PATCH /patients/me`, lalu hubungkan `ProfileScreen`.
- Hubungkan `HistoryScreen` ke session history real atau disable fitur yang belum siap.
- Tambahkan notification list/ack contract atau ubah UI menjadi explicit demo-only.
- Perluas `/clinician/alerts` agar membawa patient identity yang cukup.
- Pisahkan device settings yang belum ada backend dari user-facing settings.

### Batch 3: Backend validation/error handling

- Tambahkan active-session guard di `POST /sessions`.
- Typed validation untuk sensor chunk minimal.
- Tambah ack fields di notification model bila notification akan dipakai real.
- Standardize error response format.
- Tambah pagination/filter untuk clinician patient list.

### Batch 4: Frontend state/loading/error/empty state

- Hapus hardcoded patient/device/recent history dari `HomeScreen`.
- Tambahkan loading, empty, error states yang konsisten untuk home/history/notifications/profile/settings.
- Tambahkan global toast/error boundary ringan.
- Centralize API response normalization.

### Batch 5: UI/UX responsiveness

- Perbaiki `aria-label` icon buttons.
- Lengkapi tab semantics di `AuthScreen`.
- Tambahkan dialog focus management untuk modal emergency/feedback.
- Review typography scaling dan responsive layout.

### Batch 6: Animation/polish

- Cleanup RAF di `FHRDisplay` dan `WaveformChart`.
- Jangan tampilkan random waveform saat data kosong.
- Tambahkan transition ringan dengan `prefers-reduced-motion`.
- Buat feedback button/toggle lebih jelas: hover, focus, loading, disabled.

### Batch 7: Cleanup/refactor/test

- Hapus dead code atau beri boundary `dev-only`.
- Tambah tests backend untuk role registration, session duplication, notification ack, sensor validation.
- Tambah targeted frontend tests bila test setup tersedia.
- Jalankan `npm.cmd run lint`, `npm.cmd run build`, dan backend pytest.
