from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class WindowConfig:
    sampling_hz: float
    window_seconds: float
    stride_seconds: float
    min_valid_ratio: float = 0.8

    @property
    def window_size(self) -> int:
        return int(round(self.sampling_hz * self.window_seconds))

    @property
    def stride_size(self) -> int:
        return int(round(self.sampling_hz * self.stride_seconds))


def robust_zscore(values: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    data = np.asarray(values, dtype=np.float32)
    median = np.nanmedian(data, axis=0)
    mad = np.nanmedian(np.abs(data - median), axis=0)
    scale = np.where(mad > eps, 1.4826 * mad, np.nanstd(data, axis=0))
    scale = np.where(scale > eps, scale, 1.0)
    normalized = (data - median) / scale
    return np.nan_to_num(normalized, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def interpolate_missing(values: np.ndarray) -> np.ndarray:
    data = np.asarray(values, dtype=np.float32)
    if data.ndim == 1:
        return _interpolate_1d(data)
    if data.ndim != 2:
        raise ValueError("Expected a 1D or 2D array.")
    return np.column_stack([_interpolate_1d(data[:, idx]) for idx in range(data.shape[1])])


def _interpolate_1d(values: np.ndarray) -> np.ndarray:
    data = values.astype(np.float32, copy=True)
    valid = np.isfinite(data)
    if valid.all():
        return data
    if not valid.any():
        return np.zeros_like(data, dtype=np.float32)

    x = np.arange(data.size)
    data[~valid] = np.interp(x[~valid], x[valid], data[valid])
    return data


def resample_uniform(values: np.ndarray, source_hz: float, target_hz: float) -> np.ndarray:
    if source_hz <= 0 or target_hz <= 0:
        raise ValueError("Sampling rates must be positive.")

    data = np.asarray(values, dtype=np.float32)
    if data.shape[0] == 0 or np.isclose(source_hz, target_hz):
        return data.copy()

    duration_seconds = (data.shape[0] - 1) / source_hz
    target_len = int(round(duration_seconds * target_hz)) + 1
    source_x = np.linspace(0.0, duration_seconds, data.shape[0])
    target_x = np.linspace(0.0, duration_seconds, target_len)

    if data.ndim == 1:
        return np.interp(target_x, source_x, data).astype(np.float32)
    if data.ndim == 2:
        return np.column_stack([
            np.interp(target_x, source_x, data[:, idx])
            for idx in range(data.shape[1])
        ]).astype(np.float32)
    raise ValueError("Expected a 1D or 2D array.")


def make_masked_sliding_windows(
    values: np.ndarray,
    config: WindowConfig,
    validity_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = np.asarray(values, dtype=np.float32)
    if data.ndim == 1:
        data = data[:, None]

    if validity_mask is None:
        mask = np.isfinite(data)
    else:
        mask = np.asarray(validity_mask, dtype=bool)
        if mask.ndim == 1:
            mask = mask[:, None]
        if mask.shape != data.shape:
            raise ValueError("validity_mask must match the input data shape")

    if config.window_size <= 0 or config.stride_size <= 0:
        raise ValueError("Window and stride sizes must be positive.")

    windows: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    starts: list[int] = []
    for start in range(0, max(data.shape[0] - config.window_size + 1, 0), config.stride_size):
        window = data[start : start + config.window_size]
        window_mask = mask[start : start + config.window_size]
        valid_ratio = float(window_mask.mean())
        if valid_ratio >= config.min_valid_ratio:
            windows.append(interpolate_missing(window))
            masks.append(window_mask)
            starts.append(start)

    if not windows:
        return (
            np.empty((0, config.window_size, data.shape[1]), dtype=np.float32),
            np.empty((0, config.window_size, data.shape[1]), dtype=bool),
            np.empty((0,), dtype=np.int64),
        )

    return (
        np.stack(windows).astype(np.float32),
        np.stack(masks).astype(bool),
        np.asarray(starts, dtype=np.int64),
    )


def make_sliding_windows(values: np.ndarray, config: WindowConfig) -> tuple[np.ndarray, np.ndarray]:
    windows, _masks, starts = make_masked_sliding_windows(values, config)
    return windows, starts


def prepare_ctg_matrix(fhr: np.ndarray, uterine_contraction: np.ndarray) -> np.ndarray:
    if len(fhr) != len(uterine_contraction):
        raise ValueError("FHR and uterine contraction arrays must have the same length.")
    matrix = np.column_stack([fhr, uterine_contraction]).astype(np.float32)
    return robust_zscore(interpolate_missing(matrix))
