from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Any


@dataclass(frozen=True)
class HybridCNNLSTMConfig:
    piezo_channels: int = 4
    fsr_channels: int = 1
    maternal_channels: int = 2
    branch_filters: tuple[int, int] = (32, 64)
    lstm_hidden: int = 96
    lstm_layers: int = 2
    dense_units: int = 64
    fusion_steps: int = 300
    dropout: float = 0.25
    screening_classes: int = 3

    def __post_init__(self) -> None:
        if min(self.piezo_channels, self.fsr_channels, self.maternal_channels) <= 0:
            raise ValueError("Every modality must have at least one input channel")
        if len(self.branch_filters) != 2 or min(self.branch_filters) <= 0:
            raise ValueError("branch_filters must contain two positive sizes")
        if (
            self.lstm_hidden <= 0
            or self.lstm_layers <= 0
            or self.dense_units <= 0
            or self.fusion_steps <= 0
        ):
            raise ValueError("Model hidden dimensions must be positive")
        if not 0 <= self.dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        if self.screening_classes != 3:
            raise ValueError("The canonical screening contract currently defines three learned classes")


def require_torch() -> tuple[Any, Any]:
    try:
        torch = importlib.import_module("torch")
        nn = importlib.import_module("torch.nn")
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required to instantiate the hybrid CNN-LSTM model. "
            "Install the reviewed AI environment from ai/requirements-ai.txt."
        ) from exc
    return torch, nn


def build_hybrid_cnn_lstm(config: HybridCNNLSTMConfig | None = None):
    """Build the actual multi-modal CNN-LSTM without importing torch at package load.

    Every modality keeps its reviewed native sampling rate. Each CNN branch
    pools to aligned temporal bins before fusion. The model is deliberately
    multi-task: measurement and quality heads are kept separate from the
    screening-support head so low-quality windows can be rejected by a
    deterministic safety layer.
    """

    cfg = config or HybridCNNLSTMConfig()
    torch, nn = require_torch()

    class TemporalBranch(nn.Module):
        def __init__(self, input_channels: int) -> None:
            super().__init__()
            first, second = cfg.branch_filters
            self.network = nn.Sequential(
                nn.Conv1d(input_channels, first, kernel_size=7, padding=3),
                nn.BatchNorm1d(first),
                nn.GELU(),
                nn.Conv1d(first, second, kernel_size=5, padding=2),
                nn.BatchNorm1d(second),
                nn.GELU(),
                nn.Dropout(cfg.dropout),
            )
            self.pool = nn.AdaptiveAvgPool1d(cfg.fusion_steps)

        def forward(self, values):
            if values.ndim != 3:
                raise ValueError("Each modality tensor must have shape [batch, time, channels]")
            features = self.network(values.transpose(1, 2))
            return self.pool(features).transpose(1, 2)

    class HybridCNNLSTM(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.config = cfg
            self.piezo_branch = TemporalBranch(cfg.piezo_channels)
            self.fsr_branch = TemporalBranch(cfg.fsr_channels)
            self.maternal_branch = TemporalBranch(cfg.maternal_channels)
            fused_features = cfg.branch_filters[-1] * 3
            self.temporal = nn.LSTM(
                input_size=fused_features,
                hidden_size=cfg.lstm_hidden,
                num_layers=cfg.lstm_layers,
                dropout=cfg.dropout if cfg.lstm_layers > 1 else 0.0,
                batch_first=True,
                bidirectional=False,
            )
            self.shared = nn.Sequential(
                nn.Linear(cfg.lstm_hidden, cfg.dense_units),
                nn.GELU(),
                nn.Dropout(cfg.dropout),
            )
            self.quality_head = nn.Linear(cfg.dense_units, 1)
            self.measurement_head = nn.Linear(cfg.dense_units, 2)
            self.contraction_head = nn.Linear(cfg.dense_units, 1)
            self.screening_head = nn.Linear(cfg.dense_units, cfg.screening_classes)

        def forward(self, inputs: dict[str, Any], attention_mask=None):
            required = {"piezo", "fsr", "maternal_ppg"}
            missing = sorted(required - set(inputs))
            if missing:
                raise ValueError("Missing model modalities: " + ", ".join(missing))
            batches = {inputs[name].shape[0] for name in required}
            expected_channels = {
                "piezo": cfg.piezo_channels,
                "fsr": cfg.fsr_channels,
                "maternal_ppg": cfg.maternal_channels,
            }
            for name, channel_count in expected_channels.items():
                if inputs[name].ndim != 3 or inputs[name].shape[2] != channel_count:
                    raise ValueError(
                        f"{name} must have shape [batch, time, {channel_count}]"
                    )
            if len(batches) != 1:
                raise ValueError("All modalities must share the batch dimension")

            fused = torch.cat(
                (
                    self.piezo_branch(inputs["piezo"]),
                    self.fsr_branch(inputs["fsr"]),
                    self.maternal_branch(inputs["maternal_ppg"]),
                ),
                dim=-1,
            )
            temporal, _ = self.temporal(fused)
            if attention_mask is None:
                pooled = temporal[:, -1, :]
            else:
                if attention_mask.ndim != 2 or attention_mask.shape[:2] != temporal.shape[:2]:
                    raise ValueError("attention_mask must have shape [batch, time]")
                mask = attention_mask.to(dtype=temporal.dtype).unsqueeze(-1)
                pooled = (temporal * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)

            shared = self.shared(pooled)
            return {
                "quality_logit": self.quality_head(shared).squeeze(-1),
                "measurements": self.measurement_head(shared),
                "contraction_logit": self.contraction_head(shared).squeeze(-1),
                "screening_logits": self.screening_head(shared),
            }

    return HybridCNNLSTM()


def count_trainable_parameters(model: Any) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
