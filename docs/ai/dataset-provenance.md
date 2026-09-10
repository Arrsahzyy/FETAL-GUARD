# AI Dataset Provenance

Every dataset used to train or validate a FETAL-GUARD model is recorded here:
source URL, version, download date, licence, and citation obligation. Raw
clinical data is **never** committed (see `.gitignore` and `ai/config/datasets.json`).

Rationale and the tier-1 / tier-2 mapping are in
`docs/ai/hybrid-dl-integration-prd.md` section 4b.

## Status per 2026-09-10

**Nothing downloaded yet.** No FETAL-GUARD model — ours or Adit's — has been
trained or validated on any real recording. Adit's `ctg_cnn_lstm_adit` is 100%
synthetic (`docs/ai/model-cards/ctg_cnn_lstm_adit.md`).

| Dataset | Purpose | Tier | Licence | Access | Local path | Downloaded |
|---|---|---|---|---|---|---|
| **CTU-UHB Intrapartum CTG** — physionet.org/content/ctu-uhb-ctgdb/1.0.0 | 552 intrapartum CTG, 4 Hz; FHR + UC trace; pH / BDecf / Apgar outcomes | Tier 2 benchmark | Open (free PhysioNet account) | account | `ai/data/raw/ctu-uhb-ctgdb/1.0.0` | ☐ |
| **JNU-CTG** — zenodo.org/records/21800730 | 20,769 CTG, 30 min, 4 Hz; **expert pattern annotation + Apgar + neonatal asphyxia diagnosis** | Tier 2 primary | CC-BY-4.0 | none | `ai/data/raw/jnu-ctg` | ☐ |
| **SUFHSDB** — physionet.org/content/sufhsdb/1.0.1 | 119 fetal + 92 maternal PCG, ~90 s, 16 kHz; FHR per 10 s window for some subjects | Tier 1 (+ maternal HR reference) | ODC-BY-1.0 | none | `ai/data/raw/sufhsdb/1.0.1` | ☐ |
| **IIScFHSDB** — physionet.org/content/fetalheartsounddata/1.0 | 60 fetal PCG, ~8 min, 2 kHz; FHR from patient notes where available | Tier 1 (signal → FHR) | ODC-BY-1.0 | none | `ai/data/raw/fetalheartsounddata/1.0` | ☐ |
| **fPCGDB** — physionet.org/content/fpcgdb/1.0.0 | Fetal PCG exploration | Tier 1 (exploration) | Open | account | `ai/data/raw/fpcgdb/1.0.0` | ☐ |
| **ADFECGDB** — physionet.org/content/adfecgdb/1.0.0 | Abdominal + direct fetal ECG reference | reference only | Open | account | `ai/data/raw/adfecgdb/1.0.0` | ☐ |

## When a dataset is downloaded

Add a row below with: dataset id, version, ISO date, SHA-256 of the archive (or
`wfdb` record count), the licence text location, and the required citation. Then
reference this file from the model card of any model trained or validated on it.

_(none yet)_

## Known blockers before real-data validation is meaningful

- **Sensor domain gap.** Clinical fPCG is recorded with an electronic
  stethoscope; our belt uses a piezo film. A tier-1 model trained on clinical
  fPCG may not transfer without a small piezo calibration set (belt recordings +
  a Doppler reference). This is a transfer blocker, not a footnote.
- **No separate MHR channel** in CTU-UHB / JNU-CTG — validate the MHR head on
  SUFHSDB, or retrain without it for those sets.
- **UC units.** CTU-UHB / JNU-CTG UC is toco pressure, not "contractions / 10 min"
  — needs contraction-peak detection to map onto `label_uc()`.
- fPCG sets are short (8 min / 90 s) and small (60 / 119 subjects) — fine for
  validating/tuning a tier-1 estimator, marginal for training a deep model from
  scratch.
