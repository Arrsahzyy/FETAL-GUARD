# Model Card — <model name> <version>

> Every `AIModelVersion` registered in the FETAL-GUARD pipeline MUST have a model
> card at `docs/ai/model-cards/<model_name>.md`. `backend/scripts/register_ctg_model.py`
> refuses to register a model without one. Keep it in sync with the DB row.

## 1. Identity

| Field | Value |
|---|---|
| `model_name` | |
| `version` | |
| `architecture` | |
| `input_schema_version` | |
| `preprocessing_version` | |
| `artifact_sha256` | |
| Source | repo URL + commit SHA + date |
| Owner | who trained it |

## 2. Intended use

- What it is for.
- What it is explicitly **not** for (be specific: "no clinician UI", "no patient
  output", "no clinical claim" as applicable).
- Current `deployment_slot` and `validation_status`, and what gate it would need
  to pass to advance (see `docs/ai/hybrid-dl-integration-prd.md` section 5).

## 3. Inputs and outputs

- Input tensor shape, channels, units, window length, sample rate.
- Output heads, class labels, value ranges.
- Safety layer / postprocessing applied before the result is stored.

## 4. Training data

- Source(s). **State plainly if any part is synthetic.**
- Size (sessions / windows / recordings).
- Label definition and provenance (expert annotation? outcome? threshold rule?).
- Known distribution gaps vs. FETAL-GUARD belt hardware (piezo / FSR / MAX30102).

## 5. Evaluation

- Split method (session-level? group id? leakage check?).
- Metrics on held-out data, with baselines (rule-based + a simple ML baseline).
- Cross-validation if done.
- **Real-CTG external validation**: dataset, metrics, or "not done".

## 6. Limitations and risks

- What the accuracy numbers actually measure.
- Failure modes.
- Security notes (e.g. `torch.load(weights_only=False)`).
- Anything that must be said out loud in a competition report or to a clinician.

## 7. Changelog

| Date | Change |
|---|---|
| | |
