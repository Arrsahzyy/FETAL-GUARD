"""End-to-end smoke: ingestion -> enqueue_ready_window -> inference worker -> AIAnalysisResult.

Covers the one seam the other AI tests don't: ``run_ai_inference_worker.run_once``
glue (read chunks -> prepare_stored_telemetry_window -> load the trained bundle ->
predict_preprocessed_window -> complete_inference_job).

Skipped unless torch is installed AND a research checkpoint exists at
``ai/runs/cnn_lstm/smoke-v1/`` (``docs/ai/research-model-training.md``). Not run in
CI -- torch is not in backend/requirements.txt.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

pytest.importorskip("torch")

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "ai" / "runs" / "cnn_lstm" / "smoke-v1" / "manifest.json"
pytestmark = pytest.mark.skipif(
    not MANIFEST.is_file(),
    reason="train the research checkpoint first: see docs/ai/research-model-training.md",
)

from models.ai_analysis import AIAnalysisResult, AIInferenceJob, AIModelVersion  # noqa: E402
from models.session import MonitoringSession  # noqa: E402
from tests.test_vitals_and_alerting import build_window_chunk  # noqa: E402
from tests.test_devices import create_active_session, register_device  # noqa: E402

DEVICE_UID = "FG-HYBRID-01"


def test_trained_research_model_processes_a_streamed_window(client, auth_headers, db_session, monkeypatch):
    import run_ai_inference_worker as worker
    from services import ai_pipeline

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    patient_headers = auth_headers(email="hybrid-smoke@example.com", role="patient")
    admin_headers = auth_headers(email="hybrid-smoke-admin@example.com", role="admin")
    session_data = create_active_session(client, patient_headers, name="Hybrid Smoke")
    register_device(client, admin_headers, session_data["patient_id"], device_uid=DEVICE_UID)

    # Backdate the session so a full AI window has already elapsed.
    monitoring_session = db_session.query(MonitoringSession).filter_by(id=session_data["id"]).one()
    session_start = datetime.now(timezone.utc) - timedelta(seconds=40)
    monitoring_session.start_time = session_start
    db_session.commit()

    for attr, value in {
        "AI_PIPELINE_MODE": "research",
        "AI_WINDOW_SECONDS": 12,
        "AI_WINDOW_STRIDE_SECONDS": 6,
        "AI_LATE_ARRIVAL_GRACE_SECONDS": 5,
    }.items():
        monkeypatch.setattr(ai_pipeline.settings, attr, value)

    model = AIModelVersion(
        model_name=manifest["model_name"],
        version=manifest["model_version"],
        architecture=manifest["architecture"],
        preprocessing_version=manifest["preprocessing_version"],
        input_schema_version=int(manifest["input_schema_version"]),
        artifact_sha256=manifest["artifact_sha256"],
        manifest_uri=MANIFEST.as_uri(),
        validation_status=manifest["validation_status"],
        deployment_slot="research",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        activated_at=datetime.now(timezone.utc),
    )
    db_session.add(model)
    db_session.commit()
    monkeypatch.setattr(ai_pipeline.settings, "AI_ACTIVE_MODEL_VERSION_ID", model.id)

    # Stream 30 s of telemetry forward from the (backdated) session start.
    for index in range(30):
        captured_at = session_start + timedelta(seconds=index)
        chunk = build_window_chunk(index, fhr_bpm=142, maternal_bpm=84, captured_at=captured_at)
        chunk["device_uid"] = DEVICE_UID
        chunk["ingestion_id"] = f"hybrid-{index}"
        response = client.post(
            f"/sessions/{session_data['id']}/data", headers=patient_headers, json=chunk
        )
        assert response.status_code == 201, response.json()

    jobs = db_session.query(AIInferenceJob).filter_by(session_id=session_data["id"]).all()
    assert jobs, "ingestion did not enqueue an AI inference job"
    assert any(job.status == "pending" for job in jobs)

    # Point the worker's own SessionLocal at the shared in-memory test engine.
    monkeypatch.setattr(worker, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    runtime = worker.ModelRuntime()
    processed = sum(worker.run_once(runtime=runtime) for _ in range(len(jobs) + 2))
    assert processed >= 1

    db_session.expire_all()
    results = db_session.query(AIAnalysisResult).filter_by(session_id=session_data["id"]).all()
    assert results, "worker did not persist an AIAnalysisResult"
    result = results[0]
    assert result.visibility == "shadow"          # research -> shadow, no clinician/patient exposure
    assert result.model_version == manifest["model_version"]
    assert result.screening_status in {
        "routine_monitoring", "needs_observation", "review_with_clinician", "insufficient_signal",
    }
    assert result.quality_status in {"usable", "limited", "unusable"}
    completed = db_session.query(AIInferenceJob).filter_by(id=result.job_id).one()
    assert completed.status == "completed"
