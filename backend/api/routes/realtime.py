from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.authorization import (
    Principal,
    get_current_staff_principal,
    require_permission,
    scoped_patient_query,
)
from db.database import get_db
from models.patient import Patient
from models.realtime_event import RealtimeEvent
from models.user import User
from schemas.realtime import RealtimeEventPageResponse, RealtimeEventResponse


router = APIRouter()
DEFAULT_RETRY_AFTER_MS = 5_000


def _serialize_event(event: RealtimeEvent) -> RealtimeEventResponse:
    return RealtimeEventResponse(
        cursor=event.cursor,
        event_id=event.id,
        event_type=event.event_type,
        patient_id=event.patient_id,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        occurred_at=event.occurred_at,
        data=event.payload if isinstance(event.payload, dict) else {},
    )


def _build_event_page(
    db: Session,
    *,
    authorized_patient_ids,
    organization_id: str,
    after_cursor: int | None,
    limit: int,
    patient_audience_only: bool = False,
) -> RealtimeEventPageResponse:
    base_query = db.query(RealtimeEvent).filter(
        RealtimeEvent.organization_id == organization_id,
        RealtimeEvent.patient_id.in_(authorized_patient_ids),
        RealtimeEvent.expires_at > datetime.now(timezone.utc),
    )
    if patient_audience_only:
        base_query = base_query.filter(
            or_(
                RealtimeEvent.event_type != "ai.analysis.updated",
                RealtimeEvent.payload["visibility"].as_string() == "patient",
            )
        )
    if after_cursor is None:
        latest = base_query.order_by(RealtimeEvent.cursor.desc()).first()
        return RealtimeEventPageResponse(
            events=[],
            next_cursor=latest.cursor if latest else 0,
            has_more=False,
            retry_after_ms=DEFAULT_RETRY_AFTER_MS,
        )

    rows = (
        base_query.filter(RealtimeEvent.cursor > after_cursor)
        .order_by(RealtimeEvent.cursor.asc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    next_cursor = visible_rows[-1].cursor if visible_rows else after_cursor
    return RealtimeEventPageResponse(
        events=[_serialize_event(event) for event in visible_rows],
        next_cursor=next_cursor,
        has_more=has_more,
        retry_after_ms=DEFAULT_RETRY_AFTER_MS,
    )


@router.get("/patient/events", response_model=RealtimeEventPageResponse)
def list_patient_realtime_events(
    after_cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PATIENT_NOT_FOUND", "message": "Patient record not found"},
        )
    return _build_event_page(
        db,
        authorized_patient_ids=select(Patient.id).where(Patient.id == patient.id),
        organization_id=patient.organization_id,
        after_cursor=after_cursor,
        limit=limit,
        patient_audience_only=True,
    )


@router.get("/clinician/events", response_model=RealtimeEventPageResponse)
def list_clinician_realtime_events(
    after_cursor: int | None = Query(default=None, ge=0),
    patient_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "patients:read:assigned", "patients:read:facility")
    scoped = scoped_patient_query(db, principal)
    if patient_id:
        scoped = scoped.filter(Patient.id == patient_id)
    authorized_patient_ids = scoped.with_entities(Patient.id).subquery()
    return _build_event_page(
        db,
        authorized_patient_ids=select(authorized_patient_ids.c.id),
        organization_id=principal.organization_id,
        after_cursor=after_cursor,
        limit=limit,
    )
