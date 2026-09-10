"""Register Adit's CTG CNN-LSTM checkpoint as an ``AIModelVersion`` (research slot).

Usage (from ``backend/``)::

    python scripts/register_ctg_model.py \
        --checkpoint ../ai/vendor/ctg_cnn_lstm_adit/checkpoints/best.pt \
        --model-card ../docs/ai/model-cards/ctg_cnn_lstm_adit.md

The script will:

- verify the checkpoint and the model card both exist
- compute the checkpoint SHA-256
- ensure DB tables exist (``init_db``)
- insert one ``AIModelVersion`` row (``is_active=True``,
  ``validation_status="experimental"``, ``deployment_slot="research"``)
- append ``AI_PIPELINE_MODE=research`` + ``AI_ACTIVE_MODEL_VERSION_ID=<id>`` to
  ``backend/.env``

This is a **local / dev** tool for Fase 1 of the hybrid-DL PRD. The model is
trained 100% on synthetic data and has no real-CTG validation, so it stays in
the ``research`` slot: no clinician UI, no patient output. Do not set
``validation_status`` to ``analytical_validated`` until
``training/external_validation.py`` has run against real held-out CTG data and
the results are written into the model card (see
``docs/ai/hybrid-dl-integration-prd.md`` sections 4b and 5).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure the backend package can be imported when running from backend/.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.database import SessionLocal, init_db  # noqa: E402
from models.ai_analysis import AIModelVersion  # noqa: E402

DEFAULT_CHECKPOINT = ROOT / ".." / "ai" / "vendor" / "ctg_cnn_lstm_adit" / "checkpoints" / "best.pt"
DEFAULT_MODEL_CARD = ROOT / ".." / "docs" / "ai" / "model-cards" / "ctg_cnn_lstm_adit.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8192), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--model-card", type=Path, default=DEFAULT_MODEL_CARD)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    checkpoint = args.checkpoint.resolve()
    model_card = args.model_card.resolve()

    if not checkpoint.exists():
        raise SystemExit(
            f"Checkpoint not found: {checkpoint}\n"
            "Fetch the reference repo (scripts/fetch-ctg-adit-reference.ps1) and train it:\n"
            "  python training/generate_sequences.py && python training/train.py\n"
            "The checkpoint is reproducible from seed 42 -- do not copy an untrusted .pt."
        )
    if not model_card.exists():
        raise SystemExit(
            f"Model card not found: {model_card}\n"
            "Every AIModelVersion needs a model card. See docs/ai/model-cards/TEMPLATE.md."
        )

    sha = _sha256(checkpoint)
    init_db()

    session = SessionLocal()
    try:
        model_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        model = AIModelVersion(
            id=model_id,
            model_name="ctg_cnn_lstm_adit",
            version=f"adit-{now.strftime('%Y%m%d%H%M%S')}",
            architecture="cnn_lstm_multitask",
            preprocessing_version="adit-derived-vitals-15x3",
            input_schema_version=2,
            artifact_sha256=sha,
            manifest_uri=f"file://{checkpoint.as_posix()}",
            # Synthetic-only training, no real-CTG validation -> experimental / research.
            validation_status="experimental",
            deployment_slot="research",
            is_active=True,
            created_at=now,
            activated_at=now,
        )
        session.add(model)
        session.commit()
        print(f"Inserted AIModelVersion id={model_id} (experimental / research)")
        print(f"  checkpoint : {checkpoint}")
        print(f"  sha256     : {sha}")
        print(f"  model card : {model_card}")

        env_path = ROOT / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        keys = {"AI_PIPELINE_MODE", "AI_ACTIVE_MODEL_VERSION_ID"}
        kept = [line for line in lines if not any(line.strip().startswith(f"{key}=") for key in keys)]
        kept.append("AI_PIPELINE_MODE=research")
        kept.append(f"AI_ACTIVE_MODEL_VERSION_ID={model_id}")
        env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"Wrote {env_path}: AI_PIPELINE_MODE=research, AI_ACTIVE_MODEL_VERSION_ID={model_id}")
        print("Restart the API and the inference worker for this to take effect.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
