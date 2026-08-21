# FETAL-GUARD AI Infrastructure

Folder ini berisi infrastruktur riset CNN-LSTM multimodal untuk membantu skrining awal. Kode ini belum merupakan model tervalidasi klinis dan belum boleh dipakai sebagai diagnosis atau pengganti pemeriksaan tenaga kesehatan.

## Komponen yang tersedia

- kontrak input untuk 4 kanal piezo, 1 kanal FSR, dan 2 kanal PPG ibu;
- window 60 detik, stride 15 detik, validity mask, dan penolakan window dengan data tidak cukup;
- tiga CNN branch dengan adaptive temporal pooling, dilanjutkan LSTM unidirectional;
- head terpisah untuk kualitas sinyal, estimasi FHR/MHR, indikator kontraksi, dan status skrining;
- safety layer yang menahan klasifikasi saat kualitas sinyal terbatas, uncertainty tinggi, atau output teknis tidak valid;
- loader dan executor satu-window yang memverifikasi input/mask lalu menjalankan artefak dalam inference mode;
- split train/validation/test berbasis subjek untuk mencegah data leakage;
- training runner, checkpoint, SHA-256 manifest, dan deployment validation gate;
- backend job/result/review persistence, audit, RBAC, realtime event, retry terbatas, dan mode fail-closed.

## Kontrak dataset training

`train_cnn_lstm.py` hanya menerima `.npz` dengan semua key berikut:

```text
piezo                       float32 [window, time, 4]
piezo_validity_mask         bool    [window, time, 4]
fsr                         float32 [window, time, 1]
fsr_validity_mask           bool    [window, time, 1]
maternal_ppg                float32 [window, time, 2]
maternal_ppg_validity_mask  bool    [window, time, 2]
screening_labels            int64   [window]      # 0, 1, atau 2
quality_targets             float32 [window]      # 0..1
measurement_targets         float32 [window, 2]   # FHR, MHR; NaN jika tidak berlabel
contraction_targets         float32 [window]      # 0..1; NaN jika tidak berlabel
group_ids                   string  [window]      # pseudonymous subject/record id
dataset_kind                scalar string
preprocessing_version       scalar string
input_schema_version        scalar int = 2
```

`dataset_kind` hanya boleh `research_public`, `fetal_guard_hardware`, atau `synthetic_smoke_test`. Data sintetis diblokir secara default dan artefaknya tidak boleh dipromosikan.

Script CSV generik tetap tersedia untuk eksplorasi satu dataset, tetapi outputnya bukan kontrak training hybrid. Jangan menyamakan kanal CTG publik dengan kanal hardware FETAL-GUARD tanpa adapter dan eksperimen lintas modalitas yang direview.

## Perintah

Jalankan unit test yang tidak membutuhkan PyTorch:

```powershell
python -m unittest discover -s ai\tests -v
```

Validasi kontrak dataset dan split tanpa melatih:

```powershell
python ai\scripts\train_cnn_lstm.py `
  --windows ai\data\processed\reviewed_hybrid_windows.npz `
  --model-version research-001 `
  --dry-run
```

Training hanya setelah dataset, label, dan environment PyTorch direview:

```powershell
python ai\scripts\train_cnn_lstm.py `
  --windows ai\data\processed\reviewed_hybrid_windows.npz `
  --model-version research-001 `
  --epochs 25
```

Hasil training disimpan di `ai/runs/cnn_lstm/<model-version>/` sebagai `model.pt`, `manifest.json`, dan `training_summary.json`. Manifest selalu dimulai dengan `validation_status: experimental`.

## Gate backend

- `AI_PIPELINE_MODE=disabled`: default; ingest tidak membuat job AI.
- `AI_PIPELINE_MODE=research`: mengizinkan artefak experimental untuk penelitian internal; hasil tetap `shadow`.
- `AI_PIPELINE_MODE=shadow`: membutuhkan minimal `analytical_validated`; hasil tetap tidak terlihat pengguna.
- `AI_PIPELINE_MODE=clinician`: hanya menerima model `clinical_validated` pada slot `clinician`; hasil tersedia untuk nakes yang berwenang.
- Hasil nakes baru dipublikasikan ke pasien setelah review `confirmed`/`needs_followup` dan diproses worker publication dengan database role terisolasi.

Set `AI_ACTIVE_MODEL_VERSION_ID` ketika mode bukan `disabled`. Readiness backend gagal jika model aktif tidak ada atau status validasinya tidak memenuhi mode.

Worker publication dijalankan terpisah dari backend web:

```powershell
cd backend
.\venv\Scripts\python.exe run_ai_publication_worker.py
```

Proses tersebut belum menjalankan inference. Adapter window hardware dan inference worker end-to-end tetap wajib diselesaikan sebelum mode `clinician` digunakan.

## Yang masih wajib sebelum penggunaan klinis

- payload hardware schema v2 dan adapter window multimodal nyata;
- dataset hardware berprovenance dengan ground truth tersinkron;
- review label/protokol oleh nakes dan persetujuan etik;
- analytical validation, external validation, calibration, dan subgroup analysis;
- worker inference terisolasi beserta observability dan load/failure testing;
- proses promosi model, rollback, drift monitoring, dan human review.

Jangan mencantumkan akurasi, sensitivitas, spesifisitas, atau manfaat klinis sebelum tersedia bukti evaluasi yang sah.
