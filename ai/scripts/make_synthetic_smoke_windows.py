"""Generate a synthetic multimodal ``.npz`` for a NON-CLINICAL pipeline smoke test.

This produces the exact key layout that ``ai/scripts/train_cnn_lstm.py`` expects
(``fetal_guard_ai.training_data.load_hybrid_training_npz``), with
``dataset_kind="synthetic_smoke_test"`` so training refuses to run without
``--allow-synthetic-smoke-test`` and the resulting artifact can never be promoted
past the ``research`` slot.

What the signals are:

- **piezo** (4 ch, 250 Hz): a fetal-beat pulse train at the window's FHR, with a
  per-channel amplitude taper + baseline wander + white noise.
- **fsr** (1 ch, 50 Hz): uterine tone baseline; a raised-cosine plateau when a
  contraction is injected.
- **maternal_ppg** (2 ch, 100 Hz): IR + red pulse trains at the window's MHR.

Each window is passed through the SAME ``robust_zscore(interpolate_missing(...))``
that ``fetal_guard_ai.telemetry.prepare_stored_telemetry_window`` applies at
inference, so training and serving see the same scale.

Labels are derived from the clean physiological FHR/MHR the window was built from
(threshold rule + a reduced-variability flag) -- exactly the "mimic the
thresholds through noise" task Adit's model has, and just as non-clinical. See
``docs/ai/model-cards/`` and ``docs/ai/hybrid-dl-integration-prd.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ai" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fetal_guard_ai.preprocessing import interpolate_missing, robust_zscore
from fetal_guard_ai.telemetry import DEFAULT_TARGET_RATES_HZ

PREPROCESSING_VERSION = "synthetic-smoke-v1"

# (baseline_fhr, fhr_drift_per_window, baseline_mhr, reduced_variability, noise_boost)
SCENARIOS = {
    "normal": (142.0, 0.0, 82.0, False, 0.0),
    "normal_active": (150.0, 0.0, 92.0, False, 0.05),
    "mild_brady_drift": (150.0, -6.0, 84.0, False, 0.0),
    "tachy": (172.0, 1.2, 96.0, False, 0.03),
    "reduced_variability": (140.0, 0.0, 80.0, True, 0.0),
    "noisy_borderline": (164.0, 0.0, 100.0, False, 0.28),
}


def _pulse_train(duration_s: float, hz: float, rate_bpm: float, rng) -> np.ndarray:
    n = int(round(duration_s * hz))
    t = np.arange(n) / hz
    beat_hz = rate_bpm / 60.0
    phase = 2.0 * np.pi * beat_hz * t
    # narrow positive pulse once per beat + a smaller secondary bump
    beat = np.exp(3.0 * (np.cos(phase) - 1.0)) + 0.35 * np.exp(6.0 * (np.cos(phase - 0.9) - 1.0))
    wander = 0.25 * np.sin(2.0 * np.pi * rng.uniform(0.08, 0.2) * t + rng.uniform(0, 6.28))
    return (beat - beat.mean() + wander).astype(np.float32)


def _contraction_curve(duration_s: float, hz: float, present: bool, rng) -> np.ndarray:
    n = int(round(duration_s * hz))
    t = np.linspace(0.0, 1.0, n)
    baseline = 0.15 + 0.05 * np.sin(2.0 * np.pi * rng.uniform(0.03, 0.09) * np.arange(n) / hz)
    if not present:
        return baseline.astype(np.float32)
    centre = rng.uniform(0.35, 0.65)
    width = rng.uniform(0.28, 0.5)
    bump = 0.8 * np.exp(-0.5 * ((t - centre) / width) ** 2)
    return (baseline + bump).astype(np.float32)


def _finalize(window: np.ndarray, rng, *, dropout: bool) -> tuple[np.ndarray, np.ndarray]:
    """z-score like the inference path; optionally knock out a <20% contiguous gap."""
    values = window.astype(np.float32, copy=True)
    mask = np.ones(values.shape, dtype=bool)
    if dropout:
        gap = int(values.shape[0] * rng.uniform(0.08, 0.16))
        start = rng.integers(0, max(1, values.shape[0] - gap))
        values[start : start + gap, :] = np.nan
        mask[start : start + gap, :] = False
    prepared = robust_zscore(interpolate_missing(values))
    return prepared.astype(np.float32), mask


def _screening_label(fhr: float, reduced_variability: bool) -> int:
    if fhr < 100.0 or fhr > 175.0:
        return 2  # review_with_clinician
    if fhr < 110.0 or fhr > 160.0 or reduced_variability:
        return 1  # needs_observation
    return 0  # routine_monitoring


def build_dataset(sessions: int, windows_per_session: int, window_seconds: float, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    rates = DEFAULT_TARGET_RATES_HZ
    scenario_names = list(SCENARIOS)

    piezo, fsr, ppg = [], [], []
    piezo_m, fsr_m, ppg_m = [], [], []
    screening, quality, measurement, contraction, groups = [], [], [], [], []

    for session in range(sessions):
        scenario = scenario_names[session % len(scenario_names)]
        base_fhr, drift, base_mhr, reduced_var, noise_boost = SCENARIOS[scenario]
        group_id = f"synthbench-{session:03d}"
        session_fhr = base_fhr + rng.normal(0.0, 3.0)
        session_mhr = base_mhr + rng.normal(0.0, 2.5)

        for w in range(windows_per_session):
            var_scale = 0.6 if reduced_var else 2.4
            fhr = float(np.clip(session_fhr + drift * w + rng.normal(0.0, var_scale), 60.0, 220.0))
            mhr = float(np.clip(session_mhr + rng.normal(0.0, 1.8), 45.0, 180.0))
            noise = 0.12 + noise_boost + rng.uniform(0.0, 0.05)
            has_contraction = bool(rng.random() < 0.25)

            p = np.column_stack([
                taper * _pulse_train(window_seconds, rates["piezo"], fhr, rng)
                + rng.normal(0.0, noise, int(round(window_seconds * rates["piezo"])))
                for taper in (1.0, 0.62, 0.34, 0.16)
            ]).astype(np.float32)

            f = _contraction_curve(window_seconds, rates["fsr"], has_contraction, rng)
            f = (f + rng.normal(0.0, 0.02, f.shape))[:, None].astype(np.float32)

            m = np.column_stack([
                amp * _pulse_train(window_seconds, rates["maternal_ppg"], mhr, rng)
                + rng.normal(0.0, noise * 0.8, int(round(window_seconds * rates["maternal_ppg"])))
                for amp in (1.0, 0.7)
            ]).astype(np.float32)

            do_dropout = noise_boost > 0.2 and rng.random() < 0.5
            p, pm = _finalize(p, rng, dropout=do_dropout)
            f, fm = _finalize(f, rng, dropout=False)
            m, mm = _finalize(m, rng, dropout=do_dropout)

            q = float(np.clip(0.95 - noise_boost - (0.12 if do_dropout else 0.0) + rng.normal(0.0, 0.02), 0.55, 0.99))

            piezo.append(p); fsr.append(f); ppg.append(m)
            piezo_m.append(pm); fsr_m.append(fm); ppg_m.append(mm)
            screening.append(_screening_label(fhr, reduced_var))
            quality.append(q)
            measurement.append([fhr, mhr])
            contraction.append(1.0 if has_contraction else 0.0)
            groups.append(group_id)

    return {
        "piezo": np.stack(piezo), "fsr": np.stack(fsr), "maternal_ppg": np.stack(ppg),
        "piezo_validity_mask": np.stack(piezo_m),
        "fsr_validity_mask": np.stack(fsr_m),
        "maternal_ppg_validity_mask": np.stack(ppg_m),
        "screening_labels": np.asarray(screening, dtype=np.int64),
        "quality_targets": np.asarray(quality, dtype=np.float32),
        "measurement_targets": np.asarray(measurement, dtype=np.float32),
        "contraction_targets": np.asarray(contraction, dtype=np.float32),
        "group_ids": np.asarray(groups),
        "dataset_kind": np.asarray("synthetic_smoke_test"),
        "preprocessing_version": np.asarray(PREPROCESSING_VERSION),
        "input_schema_version": np.asarray(2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=str(ROOT / "ai" / "data" / "processed" / "synthetic_smoke_windows.npz"))
    parser.add_argument("--sessions", type=int, default=18)
    parser.add_argument("--windows-per-session", type=int, default=12)
    parser.add_argument("--window-seconds", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data = build_dataset(args.sessions, args.windows_per_session, args.window_seconds, args.seed)
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **data)

    labels, counts = np.unique(data["screening_labels"], return_counts=True)
    print(f"wrote {out}")
    print(f"  windows: {data['screening_labels'].shape[0]}  groups: {np.unique(data['group_ids']).size}")
    print(f"  screening class counts: {dict(zip(labels.tolist(), counts.tolist()))}")
    print(f"  piezo {data['piezo'].shape}  fsr {data['fsr'].shape}  maternal_ppg {data['maternal_ppg'].shape}")
    print(f"  contraction windows: {int(data['contraction_targets'].sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
