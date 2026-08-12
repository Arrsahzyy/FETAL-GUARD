from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BranchSpec:
    name: str
    input_channels: int
    cnn_filters: tuple[int, ...] = (32, 64)
    kernel_size: int = 7
    lstm_hidden: int = 64


@dataclass(frozen=True)
class CNNLSTMFusionSpec:
    """Framework-neutral CNN-LSTM fusion architecture description."""

    branches: tuple[BranchSpec, ...] = field(default_factory=lambda: (
        BranchSpec(name="ctg", input_channels=2),
    ))
    dense_units: tuple[int, ...] = (64, 32)
    dropout: float = 0.2
    outputs: tuple[str, ...] = (
        "routine_monitoring",
        "needs_observation",
        "review_with_clinician",
    )

    def as_dict(self) -> dict[str, object]:
        return {
            "branches": [
                {
                    "name": branch.name,
                    "input_channels": branch.input_channels,
                    "cnn_filters": list(branch.cnn_filters),
                    "kernel_size": branch.kernel_size,
                    "lstm_hidden": branch.lstm_hidden,
                }
                for branch in self.branches
            ],
            "dense_units": list(self.dense_units),
            "dropout": self.dropout,
            "outputs": list(self.outputs),
        }
