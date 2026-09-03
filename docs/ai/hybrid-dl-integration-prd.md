# PRD — Integrasi Hybrid Deep Learning ke Pengolahan & Monitoring Data FETAL-GUARD

**Status:** Draft untuk keputusan tim
**Tanggal:** 2026-09-04
**Penulis:** review & rancangan oleh Claude (Sonnet 5), atas permintaan pemilik repo
**Input:** repo model `https://github.com/Adityakknn/ctg_cnn_lstm_adit` (Adit), kondisi kode AI di repo FETAL-GUARD per commit `69a3939`
**Baca bersama:** `FETAL_GUARD_ROADMAP.md` §9 (Milestone 6), `AGENTS.md` §8, `docs/ops/*`

---

## 0. TL;DR — keputusan yang diminta

1. **Model Adit layak dipakai?** Ya sebagai **artefak riset & template metodologi**, **tidak** sebagai mesin hybrid-DL produksi apa adanya. Metodologinya bagus dan jujur; datanya 100% sintetis; keunggulannya atas baseline sederhana (Random Forest) marginal; pendekatan pemodelannya berbeda dari paket `ai/src/fetal_guard_ai` milik kita.
2. **Masalah utama sekarang bukan "model belum diintegrasikan" — tapi ada 3 badan kode AI yang tumpang tindih di repo** (paket `fetal_guard_ai` kita, model Adit yang sudah di-vendor di `ctg_cnn_lstm_merged/`, dan adapter `ctg_cnn_lstm_adapter.py`), plus lapisan signal-processing baru (`services/signal_processing.py`) yang menduplikasi lapisan DSP Adit. Ini persis sumber redundansi yang dikhawatirkan.
3. **Rekomendasi:** satukan menjadi **satu pipeline** (paket `fetal_guard_ai` + worker terisolasi + gate artefak `AIModelVersion`). Jadikan model Adit sebagai **baseline pembanding** dan **resep training** untuk melatih model kita sendiri di atas kontrak telemetri kita. Hapus jalur ganda.
4. **AI tetap `disabled` untuk pasien/nakes** sampai ada validasi terhadap data CTG nyata (JNU-CTG / CTU-UHB / fPCG PhysioNet — lihat §4b). Model Adit saat ini hanya memenuhi syarat slot `research`.

---

## 1. Review model Adit (`ctg_cnn_lstm_adit`)

### 1.1 Arsitektur

`app/ai/model.py` — `CTGCNNLSTM`:

```
input  (batch, seq_len=15, 3)   # 3 fitur = [FHR bpm, MHR bpm, UC per-10-min]
  -> Conv1d(3->32, k=3) -> ReLU
  -> Conv1d(32->64, k=3) -> BatchNorm1d -> ReLU
  -> LSTM(64 -> 64, unidirectional)   # ambil hidden state terakhir
  -> Dropout(0.3)
  -> 4 head Linear:  fhr(3) | mhr(3) | uc(3) | overall(2)
```

- Input **bukan sinyal mentah** — sudah berupa deret nilai bpm/kontraksi hasil DSP.
- `seq_len=15`, `dt=15 s` → satu window = **±3,75 menit konteks**.
- Multi-task 4 head. `overall` = biner Normal/Abnormal (turunan dari 3 head lain).
- Checkpoint menyimpan `scaler_mean`/`scaler_std` (z-score dari **train set saja** — benar).

### 1.2 Data & pelabelan

`training/generate_sequences.py`:

- **100% sintetis.** `_generate_raw_series()` = random walk + 2–6 "episode abnormal" buatan (brady/tachy/hypo/tachysystole) per sesi.
- Label = **ambang klinis eksak** pada sinyal **bersih** (`label_fhr`: <110 brady, >160 tachy; `label_mhr` ACOG 70–110; `label_uc` 2–5/10 mnt).
- Window `X` yang dilihat model = sinyal + **noise Gaussian** (`std` FHR 6,0 / MHR 5,0 / UC 1,0) + **artifact** 10%/timestep (out-of-range pendek = elektroda lepas).
- 250 sesi × ~106 window = **26.500 window**.

**Konsekuensi:** model belajar **"terapkan ambang klinis, tahan terhadap noise pengukuran"** — bukan mengenali pola patologi CTG nyata (deselerasi lambat, hilangnya variabilitas, dsb.), karena pola itu tidak ada di generator. Angka akurasi 97% adalah "seberapa baik CNN-LSTM meniru fungsi `label_fhr()` lewat noise", bukan validasi klinis.

### 1.3 Metodologi — **kuat**

Poin yang benar dan jarang dilakukan mahasiswa:

- **Split level sesi** (`GroupShuffleSplit`, `groups=session_id`), overlap `session_id` antar split diverifikasi kosong lewat assertion — bukan split level window (yang bocor karena window tetangga nyaris identik).
- **Normalisasi hanya dari train set** — statistik val/test tidak bocor ke skala input.
- **Ada baseline pembanding**: rule-based (ambang di bacaan terakhir), Logistic Regression, Random Forest.
- **5-fold Group CV** (`cross_validate.py`) — tiap sesi jadi test tepat sekali.
- **Regularisasi** setelah ketahuan overfitting (dropout 0.3, weight_decay 1e-4, early stopping).
- **Pelaporan jujur** (`results/README_RESULTS.md`) — hasil campuran dilaporkan apa adanya, tidak dipoles.

### 1.4 Hasil (5-fold CV, mean ± std)

| Target  | Rule-based | Random Forest | CNN-LSTM |
|---------|-----------:|--------------:|---------:|
| FHR     | 92,84 ± 0,70 | **97,32 ± 0,35** | 97,14 ± 0,75 |
| MHR     | 92,12 ± 0,99 | **97,03 ± 0,49** | 96,81 ± 0,48 |
| UC      | 79,55 ± 1,02 | 88,12 ± 0,72 | **88,35 ± 0,95** |
| Overall | 82,27 ± 1,20 | 88,49 ± 1,08 | **89,13 ± 1,13** |

**Interpretasi jujur:**

- CNN-LSTM **> rule-based** di semua target (+5 s.d. +7 poin) — konteks temporal jelas menambah nilai vs ambang di bacaan terakhir.
- CNN-LSTM **≈ Random Forest** (setara secara statistik). Menang di Overall di 5/5 fold, tapi marginnya **< 1 poin**; sedikit **kalah** di FHR & MHR individual.
- Penyebab (kemungkinan): pada data 3-fitur + window 15-langkah + pola sintetis "random walk + episode", Random Forest yang melihat window di-flatten (45 fitur) sudah cukup menangkap kombinasi 3 ambang. Keunggulan LSTM baru terasa pada pola temporal yang lebih kompleks dari yang ada di generator.

### 1.5 Temuan teknis untuk integrasi

| # | Temuan | Dampak |
|---|--------|--------|
| T1 | Training data 100% sintetis; `external_validation.py` masih **skeleton** (butuh unduh JNU-CTG + CTU-UHB, atasi ketiadaan kanal MHR, mapping UC tekanan→count — lihat §4b) | **Blocker validasi.** Tidak boleh `analytical_validated`. |
| T2 | `torch.load(..., weights_only=False)` di `app/ai/inference.py` | Eksekusi kode arbitrer saat load checkpoint. Harus `weights_only=True` / safetensors sebelum masuk gate artefak kita. |
| T3 | `main.py` = FastAPI standalone: state buffer **in-memory per-device** (`_windows`, `_latest_by_device`), `allow_origins=["*"]`, **tanpa auth** | Prototipe riset, bukan service. Jangan deploy sebagai service terpisah. |
| T4 | Input model butuh `uc_per_10min` (hitungan kontraksi) | Pipeline kita hanya meng-*klasifikasi* kontraksi (none/mild/regular/strong), **tidak menghitung**. Perlu estimator baru. |
| T5 | Butuh **15 bacaan berurutan** [FHR,MHR,UC] rentang ~3,75 mnt | `SessionSensorSummary` kita hanya simpan derivasi **terakhir**. Tidak ada deret waktu nilai turunan yang dipersistensi. |
| T6 | Lapisan `app/signal_processing/` + `app/services/sensor_pipeline.py` (bandpass + peak + SQI + `SensorSelector` hysteresis + `UterineBaseline`) | **Duplikasi** `backend/services/signal_processing.py` + `vitals_derivation.py` kita (autocorrelation + envelope). Dua implementasi DSP untuk pekerjaan yang sama. |
| T7 | `ctg_cnn_lstm_merged/` (model Adit yang sudah di-vendor di repo kita) **lebih lama** dari GitHub Adit — belum ada `README_RESULTS.md`, `cross_validate.py`, `baseline.py`, checkpoint & dataset berbeda | Vendor stale. |

### 1.6 Verdict

**Model Adit = artefak PKM yang solid + template metodologi yang sangat baik.** Untuk lomba, hasil CV + baseline + pelaporan jujur adalah materi presentasi yang kuat.

**Untuk sistem kita, model ini BUKAN mesin hybrid-DL yang bisa langsung dipasang**, karena: (a) tidak tervalidasi terhadap data nyata, (b) keunggulan atas baseline sederhana marginal, (c) beroperasi pada nilai turunan, bukan sinyal mentah — sedangkan visi roadmap M6 kita adalah belajar dari sinyal multimodal mentah, (d) memasukkannya apa adanya akan **menambah** jalur AI ke-4 di atas 3 yang sudah tumpang tindih.

---

## 2. Kondisi kode AI di repo sekarang — peta redundansi

Repo FETAL-GUARD **sudah** punya infrastruktur AI yang cukup matang. Masalahnya bukan "belum ada", tapi **ada dua filosofi pemodelan yang jalan paralel + satu model tamu**:

### 2.1 Jalur A — paket `fetal_guard_ai` (milik kita, "cara roadmap")

- `ai/src/fetal_guard_ai/` — `model.py` (`HybridCNNLSTMConfig`: multimodal **piezo 4ch + FSR 1ch + PPG maternal 2ch**, branch CNN → temporal bins → fusion → LSTM → **multi-task: measurement + quality + screening 3-kelas**), `contracts.py`, `preprocessing.py`, `features.py`, `labels.py`, `artifact.py`, `model_spec.py`, `telemetry.py`, `training_data.py`
- `ai/scripts/train_cnn_lstm.py` — training runner (group holdout split, hash artefak)
- `backend/run_ai_inference_worker.py` — worker terisolasi, `from fetal_guard_ai.inference import predict_preprocessed_window`, `prepare_stored_telemetry_window` (rekonstruksi window dari `SensorDataChunk` mentah)
- `backend/services/ai_pipeline.py` — `enqueue_ready_window()` (dipanggil dari `api/routes/sessions.py:818` saat ingestion), job/lease/attempt lifecycle, `AIModelVersion` gate (`deployment_slot` harus == `AI_PIPELINE_MODE`, `validation_status` gate)
- `backend/run_ai_publication_worker.py` — worker promosi hasil yang sudah di-review nakes
- **Input:** window telemetri v2 mentah. **Output:** screening 3-kelas + measurement + quality. **Belum ada checkpoint terlatih** (butuh data).

### 2.2 Jalur B — adapter model Adit

- `ctg_cnn_lstm_merged/` — model Adit di-vendor (versi lama)
- `backend/services/ctg_cnn_lstm_adapter.py` — `predict_from_payload()`: coerce payload → window `(15,3)` → `from app.ai.inference import CTGPredictor`
- `backend/api/routes/ai.py:/predict` — endpoint langsung, panggil adapter, **melewati** worker & job lifecycle & artefak gate jalur A
- `backend/scripts/register_ctg_model.py` — daftarkan checkpoint Adit sebagai `AIModelVersion`, **set `validation_status="analytical_validated"`** (❌ salah — datanya sintetis), `deployment_slot="research"`
- **Input:** deret bpm turunan. **Output:** 4-head klasifikasi ambang.

### 2.3 Lapisan DSP — dua implementasi

| Pekerjaan | Milik kita (`backend/services/`) | Milik Adit (`ctg_cnn_lstm_merged/app/`) |
|---|---|---|
| piezo → FHR bpm | `signal_processing.py` — envelope + autocorrelation ternormalisasi, pure-Python | `signal_processing/bpm.py` — bandpass + peak detect |
| pilih kanal piezo terbaik | best-per-window (SQI) | `SensorSelector` **dengan hysteresis** |
| PPG → MHR bpm | `signal_processing.py` autocorrelation | `signal_processing/bpm.py` |
| SQI | tinggi puncak autocorrelation | `signal_quality/sqi.py` |
| FSR → kontraksi | `classify_contraction_indicator()` — **kategori** none/mild/regular/strong | `ctg/uterine.py` — `estimate_uc_rate()` **hitungan /10 mnt** + `UterineBaseline` kalibrasi |
| orkestrasi | `vitals_derivation.py` (throttle, fail-closed, window 20s) | `services/sensor_pipeline.py` + `ctg_service.py` (buffer per-device in-memory) |

### 2.4 Kesimpulan peta

- **`enqueue_ready_window` (jalur A) sudah terpasang di ingestion** — jadi begitu `AI_PIPELINE_MODE≠disabled` + ada `AIModelVersion` aktif, job mulai dibuat. Tapi worker jalur A butuh model `fetal_guard_ai` yang **belum ada checkpoint-nya**.
- **`api/routes/ai.py:/predict` (jalur B) hidup paralel** dan akan pakai model Adit lewat adapter — **melewati** gate keselamatan jalur A.
- **Lapisan DSP terduplikasi.** Untuk demo lokal, kita punya `vitals_derivation.py`. Untuk model Adit, `sensor_pipeline.py`-nya perlu di-port atau di-panggil.

---

## 3. Arsitektur target — satu pipeline

### 3.1 Prinsip

1. **Satu jalur inferensi.** Semua inferensi lewat: ingestion → `enqueue_ready_window` → job → **worker terisolasi** → `AIAnalysisResult` → review nakes → publication worker. Tidak ada endpoint "predict langsung".
2. **Satu lapisan DSP.** `backend/services/signal_processing.py` + `vitals_derivation.py` adalah sumber tunggal FHR/MHR/SQI/kontraksi. Lapisan DSP Adit **tidak di-vendor**; yang berguna (hysteresis pemilih kanal, `estimate_uc_rate`) di-port ke modul kita.
3. **Satu registry model.** `AIModelVersion` dengan `deployment_slot` + `validation_status` + `artifact_sha256` + `input_schema_version`. `AI_PIPELINE_MODE` (disabled → research → shadow → clinician) adalah satu-satunya saklar.
4. **Gate validasi non-negotiable** (§5).
5. **Model = pluggable.** Worker memuat model lewat kontrak (`fetal_guard_ai.inference` style), bukan `import app.ai` hard-coded. Model Adit dan model kita sama-sama bisa didaftarkan sebagai `AIModelVersion` berbeda; yang aktif ditentukan `AI_ACTIVE_MODEL_VERSION_ID`.

### 3.2 Peran model Adit dalam arsitektur target

**Model Adit = `AIModelVersion` di slot `research`, sebagai baseline pembanding.** Bukan model utama, bukan clinician-facing. Nilainya:

- **Baseline "rule + temporal smoothing"** untuk mengukur apakah model multimodal kita benar-benar lebih baik.
- **Resep training** — `generate_sequences.py`, `train.py`, `cross_validate.py`, `baseline.py`, `sanity_check.py` adalah template yang bagus untuk melatih `fetal_guard_ai` (split sesi, CV, baseline, ablation noise).
- **Cadangan** — jika model multimodal kita gagal konvergen pada data terbatas, model 3-fitur Adit (di atas nilai turunan `vitals_derivation`) adalah fallback yang jujur asal digate `shadow`.

### 3.3 Alur data (target)

```
ESP32 belt --(telemetri v2, HMAC-signed)--> POST /sessions/{id}/data
    -> SensorDataChunk (raw p/fsr/hr_ir/hr_red disimpan)
    -> derive_session_vitals()  [ingestion, throttled]
         -> SessionSensorSummary.{fhr,maternal_hr,sqi,contraction,derivation_status}  [nilai TERBARU]
         -> evaluate_session_alerts()  [rule-based, dari nilai turunan]
    -> enqueue_ready_window()  [jika AI_PIPELINE_MODE != disabled]
         -> AIInferenceJob (window [start,end), input_hash)

[worker terisolasi — proses & role DB terpisah]
    claim_next_inference_job()
    -> prepare_window(): baca SensorDataChunk dalam window
         -> DSP kita: derive deret 15-titik [FHR, MHR, UC-rate] dari sub-window
            ATAU rekonstruksi tensor multimodal mentah (tergantung model aktif)
    -> model.predict()  [fetal_guard_ai ATAU adapter Adit, sesuai AIModelVersion]
    -> safety layer: quality gate, uncertainty gate, insufficient-signal gate
    -> AIAnalysisResult (visibility = shadow)  + reason codes

[nakes] lihat feed AI shadow di patient-detail -> catat review decision
[publication worker] promosikan HANYA hasil yang di-review dari model clinical_validated
    -> AIAnalysisResult.visibility = clinician / patient
```

### 3.4 Yang perlu dibangun / diubah

| # | Item | Lokasi | Estimasi |
|---|------|--------|----------|
| I1 | Estimator **UC rate** (hitungan kontraksi/10 mnt) dari FSR — port `estimate_uc_rate` + `UterineBaseline` Adit ke `services/signal_processing.py` | backend | S |
| I2 | Hysteresis pemilih kanal piezo — port `SensorSelector` ke `signal_processing.py` (kurangi flip-flop antar window) | backend | S |
| I3 | `prepare_window()` di worker: dari `SensorDataChunk` window → deret 15-titik `[FHR,MHR,UC-rate]` (untuk model Adit) **atau** tensor multimodal (untuk model kita) — dispatch by `AIModelVersion.architecture` | backend/worker | M |
| I4 | Perbaiki `register_ctg_model.py`: `validation_status="experimental"` (bukan `analytical_validated`), `deployment_slot="research"`, tambah `model_card_uri` | backend/scripts | S |
| I5 | **Hapus jalur B**: `api/routes/ai.py:/predict` diarahkan ke job lifecycle (atau dihapus), `ctg_cnn_lstm_adapter.py` dipindah jadi salah satu loader di worker | backend | M |
| I6 | Vendor **hanya** model + inference + definisi label + skrip training Adit ke `ai/vendor/ctg_cnn_lstm/` (bukan `app/signal_processing/`, bukan `main.py`, bukan `aiService.js`). Update dari GitHub terbaru. `torch.load(weights_only=True)`. | repo | S |
| I7 | Model card wajib untuk tiap `AIModelVersion` (`ai/model-cards/*.md`): data training, intended use, batasan, metrik validasi | repo | S |
| I8 | Persistensi deret nilai turunan **opsional** — worker sudah bisa derive on-demand dari raw chunk; hanya perlu tabel `session_vitals_series` kalau mau chart tren per-window (bukan per-sesi) | backend | M (defer) |
| I9 | Validasi tier-2 ke JNU-CTG + CTU-UHB, tier-1 ke IIScFHSDB + SUFHSDB (§4b); selesaikan `external_validation.py` (kolaborasi dengan Adit) | model repo | L |
| I10 | Latih `fetal_guard_ai` (model multimodal kita) — butuh data window telemetri v2 nyata/semi-nyata + label. Pakai resep Adit (split sesi, CV, baseline). | ai/ | L |

Ukuran: S = <1 hari, M = 1–3 hari, L = >1 minggu / butuh data eksternal.

---

## 4. Hybrid DL di "pengolahan data" & "monitoring" — desain konkret

### 4.1 Pengolahan data (ingestion → analisis)

- **Layer rule (sudah ada, tetap jadi tulang punggung):** `services/alerting.py` — alert dari nilai turunan `vitals_derivation`, bahasa skrining, gate SQI, 1 alert per rule per sesi. Ini yang clinician lihat **sekarang** dan **selama AI belum tervalidasi**.
- **Layer DL (shadow):** worker menjalankan model aktif per window; hasil disimpan sebagai `AIAnalysisResult` dengan `visibility=shadow`. Tidak memicu alert, tidak tampil ke pasien.
- **Hybrid = rule ∪ DL, dengan rule sebagai otoritas:** ketika (dan hanya ketika) model mencapai `clinical_validated`, hasil DL yang **sudah di-review nakes** boleh:
  - menambah reason-code pada alert rule yang sudah ada ("pola deselerasi terdeteksi model, konsisten dengan FHR di luar rentang"), **atau**
  - memunculkan "perlu observasi" untuk pola temporal yang rule lewatkan (mis. variabilitas menurun sementara nilai masih in-range) — selalu lewat review nakes dulu.
- **Safety layer (sudah dispesifikasikan di `fetal_guard_ai`):** quality head, uncertainty gate, technical-output-range gate, insufficient-signal gate. Window yang tidak lolos → tidak ada output DL (bukan output "normal").

### 4.2 Monitoring (dashboard nakes & app pasien)

- **Nakes — patient detail panel:** blok "Rentetan Analisis Hybrid" yang sekarang selalu kosong → diisi feed `AIAnalysisResult` shadow **hanya untuk nakes**, dengan label eksplisit "SHADOW — belum tervalidasi, tidak untuk keputusan klinis" + tombol review (agree / disagree / dismiss). Review nakes inilah yang jadi label untuk validasi lanjutan.
- **Nakes — kalau AI masih `disabled`:** blok itu **disembunyikan**, bukan menampilkan empty state (lihat rekomendasi UI di `clinician-dashboard-ui-state`).
- **Pasien:** **tidak ada** output DL sampai `clinical_validated` **dan** ada review nakes non-dismissed (sudah dienforce di `publish_reviewed_analysis_results`). Sampai itu, pasien hanya lihat hasil rule-based dengan bahasa skrining.
- **Realtime:** event `ai.analysis.updated` sudah ada di `ai_pipeline.py` — dipakai untuk push feed shadow ke dashboard nakes.

### 4.3 Konfigurasi

| Setting | Nilai sekarang (staging) | Target fase |
|---|---|---|
| `AI_PIPELINE_MODE` | `disabled` | `research` (internal) → `shadow` (feed nakes berlabel) → `clinician` |
| `AI_ACTIVE_MODEL_VERSION_ID` | kosong | id `AIModelVersion` model aktif |
| `AI_WINDOW_SECONDS` / `_STRIDE_SECONDS` | 60 / 15 | sesuaikan dgn `seq_len` model (Adit butuh ~225s untuk 15×15s; model kita 60s) |

---

## 4b. Dataset publik untuk training & validasi nyata

**Model Adit sekarang dilatih 0% data nyata** (100% generator sintetis). Keempat dataset di bawah adalah yang tepat, dipetakan ke dua tingkat pipeline:

| Dataset | Isi | Sinyal | Label / ground-truth | Tingkat | Lisensi |
|---|---|---|---|---|---|
| **IIScFHSDB** — physionet.org/content/fetalheartsounddata/1.0 | 60 rekaman fPCG, ~8 mnt, 2 kHz, `.wav` | Bunyi jantung janin (stetoskop elektronik, perut bawah) — sepadan kanal **piezo** | FHR dari catatan pasien "bila ada", tidak sistematis | **Tier 1** (sinyal→FHR) | ODC-BY 1.0, tanpa login |
| **SUFHSDB** — physionet.org/content/sufhsdb/1.0.1 | 119 fPCG janin + 92 bunyi jantung ibu, ~90 dtk, 16 kHz, WFDB | fPCG janin **+ maternal** | FHR CTG per window 10 dtk untuk sebagian subjek | **Tier 1** + referensi **HR ibu** | ODC-BY 1.0, tanpa login |
| **JNU-CTG** — zenodo.org/records/21800730 | **20.769** rekaman CTG, 30 mnt, 4 Hz | Trace FHR + UC turunan | **Anotasi pola CTG oleh ahli + Apgar 1/5/10 + diagnosis asfiksia neonatal** + demografi + 100+ fitur precomputed | **Tier 2** (vitals→skrining) — dataset utama | CC-BY-4.0 |
| **CTU-UHB** — physionet.org/content/ctu-uhb-ctgdb/1.0.0 | 552 rekaman CTG intrapartum, 4 Hz, WFDB | Trace FHR + UC | pH tali pusat, BDecf, Apgar (outcome, bukan label pola) | **Tier 2** — benchmark klasik, kecil | Open, perlu akun PhysioNet gratis |

**Pemetaan:**

- **Tier 1 — sinyal mentah → FHR/MHR** (`services/signal_processing.py` + branch CNN `fetal_guard_ai`): dilatih/divalidasi pada **IIScFHSDB + SUFHSDB**. Ini yang belt benar-benar "dengar" (piezo ≈ fPCG). SUFHSDB memberi referensi HR ibu yang CTU-UHB tidak punya.
- **Tier 2 — deret vitals → skrining pola** (model Adit / screening-head kita): dilatih/divalidasi pada **JNU-CTG (utama) + CTU-UHB (benchmark)**. JNU-CTG jauh lebih besar dan punya label pola ahli + outcome asfiksia — ini yang membuat "hybrid DL" bermakna klinis, bukan sekadar meniru ambang.

**Risiko & catatan yang harus dicantumkan di model card:**

- **Gap domain sensor.** fPCG klinis direkam stetoskop elektronik; belt kita piezo film. Kopling akustik & respons frekuensi berbeda — model tier-1 yang dilatih fPCG klinis **belum tentu transfer** ke piezo tanpa set kalibrasi piezo kecil (rekaman belt sendiri + referensi Doppler). Ini blocker transfer, bukan sekadar catatan.
- Model Adit **tidak bisa** langsung memakai IIScFHSDB/SUFHSDB (minta angka FHR/MHR/UC, bukan audio) — estimator bpm tier-1 harus jalan dulu.
- CTU-UHB & JNU-CTG: tidak ada kanal MHR terpisah → head MHR tidak bisa divalidasi di sini (pakai SUFHSDB untuk itu).
- UC: CTU-UHB & JNU-CTG dalam satuan tekanan toco, bukan "kontraksi/10 menit" — perlu deteksi puncak kontraksi untuk memetakan ke `label_uc()`.
- fPCG DB pendek (8 mnt / 90 dtk) & kecil (60 / 119 subjek) — cukup untuk validasi/tuning estimator tier-1, **marginal untuk melatih deep model tier-1 dari nol**; pertimbangkan pretraining + fine-tune, atau tetap pakai DSP klasik untuk tier-1 dan simpan DL untuk tier-2.
- Semua dataset butuh sitasi; JNU-CTG & fPCG DB tanpa proses kredensial, CTU-UHB perlu akun PhysioNet gratis. Catat provenance + versi + tanggal unduh di `docs/ai/dataset-provenance.md`.

## 5. Gate validasi (non-negotiable — dari `AGENTS.md` §8)

| Slot | Syarat masuk | Yang boleh dilihat |
|------|--------------|--------------------|
| `research` | model terdaftar sebagai `AIModelVersion`, artefak hash tercatat, model card ada | Tidak ada UI. Log & metrik internal saja. **Model Adit sekarang di sini.** |
| `shadow` | `validation_status = analytical_validated` = dievaluasi pada **data CTG nyata held-out** (tier-2: JNU-CTG + CTU-UHB; tier-1: SUFHSDB, §4b), MAE FHR + confusion matrix + provenance data terdokumentasi di model card | Feed di dashboard nakes, **berlabel SHADOW**, untuk dikumpulkan review-nya. Tidak memicu alert. Tidak ke pasien. |
| `clinician` | `validation_status = clinical_validated` = perbandingan terhadap CTG/Doppler/toco pada subjek nyata + **ethical clearance** + sign-off nakes/dokter | Boleh menambah reason-code / memicu "perlu observasi" — **selalu** lewat review nakes. |
| pasien-facing | slot `clinician` **dan** review nakes non-dismissed per hasil | Baru boleh muncul di app pasien, bahasa skrining. |

**Model Adit sekarang: `experimental` → hanya `research`.** Untuk naik ke `shadow` butuh item I9 (validasi ke JNU-CTG/CTU-UHB/fPCG, §4b).

---

## 6. Blocker & TODO untuk Adit (kolaborasi)

1. **Selesaikan validasi ke data nyata** (lihat §4b untuk detail dataset):
   - **Tier 2 (model Adit):** validasi ke **JNU-CTG** (utama, 20.769 rekaman + label pola ahli + asfiksia) dan **CTU-UHB** (benchmark). Selesaikan `training/external_validation.py`.
   - Resolusi ketiadaan kanal MHR di CTU-UHB/JNU-CTG (validasi head MHR pakai SUFHSDB, atau latih ulang tanpa head MHR untuk data ini).
   - Mapping UC (tekanan toco) → "kontraksi/10 menit" `label_uc()` — butuh deteksi puncak kontraksi.
   - **Pertimbangkan melatih ulang** model tier-2 langsung di JNU-CTG (label pola nyata) alih-alih sintetis — ini yang membuatnya bermakna klinis.
   - Laporkan akurasi/MAE pada data nyata, **bandingkan dengan kurva ablation noise sintetis** untuk menunjukkan seberapa representatif data sintetis.
2. **`torch.load(weights_only=False)` → `weights_only=True`** atau ekspor ke `safetensors`. Pisahkan bobot dari kode.
3. **Publikasikan spec preprocessing + scaler sebagai versi eksplisit** (mirip `ai/src/fetal_guard_ai/model_spec.py`), supaya backend bisa memverifikasi kontrak input.
4. **Model card** (`ai/model-cards/ctg_cnn_lstm_adit.md`): data training = sintetis, intended use = riset/shadow, batasan (bukan diagnosis, belum data nyata), metrik CV, lisensi.
5. **Freeze API kontrak inferensi** — fungsi `predict(window: (15,3)) -> {fhr,mhr,uc,overall: {status, confidence}}` distabilkan; hilangkan state global (`_windows`, `_latest_by_device`) dari path yang di-import backend (itu tugas worker kita).
6. (opsional, kuat untuk lomba) ablation "akurasi vs level noise" pada data sintetis **dan** data nyata, satu grafik.

---

## 7. Rencana bertahap

### Fase 0 — Konsolidasi (sekarang, tanpa mengaktifkan AI)

- [ ] I6 — vendor bersih model Adit dari GitHub terbaru ke `ai/vendor/ctg_cnn_lstm/` (model + inference + label + training, TANPA DSP/`main.py`)
- [ ] I4 — perbaiki `register_ctg_model.py` (`experimental`, model card wajib)
- [ ] I5 — hapus/arahkan `api/routes/ai.py:/predict`; `ctg_cnn_lstm_adapter.py` jadi loader di worker
- [ ] Hapus `ctg_cnn_lstm_merged/` lama dari root repo
- [ ] I7 — template model card
- **Hasil:** satu jalur AI, satu lapisan DSP, redundansi hilang. `AI_PIPELINE_MODE` tetap `disabled`.

### Fase 1 — Research (internal)

- [ ] I1, I2, I3 — UC rate estimator, hysteresis, `prepare_window` di worker
- [ ] Daftarkan model Adit sebagai `AIModelVersion` slot `research`
- [ ] `AI_PIPELINE_MODE=research` di lingkungan dev; worker jalan, hasil masuk `AIAnalysisResult` (tidak ada UI)
- [ ] `npm run simulate:belt` → verifikasi job dibuat, worker memproses, hasil tersimpan
- **Hasil:** pipeline end-to-end terbukti jalan dengan model nyata (walau sintetis).

### Fase 2 — Validasi (paralel, butuh Adit + data)

- [ ] I9 — Adit selesaikan validasi JNU-CTG + CTU-UHB (+ SUFHSDB untuk head MHR) → model card diperbarui → `validation_status=analytical_validated` bila lolos
- [ ] I10 — mulai latih `fetal_guard_ai` (model multimodal kita) dengan resep Adit
- [ ] Bandingkan: model Adit (3-fitur turunan) vs model kita (multimodal mentah) vs rule-based, pada data validasi yang sama

### Fase 3 — Shadow (nakes)

- [ ] `AI_PIPELINE_MODE=shadow` di staging; feed shadow berlabel di patient-detail panel
- [ ] Kumpulkan review nakes (agree/disagree/dismiss) sebagai label
- [ ] Blok "Rentetan Analisis Hybrid" di UI: tampil hanya saat ada hasil shadow, dengan disclaimer

### Fase 4 — Clinician (butuh ethical clearance + uji klinis)

- [ ] Uji terbatas klinis (bandingkan CTG/Doppler), ethical clearance
- [ ] `validation_status=clinical_validated` + sign-off
- [ ] `AI_PIPELINE_MODE=clinician`; hybrid rule+DL aktif lewat review nakes
- [ ] Baru setelah ini: output ke app pasien

---

## 8. Yang TIDAK dilakukan

- ❌ Deploy `main.py` Adit sebagai microservice terpisah (state in-memory, tanpa auth, CORS `*`).
- ❌ Vendor `app/signal_processing/` Adit — kita sudah punya `services/signal_processing.py`.
- ❌ Set `validation_status=analytical_validated` untuk model yang dilatih data sintetis.
- ❌ Tampilkan output DL apa pun ke pasien sebelum Fase 4.
- ❌ Membiarkan dua jalur inferensi (A & B) hidup bersamaan.
- ❌ Mengubah `alerting.py` rule-based jadi bergantung pada DL — rule tetap otoritas.

---

## 9. Ringkasan keputusan

| Pertanyaan | Jawaban |
|---|---|
| Model Adit bagus? | Metodologi ya, data & keunggulan marginal. Slot `research` saja untuk sekarang. |
| Integrasikan apa adanya? | Tidak. Konsolidasi dulu (Fase 0), jadikan baseline + resep training. |
| Pakai model siapa? | Target: model multimodal kita (`fetal_guard_ai`). Model Adit = baseline & fallback shadow. |
| Kapan pasien lihat hasil AI? | Fase 4 — setelah `clinical_validated` + review nakes. Tidak sebelum itu. |
| Redundansi kode AI? | Nyata dan sudah ada di repo. Fase 0 menghapusnya. |
