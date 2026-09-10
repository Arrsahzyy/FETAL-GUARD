"""Offline smoke test of the AI inference worker's inner loop (no DB, no HTTP).

Proves, with a trained checkpoint, that:

  stored telemetry v2 chunks
    -> fetal_guard_ai.telemetry.prepare_stored_telemetry_window   (resample + mask)
    -> fetal_guard_ai.inference.load_model_bundle                 (manifest verify + weights_only load)
    -> fetal_guard_ai.inference.predict_preprocessed_window       (model + safety layer)
    -> a valid HybridScreeningResult

This is exactly what ``backend/run_ai_inference_worker.py`` does between claiming
a job and calling ``complete_inference_job``. Run it after training:

    .venv-ai/Scripts/python ai/scripts/smoke_research_pipeline.py \
        --manifest ai/runs/cnn_lstm/smoke-v1/manifest.json

Synthetic input -> non-clinical. This checks mechanics only.
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

from fetal_guard_ai.inference import load_model_bundle, predict_preprocessed_window
from fetal_guard_ai.telemetry import prepare_stored_telemetry_window

NATIVE_HZ = {"p": 200.0, "fsr": 50.0, "hr_ir": 100.0, "hr_red": 100.0}


def _beats(n: int, hz: float, bpm: float, amp: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n) / hz
    phase = 2.0 * np.pi * (bpm / 60.0) * t
    beat = np.exp(3.0 * (np.cos(phase) - 1.0))
    return amp * (beat - beat.mean()) + rng.normal(0.0, amp * 0.08, n)


def _chunk(seq: int, boot_id: str, seconds: float, fhr: float, mhr: float, rng) -> dict:
    p_n = int(seconds * NATIVE_HZ["p"])
    piezo = np.stack(
        [_beats(p_n, NATIVE_HZ["p"], fhr, a, rng) for a in (1.0, 0.6, 0.33, 0.15)], axis=1
    )
    interleaved = (2048 + 200 * piezo).round().astype(int).reshape(-1).tolist()
    fsr_n = int(seconds * NATIVE_HZ["fsr"])
    fsr = (700 + 30 * np.sin(np.arange(fsr_n) / NATIVE_HZ["fsr"]) + rng.normal(0, 4, fsr_n)).round().astype(int).tolist()
    ppg_n = int(seconds * NATIVE_HZ["hr_ir"])
    ir = (50000 + 1500 * _beats(ppg_n, NATIVE_HZ["hr_ir"], mhr, 1.0, rng)).round().astype(int).tolist()
    red = (48000 + 1000 * _beats(ppg_n, NATIVE_HZ["hr_ir"], mhr, 1.0, rng)).round().astype(int).tolist()
    return {
        "schema_version": 2,
        "is_simulated": False,
        "boot_id": boot_id,
        "sequence_number": seq,
        "samples": {"p": interleaved, "fsr": fsr, "hr_ir": ir, "hr_red": red},
        "sample_rates_hz": {k: v for k, v in NATIVE_HZ.items()},
        "channel_layout": {"p": 4},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--window-seconds", type=float, default=8.0)
    parser.add_argument("--fhr", type=float, default=142.0)
    parser.add_argument("--mhr", type=float, default=84.0)
    args = parser.parse_args()

    rng = np.random.default_rng(7)
    boot_id = "smoke-boot-0001"
    per_chunk = 1.0
    payloads = [
        _chunk(i, boot_id, per_chunk, args.fhr, args.mhr, rng)
        for i in range(int(args.window_seconds / per_chunk))
    ]

    prepared = prepare_stored_telemetry_window(payloads, window_seconds=args.window_seconds)
    print("prepared window:")
    for name, arr in prepared.inputs.items():
        print(f"  {name:13s} {arr.shape}  valid_ratio={prepared.valid_ratios[name]:.3f}")

    model, manifest = load_model_bundle(args.manifest, deployment_mode="research", device="cpu")
    print(f"loaded {manifest.model_name} {manifest.model_version} ({manifest.validation_status.value})")

    result = predict_preprocessed_window(
        model, manifest,
        inputs=prepared.inputs, validity_masks=prepared.validity_masks,
        min_valid_ratio=0.8,
    )
    print("\nHybridScreeningResult:")
    print(f"  quality_status   : {result.quality_status.value}  (score {result.quality_score:.3f})")
    print(f"  screening_status : {result.screening_status.value}")
    print(f"  uncertainty      : {result.uncertainty}")
    print(f"  fhr_bpm          : {result.fhr_bpm}")
    print(f"  maternal_hr_bpm  : {result.maternal_hr_bpm}")
    print(f"  contraction_prob : {result.contraction_probability}")
    print(f"  reasons          : {list(result.reasons)}")
    print("\nOK - the inference worker inner loop runs end to end on a trained checkpoint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
