from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .artifact import DeploymentMode, ModelArtifactManifest
from .contracts import (
    HybridScreeningResult,
    ScreeningStatus,
    SignalQualityStatus,
    normalize_reason_codes,
)
from .model import HybridCNNLSTMConfig, build_hybrid_cnn_lstm, require_torch


LEARNED_SCREENING_STATUSES = (
    ScreeningStatus.routine_monitoring,
    ScreeningStatus.needs_observation,
    ScreeningStatus.review_with_clinician,
)


def load_model_bundle(
    manifest_path: str | Path,
    *,
    deployment_mode: DeploymentMode = "research",
    device: str = "cpu",
):
    """Verify a reviewed artifact before deserializing model weights."""

    manifest = ModelArtifactManifest.load(manifest_path)
    artifact_path = manifest.verify(manifest_path)
    manifest.assert_allowed_for(deployment_mode)
    torch, _ = require_torch()
    checkpoint = torch.load(artifact_path, map_location=device, weights_only=True)
    if not isinstance(checkpoint, Mapping):
        raise ValueError("Model checkpoint must be a mapping")
    required = {
        "state_dict",
        "model_config",
        "screening_labels",
        "input_schema_version",
        "preprocessing_version",
    }
    missing = sorted(required - set(checkpoint))
    if missing:
        raise ValueError("Model checkpoint is missing keys: " + ", ".join(missing))
    if int(checkpoint["input_schema_version"]) != manifest.input_schema_version:
        raise ValueError("Checkpoint and manifest input schema versions differ")
    if manifest.input_schema_version != 2:
        raise ValueError("Hybrid CNN-LSTM inference requires input_schema_version 2")
    if str(checkpoint["preprocessing_version"]) != manifest.preprocessing_version:
        raise ValueError("Checkpoint and manifest preprocessing versions differ")
    expected_labels = {index: status.value for index, status in enumerate(LEARNED_SCREENING_STATUSES)}
    labels = {int(key): str(value) for key, value in checkpoint["screening_labels"].items()}
    if labels != expected_labels:
        raise ValueError("Checkpoint screening label mapping is not canonical")

    config_values = dict(checkpoint["model_config"])
    if "branch_filters" in config_values:
        config_values["branch_filters"] = tuple(config_values["branch_filters"])
    config = HybridCNNLSTMConfig(**config_values)
    model = build_hybrid_cnn_lstm(config)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.to(torch.device(device))
    model.eval()
    return model, manifest


def apply_safety_layer(
    *,
    quality_probability: float,
    screening_probabilities: Sequence[float],
    fhr_bpm: float | None,
    maternal_hr_bpm: float | None,
    contraction_probability: float | None,
    model_version: str,
    preprocessing_version: str,
    usable_quality_threshold: float = 0.8,
    limited_quality_threshold: float = 0.5,
    max_uncertainty: float = 0.4,
) -> HybridScreeningResult:
    """Convert raw heads to a conservative result; never infer on weak signals."""

    if not 0 <= limited_quality_threshold <= usable_quality_threshold <= 1:
        raise ValueError("Quality thresholds must be ordered within [0, 1]")
    if not 0 <= max_uncertainty <= 1:
        raise ValueError("max_uncertainty must be between 0 and 1")
    quality_probability = _probability(quality_probability, "quality_probability")
    probabilities = np.asarray(screening_probabilities, dtype=np.float64)
    if probabilities.shape != (len(LEARNED_SCREENING_STATUSES),):
        raise ValueError("screening_probabilities must contain exactly three classes")
    if not np.isfinite(probabilities).all() or np.any(probabilities < 0):
        raise ValueError("screening_probabilities must be finite and non-negative")
    probability_sum = float(probabilities.sum())
    if probability_sum <= 0:
        raise ValueError("screening_probabilities must have a positive sum")
    probabilities = probabilities / probability_sum
    uncertainty = 1.0 - float(probabilities.max())
    reasons: list[str] = []

    if quality_probability >= usable_quality_threshold:
        quality_status = SignalQualityStatus.usable
    elif quality_probability >= limited_quality_threshold:
        quality_status = SignalQualityStatus.limited
        reasons.append("limited_signal_quality")
    else:
        quality_status = SignalQualityStatus.unusable
        reasons.append("unusable_signal_quality")

    if quality_status is not SignalQualityStatus.usable:
        screening_status = ScreeningStatus.insufficient_signal
    elif uncertainty > max_uncertainty:
        screening_status = ScreeningStatus.insufficient_signal
        reasons.append("high_model_uncertainty")
    else:
        screening_status = LEARNED_SCREENING_STATUSES[int(probabilities.argmax())]
        reasons.append("screening_model_signal")

    safe_fhr = _technical_measurement_or_none(fhr_bpm, 30, 240)
    safe_maternal_hr = _technical_measurement_or_none(maternal_hr_bpm, 30, 220)
    if fhr_bpm is not None and safe_fhr is None:
        reasons.append("invalid_fhr_output")
        screening_status = ScreeningStatus.insufficient_signal
    if maternal_hr_bpm is not None and safe_maternal_hr is None:
        reasons.append("invalid_maternal_hr_output")
        screening_status = ScreeningStatus.insufficient_signal
    safe_contraction = (
        None
        if contraction_probability is None
        else _probability(contraction_probability, "contraction_probability")
    )
    return HybridScreeningResult(
        quality_status=quality_status,
        quality_score=quality_probability,
        screening_status=screening_status,
        uncertainty=uncertainty,
        fhr_bpm=safe_fhr,
        maternal_hr_bpm=safe_maternal_hr,
        contraction_probability=safe_contraction,
        reasons=normalize_reason_codes(reasons),
        model_version=model_version,
        preprocessing_version=preprocessing_version,
    )


def predict_preprocessed_window(
    model,
    manifest: ModelArtifactManifest,
    *,
    inputs: Mapping[str, np.ndarray],
    validity_masks: Mapping[str, np.ndarray],
    min_valid_ratio: float = 0.8,
) -> HybridScreeningResult:
    """Run one reviewed multimodal window and apply conservative postprocessing."""

    if not 0 < min_valid_ratio <= 1:
        raise ValueError("min_valid_ratio must be in (0, 1]")
    config = model.config
    expected_channels = {
        "piezo": config.piezo_channels,
        "fsr": config.fsr_channels,
        "maternal_ppg": config.maternal_channels,
    }
    prepared: dict[str, np.ndarray] = {}
    masks: dict[str, np.ndarray] = {}
    valid_ratios: dict[str, float] = {}
    for name, channel_count in expected_channels.items():
        if name not in inputs or name not in validity_masks:
            raise ValueError(f"Missing inference modality or validity mask: {name}")
        values = np.asarray(inputs[name], dtype=np.float32)
        mask = np.asarray(validity_masks[name])
        if values.ndim != 2 or values.shape[1] != channel_count:
            raise ValueError(f"{name} must have shape [time, {channel_count}]")
        if mask.shape != values.shape:
            raise ValueError(f"{name} validity mask must match its values")
        if mask.dtype != np.bool_:
            if not np.isin(mask, (0, 1)).all():
                raise ValueError(f"{name} validity mask must be boolean or binary")
            mask = mask.astype(bool)
        if not np.isfinite(values).all():
            raise ValueError(f"{name} must be finite after reviewed preprocessing")
        prepared[name] = values
        masks[name] = mask
        valid_ratios[name] = float(mask.mean())

    weakest_modality = min(valid_ratios, key=valid_ratios.get)
    weakest_ratio = valid_ratios[weakest_modality]
    if weakest_ratio < min_valid_ratio:
        return HybridScreeningResult(
            quality_status=SignalQualityStatus.unusable,
            quality_score=max(0.0, min(1.0, weakest_ratio)),
            screening_status=ScreeningStatus.insufficient_signal,
            uncertainty=None,
            reasons=normalize_reason_codes((f"low_valid_{weakest_modality}",)),
            model_version=manifest.model_version,
            preprocessing_version=manifest.preprocessing_version,
        )

    torch, _ = require_torch()
    device = next(model.parameters()).device
    tensors = {
        name: torch.as_tensor(values, dtype=torch.float32, device=device).unsqueeze(0)
        for name, values in prepared.items()
    }
    mask_tensors = {
        name: torch.as_tensor(mask, dtype=torch.bool, device=device).unsqueeze(0)
        for name, mask in masks.items()
    }
    attention_mask = _fusion_attention_mask(
        torch, mask_tensors, fusion_steps=config.fusion_steps
    )
    with torch.inference_mode():
        outputs = model(tensors, attention_mask=attention_mask)
        quality_probability = float(torch.sigmoid(outputs["quality_logit"])[0].cpu())
        screening_probabilities = (
            torch.softmax(outputs["screening_logits"], dim=-1)[0].cpu().numpy()
        )
        measurements = outputs["measurements"][0].cpu().numpy()
        contraction_probability = float(
            torch.sigmoid(outputs["contraction_logit"])[0].cpu()
        )
    return apply_safety_layer(
        quality_probability=quality_probability,
        screening_probabilities=screening_probabilities,
        fhr_bpm=float(measurements[0]),
        maternal_hr_bpm=float(measurements[1]),
        contraction_probability=contraction_probability,
        model_version=manifest.model_version,
        preprocessing_version=manifest.preprocessing_version,
    )


def model_config_dict(config: HybridCNNLSTMConfig) -> dict:
    return asdict(config)


def _fusion_attention_mask(torch, masks: Mapping[str, object], *, fusion_steps: int):
    pooled_masks = []
    for name in ("piezo", "fsr", "maternal_ppg"):
        time_validity = masks[name].to(dtype=torch.float32).mean(dim=2).unsqueeze(1)
        pooled = torch.nn.functional.adaptive_avg_pool1d(
            time_validity, fusion_steps
        ).squeeze(1)
        pooled_masks.append(pooled >= 0.5)
    return torch.stack(pooled_masks, dim=0).all(dim=0)


def _probability(value: float, name: str) -> float:
    converted = float(value)
    if not np.isfinite(converted) or not 0 <= converted <= 1:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return converted


def _technical_measurement_or_none(
    value: float | None,
    lower: float,
    upper: float,
) -> float | None:
    if value is None:
        return None
    converted = float(value)
    if not np.isfinite(converted) or not lower <= converted <= upper:
        return None
    return converted
