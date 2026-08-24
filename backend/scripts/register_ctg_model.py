"""Register bundled CTG checkpoint as an AIModelVersion and enable AI pipeline.

Usage (from backend/):
    python scripts/register_ctg_model.py

The script will:
- compute SHA256 of ../ctg_cnn_lstm_merged/checkpoints/best.pt
- ensure DB tables exist (init_db)
- insert an AIModelVersion row (is_active=True)
- write/append backend/.env with AI_PIPELINE_MODE=research and AI_ACTIVE_MODEL_VERSION_ID=<id>

This is intended for local/dev only. Review values before using in production.
"""
from datetime import datetime, timezone
import hashlib
import uuid
from pathlib import Path
import sys

# Ensure the backend package can be imported when running from backend/
# (this script lives in backend/scripts)
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from db.database import init_db, SessionLocal
from models.ai_analysis import AIModelVersion

CHECKPOINT = root.joinpath("..", "ctg_cnn_lstm_merged", "checkpoints", "best.pt").resolve()
if not CHECKPOINT.exists():
    raise SystemExit(f"Checkpoint not found at {CHECKPOINT}. Extract ctg bundle into repository first.")

# compute sha256
h = hashlib.sha256()
with CHECKPOINT.open("rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        h.update(chunk)
sha = h.hexdigest()

# create DB/tables if needed
init_db()

session = SessionLocal()
try:
    model_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    model = AIModelVersion(
        id=model_id,
        model_name="ctg_cnn_lstm_merged",
        version=f"bundle-{now.strftime('%Y%m%d%H%M%S')}",
        architecture="cnn_lstm_multitask",
        preprocessing_version="bundle-import",
        input_schema_version=2,
        artifact_sha256=sha,
        manifest_uri=f"file://{CHECKPOINT.as_posix()}",
        validation_status="analytical_validated",
        deployment_slot="research",
        is_active=True,
        created_at=now,
        activated_at=now,
    )
    session.add(model)
    session.commit()
    print(f"Inserted AIModelVersion id={model_id}")

    # Update backend/.env
    env_path = root.joinpath('.env')
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding='utf-8').splitlines()
    # remove existing keys if present
    keys = {"AI_PIPELINE_MODE", "AI_ACTIVE_MODEL_VERSION_ID"}
    new_lines = [l for l in lines if not any(l.strip().startswith(k + "=") for k in keys)]
    new_lines.append(f"AI_PIPELINE_MODE=research")
    new_lines.append(f"AI_ACTIVE_MODEL_VERSION_ID={model_id}")
    env_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    print(f"Wrote {env_path} with AI_PIPELINE_MODE=research and AI_ACTIVE_MODEL_VERSION_ID={model_id}")
finally:
    session.close()
