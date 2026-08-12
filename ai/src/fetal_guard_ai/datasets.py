from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetDescriptor:
    id: str
    name: str
    provider: str
    official_url: str
    access: str
    primary_use: str
    modality: list[str]
    sampling_hz: float | None
    local_raw_dir: Path
    notes: list[str]

    @property
    def is_available_locally(self) -> bool:
        return self.local_raw_dir.exists() and any(self.local_raw_dir.iterdir())


def load_dataset_manifest(path: str | Path) -> list[DatasetDescriptor]:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_dir = manifest_path.parents[2]
    descriptors: list[DatasetDescriptor] = []

    for item in data.get("datasets", []):
        local_raw_dir = Path(item["local_raw_dir"])
        if not local_raw_dir.is_absolute():
            local_raw_dir = base_dir / local_raw_dir

        descriptors.append(
            DatasetDescriptor(
                id=item["id"],
                name=item["name"],
                provider=item["provider"],
                official_url=item["official_url"],
                access=item["access"],
                primary_use=item["primary_use"],
                modality=list(item["modality"]),
                sampling_hz=item.get("sampling_hz"),
                local_raw_dir=local_raw_dir,
                notes=list(item.get("notes", [])),
            )
        )

    return descriptors


def get_dataset_descriptor(path: str | Path, dataset_id: str) -> DatasetDescriptor:
    for descriptor in load_dataset_manifest(path):
        if descriptor.id == dataset_id:
            return descriptor
    raise KeyError(f"Unknown dataset id: {dataset_id}")


def require_wfdb() -> Any:
    try:
        import wfdb  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "WFDB is required for PhysioNet record loading. "
            "Install AI dependencies with: python -m pip install -r ai/requirements-ai.txt"
        ) from exc
    return wfdb
