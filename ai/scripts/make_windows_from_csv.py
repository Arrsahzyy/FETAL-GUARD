from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ai" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fetal_guard_ai.features import signal_quality_index
from fetal_guard_ai.preprocessing import WindowConfig, make_masked_sliding_windows, robust_zscore


def main() -> int:
    parser = argparse.ArgumentParser(description="Create model-ready windows from a CSV time-series file.")
    parser.add_argument("--input", required=True, help="CSV with numeric signal columns.")
    parser.add_argument("--output", required=True, help="Output .npz path.")
    parser.add_argument("--columns", required=True, help="Comma-separated signal columns, e.g. fhr,uc.")
    parser.add_argument("--sampling-hz", type=float, required=True)
    parser.add_argument("--window-seconds", type=float, default=60.0)
    parser.add_argument("--stride-seconds", type=float, default=15.0)
    args = parser.parse_args()

    columns = [column.strip() for column in args.columns.split(",") if column.strip()]
    frame = pd.read_csv(args.input)
    missing_columns = [column for column in columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing columns in CSV: {missing_columns}")

    matrix = frame[columns].to_numpy(dtype=np.float32)
    validity_mask = np.isfinite(matrix)
    normalized = robust_zscore(matrix)
    config = WindowConfig(
        sampling_hz=args.sampling_hz,
        window_seconds=args.window_seconds,
        stride_seconds=args.stride_seconds,
    )
    windows, masks, starts = make_masked_sliding_windows(
        normalized,
        config,
        validity_mask=validity_mask,
    )
    quality = signal_quality_index(matrix)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        windows=windows,
        validity_masks=masks,
        starts=starts,
        columns=np.asarray(columns),
        sampling_hz=np.asarray([args.sampling_hz], dtype=np.float32),
    )
    metadata = {
        "input": str(Path(args.input).resolve()),
        "output": str(output_path.resolve()),
        "columns": columns,
        "window_count": int(windows.shape[0]),
        "window_shape": list(windows.shape),
        "signal_quality": quality.__dict__,
    }
    output_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
