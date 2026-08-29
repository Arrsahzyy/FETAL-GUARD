from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.audit import add_access_audit_event
from core.authorization import (
    Principal,
    get_current_staff_principal,
    require_permission,
    resolve_staff_principal,
    scoped_patient_or_404,
    scoped_patient_query,
)
from core.config import settings
from core.realtime import enqueue_realtime_event
from db.database import get_db
from models.ai_analysis import AIAnalysisResult, AIAnalysisReview
from models.patient import Patient
from models.sensor_data import SensorDataChunk
from models.session import MonitoringSession
from models.user import User
from schemas.ai import (
    AIAnalysisResultPage,
    AIAnalysisResultResponse,
    AIAnalysisReviewRequest,
    AIAnalysisReviewResponse,
    AIPatientAvailabilityResponse,
    AIPredictRequest,
    AIPredictResponse,
)

router = APIRouter()


@router.get("/status", response_model=AIPatientAvailabilityResponse)
def read_patient_ai_availability(
    current_user: User = Depends(get_current_user),
) -> AIPatientAvailabilityResponse:
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patient AI availability is only accessible to patients",
        )
    return AIPatientAvailabilityResponse(
        patient_results_enabled=(
            settings.AI_PIPELINE_MODE == "clinician"
            and bool(settings.AI_ACTIVE_MODEL_VERSION_ID)
        )
    )


def build_analysis_response(
    result: AIAnalysisResult,
    review: AIAnalysisReview | None = None,
) -> AIAnalysisResultResponse:
    return AIAnalysisResultResponse(
        id=result.id,
        patient_id=result.patient_id,
        session_id=result.session_id,
        device_id=result.device_id,
        window_started_at=result.window_started_at,
        window_ended_at=result.window_ended_at,
        quality_status=result.quality_status,
        quality_score=result.quality_score,
        fhr_bpm=result.fhr_bpm,
        maternal_hr_bpm=result.maternal_hr_bpm,
        contraction_probability=result.contraction_probability,
        screening_status=result.screening_status,
        uncertainty=result.uncertainty,
        reasons=list(result.reasons or []),
        visibility=result.visibility,
        is_simulated=result.is_simulated,
        model_version=result.model_version,
        preprocessing_version=result.preprocessing_version,
        created_at=result.created_at,
        review=(AIAnalysisReviewResponse.model_validate(review) if review else None),
    )


def build_analysis_page(
    db: Session,
    query,
    *,
    limit: int,
    offset: int,
) -> AIAnalysisResultPage:
    total = query.count()
    results = query.order_by(AIAnalysisResult.created_at.desc()).offset(offset).limit(limit).all()
    result_ids = [result.id for result in results]
    reviews = (
        db.query(AIAnalysisReview)
        .filter(AIAnalysisReview.analysis_result_id.in_(result_ids))
        .all()
        if result_ids
        else []
    )
    reviews_by_result = {review.analysis_result_id: review for review in reviews}
    return AIAnalysisResultPage(
        items=[
            build_analysis_response(result, reviews_by_result.get(result.id))
            for result in results
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_accessible_sensor_chunk(
    db: Session,
    chunk_id: str,
    current_user: User,
    organization_id: str | None = None,
) -> SensorDataChunk:
    if current_user.role in {"clinician", "admin"}:
        principal = resolve_staff_principal(db, current_user, organization_id)
        require_permission(principal, "patients:read:assigned", "patients:read:facility")
        authorized_patients = scoped_patient_query(db, principal).with_entities(Patient.id).subquery()
        chunk = (
            db.query(SensorDataChunk)
            .join(MonitoringSession, SensorDataChunk.session_id == MonitoringSession.id)
            .filter(
                SensorDataChunk.id == chunk_id,
                MonitoringSession.patient_id.in_(select(authorized_patients.c.id)),
            )
            .first()
        )
    elif current_user.role == "patient":
        chunk = (
            db.query(SensorDataChunk)
            .join(MonitoringSession, SensorDataChunk.session_id == MonitoringSession.id)
            .join(Patient, Patient.id == MonitoringSession.patient_id)
            .filter(
                SensorDataChunk.id == chunk_id,
                Patient.user_id == current_user.id,
            )
            .first()
        )
    else:
        chunk = None

    if chunk is not None:
        return chunk

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Sensor data chunk not found",
    )


@router.post("/predict", response_model=AIPredictResponse)
def predict_screening(
    request: AIPredictRequest,
    organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chunk = get_accessible_sensor_chunk(
        db,
        request.sensor_data_chunk_id,
        current_user,
        organization_id,
    )

    if settings.AI_PIPELINE_MODE == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AI inference is not available. Signal processing, model validation, "
                "and clinical review must be completed before this endpoint is enabled."
            ),
        )

    try:
        from services.ctg_cnn_lstm_adapter import predict_from_payload

        prediction = predict_from_payload(chunk.payload)
    except Exception as exc:  # pragma: no cover - route intentionally fails closed on missing model payload.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AI inference is not available. Signal processing, model validation, "
                "and clinical review must be completed before this endpoint is enabled."
            ),
        ) from exc

    overall_confidence = prediction["overall"]["confidence"]
    risk_score = 0.0 if prediction["overall"]["status"] == "Normal" else min(1.0, max(0.55, overall_confidence))
    classification = "Dalam Batas Normal" if prediction["overall"]["status"] == "Normal" else "Perlu Observasi"
    return AIPredictResponse(
        sensor_data_chunk_id=chunk.id,
        fhr=prediction["fhr"],
        mhr=prediction["mhr"],
        uc=prediction["uc"],
        overall=prediction["overall"],
        risk_score=risk_score,
        classification=classification,
        message="Prediksi CTG CNN-LSTM dari window sensor yang tersedia.",
        is_stub=False,
    )


@router.get("/results", response_model=AIAnalysisResultPage)
def list_patient_analysis_results(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PATIENT_ACCESS_REQUIRED", "message": "Patient access is required"},
        )
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

    query = db.query(AIAnalysisResult).filter(
        AIAnalysisResult.organization_id == patient.organization_id,
        AIAnalysisResult.patient_id == patient.id,
        AIAnalysisResult.visibility == "patient",
    )
    if session_id:
        query = query.filter(AIAnalysisResult.session_id == session_id)
    return build_analysis_page(db, query, limit=limit, offset=offset)


@router.get(
    "/clinician/patients/{patient_id}/results",
    response_model=AIAnalysisResultPage,
)
def list_clinician_analysis_results(
    patient_id: str,
    request: Request,
    session_id: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "patients:read:assigned", "patients:read:facility")
    patient = scoped_patient_or_404(db, principal, patient_id)
    query = db.query(AIAnalysisResult).filter(
        AIAnalysisResult.organization_id == principal.organization_id,
        AIAnalysisResult.patient_id == patient.id,
        AIAnalysisResult.visibility.in_(("clinician", "patient")),
    )
    if session_id:
        query = query.filter(AIAnalysisResult.session_id == session_id)
    response = build_analysis_page(db, query, limit=limit, offset=offset)
    add_access_audit_event(
        db,
        action="clinical.ai_analysis_list.read",
        resource_type="ai_analysis_collection",
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        patient_id=patient.id,
        purpose="care_delivery",
        request=request,
        details={"result_count": len(response.items), "limit": limit, "offset": offset},
    )
    db.commit()
    return response


@router.patch(
    "/clinician/results/{result_id}/review",
    response_model=AIAnalysisReviewResponse,
)
def review_clinician_analysis_result(
    result_id: str,
    review_in: AIAnalysisReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "alerts:update:assigned", "alerts:update:facility")
    result = (
        db.query(AIAnalysisResult)
        .filter(
            AIAnalysisResult.id == result_id,
            AIAnalysisResult.organization_id == principal.organization_id,
            AIAnalysisResult.visibility.in_(("clinician", "patient")),
        )
        .with_for_update(of=AIAnalysisResult)
        .first()
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AI_ANALYSIS_NOT_FOUND", "message": "AI analysis not found"},
        )
    scoped_patient_or_404(db, principal, result.patient_id)

    review = (
        db.query(AIAnalysisReview)
        .filter(AIAnalysisReview.analysis_result_id == result.id)
        .with_for_update(of=AIAnalysisReview)
        .first()
    )
    current_version = review.version if review else 0
    if review_in.expected_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "AI_REVIEW_VERSION_CONFLICT",
                "message": "AI analysis review changed; reload and retry",
                "current_version": current_version,
            },
        )

    now = datetime.now(timezone.utc)
    note = review_in.note.strip() if review_in.note and review_in.note.strip() else None
    if review is None:
        review = AIAnalysisReview(
            organization_id=principal.organization_id,
            patient_id=result.patient_id,
            analysis_result_id=result.id,
            reviewer_membership_id=principal.membership.id,
            reviewer_user_id=principal.user.id,
            decision=review_in.decision.value,
            note=note,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(review)
    else:
        review.reviewer_membership_id = principal.membership.id
        review.reviewer_user_id = principal.user.id
        review.decision = review_in.decision.value
        review.note = note
        review.version += 1
        review.updated_at = now

    db.flush()
    enqueue_realtime_event(
        db,
        organization_id=result.organization_id,
        patient_id=result.patient_id,
        event_type="ai.analysis.updated",
        resource_id=result.id,
        idempotency_key=f"ai.analysis.updated:{result.id}:review:{review.version}",
        payload={
            "quality_status": result.quality_status,
            "screening_status": result.screening_status,
            "visibility": result.visibility,
            "version": review.version,
        },
        occurred_at=now,
    )
    add_access_audit_event(
        db,
        action="clinical.ai_analysis.review",
        resource_type="ai_analysis",
        resource_id=result.id,
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        patient_id=result.patient_id,
        purpose="care_delivery",
        request=request,
        details={"decision": review.decision, "version": review.version},
    )
    db.commit()
    db.refresh(review)
    return review
