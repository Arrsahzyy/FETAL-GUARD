from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def _candidate_roots() -> list[Path]:
    project_root = Path(__file__).resolve().parents[2]
    return [
        project_root / "ctg_cnn_lstm_merged",
        project_root / "ctg_extracted" / "ctg_cnn_lstm_merged",
        project_root / "ai",
    ]


def _resolve_checkpoint() -> Path:
    for root in _candidate_roots():
        for candidate in (root / "checkpoints" / "best.pt", root / "checkpoints" / "last.pt"):
            if candidate.exists():
                return candidate
    raise RuntimeError(
        "No CTG CNN-LSTM checkpoint was found. Place best.pt under "
        "ctg_cnn_lstm_merged/checkpoints or a sibling directory that matches the repository layout."
    )


@lru_cache(maxsize=1)
def get_predictor():
    checkpoint = _resolve_checkpoint()
    project_root = checkpoint.parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    try:
        from app.ai.inference import CTGPredictor
    except ModuleNotFoundError as exc:  # pragma: no cover - raises when project layout is incomplete.
        raise RuntimeError(
            "The bundled CTG CNN-LSTM project could not be imported. "
            "Check that app/ai/inference.py and its supporting modules are present."
        ) from exc

    return CTGPredictor(str(checkpoint))


def _as_float_array(value: Any) -> np.ndarray | None:
    try:
        arr = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if arr.size == 0 or not np.isfinite(arr).all():
        return None
    return arr


def _coerce_window(payload: Any) -> list[list[float]] | None:
    if isinstance(payload, list):
        data = payload
    elif isinstance(payload, tuple):
        data = list(payload)
    elif isinstance(payload, dict):
        if "window" in payload:
            return _coerce_window(payload["window"])
        if "sequence" in payload:
            return _coerce_window(payload["sequence"])
        if "readings" in payload:
            return _coerce_window(payload["readings"])

        def _pick_series(*keys: str) -> np.ndarray | None:
            for key in keys:
                if key in payload:
                    return _as_float_array(payload[key])
            return None

        fhr = _pick_series("fhr", "fhr_bpm", "fhr_series")
        mhr = _pick_series("mhr", "mhr_bpm", "mhr_series")
        uc = _pick_series("uc", "uc_per_10min", "uc_series")
        if fhr is not None and mhr is not None and uc is not None:
            length = min(len(fhr), len(mhr), len(uc))
            if length > 0:
                return [[float(fhr[i]), float(mhr[i]), float(uc[i])] for i in range(length)]

        if isinstance(payload.get("fhr_values"), (list, tuple)) and isinstance(payload.get("mhr_values"), (list, tuple)) and isinstance(payload.get("uc_values"), (list, tuple)):
            fhr = _as_float_array(payload["fhr_values"])
            mhr = _as_float_array(payload["mhr_values"])
            uc = _as_float_array(payload["uc_values"]) 
            if fhr is not None and mhr is not None and uc is not None:
                length = min(len(fhr), len(mhr), len(uc))
                if length > 0:
                    return [[float(fhr[i]), float(mhr[i]), float(uc[i])] for i in range(length)]
        return None
    else:
        return None

    if not isinstance(data, list):
        return None
    if len(data) == 0:
        return None

    if isinstance(data[0], (list, tuple, np.ndarray)):
        window = []
        for row in data:
            if len(row) != 3:
                return None
            row_arr = _as_float_array(row)
            if row_arr is None:
                return None
            window.append([float(row_arr[0]), float(row_arr[1]), float(row_arr[2])])
        return window

    values = {
        "fhr": _as_float_array([row.get("fhr_bpm", row.get("fhr", row.get("value", 0))) for row in data if isinstance(row, dict)]),
        "mhr": _as_float_array([row.get("mhr_bpm", row.get("mhr", row.get("value", 0))) for row in data if isinstance(row, dict)]),
        "uc": _as_float_array([row.get("uc_per_10min", row.get("uc", row.get("value", 0))) for row in data if isinstance(row, dict)]),
    }
    if values["fhr"] is not None and values["mhr"] is not None and values["uc"] is not None:
        length = min(len(values["fhr"]), len(values["mhr"]), len(values["uc"]))
        return [[float(values["fhr"][i]), float(values["mhr"][i]), float(values["uc"][i])] for i in range(length)]
    return None


def predict_from_payload(payload: Any) -> dict[str, Any]:
    window = _coerce_window(payload)
    if window is None:
        raise ValueError("The sensor payload does not include a valid 3-channel CTG window.")
    if len(window) < 15:
        window = window[-15:]
    if len(window) != 15:
        raise ValueError("The CTG model requires exactly 15 readings in the sequence window.")

    predictor = get_predictor()
    result = predictor.predict(window)
    return {
        "fhr": {"status": result["fhr_status"], "confidence": float(result["fhr_confidence"])},
        "mhr": {"status": result["mhr_status"], "confidence": float(result["mhr_confidence"])},
        "uc": {"status": result["uc_status"], "confidence": float(result["uc_confidence"])},
        "overall": {"status": result["overall_status"], "confidence": float(result["overall_confidence"])},
    }
