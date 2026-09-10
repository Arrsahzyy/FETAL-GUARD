# Training the `fetal_guard_ai` hybrid model — research slot

**Status per 2026-09-10:** first end-to-end run done on **synthetic smoke-test
data**. This proves the pipeline (`fetal_guard_ai` → worker → job → gate → result)
runs with a real checkpoint. It is **not** a clinical model — the numbers only
show the net can mimic threshold labels through noise, exactly like Adit's model.
Real training is Fase 2 (`docs/ai/hybrid-dl-integration-prd.md`), and needs the
datasets in `docs/ai/dataset-provenance.md`.

## Environment

Isolated from backend/prod (see `.gitignore` `.venv-ai/`):

```powershell
python -m venv .venv-ai
.venv-ai\Scripts\python -m pip install "numpy>=2.0"
.venv-ai\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

(Full data-prep deps for Fase 2: `pip install -r ai/requirements-ai.txt`.)

## 1. Synthetic smoke dataset

```powershell
.venv-ai\Scripts\python ai\scripts\make_synthetic_smoke_windows.py
```

→ `ai/data/processed/synthetic_smoke_windows.npz` (gitignored). 18 sessions
(groups) × 12 windows, 8 s each, at the model's input rates (piezo 250 Hz / fsr
50 Hz / maternal_ppg 100 Hz). Each window is z-scored with the **same**
`robust_zscore(interpolate_missing(...))` the inference path applies. Labels are
derived from the clean physiological FHR the window was built from
(`dataset_kind="synthetic_smoke_test"`).

## 2. Train

```powershell
cd ai
..\.venv-ai\Scripts\python scripts\train_cnn_lstm.py `
  --windows data\processed\synthetic_smoke_windows.npz `
  --model-version smoke-v1 --allow-synthetic-smoke-test `
  --epochs 20 --seed 42 --output-dir runs\cnn_lstm
```

`--allow-synthetic-smoke-test` is mandatory for synthetic data and the resulting
manifest carries `dataset_kind="synthetic_smoke_test"` — it can never be promoted
past `research`. Output: `ai/runs/cnn_lstm/smoke-v1/{model.pt, manifest.json, training_summary.json}`.

## 3. Verify end to end

Hermetic (in-memory sqlite, no servers), requires torch + the trained checkpoint:

```powershell
cd backend
venv\Scripts\python -m pytest tests\test_ai_hybrid_pipeline_smoke.py -q
```

Streams telemetry → `enqueue_ready_window` creates a job → `run_ai_inference_worker.run_once`
processes it → an `AIAnalysisResult` lands with `visibility=shadow`. Skips
automatically where torch or the checkpoint is absent (so it is a no-op in CI).

### Worker inner loop only (no DB)

```powershell
.venv-ai\Scripts\python ai\scripts\smoke_research_pipeline.py `
  --manifest ai\runs\cnn_lstm\smoke-v1\manifest.json
```

Builds synthetic telemetry v2 chunks → `prepare_stored_telemetry_window` →
`load_model_bundle` → `predict_preprocessed_window`. This is the exact path
`backend/run_ai_inference_worker.py` runs between claiming a job and completing it.

## 4. Register + run the full pipeline (dev)

```powershell
cd backend
venv\Scripts\python scripts\register_hybrid_model.py --manifest ..\ai\runs\cnn_lstm\smoke-v1\manifest.json
# writes backend/.env: AI_PIPELINE_MODE=research, AI_ACTIVE_MODEL_VERSION_ID=<id>
```

The inference worker imports both backend deps and torch, so its environment
needs both (dev only — `backend/requirements.txt` and prod stay torch-free):

```powershell
cd backend
venv\Scripts\python -m pip install "numpy>=1.24"
venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Then, in three terminals:

```powershell
npm run local                              # API + web (picks up the new .env)
cd backend; venv\Scripts\python run_ai_inference_worker.py --poll-seconds 2
npm run simulate:belt -- --seconds 120 --email <bench patient> --password <pw>
```

After ~`AI_WINDOW_SECONDS` of streamed telemetry, `enqueue_ready_window` creates
an `AIInferenceJob`; the worker processes it into an `AIAnalysisResult`
(`visibility=shadow`, no UI, no alert). Check:

```sql
SELECT status, attempts, error_code FROM ai_inference_jobs ORDER BY created_at DESC LIMIT 5;
SELECT screening_status, quality_status, visibility FROM ai_analysis_results ORDER BY created_at DESC LIMIT 5;
```

## 5. Turn it back off

```powershell
# remove AI_PIPELINE_MODE / AI_ACTIVE_MODEL_VERSION_ID from backend/.env, or set:
AI_PIPELINE_MODE=disabled
```

Staging/production stay `disabled` regardless — this is a dev-only exercise.
