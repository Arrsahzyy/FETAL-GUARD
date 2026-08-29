"""Fail-closed adapter from stored telemetry v2 chunks to CNN-LSTM inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from .preprocessing import interpolate_missing, robust_zscore


DEFAULT_TARGET_RATES_HZ = {
    # Firmware currently acquires close to 200 Hz/channel; the reviewed model
    # input contract is 250 Hz, so resampling is explicit and testable here.
    "piezo": 250.0,
    "fsr": 50.0,
    "maternal_ppg": 100.0,
}


class TelemetryWindowError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PreparedTelemetryWindow:
    inputs: dict[str, np.ndarray]
    validity_masks: dict[str, np.ndarray]
    valid_ratios: dict[str, float]


def prepare_stored_telemetry_window(
    stored_payloads: Sequence[Mapping[str, object]],
    *,
    window_seconds: float,
    target_rates_hz: Mapping[str, float] = DEFAULT_TARGET_RATES_HZ,
) -> PreparedTelemetryWindow:
    """Reconstruct one ordered, multi-rate hardware window.

    The adapter accepts only non-simulated schema v2 chunks. Packet gaps are
    rejected instead of silently joining unrelated samples. Missing modality
    coverage is represented in the validity mask so the inference safety gate
    can return ``insufficient_signal`` without fabricating values.
    """

    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    if not stored_payloads:
        raise TelemetryWindowError("empty_window", "No telemetry chunks were stored for the AI window")

    payloads = list(stored_payloads)
    _validate_packet_identity(payloads)
    collected: dict[str, list[np.ndarray]] = {
        "piezo": [],
        "fsr": [],
        "maternal_ppg": [],
    }
    for payload in payloads:
        if int(payload.get("schema_version", 0)) != 2:
            raise TelemetryWindowError(
                "unsupported_telemetry_schema",
                "AI hardware inference requires telemetry schema version 2",
            )
        if bool(payload.get("is_simulated")):
            raise TelemetryWindowError(
                "simulated_hardware_window",
                "Simulated telemetry cannot enter the hardware inference worker",
            )
        samples = payload.get("samples")
        rates = payload.get("sample_rates_hz")
        layout = payload.get("channel_layout")
        if not isinstance(samples, Mapping) or not isinstance(rates, Mapping):
            raise TelemetryWindowError("invalid_telemetry_chunk", "Telemetry v2 samples or rates are missing")

        piezo = samples.get("p")
        if piezo:
            if not isinstance(layout, Mapping) or int(layout.get("p", 0)) != 4:
                raise TelemetryWindowError("invalid_piezo_layout", "Piezo samples require four interleaved channels")
            piezo_values = np.asarray(piezo, dtype=np.float32)
            if piezo_values.size % 4:
                raise TelemetryWindowError("invalid_piezo_layout", "Piezo sample count is not divisible by four")
            collected["piezo"].append(
                _resample_chunk(piezo_values.reshape(-1, 4), _rate(rates, "p"), target_rates_hz["piezo"])
            )

        fsr = samples.get("fsr")
        if fsr:
            collected["fsr"].append(
                _resample_chunk(np.asarray(fsr, dtype=np.float32)[:, None], _rate(rates, "fsr"), target_rates_hz["fsr"])
            )

        ir = samples.get("hr_ir")
        red = samples.get("hr_red")
        if bool(ir) != bool(red):
            raise TelemetryWindowError("unpaired_maternal_ppg", "Maternal IR and red samples must be paired")
        if ir:
            if len(ir) != len(red):
                raise TelemetryWindowError("unpaired_maternal_ppg", "Maternal IR and red sample counts differ")
            ppg = np.column_stack((ir, red)).astype(np.float32)
            ir_rate = _rate(rates, "hr_ir")
            red_rate = _rate(rates, "hr_red")
            if not np.isclose(ir_rate, red_rate, rtol=0.01):
                raise TelemetryWindowError("unpaired_maternal_ppg", "Maternal IR and red sample rates differ")
            collected["maternal_ppg"].append(
                _resample_chunk(ppg, ir_rate, target_rates_hz["maternal_ppg"])
            )

    channel_counts = {"piezo": 4, "fsr": 1, "maternal_ppg": 2}
    inputs: dict[str, np.ndarray] = {}
    masks: dict[str, np.ndarray] = {}
    ratios: dict[str, float] = {}
    for modality, channel_count in channel_counts.items():
        target_count = int(round(float(target_rates_hz[modality]) * window_seconds))
        if target_count <= 0:
            raise ValueError(f"Target sample count for {modality} must be positive")
        available = (
            np.concatenate(collected[modality], axis=0)
            if collected[modality]
            else np.empty((0, channel_count), dtype=np.float32)
        )
        usable_count = min(available.shape[0], target_count)
        padded = np.full((target_count, channel_count), np.nan, dtype=np.float32)
        if usable_count:
            padded[:usable_count] = available[:usable_count]
        mask = np.zeros((target_count, channel_count), dtype=bool)
        mask[:usable_count] = np.isfinite(padded[:usable_count])
        prepared = robust_zscore(interpolate_missing(padded))
        inputs[modality] = prepared
        masks[modality] = mask
        ratios[modality] = float(mask.mean())

    return PreparedTelemetryWindow(inputs=inputs, validity_masks=masks, valid_ratios=ratios)


def _validate_packet_identity(payloads: Sequence[Mapping[str, object]]) -> None:
    boot_ids = {str(payload.get("boot_id") or "") for payload in payloads}
    if len(boot_ids) != 1 or "" in boot_ids:
        raise TelemetryWindowError("mixed_device_boot", "AI window spans missing or multiple device boot IDs")
    sequences = [payload.get("sequence_number") for payload in payloads]
    if any(not isinstance(value, int) or value < 0 for value in sequences):
        raise TelemetryWindowError("invalid_packet_sequence", "AI window has an invalid packet sequence")
    for previous, current in zip(sequences, sequences[1:]):
        if current != previous + 1:
            raise TelemetryWindowError("packet_gap", "AI window contains a missing or reordered telemetry packet")


def _rate(rates: Mapping[str, object], channel: str) -> float:
    try:
        rate = float(rates[channel])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelemetryWindowError("missing_sample_rate", f"Missing native sample rate for {channel}") from exc
    if not np.isfinite(rate) or rate <= 0:
        raise TelemetryWindowError("invalid_sample_rate", f"Invalid native sample rate for {channel}")
    return rate


def _resample_chunk(values: np.ndarray, source_hz: float, target_hz: float) -> np.ndarray:
    if target_hz <= 0:
        raise ValueError("Target sampling rates must be positive")
    data = np.asarray(values, dtype=np.float32)
    if data.ndim != 2 or data.shape[0] == 0:
        raise TelemetryWindowError("invalid_channel_values", "A present channel must contain a 2D non-empty array")
    if not np.isfinite(data).all():
        raise TelemetryWindowError("invalid_channel_values", "Raw telemetry contains non-finite values")
    target_count = max(1, int(round(data.shape[0] * target_hz / source_hz)))
    if target_count == data.shape[0] and np.isclose(source_hz, target_hz):
        return data.copy()
    source_x = np.arange(data.shape[0], dtype=np.float32) / source_hz
    target_x = np.arange(target_count, dtype=np.float32) / target_hz
    return np.column_stack(
        [np.interp(target_x, source_x, data[:, index]) for index in range(data.shape[1])]
    ).astype(np.float32)
