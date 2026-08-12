# Arsitektur AI Hybrid FETAL-GUARD

## Status dan tujuan

Pipeline AI adalah sistem pendukung skrining awal, bukan sistem diagnosis. Implementasi saat ini menyediakan fondasi engineering dan berjalan `fail-closed`: inference sinkron publik tetap nonaktif, job baru hanya dibuat jika pipeline diaktifkan eksplisit, dan hasil worker selalu disimpan sebagai `shadow`.

## Alur data

```text
ESP32 / gateway
-> POST session telemetry tervalidasi dan idempotent
-> penyimpanan raw chunk sebagai source of truth
-> rolling-window AI job (60 detik, stride 15 detik)
-> worker terisolasi
-> verifikasi manifest dan hash artefak
-> preprocessing + validity mask + quality gate
-> CNN per modalitas -> temporal pooling -> LSTM
-> safety layer
-> shadow result
-> validasi dan controlled promotion
-> API pasien/nakes sesuai RBAC + audit + realtime event
```

Kegagalan pembuatan job turunan tidak membatalkan telemetri yang sudah berhasil disimpan. Queue memakai unique window/model constraint, claim dengan row lock, retry terbatas, dan status terminal `rejected` untuk mencegah loop tanpa akhir.

## Input model

Kontrak v2 memisahkan:

- piezo: empat kanal;
- FSR: satu kanal;
- PPG ibu: dua kanal;
- validity mask per sampel dan kanal;
- provenance, versi preprocessing, model, session, device, dan pasien.

Setiap modalitas boleh mempertahankan sampling rate yang sudah direview. CNN branch melakukan feature extraction dan adaptive pooling ke bin temporal yang sama sebelum LSTM. Ini menghindari asumsi keliru bahwa semua sensor memiliki frekuensi sampling identik.

## Model dan safety layer

Model memiliki head terpisah untuk kualitas sinyal, dua measurement target, indikator kontraksi, dan tiga kelas skrining aman. `insufficient_signal` tidak dipelajari sebagai kelas klinis; status ini dipaksakan oleh safety layer saat:

- kualitas sinyal tidak memenuhi gate;
- uncertainty melewati batas engineering;
- output numerik tidak finite atau melewati rentang teknis;
- modalitas/validity mask tidak memenuhi kontrak.

Nilai atau status yang lolos pemeriksaan teknis tetap bukan diagnosis. Threshold klinis baru boleh ditambahkan setelah protokol labeling, ground truth, dan approval nakes ditetapkan.

## Data leakage dan provenance

Split training dilakukan berdasarkan `group_ids` pseudonim, bukan berdasarkan window acak. Dengan demikian, window dari satu pasien/rekaman tidak dapat tersebar ke train dan test. Dataset wajib menyatakan jenis, versi schema, versi preprocessing, mask data asli, dan target yang tersedia. Target yang tidak tersedia harus `NaN`, bukan diisi nilai buatan.

Dataset publik CTG/PCG/ECG bukan pengganti data hardware FETAL-GUARD. Pretraining lintas modalitas adalah eksperimen terpisah dan tidak membuktikan performa pada piezo/FSR/MAX30102.

## Model registry dan promosi

Setiap artefak memiliki version, SHA-256, input schema, preprocessing version, validation status, dan deployment slot. Gate yang diterapkan:

| Status model | Research | Shadow | Nakes/pasien |
|---|---:|---:|---:|
| experimental | ya | tidak | tidak |
| analytical_validated | ya | ya | tidak |
| clinical_validated | ya | ya | ya |
| retired | tidak | tidak | tidak |

Training selalu menghasilkan status `experimental`. Perubahan status memerlukan proses validasi dan approval di luar training script. Model tervalidasi klinis dapat dipromosikan ke visibility nakes; visibility pasien juga mensyaratkan review nakes yang tidak berstatus `dismissed`.

## Isolasi dan keamanan

Tabel job, result, review, dan model version berada dalam migrasi terkontrol. Foreign key komposit mengikat organisasi, pasien, session, device, job, result, dan membership reviewer. API pasien hanya membaca hasil miliknya dengan visibility `patient`. API nakes menggunakan organization context dan assignment/facility permission. Review dicatat dengan actor, audit event, dan optimistic version untuk mencegah lost update.

Pada PostgreSQL, RLS menjadi lapisan tambahan. Mutasi job/result hanya diterima dari database role `fetal_guard_ai_worker`; API role dilarang memiliki hak UPDATE job atau INSERT/UPDATE result. Worker harus memakai connection pool dan kredensial terpisah, dan tidak boleh menjadi member/owner dari API role.

## Batas implementasi saat ini

Fondasi belum berarti sistem siap klinis. Masih diperlukan adapter payload hardware v2, worker inference end-to-end, artefak nyata, validasi analitik/klinis, monitoring drift, dan pengujian kegagalan/load. Sampai seluruh gate tersebut terpenuhi, dashboard harus mempertahankan no-data state dan tidak menampilkan hasil AI seolah-olah berasal dari perangkat nyata.
