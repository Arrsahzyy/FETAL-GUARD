from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ai" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fetal_guard_ai.model import HybridCNNLSTMConfig, build_hybrid_cnn_lstm, require_torch
from fetal_guard_ai.training_data import group_holdout_split, load_hybrid_training_npz


SCREENING_LABELS = {
    0: "routine_monitoring",
    1: "needs_observation",
    2: "review_with_clinician",
}


class IndexedDataset:
    def __init__(self, dataset, indexes: np.ndarray) -> None:
        self.dataset = dataset
        self.indexes = np.asarray(indexes, dtype=np.int64)

    def __len__(self) -> int:
        return int(self.indexes.size)

    def __getitem__(self, index: int):
        row = int(self.indexes[index])
        return {
            "inputs": {name: values[row] for name, values in self.dataset.inputs.items()},
            "masks": {
                name: values[row] for name, values in self.dataset.validity_masks.items()
            },
            "screening": self.dataset.screening_labels[row],
            "quality": self.dataset.quality_targets[row],
            "measurements": self.dataset.measurement_targets[row],
            "contraction": self.dataset.contraction_targets[row],
        }


def build_attention_mask(torch, masks, fusion_steps: int):
    pooled_masks = []
    for name in ("piezo", "fsr", "maternal_ppg"):
        time_validity = masks[name].to(dtype=torch.float32).mean(dim=2).unsqueeze(1)
        pooled = torch.nn.functional.adaptive_avg_pool1d(time_validity, fusion_steps).squeeze(1)
        pooled_masks.append(pooled >= 0.5)
    return torch.stack(pooled_masks, dim=0).all(dim=0)


def compute_loss(torch, outputs, batch):
    quality_loss = torch.nn.functional.binary_cross_entropy_with_logits(
        outputs["quality_logit"], batch["quality"]
    )
    screening_loss = torch.nn.functional.cross_entropy(
        outputs["screening_logits"], batch["screening"]
    )
    total = screening_loss + 0.25 * quality_loss
    terms = {"screening": screening_loss, "quality": quality_loss}

    measurement_mask = torch.isfinite(batch["measurements"])
    if measurement_mask.any():
        scale = torch.tensor([210.0, 190.0], device=batch["measurements"].device)
        normalized_error = (outputs["measurements"] - batch["measurements"]) / scale
        measurement_loss = normalized_error[measurement_mask].square().mean()
        total = total + 0.25 * measurement_loss
        terms["measurements"] = measurement_loss

    contraction_mask = torch.isfinite(batch["contraction"])
    if contraction_mask.any():
        contraction_loss = torch.nn.functional.binary_cross_entropy_with_logits(
            outputs["contraction_logit"][contraction_mask],
            batch["contraction"][contraction_mask],
        )
        total = total + 0.25 * contraction_loss
        terms["contraction"] = contraction_loss
    return total, terms


def move_batch(torch, batch, device):
    return {
        "inputs": {
            name: value.to(device=device, dtype=torch.float32)
            for name, value in batch["inputs"].items()
        },
        "masks": {
            name: value.to(device=device, dtype=torch.bool)
            for name, value in batch["masks"].items()
        },
        "screening": batch["screening"].to(device=device, dtype=torch.long),
        "quality": batch["quality"].to(device=device, dtype=torch.float32),
        "measurements": batch["measurements"].to(device=device, dtype=torch.float32),
        "contraction": batch["contraction"].to(device=device, dtype=torch.float32),
    }


def run_epoch(torch, model, loader, device, optimizer=None) -> float:
    is_training = optimizer is not None
    model.train(is_training)
    weighted_loss = 0.0
    sample_count = 0
    for raw_batch in loader:
        batch = move_batch(torch, raw_batch, device)
        if optimizer is not None:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(is_training):
            attention_mask = build_attention_mask(
                torch, batch["masks"], model.config.fusion_steps
            )
            outputs = model(batch["inputs"], attention_mask=attention_mask)
            loss, _ = compute_loss(torch, outputs, batch)
            if optimizer is not None:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
        current_batch_size = int(batch["screening"].shape[0])
        weighted_loss += float(loss.detach().cpu()) * current_batch_size
        sample_count += current_batch_size
    if sample_count == 0:
        raise RuntimeError("A dataset split unexpectedly contains no samples")
    return weighted_loss / sample_count


def resolve_device(torch, requested: str):
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return torch.device(requested)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train the experimental FETAL-GUARD multi-modal CNN-LSTM."
    )
    parser.add_argument("--windows", required=True, help="Reviewed hybrid training .npz file.")
    parser.add_argument("--model-version", required=True, help="Unique experiment version.")
    parser.add_argument("--output-dir", default=str(ROOT / "ai" / "runs" / "cnn_lstm"))
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--min-valid-ratio", type=float, default=0.8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-synthetic-smoke-test",
        action="store_true",
        help="Permit synthetic data only for a non-clinical pipeline smoke test.",
    )
    args = parser.parse_args()
    if args.epochs <= 0 or args.batch_size <= 0 or args.learning_rate <= 0:
        parser.error("epochs, batch-size, and learning-rate must be positive")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.model_version):
        parser.error("model-version must be 1-64 safe filename characters")

    config = HybridCNNLSTMConfig()
    dataset = load_hybrid_training_npz(
        args.windows,
        config=config,
        min_valid_ratio=args.min_valid_ratio,
    )
    if dataset.dataset_kind == "synthetic_smoke_test" and not args.allow_synthetic_smoke_test:
        raise RuntimeError(
            "Synthetic data is blocked by default. Use --allow-synthetic-smoke-test only "
            "to verify mechanics; its artifact must never be promoted."
        )
    split = group_holdout_split(dataset.group_ids, seed=args.seed)
    summary = {
        "dataset_kind": dataset.dataset_kind,
        "input_schema_version": dataset.input_schema_version,
        "preprocessing_version": dataset.preprocessing_version,
        "model_version": args.model_version,
        "sample_count": dataset.sample_count,
        "group_count": int(np.unique(dataset.group_ids).size),
        "split_samples": {
            "train": int(split.train.size),
            "validation": int(split.validation.size),
            "test": int(split.test.size),
        },
        "modality_shapes": {
            name: list(values.shape) for name, values in dataset.inputs.items()
        },
        "model_config": asdict(config),
    }
    if args.dry_run:
        print(json.dumps(summary, indent=2))
        return 0

    torch, _ = require_torch()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    device = resolve_device(torch, args.device)
    model = build_hybrid_cnn_lstm(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    loader_options = {"batch_size": args.batch_size, "num_workers": 0}
    train_loader = torch.utils.data.DataLoader(
        IndexedDataset(dataset, split.train), shuffle=True, **loader_options
    )
    validation_loader = torch.utils.data.DataLoader(
        IndexedDataset(dataset, split.validation), shuffle=False, **loader_options
    )
    test_loader = torch.utils.data.DataLoader(
        IndexedDataset(dataset, split.test), shuffle=False, **loader_options
    )

    history = []
    best_validation_loss = float("inf")
    best_state = None
    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(torch, model, train_loader, device, optimizer=optimizer)
        validation_loss = run_epoch(torch, model, validation_loader, device)
        history.append(
            {"epoch": epoch, "train_loss": train_loss, "validation_loss": validation_loss}
        )
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_state = {
                name: value.detach().cpu().clone() for name, value in model.state_dict().items()
            }
        print(json.dumps(history[-1]))

    if best_state is None:
        raise RuntimeError("Training did not produce a checkpoint")
    model.load_state_dict(best_state)
    test_loss = run_epoch(torch, model, test_loader, device)
    summary["loss"] = {
        "best_validation": best_validation_loss,
        "held_out_test": test_loss,
    }
    summary["notice"] = (
        "Experimental engineering metric only; this is not clinical performance or validation."
    )

    output_root = Path(args.output_dir).resolve()
    output_dir = (output_root / args.model_version).resolve()
    if output_dir.parent != output_root:
        raise RuntimeError("model-version must not escape output-dir")
    output_dir.mkdir(parents=True, exist_ok=False)
    artifact_path = output_dir / "model.pt"
    torch.save(
        {
            "state_dict": best_state,
            "model_config": asdict(config),
            "screening_labels": SCREENING_LABELS,
            "input_schema_version": dataset.input_schema_version,
            "preprocessing_version": dataset.preprocessing_version,
        },
        artifact_path,
    )
    artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    manifest = {
        "model_name": "fetal-guard-hybrid",
        "model_version": args.model_version,
        "architecture": "cnn_lstm_multitask",
        "preprocessing_version": dataset.preprocessing_version,
        "artifact_file": artifact_path.name,
        "artifact_sha256": artifact_sha256,
        "validation_status": "experimental",
        "input_schema_version": dataset.input_schema_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_kind": dataset.dataset_kind,
        "model_config": asdict(config),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (output_dir / "training_summary.json").write_text(
        json.dumps({**summary, "history": history}, indent=2), encoding="utf-8"
    )
    print(json.dumps({"artifact": str(artifact_path), "manifest": manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
