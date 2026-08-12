from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from .model import HybridCNNLSTMConfig


DATASET_KINDS = frozenset(
    {"research_public", "fetal_guard_hardware", "synthetic_smoke_test"}
)
MODALITY_CHANNELS = {
    "piezo": "piezo_channels",
    "fsr": "fsr_channels",
    "maternal_ppg": "maternal_channels",
}


@dataclass(frozen=True)
class HybridTrainingDataset:
    inputs: Mapping[str, np.ndarray]
    validity_masks: Mapping[str, np.ndarray]
    screening_labels: np.ndarray
    quality_targets: np.ndarray
    measurement_targets: np.ndarray
    contraction_targets: np.ndarray
    group_ids: np.ndarray
    dataset_kind: str
    preprocessing_version: str
    input_schema_version: int

    @property
    def sample_count(self) -> int:
        return int(self.screening_labels.shape[0])


@dataclass(frozen=True)
class GroupSplit:
    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray


def load_hybrid_training_npz(
    path: str | Path,
    *,
    config: HybridCNNLSTMConfig | None = None,
    min_valid_ratio: float = 0.8,
) -> HybridTrainingDataset:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Training dataset not found: {source}")
    with np.load(source, allow_pickle=False) as archive:
        required = {
            *MODALITY_CHANNELS,
            *(f"{name}_validity_mask" for name in MODALITY_CHANNELS),
            "screening_labels",
            "quality_targets",
            "measurement_targets",
            "contraction_targets",
            "group_ids",
            "dataset_kind",
            "preprocessing_version",
            "input_schema_version",
        }
        missing = sorted(required - set(archive.files))
        if missing:
            raise ValueError("Hybrid training dataset is missing keys: " + ", ".join(missing))
        dataset = HybridTrainingDataset(
            inputs={name: np.asarray(archive[name], dtype=np.float32) for name in MODALITY_CHANNELS},
            validity_masks={
                name: _validity_mask(archive[f"{name}_validity_mask"], name)
                for name in MODALITY_CHANNELS
            },
            screening_labels=_integer_array(archive["screening_labels"], "screening_labels"),
            quality_targets=np.asarray(archive["quality_targets"], dtype=np.float32),
            measurement_targets=np.asarray(archive["measurement_targets"], dtype=np.float32),
            contraction_targets=np.asarray(archive["contraction_targets"], dtype=np.float32),
            group_ids=np.asarray(archive["group_ids"]).astype(str),
            dataset_kind=_scalar_string(archive["dataset_kind"], "dataset_kind"),
            preprocessing_version=_scalar_string(
                archive["preprocessing_version"], "preprocessing_version"
            ),
            input_schema_version=_scalar_int(
                archive["input_schema_version"], "input_schema_version"
            ),
        )
    validate_hybrid_training_dataset(
        dataset,
        config=config or HybridCNNLSTMConfig(),
        min_valid_ratio=min_valid_ratio,
    )
    return dataset


def validate_hybrid_training_dataset(
    dataset: HybridTrainingDataset,
    *,
    config: HybridCNNLSTMConfig,
    min_valid_ratio: float = 0.8,
) -> None:
    if not 0 < min_valid_ratio <= 1:
        raise ValueError("min_valid_ratio must be in (0, 1]")
    if dataset.dataset_kind not in DATASET_KINDS:
        raise ValueError("Unsupported dataset_kind")
    if not dataset.preprocessing_version.strip():
        raise ValueError("preprocessing_version cannot be empty")
    if dataset.input_schema_version != 2:
        raise ValueError("Hybrid CNN-LSTM training requires input_schema_version 2")

    sample_count = dataset.sample_count
    if sample_count < 3:
        raise ValueError("At least three windows are required")
    for modality, channel_field in MODALITY_CHANNELS.items():
        values = np.asarray(dataset.inputs[modality])
        mask = np.asarray(dataset.validity_masks[modality])
        if values.ndim != 3:
            raise ValueError(f"{modality} must have shape [window, time, channel]")
        if values.shape != mask.shape:
            raise ValueError(f"{modality} validity mask must match its values")
        if values.shape[0] != sample_count:
            raise ValueError(f"{modality} window count does not match labels")
        expected_channels = int(getattr(config, channel_field))
        if values.shape[2] != expected_channels:
            raise ValueError(
                f"{modality} requires {expected_channels} channels, got {values.shape[2]}"
            )
        if not np.isfinite(values).all():
            raise ValueError(f"{modality} must be finite after reviewed preprocessing")
        valid_ratio = mask.reshape(sample_count, -1).mean(axis=1)
        if np.any(valid_ratio < min_valid_ratio):
            raise ValueError(f"{modality} contains windows below min_valid_ratio")

    if dataset.screening_labels.shape != (sample_count,):
        raise ValueError("screening_labels must have shape [window]")
    if np.any((dataset.screening_labels < 0) | (dataset.screening_labels >= config.screening_classes)):
        raise ValueError("screening_labels contain an unsupported class")
    if dataset.quality_targets.shape != (sample_count,) or not np.isfinite(
        dataset.quality_targets
    ).all():
        raise ValueError("quality_targets must be finite with shape [window]")
    if np.any((dataset.quality_targets < 0) | (dataset.quality_targets > 1)):
        raise ValueError("quality_targets must be between 0 and 1")
    if dataset.measurement_targets.shape != (sample_count, 2):
        raise ValueError("measurement_targets must have shape [window, 2]")
    _validate_optional_range(dataset.measurement_targets[:, 0], 30, 240, "fetal HR targets")
    _validate_optional_range(dataset.measurement_targets[:, 1], 30, 220, "maternal HR targets")
    if dataset.contraction_targets.shape != (sample_count,):
        raise ValueError("contraction_targets must have shape [window]")
    finite_contractions = dataset.contraction_targets[np.isfinite(dataset.contraction_targets)]
    if np.any((finite_contractions < 0) | (finite_contractions > 1)):
        raise ValueError("contraction_targets must be NaN or between 0 and 1")
    if dataset.group_ids.shape != (sample_count,):
        raise ValueError("group_ids must have shape [window]")
    if any(not value.strip() for value in dataset.group_ids):
        raise ValueError("group_ids cannot contain empty values")
    if np.unique(dataset.group_ids).size < 3:
        raise ValueError("At least three independent groups are required for leakage-safe splits")


def group_holdout_split(
    group_ids: np.ndarray,
    *,
    seed: int = 42,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> GroupSplit:
    groups = np.asarray(group_ids).astype(str)
    unique_groups = np.unique(groups)
    if unique_groups.size < 3:
        raise ValueError("At least three independent groups are required")
    if validation_ratio <= 0 or test_ratio <= 0 or validation_ratio + test_ratio >= 1:
        raise ValueError("Validation and test ratios must be positive and leave a train split")

    shuffled = unique_groups.copy()
    np.random.default_rng(seed).shuffle(shuffled)
    validation_count = max(1, int(round(unique_groups.size * validation_ratio)))
    test_count = max(1, int(round(unique_groups.size * test_ratio)))
    while validation_count + test_count >= unique_groups.size:
        if validation_count >= test_count and validation_count > 1:
            validation_count -= 1
        elif test_count > 1:
            test_count -= 1
        else:
            raise ValueError("Not enough groups to construct train, validation, and test splits")

    validation_groups = shuffled[:validation_count]
    test_groups = shuffled[validation_count : validation_count + test_count]
    train_groups = shuffled[validation_count + test_count :]
    split = GroupSplit(
        train=np.flatnonzero(np.isin(groups, train_groups)),
        validation=np.flatnonzero(np.isin(groups, validation_groups)),
        test=np.flatnonzero(np.isin(groups, test_groups)),
    )
    _assert_no_group_leakage(groups, split)
    return split


def _assert_no_group_leakage(group_ids: np.ndarray, split: GroupSplit) -> None:
    split_groups = [set(group_ids[indexes]) for indexes in (split.train, split.validation, split.test)]
    if not all(split_groups) or any(
        split_groups[left] & split_groups[right]
        for left, right in ((0, 1), (0, 2), (1, 2))
    ):
        raise RuntimeError("Group leakage detected in dataset split")


def _validate_optional_range(values: np.ndarray, lower: float, upper: float, name: str) -> None:
    finite = values[np.isfinite(values)]
    if np.any((finite < lower) | (finite > upper)):
        raise ValueError(f"{name} are outside the technical target range")


def _scalar_string(value: np.ndarray, name: str) -> str:
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError(f"{name} must be a scalar")
    result = str(array.reshape(-1)[0]).strip()
    if not result:
        raise ValueError(f"{name} cannot be empty")
    return result


def _scalar_int(value: np.ndarray, name: str) -> int:
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError(f"{name} must be a scalar")
    scalar = array.reshape(-1)[0]
    converted = int(scalar)
    if not np.isfinite(float(scalar)) or float(scalar) != converted:
        raise ValueError(f"{name} must be an integer")
    return converted


def _integer_array(value: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(value)
    try:
        numeric = array.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain integers") from exc
    if not np.isfinite(numeric).all() or not np.equal(numeric, np.floor(numeric)).all():
        raise ValueError(f"{name} must contain integers")
    return numeric.astype(np.int64)


def _validity_mask(value: np.ndarray, modality: str) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype == np.bool_:
        return array.copy()
    try:
        numeric = array.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{modality} validity mask must be boolean or binary") from exc
    if not np.isfinite(numeric).all() or not np.isin(numeric, (0, 1)).all():
        raise ValueError(f"{modality} validity mask must be boolean or binary")
    return numeric.astype(bool)
