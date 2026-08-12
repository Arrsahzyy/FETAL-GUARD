from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class SignalQualityStatus(str, Enum):
    usable = "usable"
    limited = "limited"
    unusable = "unusable"


class ScreeningStatus(str, Enum):
    routine_monitoring = "routine_monitoring"
    needs_observation = "needs_observation"
    review_with_clinician = "review_with_clinician"
    insufficient_signal = "insufficient_signal"


class ModelValidationStatus(str, Enum):
    experimental = "experimental"
    analytical_validated = "analytical_validated"
    clinical_validated = "clinical_validated"
    retired = "retired"


@dataclass(frozen=True)
class ChannelContract:
    name: str
    channels: int
    sampling_hz: float
    unit: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Channel contract name cannot be empty")
        if self.channels <= 0:
            raise ValueError("Channel count must be positive")
        if self.sampling_hz <= 0:
            raise ValueError("Sampling rate must be positive")
        if not self.unit.strip():
            raise ValueError("Channel unit cannot be empty")


@dataclass(frozen=True)
class WindowContract:
    duration_seconds: float = 60.0
    stride_seconds: float = 15.0
    min_valid_ratio: float = 0.8
    modalities: tuple[ChannelContract, ...] = field(
        default_factory=lambda: (
            ChannelContract("piezo", channels=4, sampling_hz=250.0, unit="adc_count"),
            ChannelContract("fsr", channels=1, sampling_hz=50.0, unit="adc_count"),
            ChannelContract("maternal_ppg", channels=2, sampling_hz=100.0, unit="adc_count"),
        )
    )

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0 or self.stride_seconds <= 0:
            raise ValueError("Window duration and stride must be positive")
        if not 0 < self.min_valid_ratio <= 1:
            raise ValueError("Minimum valid ratio must be in (0, 1]")
        names = [modality.name for modality in self.modalities]
        if len(names) != len(set(names)):
            raise ValueError("Window modality names must be unique")

    def modality_map(self) -> Mapping[str, ChannelContract]:
        return {modality.name: modality for modality in self.modalities}


@dataclass(frozen=True)
class HybridScreeningResult:
    quality_status: SignalQualityStatus
    quality_score: float
    screening_status: ScreeningStatus
    uncertainty: float | None
    fhr_bpm: float | None = None
    maternal_hr_bpm: float | None = None
    contraction_probability: float | None = None
    reasons: tuple[str, ...] = ()
    model_version: str = ""
    preprocessing_version: str = ""

    def __post_init__(self) -> None:
        _validate_probability(self.quality_score, "quality_score")
        if self.uncertainty is not None:
            _validate_probability(self.uncertainty, "uncertainty")
        if self.contraction_probability is not None:
            _validate_probability(self.contraction_probability, "contraction_probability")
        for value, name in (
            (self.fhr_bpm, "fhr_bpm"),
            (self.maternal_hr_bpm, "maternal_hr_bpm"),
        ):
            if value is not None and not 0 < value < 400:
                raise ValueError(f"{name} is outside the broad technical range")


def normalize_reason_codes(values: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
    if any(not value.replace("_", "").isalnum() for value in normalized):
        raise ValueError("Reason codes may only contain letters, numbers, and underscores")
    return normalized


def _validate_probability(value: float, name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
