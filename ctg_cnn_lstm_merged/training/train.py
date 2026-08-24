import os
import sys
import argparse
import random
import json
from datetime import datetime, timezone

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.ai.model import CTGCNNLSTM


# ============================================================
# PATH
# ============================================================

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE, "data", "ctg_cnn_lstm_dataset.npz")
CKPT_DIR = os.path.join(BASE, "checkpoints")
RESULT_DIR = os.path.join(BASE, "results")

os.makedirs(CKPT_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)


# ============================================================
# REPRODUCIBILITY
# ============================================================

SEED = 42


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # Deterministic behavior for reproducibility.
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# DATA
# ============================================================

def load_data(path=DATA_PATH):
    d = np.load(path)

    X = d["X"]

    # Per-channel normalization.
    mean = X.reshape(-1, 3).mean(0)
    std = X.reshape(-1, 3).std(0) + 1e-6

    X = (X - mean) / std

    y_fhr = d["y_fhr"].astype(np.int64)
    y_mhr = d["y_mhr"].astype(np.int64)
    y_uc = d["y_uc"].astype(np.int64)
    y_overall = d["y_overall"].astype(np.int64)

    return (
        X.astype(np.float32),
        y_fhr,
        y_mhr,
        y_uc,
        y_overall,
        mean.astype(np.float32),
        std.astype(np.float32),
    )


# ============================================================
# CHECKPOINT
# ============================================================

def save_checkpoint(
    path,
    model,
    optimizer,
    epoch,
    best_val_acc,
    mean,
    std,
):
    torch.save(
        {
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "epoch": epoch,
            "best_val_acc": best_val_acc,
            "scaler_mean": mean,
            "scaler_std": std,
        },
        path,
    )


# ============================================================
# DATASET SPLIT
# ============================================================

def create_split(y_overall):
    indices = np.arange(len(y_overall))

    stratify = (
        y_overall
        if len(np.unique(y_overall)) > 1
        else None
    )

    # First:
    # 80% train
    # 20% temporary
    idx_train, idx_temp = train_test_split(
        indices,
        test_size=0.20,
        random_state=SEED,
        stratify=stratify,
    )

    # Then split temporary 20% into:
    # 10% validation
    # 10% test
    temp_y = y_overall[idx_temp]

    temp_stratify = (
        temp_y
        if len(np.unique(temp_y)) > 1
        else None
    )

    idx_val, idx_test = train_test_split(
        idx_temp,
        test_size=0.50,
        random_state=SEED,
        stratify=temp_stratify,
    )

    # Safety checks.
    train_set = set(idx_train)
    val_set = set(idx_val)
    test_set = set(idx_test)

    assert train_set.isdisjoint(val_set), \
        "TRAIN and VALIDATION overlap!"

    assert train_set.isdisjoint(test_set), \
        "TRAIN and TEST overlap!"

    assert val_set.isdisjoint(test_set), \
        "VALIDATION and TEST overlap!"

    assert (
        len(idx_train)
        + len(idx_val)
        + len(idx_test)
        == len(indices)
    ), "Dataset split does not cover all samples!"

    return idx_train, idx_val, idx_test


# ============================================================
# DATASET OBJECT
# ============================================================

def make_dataset(X, y_fhr, y_mhr, y_uc, y_overall, indices):
    return TensorDataset(
        torch.tensor(X[indices], dtype=torch.float32),
        torch.tensor(y_fhr[indices], dtype=torch.long),
        torch.tensor(y_mhr[indices], dtype=torch.long),
        torch.tensor(y_uc[indices], dtype=torch.long),
        torch.tensor(y_overall[indices], dtype=torch.long),
    )


# ============================================================
# CLASS DISTRIBUTION
# ============================================================

def class_distribution(y, indices):
    values, counts = np.unique(
        y[indices],
        return_counts=True,
    )

    return {
        str(int(v)): int(c)
        for v, c in zip(values, counts)
    }


def print_distributions(
    y_fhr,
    y_mhr,
    y_uc,
    y_overall,
    idx_train,
    idx_val,
    idx_test,
):
    print()
    print("=" * 60)
    print("CLASS DISTRIBUTION")
    print("=" * 60)

    datasets = {
        "TOTAL": np.arange(len(y_overall)),
        "TRAIN": idx_train,
        "VALIDATION": idx_val,
        "TEST": idx_test,
    }

    targets = {
        "FHR": y_fhr,
        "MHR": y_mhr,
        "UC": y_uc,
        "OVERALL": y_overall,
    }

    for dataset_name, indices in datasets.items():
        print(f"\n{dataset_name}")

        for target_name, y in targets.items():
            print(
                f"  {target_name}: "
                f"{class_distribution(y, indices)}"
            )


# ============================================================
# EVALUATION
# ============================================================

def calculate_metrics(y_true, y_pred):
    labels = sorted(
        set(y_true.tolist()) |
        set(y_pred.tolist())
    )

    return {
        "accuracy": float(
            accuracy_score(y_true, y_pred)
        ),
        "precision": float(
            precision_score(
                y_true,
                y_pred,
                average="weighted",
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_true,
                y_pred,
                average="weighted",
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y_true,
                y_pred,
                average="weighted",
                zero_division=0,
            )
        ),
        "confusion_matrix": confusion_matrix(
            y_true,
            y_pred,
            labels=labels,
        ).tolist(),
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=labels,
            output_dict=True,
            zero_division=0,
        ),
        "labels": labels,
    }


def evaluate_model(
    model,
    loader,
    device,
):
    model.eval()

    true_fhr = []
    pred_fhr = []

    true_mhr = []
    pred_mhr = []

    true_uc = []
    pred_uc = []

    true_overall = []
    pred_overall = []

    with torch.no_grad():
        for xb, fb, mb, ub, ob in loader:

            xb = xb.to(device)

            out = model(xb)

            pf = out["fhr"].argmax(1).cpu().numpy()
            pm = out["mhr"].argmax(1).cpu().numpy()
            pu = out["uc"].argmax(1).cpu().numpy()
            po = out["overall"].argmax(1).cpu().numpy()

            true_fhr.extend(fb.numpy())
            pred_fhr.extend(pf)

            true_mhr.extend(mb.numpy())
            pred_mhr.extend(pm)

            true_uc.extend(ub.numpy())
            pred_uc.extend(pu)

            true_overall.extend(ob.numpy())
            pred_overall.extend(po)

    results = {
        "fhr": calculate_metrics(
            np.array(true_fhr),
            np.array(pred_fhr),
        ),
        "mhr": calculate_metrics(
            np.array(true_mhr),
            np.array(pred_mhr),
        ),
        "uc": calculate_metrics(
            np.array(true_uc),
            np.array(pred_uc),
        ),
        "overall": calculate_metrics(
            np.array(true_overall),
            np.array(pred_overall),
        ),
    }

    return results


# ============================================================
# SAVE RESULTS
# ============================================================

def save_evaluation_results(
    results,
    idx_train,
    idx_val,
    idx_test,
    total,
):
    train_count = len(idx_train)
    val_count = len(idx_val)
    test_count = len(idx_test)

    summary = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "seed": SEED,

        "total_dataset": total,

        "train_count": train_count,
        "validation_count": val_count,
        "test_count": test_count,

        "train_percentage": train_count / total,
        "validation_percentage": val_count / total,
        "test_percentage": test_count / total,

        "metrics": {
            "fhr": {
                "accuracy": results["fhr"]["accuracy"],
                "precision": results["fhr"]["precision"],
                "recall": results["fhr"]["recall"],
                "f1": results["fhr"]["f1"],
            },
            "mhr": {
                "accuracy": results["mhr"]["accuracy"],
                "precision": results["mhr"]["precision"],
                "recall": results["mhr"]["recall"],
                "f1": results["mhr"]["f1"],
            },
            "uc": {
                "accuracy": results["uc"]["accuracy"],
                "precision": results["uc"]["precision"],
                "recall": results["uc"]["recall"],
                "f1": results["uc"]["f1"],
            },
            "overall": {
                "accuracy": results["overall"]["accuracy"],
                "precision": results["overall"]["precision"],
                "recall": results["overall"]["recall"],
                "f1": results["overall"]["f1"],
            },
        },

        "metric_averaging": "weighted",

        "warning": (
            "Evaluation uses window-level random splitting. "
            "If overlapping windows originate from the same "
            "patient/session and no group identifier exists, "
            "potential data leakage may remain."
        ),
    }

    with open(
        os.path.join(
            RESULT_DIR,
            "evaluation_summary.json",
        ),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            indent=2,
        )

    split_info = {
        "seed": SEED,
        "total": total,
        "train": train_count,
        "validation": val_count,
        "test": test_count,
        "train_percentage": train_count / total,
        "validation_percentage": val_count / total,
        "test_percentage": test_count / total,
    }

    with open(
        os.path.join(
            RESULT_DIR,
            "dataset_split.json",
        ),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            split_info,
            f,
            indent=2,
        )

    for name in ["fhr", "mhr", "uc", "overall"]:

        with open(
            os.path.join(
                RESULT_DIR,
                f"classification_report_{name}.json",
            ),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                results[name]["classification_report"],
                f,
                indent=2,
            )

        np.savetxt(
            os.path.join(
                RESULT_DIR,
                f"confusion_matrix_{name}.csv",
            ),
            np.array(
                results[name]["confusion_matrix"]
            ),
            delimiter=",",
            fmt="%d",
        )


# ============================================================
# PRINT FINAL REPORT
# ============================================================

def print_final_report(
    results,
    idx_train,
    idx_val,
    idx_test,
):
    total = (
        len(idx_train)
        + len(idx_val)
        + len(idx_test)
    )

    print()
    print("=" * 60)
    print("FETAL GUARD CNN-LSTM EVALUATION")
    print("=" * 60)

    print(
        f"TOTAL DATASET              = {total}"
    )

    print(
        f"TRAIN                      = "
        f"{len(idx_train)} "
        f"({len(idx_train) / total * 100:.2f}%)"
    )

    print(
        f"VALIDATION                 = "
        f"{len(idx_val)} "
        f"({len(idx_val) / total * 100:.2f}%)"
    )

    print(
        f"TEST                       = "
        f"{len(idx_test)} "
        f"({len(idx_test) / total * 100:.2f}%)"
    )

    for name in ["fhr", "mhr", "uc", "overall"]:

        print()
        print("-" * 60)
        print(name.upper())

        print(
            f"Accuracy                   = "
            f"{results[name]['accuracy'] * 100:.2f}%"
        )

        print(
            f"Precision                  = "
            f"{results[name]['precision'] * 100:.2f}%"
        )

        print(
            f"Recall                     = "
            f"{results[name]['recall'] * 100:.2f}%"
        )

        print(
            f"F1-score                   = "
            f"{results[name]['f1'] * 100:.2f}%"
        )

    print("=" * 60)


# ============================================================
# TRAIN
# ============================================================

def train(
    epochs=30,
    batch_size=64,
    lr=1e-3,
    resume=False,
    device=None,
    data_path=DATA_PATH,
):
    set_seed(SEED)

    device = device or (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    device = torch.device(device)

    print(f"Training device: {device}")

    (
        X,
        y_fhr,
        y_mhr,
        y_uc,
        y_overall,
        mean,
        std,
    ) = load_data(data_path)

    print()
    print(f"Dataset loaded: {len(X)} samples")
    print(f"X shape: {X.shape}")

    # --------------------------------------------------------
    # SPLIT
    # --------------------------------------------------------

    idx_train, idx_val, idx_test = create_split(
        y_overall
    )

    print()
    print("DATASET SPLIT")
    print("-" * 40)
    print(f"TOTAL      : {len(X)}")
    print(f"TRAIN      : {len(idx_train)}")
    print(f"VALIDATION : {len(idx_val)}")
    print(f"TEST       : {len(idx_test)}")

    # --------------------------------------------------------
    # CLASS DISTRIBUTION
    # --------------------------------------------------------

    print_distributions(
        y_fhr,
        y_mhr,
        y_uc,
        y_overall,
        idx_train,
        idx_val,
        idx_test,
    )

    # --------------------------------------------------------
    # DATA LOADERS
    # --------------------------------------------------------

    train_dataset = make_dataset(
        X,
        y_fhr,
        y_mhr,
        y_uc,
        y_overall,
        idx_train,
    )

    val_dataset = make_dataset(
        X,
        y_fhr,
        y_mhr,
        y_uc,
        y_overall,
        idx_val,
    )

    test_dataset = make_dataset(
        X,
        y_fhr,
        y_mhr,
        y_uc,
        y_overall,
        idx_test,
    )

    num_workers = 0

    pin_memory = (
        device.type == "cuda"
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    model = CTGCNNLSTM().to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=lr,
    )

    criterion = nn.CrossEntropyLoss()

    # --------------------------------------------------------
    # CHECKPOINT
    # --------------------------------------------------------

    start_epoch = 1
    best_val_acc = 0.0

    last_ckpt = os.path.join(
        CKPT_DIR,
        "last.pt",
    )

    best_ckpt = os.path.join(
        CKPT_DIR,
        "best.pt",
    )

    if resume and os.path.exists(last_ckpt):

        ckpt = torch.load(
            last_ckpt,
            map_location=device,
            weights_only=False,
        )

        model.load_state_dict(
            ckpt["model_state"]
        )

        if ckpt.get("optimizer_state"):
            optimizer.load_state_dict(
                ckpt["optimizer_state"]
            )

        start_epoch = (
            ckpt.get("epoch", 0) + 1
        )

        best_val_acc = ckpt.get(
            "best_val_acc",
            0.0,
        )

        print(
            f"Resuming from epoch "
            f"{start_epoch}"
        )

    # --------------------------------------------------------
    # TRAINING LOOP
    # --------------------------------------------------------

    for epoch in range(
        start_epoch,
        epochs + 1,
    ):

        model.train()

        running_loss = 0.0

        for (
            xb,
            fb,
            mb,
            ub,
            ob,
        ) in train_loader:

            xb = xb.to(device)
            fb = fb.to(device)
            mb = mb.to(device)
            ub = ub.to(device)
            ob = ob.to(device)

            optimizer.zero_grad()

            out = model(xb)

            loss = (
                criterion(
                    out["fhr"],
                    fb,
                )
                + criterion(
                    out["mhr"],
                    mb,
                )
                + criterion(
                    out["uc"],
                    ub,
                )
                + criterion(
                    out["overall"],
                    ob,
                )
            )

            loss.backward()

            optimizer.step()

            running_loss += (
                loss.item()
                * xb.size(0)
            )

        avg_loss = (
            running_loss
            / len(idx_train)
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        model.eval()

        correct = 0
        total_val = 0

        with torch.no_grad():

            for (
                xb,
                fb,
                mb,
                ub,
                ob,
            ) in val_loader:

                xb = xb.to(device)
                ob = ob.to(device)

                out = model(xb)

                pred = (
                    out["overall"]
                    .argmax(1)
                )

                correct += (
                    pred == ob
                ).sum().item()

                total_val += (
                    ob.size(0)
                )

        val_acc = (
            correct / total_val
            if total_val > 0
            else 0.0
        )

        print(
            f"Epoch {epoch}/{epochs} "
            f"- loss: {avg_loss:.4f} "
            f"- val_overall_acc: "
            f"{val_acc:.4f}"
        )

        # ----------------------------------------------------
        # SAVE LAST
        # ----------------------------------------------------

        save_checkpoint(
            last_ckpt,
            model,
            optimizer,
            epoch,
            best_val_acc,
            mean,
            std,
        )

        # ----------------------------------------------------
        # SAVE BEST
        # ----------------------------------------------------

        if val_acc > best_val_acc:

            best_val_acc = val_acc

            save_checkpoint(
                best_ckpt,
                model,
                optimizer,
                epoch,
                best_val_acc,
                mean,
                std,
            )

            print(
                f"  -> best.pt updated "
                f"(val_acc={val_acc:.4f})"
            )

    print()
    print(
        f"Training finished. "
        f"best_val_acc={best_val_acc:.4f}"
    )

    # ========================================================
    # FINAL TEST EVALUATION
    # ========================================================

    if not os.path.exists(best_ckpt):
        raise FileNotFoundError(
            "best.pt was not created."
        )

    print()
    print(
        "Loading best.pt for FINAL TEST "
        "EVALUATION..."
    )

    checkpoint = torch.load(
        best_ckpt,
        map_location=device,
        weights_only=False,
    )

    model.load_state_dict(
        checkpoint["model_state"]
    )

    results = evaluate_model(
        model,
        test_loader,
        device,
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    save_evaluation_results(
        results,
        idx_train,
        idx_val,
        idx_test,
        len(X),
    )

    # --------------------------------------------------------
    # PRINT
    # --------------------------------------------------------

    print_final_report(
        results,
        idx_train,
        idx_val,
        idx_test,
    )

    print()
    print(
        f"Evaluation results saved to: "
        f"{RESULT_DIR}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Train CTG CNN-LSTM"
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
    )

    parser.add_argument(
        "--lr",
        type=float,
        default=1e-3,
    )

    parser.add_argument(
        "--resume",
        action="store_true",
    )

    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="cpu or cuda",
    )

    parser.add_argument(
        "--data",
        type=str,
        default=DATA_PATH,
    )

    args = parser.parse_args()

    train(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        resume=args.resume,
        device=args.device,
        data_path=args.data,
    )