# Model Card — ctg_cnn_lstm_adit

**Status per 2026-09-10:** `experimental` → `research` slot only. Not registered
in any running environment. Fetched on demand, not vendored (see section 6).

## 1. Identity

| Field | Value |
|---|---|
| `model_name` | `ctg_cnn_lstm_adit` |
| `architecture` | `cnn_lstm_multitask` (`CTGCNNLSTM`) |
| `input_schema_version` | 2 (operates on **derived** vitals, not raw telemetry) |
| `preprocessing_version` | `adit-derived-vitals-15x3` |
| Source | https://github.com/Adityakknn/ctg_cnn_lstm_adit @ `25e60611b17426b10a4fd76a41c08bcaa5a5c76d` (2026-09-01) |
| Owner | Adit (Adityakknn) — collaborating PKM team member |
| In our system | `scripts/fetch-ctg-adit-reference.ps1` → `ai/vendor/ctg_cnn_lstm_adit/` (gitignored); register with `backend/scripts/register_ctg_model.py` |

## 2. Intended use

**For:**

1. **Baseline comparator** — a "rule + temporal smoothing on derived FHR/MHR/UC"
   yardstick to measure whether our own multimodal model (`ai/src/fetal_guard_ai`,
   raw telemetry) actually beats a simple approach.
2. **Training-methodology template** — its session-level split, Group K-Fold CV,
   baseline suite, and noise-ablation harness are a good recipe for training
   `fetal_guard_ai` (PRD item I10).
3. **Competition material** — the CV + baseline + honest reporting is solid PKM
   content.

**Not for:**

- ❌ Any clinician-facing output (not even a labelled SHADOW feed).
- ❌ Any patient-facing output.
- ❌ Any claim of clinical accuracy, sensitivity, or specificity.
- ❌ Triggering or modifying alerts. Rule-based `alerting.py` stays the authority.

To advance to `shadow` it must reach `analytical_validated` = evaluated on real
held-out CTG data (JNU-CTG + CTU-UHB; SUFHSDB for the MHR head) with MAE +
confusion matrix + data provenance written into this card. See PRD sections 4b
and 5.

## 3. Inputs and outputs

- **Input:** `(batch, 15, 3)` — 15 sequential readings of
  `[FHR bpm, MHR bpm, UC count / 10 min]`. `dt = 15 s` → one window is ~3.75 min
  of context. These are **DSP-derived values**, not raw piezo/FSR/PPG.
- **Architecture:** `Conv1d(3→32, k3) → ReLU → Conv1d(32→64, k3) → BatchNorm1d →
  ReLU → LSTM(64→64) → Dropout(0.3) → 4 linear heads`.
- **Output heads:** `fhr` (3-class), `mhr` (3-class), `uc` (3-class), `overall`
  (2-class Normal/Abnormal, derived from the other three).
- **Scaler:** z-score from the **training split only**, stored in the checkpoint.

## 4. Training data

**100% synthetic. Zero real patient recordings.**

- `training/generate_sequences.py`: `_generate_raw_series()` = random walk +
  2–6 injected "abnormal episodes" (brady / tachy / hypo / tachysystole) per
  session.
- Labels = **exact clinical thresholds** on the *clean* physiological signal
  (`label_fhr`: <110 brady, >160 tachy; `label_mhr`: ACOG 70–110;
  `label_uc`: 2–5 / 10 min).
- The window `X` the model sees = clean signal + Gaussian measurement noise
  (σ: FHR 6.0, MHR 5.0, UC 1.0) + 10 %/timestep artifact dropout
  (electrode-off / motion).
- 250 sessions × ~106 windows = **26,500 windows**.

**What this means:** the model learns *"apply the clinical thresholds, robust to
measurement noise"* — not *"recognise real CTG pathology"* (late decelerations,
loss of variability, etc. are not in the generator). A 97 % accuracy figure is
"how well a CNN-LSTM mimics `label_fhr()` through noise", not a clinical result.

**Domain gap vs. our hardware:** the model never touches piezo/FSR/MAX30102
signals. It sits downstream of whatever DSP produces the bpm series. Our
`backend/services/signal_processing.py` would have to feed it.

## 5. Evaluation

**Methodology — strong and honestly reported:**

- Session-level `GroupShuffleSplit` (`groups=session_id`), zero-overlap asserted.
- Normalisation computed from the train split only.
- Baselines: rule-based (threshold on last reading), Logistic Regression,
  Random Forest (flattened window).
- 5-fold Group CV (`training/cross_validate.py`), each session in test exactly
  once; dropout 0.3, `weight_decay=1e-4`, early stopping.
- `results/README_RESULTS.md` reports the mixed result without polishing it.

**5-fold Group CV — accuracy, mean ± std** (from `results/README_RESULTS.md`):

| Target  | Rule-based    | Random Forest   | CNN-LSTM        |
|---------|--------------:|----------------:|----------------:|
| FHR     | 92.84 ± 0.70  | **97.32 ± 0.35** | 97.14 ± 0.75    |
| MHR     | 92.12 ± 0.99  | **97.03 ± 0.49** | 96.81 ± 0.48    |
| UC      | 79.55 ± 1.02  | 88.12 ± 0.72    | **88.35 ± 0.95** |
| Overall | 82.27 ± 1.20  | 88.49 ± 1.08    | **89.13 ± 1.13** |

Per-fold, CNN-LSTM beats Random Forest on **Overall in 5/5 folds** — but by only
**+0.34 to +1.15 points**, and it loses slightly on FHR and MHR individually. The
repo's own `results/cross_validation_results.json` (a 15-epoch re-run) gives
Overall 88.9 %, i.e. the "≈ Random Forest, <1 pt edge" conclusion is stable.

**Interpretation:** on 3 features × 15 steps with random-walk + injected-episode
patterns, the extra capacity of a CNN-LSTM buys little over a Random Forest on
the flattened window. The LSTM's advantage would show on more complex temporal
patterns than this generator produces.

**Real-CTG external validation: NOT DONE.** `training/external_validation.py` has
real WFDB-loading code but has never been run — CTU-UHB is not downloaded, the
missing-MHR-channel issue is unresolved, and the UC (mmHg → count/10min) mapping
is not implemented.

## 6. Limitations and risks

- Accuracy numbers measure threshold-mimicry through synthetic noise, not
  clinical detection.
- No real data anywhere in training or evaluation.
- Marginal (<1 pt) edge over a much simpler Random Forest on this task.
- Operates on derived vitals, so it inherits every error of the upstream DSP and
  adds a domain gap (trained on synthetic bpm, not our sensor's bpm).
- **Security:** `app/ai/inference.py` uses `torch.load(weights_only=False)` →
  arbitrary code execution on checkpoint load. Only ever load a checkpoint you
  trained yourself. The synthetic dataset and weights are reproducible from
  seed 42 (`generate_sequences.py` → `train.py`), so there is no reason to accept
  an untrusted `.pt`. `fetal_guard_ai` (path A) already uses `weights_only=True`;
  if this model is wired into the worker, its loader must be hardened first.
- **Not vendored on purpose.** A copy in-tree drifted ~2 weeks stale once already
  (the old `ctg_cnn_lstm_merged/`, removed in Fase 0). Fetch it at the pinned
  commit when a phase actually needs it.

## 7. Changelog

| Date | Change |
|---|---|
| 2026-09-04 | Reviewed for the hybrid-DL PRD; verdict: `research` slot only |
| 2026-09-10 | Fase 0 — stale in-tree copy removed; this card written; fetch-on-demand script added; `register_ctg_model.py` corrected to `experimental` |
