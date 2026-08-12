from __future__ import annotations

from enum import Enum
from typing import Mapping


class SafeScreeningLabel(str, Enum):
    routine_monitoring = "routine_monitoring"
    needs_observation = "needs_observation"


def ph_regression_target(metadata: Mapping[str, object], key: str = "pH") -> float | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def screening_label_from_ph(
    metadata: Mapping[str, object],
    observation_cutoff: float | None,
    key: str = "pH",
) -> SafeScreeningLabel | None:
    """Create a conservative training label only when a reviewed cutoff exists.

    The cutoff is intentionally not hard-coded. A clinical supervisor must
    approve the threshold and document the source before enabling this task.
    """

    if observation_cutoff is None:
        return None

    ph_value = ph_regression_target(metadata, key=key)
    if ph_value is None:
        return None

    if ph_value < observation_cutoff:
        return SafeScreeningLabel.needs_observation
    return SafeScreeningLabel.routine_monitoring
