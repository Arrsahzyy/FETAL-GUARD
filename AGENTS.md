# FETAL-GUARD Project Context and Agent Guide

Dokumen ini adalah sumber konteks utama untuk manusia dan AI agent saat bekerja di repository FETAL-GUARD. Root project sengaja hanya memakai dua file Markdown:

1. `AGENTS.md` - konteks produk, arsitektur, aturan kerja, guardrail medis, dan workflow agent.
2. `FETAL_GUARD_ROADMAP.md` - roadmap, checklist, milestone, acceptance criteria, dan rencana validasi sampai sistem bekerja optimal.

Jika ada dokumen lama seperti prompt, implementation plan, task tracker, atau roadmap teknis root-level, isinya harus digabungkan ke dua file ini, bukan dibuat sebagai file root baru.

## 1. Identitas Proyek

FETAL-GUARD adalah prototype PKM-KC berupa sabuk pintar wearable untuk skrining awal risiko feto-maternal pada ibu hamil. Sistem memantau:

- DJJ/FHR melalui array piezoelektrik.
- Indikator kontraksi rahim melalui FSR408.
- Parameter vital ibu melalui MAX30102.
- Status perangkat, sesi pemantauan, riwayat, alert, dan tindak lanjut melalui aplikasi pasien dan dashboard nakes.

Proyek ini adalah alat bantu skrining awal dan rekayasa prototipe. Sistem bukan alat diagnosis medis, bukan pengganti CTG, tocotransducer, Doppler, USG, dokter, bidan, atau fasilitas kesehatan.

## 2. Prinsip Produk

- Patient-first safety: copy pasien harus tenang, sederhana, tidak alarmis, dan tidak membuat klaim diagnosis.
- Clinician workflow: dashboard nakes harus operasional, padat, mudah dipindai, dan tidak menampilkan detail developer seperti API base URL atau endpoint teknis kecuali masuk mode admin/developer.
- Honest data: jangan mengarang FHR, signal quality, confidence, akurasi, sensitivitas, spesifisitas, atau hasil validasi jika belum ada sumber data nyata.
- Role separation: pasien, nakes, admin, dan developer adalah domain berbeda. Jangan menyatukan alur registrasi atau data sensitif tanpa alasan desain yang jelas.
- Validasi bertahap: bench test -> signal generator/dataset -> phantom/manikin -> relawan non-klinis -> uji terbatas dengan ethical clearance.

## 3. Status Arsitektur Repository Saat Ini

Stack aktual repository:

- Frontend web/mobile shell: React + Vite.
- Mobile target: Capacitor/Android.
- Backend/API: FastAPI.
- Database dan schema backend berada di folder `backend/`.
- Auth: backend JWT dengan role guard pasien, clinician/nakes, dan admin.
- i18n: `src/i18n/id.json` dan `src/i18n/en.json`.
- Dashboard nakes: `src/screens/clinician/ClinicianDashboard/`.
- Aplikasi pasien: `src/screens/mobile/`.
- Shared API client: `src/services/api.js`.

Catatan: proposal awal menyebut Node.js + MQTT untuk backend. Pada implementasi repository ini, backend yang menjadi source of truth adalah FastAPI. MQTT/hardware pipeline tetap bagian roadmap integrasi berikutnya.

## 4. Hardware Baseline

Komponen utama yang tidak boleh dihapus dari arsitektur tanpa diskusi:

- ESP32 DevKit V1.
- 4x sensor piezoelektrik untuk vibrasi mekanik DJJ.
- FSR408 untuk indikator tekanan/kontraksi.
- MAX30102 untuk HR/SpO2 ibu.
- LM324 sebagai pre-amplifier sinyal piezo.
- Li-Po 3.7 V, TP4056 charger, MT3608 step-up.
- Sabuk maternity wearable dengan pocket sensor dan casing main hub.

Rekomendasi teknis yang perlu diputuskan tim:

- Pertimbangkan external ADC seperti ADS1115 untuk sinyal piezo karena ADC internal ESP32 berisiko noisy.
- Pertimbangkan BLE ke smartphone sebagai gateway untuk fase produk, sementara WiFi/hotspot/MQTT cukup untuk prototipe awal.
- AI inference sebaiknya berada di backend/cloud, bukan ESP32.

## 5. Data Flow Target

Alur sistem target:

```text
Sensor sabuk
-> analog front-end
-> ESP32 acquisition and preprocessing
-> WiFi/MQTT or BLE-to-phone gateway
-> backend storage and processing
-> hybrid rule + CNN-LSTM analysis
-> patient mobile app
-> clinician dashboard
-> alert, review, and follow-up workflow
```

Pada tahap software saat ini, frontend dan backend tidak boleh menampilkan seolah-olah data sensor real tersedia jika hardware/MQTT belum benar-benar mengirim data.

## 6. Subsystem

- Embedded/ESP32: ADC/I2C acquisition, buffering, preprocessing awal, BLE/WiFi/MQTT.
- Analog front-end: LM324, bias tengah sinyal AC, filter, shielding, proteksi ADC.
- Power management: baterai, charger, regulator, thermal safety, load sharing.
- Wearable design: sabuk, pocket sensor, casing, ergonomi, material kulit.
- Patient app: home, monitoring, history, notifications, settings, profile.
- Clinician dashboard: patient list, active monitoring, alert queue, patient detail, report, settings nakes.
- Admin: registrasi dan manajemen nakes, audit, konfigurasi operasional.
- Backend/API: auth, RBAC, patient/session/device data, clinician data, alert workflow.
- AI/ML: preprocessing, feature extraction, rule layer, CNN-LSTM baseline, validation pipeline.
- Connectivity: MQTT broker, offline buffer, BLE gateway, cloud sync.
- Security/privacy: JWT, RBAC, data minimization, audit log, no secrets in UI or docs.
- Validation/testing: unit, integration, frontend visual QA, backend tests, hardware bench tests, clinical validation plan.

## 7. Role and Route Expectations

Pasien:

- Login/register pasien harus masuk ke portal pasien.
- Pasien melihat ringkasan kondisi pribadi, status perangkat, sesi pemantauan, riwayat, edukasi, dan notifikasi dengan bahasa non-alarmis.
- Pasien tidak boleh melihat data pasien lain, daftar pasien global, atau tools teknis nakes.

Nakes/clinician:

- Nakes login melalui portal nakes.
- Akun nakes idealnya dibuat oleh admin melalui admin GUI/portal, bukan di-hardcode manual untuk production.
- Dashboard nakes berisi daftar pasien, detail monitoring, alert, status risiko awal, catatan tindak lanjut, dan laporan operasional.
- Nakes tidak boleh melihat secret/backend config yang tidak relevan dengan workflow klinis.

Admin:

- Admin bertugas mendaftarkan nakes, mengatur role, melihat audit, dan mengelola akses.
- Untuk production, admin flow wajib GUI/backend API dengan RBAC dan audit trail. Jangan mengandalkan edit kode manual.

Developer:

- Detail endpoint, base URL, broker topic, atau debug panel hanya boleh muncul di mode developer/admin yang jelas, bukan UI pasien/nakes umum.

## 8. Medical Claim Guardrail

Gunakan frasa aman:

- "skrining awal"
- "indikasi awal"
- "membantu pemantauan"
- "perlu observasi"
- "segera tinjau"
- "segera konsultasi"
- "perlu validasi lanjutan"
- "tidak menggantikan pemeriksaan tenaga kesehatan"

Hindari frasa berisiko:

- "mendiagnosis"
- "akurasi menyamai alat medis"
- "terbukti klinis" tanpa data validasi nyata
- "menggantikan CTG/USG/Doppler"
- "gawat janin" sebagai klaim output aplikasi
- klaim sensitivitas/spesifisitas tanpa hasil uji

Threshold rujukan yang tidak boleh diubah tanpa approval eksplisit:

- FHR/DJJ: 110-160 bpm sebagai rentang rujukan tampilan.
- HR ibu: 60-100 bpm sebagai rentang rujukan tampilan.

## 9. Engineering Rules for Agents

Sebelum mengubah file:

1. Baca `AGENTS.md`.
2. Jika pekerjaan menyangkut roadmap, milestone, hardware, AI, validasi, atau scope besar, baca `FETAL_GUARD_ROADMAP.md`.
3. Identifikasi subsystem terdampak.
4. Untuk audit, lakukan discovery read-only terlebih dahulu.
5. Untuk implementasi yang sudah diminta eksplisit, kerjakan minimal namun tuntas.
6. Jangan menghapus fitur atau data tanpa alasan jelas.
7. Jangan install dependency baru tanpa menjelaskan alasan dan meminta izin bila perlu.
8. Jangan menjalankan command destruktif seperti `git reset --hard`.
9. Jangan menampilkan API key, token, password, atau isi `.env`.
10. Jika ada perubahan user di worktree, jangan revert.

## 10. Code and UI Standards

Frontend:

- Ikuti pola React/Vite yang sudah ada.
- Utamakan komponen kecil yang jelas dan helper shared jika duplikasi bermakna.
- i18n ID/EN harus parity untuk copy yang user-facing.
- UI pasien harus sederhana dan menenangkan.
- UI nakes harus operasional, padat, scan-friendly, dan tidak terasa demo.
- Jangan tampilkan data klinis palsu; gunakan empty state atau "Belum tersedia dari sistem".

Backend:

- Backend FastAPI adalah source of truth untuk contract API.
- `api/openapi.yaml` dan dokumen lama bisa tertinggal dari implementasi; verifikasi ke source backend.
- Role guard wajib diuji untuk pasien/nakes/admin.
- Endpoint clinician harus mempertimbangkan pagination, scoping klinik, dan audit trail sebelum production.

AI/ML:

- Model awal harus diposisikan sebagai screening support.
- Hybrid rule + ML lebih aman dibanding pure ML untuk tahap data terbatas.
- Jangan klaim performa sebelum ada dataset, ground truth, dan evaluasi.

## 11. Development Commands

Menjalankan website lokal lengkap (migrasi database local-mobile, backend port 3020,
dan frontend port 5173) cukup dengan:

```powershell
npm.cmd run local
```

Alias `npm.cmd run localserver` tersedia untuk perintah yang lebih eksplisit.

Pasien dapat mendaftar melalui portal pasien. Akun admin dan nakes diprovisikan satu kali
secara interaktif tanpa password hard-coded:

```powershell
npm.cmd run local:staff
```

Daftarkan UID ESP32 pengujian ke akun pasien lokal secara interaktif dengan:

```powershell
npm.cmd run local:device
```

Gunakan `Ctrl+C` pada terminal local server untuk menghentikan backend dan frontend bersama.

Frontend:

```powershell
npm.cmd install
npm.cmd run dev
npm.cmd run lint
npm.cmd run build
```

Backend:

```powershell
cd backend
.\venv\Scripts\pytest.exe -p no:cacheprovider
.\venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000
```

Local access expectation:

- Frontend: `http://127.0.0.1:5173/`
- Backend: `http://127.0.0.1:8000/`
- Backend docs: `http://127.0.0.1:8000/docs`

Embedded if PlatformIO is used:

```powershell
pio run
pio run --target upload
pio device monitor
```

## 12. Definition of Done

Setiap perubahan signifikan dianggap selesai jika:

- Requirement user sudah dipenuhi.
- Tidak ada role flow yang tercampur.
- Tidak ada data klinis palsu atau klaim medis berlebihan.
- `npm.cmd run lint` lulus untuk perubahan frontend.
- `npm.cmd run build` lulus untuk perubahan frontend.
- Backend tests relevan lulus jika backend/API terdampak.
- i18n ID/EN lengkap jika ada copy user-facing.
- UI responsive aman jika menyentuh layout.
- Final response menyebut file yang diubah dan verifikasi yang berhasil/gagal.
