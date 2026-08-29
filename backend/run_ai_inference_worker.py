"""Run fail-closed CNN-LSTM inference for stored telemetry v2 windows.

Run this process from ``backend`` with the dedicated
``fetal_guard_ai_worker`` PostgreSQL role. The active model record must point
to a local reviewed manifest via ``file://`` or an absolute filesystem path.
Patient publication remains a separate clinician-review workflow.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
import time
from urllib.parse import unquote, urlparse

from core.config import settings
from db.database import SessionLocal
from models.ai_analysis import AIModelVersion
from models.sensor_data import SensorDataChunk
from services.ai_pipeline import (
    AIWorkerOutput,
    claim_next_inference_job,
    complete_inference_job,
    fail_inference_job,
)


AI_SOURCE_DIR = Path(__file__).resolve().parents[1] / "ai" / "src"
if str(AI_SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SOURCE_DIR))

from fetal_guard_ai.inference import load_model_bundle, predict_preprocessed_window  # noqa: E402
from fetal_guard_ai.telemetry import (  # noqa: E402
    TelemetryWindowError,
    prepare_stored_telemetry_window,
)


LOGGER = logging.getLogger("fetal_guard.ai_inference_worker")


class ModelRuntime:
    def __init__(self, *, device: str = "cpu") -> None:
        self.device = device
        self.model_id: str | None = None
        self.model = None
        self.manifest = None

    def load_for(self, record: AIModelVersion):
        if self.model_id == record.id and self.model is not None and self.manifest is not None:
            return self.model, self.manifest
        manifest_path = _local_manifest_path(record.manifest_uri)
        model, manifest = load_model_bundle(
            manifest_path,
            deployment_mode=settings.AI_PIPELINE_MODE,
            device=self.device,
        )
        _assert_manifest_matches_record(record, manifest)
        self.model_id = record.id
        self.model = model
        self.manifest = manifest
        return model, manifest


def _local_manifest_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme not in {"", "file"}:
        raise RuntimeError("AI model manifest must be a local file path")
    if parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise RuntimeError("Remote file hosts are not supported for AI manifests")
        raw_path = unquote(parsed.path)
        if sys.platform == "win32" and raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
            raw_path = raw_path[1:]
        path = Path(raw_path)
    else:
        path = Path(uri)
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"AI model manifest not found: {resolved}")
    return resolved


def _assert_manifest_matches_record(record: AIModelVersion, manifest) -> None:
    mismatches = []
    for label, database_value, manifest_value in (
        ("model_name", record.model_name, manifest.model_name),
        ("version", record.version, manifest.model_version),
        ("preprocessing_version", record.preprocessing_version, manifest.preprocessing_version),
        ("artifact_sha256", record.artifact_sha256, manifest.artifact_sha256),
        ("input_schema_version", record.input_schema_version, manifest.input_schema_version),
        ("validation_status", record.validation_status, manifest.validation_status.value),
    ):
        if database_value != manifest_value:
            mismatches.append(label)
    if mismatches:
        raise RuntimeError("AI manifest differs from active database record: " + ", ".join(mismatches))


def _worker_output(result) -> AIWorkerOutput:
    return AIWorkerOutput(
        quality_status=result.quality_status.value,
        quality_score=result.quality_score,
        screening_status=result.screening_status.value,
        reasons=tuple(result.reasons),
        fhr_bpm=result.fhr_bpm,
        maternal_hr_bpm=result.maternal_hr_bpm,
        contraction_probability=result.contraction_probability,
        uncertainty=result.uncertainty,
        is_simulated=False,
    )


def run_once(*, runtime: ModelRuntime) -> int:
    if settings.AI_PIPELINE_MODE == "disabled":
        raise RuntimeError("AI inference worker cannot run while AI_PIPELINE_MODE=disabled")

    db = SessionLocal()
    job = None
    try:
        job = claim_next_inference_job(db)
        if job is None:
            db.commit()
            return 0
        record = db.query(AIModelVersion).filter(AIModelVersion.id == job.model_version_id).one()
        chunks = (
            db.query(SensorDataChunk)
            .filter(
                SensorDataChunk.session_id == job.session_id,
                SensorDataChunk.organization_id == job.organization_id,
                SensorDataChunk.captured_at >= job.window_started_at,
                SensorDataChunk.captured_at < job.window_ended_at,
            )
            .order_by(SensorDataChunk.captured_at.asc(), SensorDataChunk.sequence_number.asc())
            .all()
        )
        window_seconds = (job.window_ended_at - job.window_started_at).total_seconds()
        prepared = prepare_stored_telemetry_window(
            [chunk.payload for chunk in chunks],
            window_seconds=window_seconds,
        )
        model, manifest = runtime.load_for(record)
        result = predict_preprocessed_window(
            model,
            manifest,
            inputs=prepared.inputs,
            validity_masks=prepared.validity_masks,
            min_valid_ratio=settings.AI_MIN_VALID_RATIO,
        )
        complete_inference_job(db, job=job, output=_worker_output(result))
        db.commit()
        return 1
    except TelemetryWindowError as error:
        if job is None:
            db.rollback()
            raise
        fail_inference_job(db, job=job, error_code=error.code, error_message=str(error))
        db.commit()
        LOGGER.warning("Rejected AI job %s: %s", job.id, error.code)
        return 1
    except Exception as error:
        if job is None:
            db.rollback()
            raise
        fail_inference_job(
            db,
            job=job,
            error_code="inference_worker_error",
            error_message=f"{type(error).__name__}: {error}",
        )
        db.commit()
        LOGGER.exception("AI inference job %s failed safely", job.id)
        return 1
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    if not 0.2 <= args.poll_seconds <= 300:
        parser.error("--poll-seconds must be between 0.2 and 300")

    logging.basicConfig(level=logging.INFO)
    runtime = ModelRuntime(device=args.device)
    while True:
        processed = run_once(runtime=runtime)
        if args.once:
            return
        if processed == 0:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
