from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.audit import add_access_audit_event
from core.authorization import (
    Principal,
    get_current_staff_principal,
    require_permission,
    scoped_patient_or_404,
)
from core.config import settings
from core.realtime import enqueue_realtime_event
from db.database import get_db
from models.ai_analysis import AIAnalysisResult, AIAnalysisReview
from models.patient import Patient
from models.user import User
from schemas.ai import (
    AIAnalysisResultPage,
    AIAnalysisResultResponse,
    AIAnalysisReviewRequest,
    AIAnalysisReviewResponse,
    AIPatientAvailabilityResponse,
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
