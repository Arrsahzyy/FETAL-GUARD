"""Register a trained ``fetal_guard_ai`` hybrid CNN-LSTM run as an ``AIModelVersion``.

Usage (from ``backend/``)::

    python scripts/register_hybrid_model.py --manifest ../ai/runs/cnn_lstm/<version>/manifest.json

The manifest is produced by ``ai/scripts/train_cnn_lstm.py``. This script:

- loads and verifies the manifest (artifact hash must match ``model.pt`` beside it)
- refuses anything that is not ``validation_status="experimental"`` for now
- deactivates any currently-active model in the ``research`` slot
- inserts one ``AIModelVersion`` row (``is_active=True``, ``deployment_slot="research"``)
- appends ``AI_PIPELINE_MODE=research`` + ``AI_ACTIVE_MODEL_VERSION_ID`` to ``backend/.env``

Local / dev only. A ``synthetic_smoke_test`` run proves the pipeline mechanics
end-to-end; it is never clinical and must never be promoted past ``research``.
See ``docs/ai/hybrid-dl-integration-prd.md`` (Fase 1).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
AI_SRC = ROOT / ".." / "ai" / "src"
if str(AI_SRC.resolve()) not in sys.path:
    sys.path.insert(0, str(AI_SRC.resolve()))

from db.database import SessionLocal, init_db  # noqa: E402
from models.ai_analysis import AIModelVersion  # noqa: E402
from fetal_guard_ai.artifact import ModelArtifactManifest  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True, help="manifest.json from train_cnn_lstm.py")
    parser.add_argument("--slot", default="research", choices=["research"], help="only research is allowed here")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    manifest = ModelArtifactManifest.load(manifest_path)
    manifest.verify(manifest_path)  # raises if model.pt is missing or the hash drifted
    if manifest.validation_status.value != "experimental":
        raise SystemExit(
            f"Refusing to register validation_status={manifest.validation_status.value} here. "
            "Advancing past experimental goes through the validation gate, not this script."
        )
    if manifest.input_schema_version != 2:
        raise SystemExit("Hybrid model requires input_schema_version 2")

    init_db()
    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        active = (
            session.query(AIModelVersion)
            .filter(AIModelVersion.deployment_slot == args.slot, AIModelVersion.is_active.is_(True))
            .all()
        )
        for row in active:
            row.is_active = False
            print(f"Deactivated prior active model in {args.slot}: {row.model_name} {row.version}")

        model = AIModelVersion(
            model_name=manifest.model_name,
            version=manifest.model_version,
            architecture=manifest.architecture,
            preprocessing_version=manifest.preprocessing_version,
            input_schema_version=manifest.input_schema_version,
            artifact_sha256=manifest.artifact_sha256,
            manifest_uri=manifest_path.as_uri(),
            validation_status=manifest.validation_status.value,
            deployment_slot=args.slot,
            is_active=True,
            created_at=now,
            activated_at=now,
        )
        session.add(model)
        session.flush()
        model_id = model.id
        session.commit()
        print(f"Inserted AIModelVersion id={model_id} ({manifest.model_name} {manifest.model_version}, experimental / {args.slot})")

        env_path = ROOT / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        keys = {"AI_PIPELINE_MODE", "AI_ACTIVE_MODEL_VERSION_ID"}
        kept = [line for line in lines if not any(line.strip().startswith(f"{key}=") for key in keys)]
        kept.append("AI_PIPELINE_MODE=research")
        kept.append(f"AI_ACTIVE_MODEL_VERSION_ID={model_id}")
        env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"Wrote {env_path}: AI_PIPELINE_MODE=research, AI_ACTIVE_MODEL_VERSION_ID={model_id}")
        print("Restart the API, then run the inference worker:")
        print("  python run_ai_inference_worker.py --poll-seconds 2")
    finally:
        session.close()


if __name__ == "__main__":
    main()
