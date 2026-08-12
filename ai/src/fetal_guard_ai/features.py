from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SignalQualitySummary:
    valid_ratio: float
    flatline_ratio: float
    missing_ratio: float
    score: float


def signal_quality_index(values: np.ndarray, flatline_epsilon: float = 1e-4) -> SignalQualitySummary:
    data = np.asarray(values, dtype=np.float32)
    if data.size == 0:
        return SignalQualitySummary(valid_ratio=0.0, flatline_ratio=1.0, missing_ratio=1.0, score=0.0)

    valid = np.isfinite(data)
    valid_ratio = float(valid.mean())
    missing_ratio = 1.0 - valid_ratio

    if data.ndim == 1:
        diffs = np.diff(data[valid]) if valid.any() else np.asarray([], dtype=np.float32)
    else:
        clean = np.nan_to_num(data, nan=0.0)
        diffs = np.diff(clean, axis=0).reshape(-1)

    if diffs.size == 0:
        flatline_ratio = 1.0
    else:
        flatline_ratio = float((np.abs(diffs) <= flatline_epsilon).mean())

    score = max(0.0, min(1.0, valid_ratio * (1.0 - 0.5 * flatline_ratio)))
    return SignalQualitySummary(
        valid_ratio=valid_ratio,
        flatline_ratio=flatline_ratio,
        missing_ratio=missing_ratio,
        score=score,
    )
