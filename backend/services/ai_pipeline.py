from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import uuid

from sqlalchemy import and_, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.realtime import enqueue_realtime_event
from models.ai_analysis import (
    AIAnalysisResult,
    AIAnalysisReview,
    AIInferenceJob,
    AIModelVersion,
)
from models.sensor_data import SensorDataChunk
from models.session import MonitoringSession


QUALITY_STATUSES = frozenset({"usable", "limited", "unusable"})
SCREENING_STATUSES = frozenset(
    {
        "routine_monitoring",
        "needs_observation",
        "review_with_clinician",
        "insufficient_signal",
    }
)
REASON_CODE_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")


@dataclass(frozen=True)
class AIWorkerOutput:
    quality_status: str
    quality_score: float
    screening_status: str
    reasons: tuple[str, ...]
    fhr_bpm: float | None = None
    maternal_hr_bpm: float | None = None
    contraction_probability: float | None = None
    uncertainty: float | None = None
    is_simulated: bool = False

    def validate(self) -> None:
        if self.quality_status not in QUALITY_STATUSES:
            raise ValueError("Unsupported AI quality status")
        if self.screening_status not in SCREENING_STATUSES:
            raise ValueError("Unsupported AI screening status")
        _validate_probability(self.quality_score, "quality_score")
        if self.uncertainty is not None:
            _validate_probability(self.uncertainty, "uncertainty")
        if self.contraction_probability is not None:
            _validate_probability(self.contraction_probability, "contraction_probability")
        for value, name, lower, upper in (
            (self.fhr_bpm, "fhr_bpm", 30, 240),
            (self.maternal_hr_bpm, "maternal_hr_bpm", 30, 220),
        ):
            if value is not None and (not math.isfinite(value) or not lower <= value <= upper):
                raise ValueError(f"{name} is outside the technical output range")
        if self.quality_status == "unusable" and self.screening_status != "insufficient_signal":
            raise ValueError("Unusable signal must produce insufficient_signal")
        if len(self.reasons) > 16:
            raise ValueError("AI output may contain at most 16 reason codes")
        for reason in self.reasons:
            if not reason or len(reason) > 64 or any(character not in REASON_CODE_CHARACTERS for character in reason):
                raise ValueError("AI reason codes must be lowercase snake_case")


def _validate_probability(value: float, field_name: str) -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be a finite value between 0 and 1")


def set_ai_worker_database_context(db: Session) -> None:
    """Refuse AI mutations unless PostgreSQL uses the isolated worker role."""

    if db.get_bind().dialect.name == "postgresql":
        database_role = db.execute(text("SELECT current_user")).scalar_one()
        if database_role != "fetal_guard_ai_worker":
            raise RuntimeError(
                "AI worker mutations require the fetal_guard_ai_worker database role"
            )


def _active_model(db: Session) -> AIModelVersion:
    model_version_id = settings.AI_ACTIVE_MODEL_VERSION_ID
    if settings.AI_PIPELINE_MODE == "disabled" or not model_version_id:
        raise RuntimeError("AI pipeline is disabled")
    model = (
        db.query(AIModelVersion)
        .filter(
            AIModelVersion.id == model_version_id,
            AIModelVersion.is_active.is_(True),
        )
        .first()
    )
    if model is None:
        raise RuntimeError("Configured AI model version is not active")
    if model.deployment_slot != settings.AI_PIPELINE_MODE:
        raise RuntimeError("Configured AI model deployment slot does not match pipeline mode")
    if settings.AI_PIPELINE_MODE == "shadow" and model.validation_status not in {
        "analytical_validated",
        "clinical_validated",
    }:
        raise RuntimeError("Shadow mode requires at least analytical validation")
    if model.validation_status == "retired":
        raise RuntimeError("Retired AI model cannot receive inference jobs")
    return model


def assert_ai_pipeline_ready(db: Session) -> None:
    if settings.AI_PIPELINE_MODE == "disabled":
        return
    _active_model(db)


def enqueue_ready_window(
    db: Session,
    *,
    monitoring_session: MonitoringSession,
    latest_chunk: SensorDataChunk,
) -> AIInferenceJob | None:
    """Create one idempotent rolling-window job after sufficient session time.

    This function does not perform inference. A dedicated worker must claim the
    job, reconstruct and validate every modality, and either persist a result or
    reject the window. When the pipeline is disabled it is a strict no-op.
    """

    if settings.AI_PIPELINE_MODE == "disabled":
        return None
    if latest_chunk.captured_at is None or monitoring_session.device_id is None:
        return None

    model = _active_model(db)
    session_start = _as_utc(monitoring_session.start_time)
    captured_at = _as_utc(latest_chunk.captured_at)
    elapsed_seconds = (
        captured_at - session_start
    ).total_seconds() - settings.AI_LATE_ARRIVAL_GRACE_SECONDS
    if elapsed_seconds < settings.AI_WINDOW_SECONDS:
        return None

    stride_index = int(elapsed_seconds // settings.AI_WINDOW_STRIDE_SECONDS)
    window_end = session_start + timedelta(
        seconds=stride_index * settings.AI_WINDOW_STRIDE_SECONDS
    )
    window_start = window_end - timedelta(seconds=settings.AI_WINDOW_SECONDS)
    chunks = (
        db.query(SensorDataChunk)
        .filter(
            SensorDataChunk.session_id == monitoring_session.id,
            SensorDataChunk.organization_id == monitoring_session.organization_id,
            SensorDataChunk.captured_at >= window_start,
            SensorDataChunk.captured_at < window_end,
        )
        .order_by(SensorDataChunk.captured_at.asc(), SensorDataChunk.sequence_number.asc())
        .all()
    )
    if not chunks:
        return None
    input_hash = hashlib.sha256(
        json.dumps(
            [
                {
                    "id": chunk.id,
                    "ingestion_id": chunk.ingestion_id,
                    "captured_at": _as_utc(chunk.captured_at).isoformat()
                    if chunk.captured_at
                    else None,
                }
                for chunk in chunks
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    existing = (
        db.query(AIInferenceJob)
        .filter(
            AIInferenceJob.session_id == monitoring_session.id,
            AIInferenceJob.window_started_at == window_start,
            AIInferenceJob.model_version_id == model.id,
        )
        .first()
    )
    if existing is not None:
        return existing

    job = AIInferenceJob(
        id=str(uuid.uuid4()),
        organization_id=monitoring_session.organization_id,
        patient_id=monitoring_session.patient_id,
        session_id=monitoring_session.id,
        device_id=monitoring_session.device_id,
        model_version_id=model.id,
        window_started_at=window_start,
        window_ended_at=window_end,
        input_hash=input_hash,
        status="pending",
        attempts=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        concurrent = (
            db.query(AIInferenceJob)
            .filter(
                AIInferenceJob.session_id == monitoring_session.id,
                AIInferenceJob.window_started_at == window_start,
                AIInferenceJob.model_version_id == model.id,
            )
            .first()
        )
        if concurrent is not None:
            return concurrent
        raise
    return job


def claim_next_inference_job(db: Session) -> AIInferenceJob | None:
    set_ai_worker_database_context(db)
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=settings.AI_JOB_LEASE_SECONDS)
    db.query(AIInferenceJob).filter(
        AIInferenceJob.status == "processing",
        AIInferenceJob.attempts >= settings.AI_MAX_JOB_ATTEMPTS,
        AIInferenceJob.locked_at.is_not(None),
        AIInferenceJob.locked_at <= stale_before,
    ).update(
        {
            AIInferenceJob.status: "rejected",
            AIInferenceJob.error_code: "worker_lease_exhausted",
            AIInferenceJob.error_message: "Worker lease expired after the final allowed attempt",
            AIInferenceJob.locked_at: None,
            AIInferenceJob.updated_at: now,
        },
        synchronize_session="fetch",
    )
    retryable = and_(
        AIInferenceJob.status.in_(("pending", "failed")),
        or_(
            AIInferenceJob.next_attempt_at.is_(None),
            AIInferenceJob.next_attempt_at <= now,
        ),
    )
    abandoned = and_(
        AIInferenceJob.status == "processing",
        AIInferenceJob.locked_at.is_not(None),
        AIInferenceJob.locked_at <= stale_before,
    )
    job = (
        db.query(AIInferenceJob)
        .filter(
            AIInferenceJob.attempts < settings.AI_MAX_JOB_ATTEMPTS,
            or_(retryable, abandoned),
        )
        .order_by(AIInferenceJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if job is None:
        return None
    job.status = "processing"
    job.attempts += 1
    job.locked_at = now
    job.updated_at = now
    job.error_code = None
    job.error_message = None
    db.flush()
    return job


def complete_inference_job(
    db: Session,
    *,
    job: AIInferenceJob,
    output: AIWorkerOutput,
) -> AIAnalysisResult:
    set_ai_worker_database_context(db)
    output.validate()
    if job.status != "processing":
        raise ValueError("Only a processing inference job can be completed")
    model = db.query(AIModelVersion).filter(AIModelVersion.id == job.model_version_id).one()
    if not model.is_active or model.validation_status == "retired":
        raise RuntimeError("Inference job model is no longer active")
    existing = db.query(AIAnalysisResult).filter(AIAnalysisResult.job_id == job.id).first()
    if existing is not None:
        return existing

    visibility = "shadow"
    result = AIAnalysisResult(
        id=str(uuid.uuid4()),
        organization_id=job.organization_id,
        patient_id=job.patient_id,
        session_id=job.session_id,
        device_id=job.device_id,
        job_id=job.id,
        model_version_id=model.id,
        model_version=model.version,
        preprocessing_version=model.preprocessing_version,
        window_started_at=job.window_started_at,
        window_ended_at=job.window_ended_at,
        quality_status=output.quality_status,
        quality_score=output.quality_score,
        fhr_bpm=output.fhr_bpm,
        maternal_hr_bpm=output.maternal_hr_bpm,
        contraction_probability=output.contraction_probability,
        screening_status=output.screening_status,
        uncertainty=output.uncertainty,
        reasons=list(dict.fromkeys(output.reasons)),
        visibility=visibility,
        is_simulated=output.is_simulated,
        created_at=datetime.now(timezone.utc),
    )
    db.add(result)
    job.status = "completed"
    job.locked_at = None
    job.updated_at = datetime.now(timezone.utc)
    db.flush()
    return result


def publish_analysis_result(
    db: Session,
    *,
    result: AIAnalysisResult,
    visibility: str,
) -> AIAnalysisResult:
    """Promote a stored result only after its model validation gate passes."""

    set_ai_worker_database_context(db)
    if visibility not in {"clinician", "patient"}:
        raise ValueError("Published AI visibility must be clinician or patient")
    model = db.query(AIModelVersion).filter(AIModelVersion.id == result.model_version_id).one()
    if model.validation_status != "clinical_validated":
        raise RuntimeError("Only a clinically validated model can publish visible results")
    if result.quality_status == "unusable" and result.screening_status != "insufficient_signal":
        raise RuntimeError("Unusable signal cannot publish a screening classification")
    if visibility == "patient":
        review = (
            db.query(AIAnalysisReview)
            .filter(AIAnalysisReview.analysis_result_id == result.id)
            .first()
        )
        if review is None or review.decision == "dismissed":
            raise RuntimeError(
                "Patient publication requires a non-dismissed clinician review"
            )

    result.visibility = visibility
    enqueue_realtime_event(
        db,
        organization_id=result.organization_id,
        patient_id=result.patient_id,
        event_type="ai.analysis.updated",
        resource_id=result.id,
        idempotency_key=f"ai.analysis.updated:{result.id}:visibility:{visibility}",
        payload={
            "quality_status": result.quality_status,
            "screening_status": result.screening_status,
            "visibility": visibility,
            "version": 1,
        },
        occurred_at=result.created_at,
    )
    db.flush()
    return result


def fail_inference_job(
    db: Session,
    *,
    job: AIInferenceJob,
    error_code: str,
    error_message: str,
) -> None:
    set_ai_worker_database_context(db)
    if job.status != "processing":
        raise ValueError("Only a processing inference job can fail")
    normalized_error_code = error_code.strip().lower()
    if (
        not normalized_error_code
        or any(character not in REASON_CODE_CHARACTERS for character in normalized_error_code)
    ):
        raise ValueError("AI job error_code must be lowercase snake_case")
    job.status = "rejected" if job.attempts >= settings.AI_MAX_JOB_ATTEMPTS else "failed"
    job.error_code = normalized_error_code[:64]
    job.error_message = error_message[:500]
    job.locked_at = None
    job.next_attempt_at = (
        None
        if job.status == "rejected"
        else datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** job.attempts))
    )
    job.updated_at = datetime.now(timezone.utc)
    db.flush()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
