from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ai" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fetal_guard_ai.datasets import get_dataset_descriptor, require_wfdb


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local CTU-UHB records without downloading data automatically.")
    parser.add_argument("--manifest", default=str(ROOT / "ai" / "config" / "datasets.json"))
    parser.add_argument("--dataset-id", default="ctu_uhb_ctgdb")
    parser.add_argument("--list-records", action="store_true")
    args = parser.parse_args()

    descriptor = get_dataset_descriptor(args.manifest, args.dataset_id)
    print(json.dumps({
        "id": descriptor.id,
        "name": descriptor.name,
        "official_url": descriptor.official_url,
        "local_raw_dir": str(descriptor.local_raw_dir),
        "available_locally": descriptor.is_available_locally,
    }, indent=2))

    if not descriptor.is_available_locally:
        print(
            "\nDataset belum ada secara lokal. Unduh dari URL resmi PhysioNet, "
            "lalu simpan sesuai local_raw_dir. Script ini sengaja tidak auto-download "
            "agar lisensi, ukuran data, dan provenance tetap diawasi."
        )
        return 0

    if args.list_records:
        wfdb = require_wfdb()
        records = wfdb.get_record_list(str(descriptor.local_raw_dir))
        for record in records[:20]:
            print(record)
        print(f"total_records_seen={len(records)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
