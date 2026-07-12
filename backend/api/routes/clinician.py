from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_current_user
from db.database import get_db
from models.notification import Notification
from models.patient import Patient
from models.patient_clinician_assignment import PatientClinicianAssignment
from models.session import MonitoringSession
from models.user import User
from schemas.clinician import (
    AlertAcknowledgeRequest,
    AlertStatusUpdateRequest,
    NotificationResponse,
    NotificationStatus,
    PatientListResponse,
    PatientSummaryResponse,
)

router = APIRouter()


def require_clinician_role(current_user: User) -> User:
    if current_user.role != "clinician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clinician users can access this resource",
        )
    if current_user.must_reset_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password reset required before accessing this resource",
        )
    return current_user


def build_patient_summary(patient: Patient) -> PatientSummaryResponse:
    sorted_sessions = sorted(patient.sessions, key=lambda item: item.start_time, reverse=True)
    active_sessions = [session for session in sorted_sessions if session.status == "active"]
    latest_session = sorted_sessions[0] if sorted_sessions else None

    return PatientSummaryResponse(
        id=patient.id,
        user_id=patient.user_id,
        name=patient.name,
        age=patient.age,
        gestational_age_weeks=patient.gestational_age_weeks,
        latest_session=latest_session,
        active_sessions=active_sessions,
    )


def apply_alert_lifecycle_update(
    alert: Notification,
    next_status: NotificationStatus,
    current_user: User,
    note: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    alert.status = next_status.value

    if next_status == NotificationStatus.open:
        alert.is_acknowledged = False
        alert.acknowledged_at = None
        alert.acknowledged_by_user_id = None
    else:
        if not alert.is_acknowledged:
            alert.is_acknowledged = True
            alert.acknowledged_at = now
        if not alert.acknowledged_by_user_id:
            alert.acknowledged_by_user_id = current_user.id

    if note:
        alert.acknowledgement_note = note.strip() or None


@router.get("/patients", response_model=PatientListResponse)
def list_patients_for_clinician(
    q: str | None = Query(default=None, max_length=120),
    risk: str = Query(default="all", pattern="^(all|alerts|low|medium|high)$"),
    session_status: str = Query(default="all", alias="status", pattern="^(all|active|inactive)$"),
    sort: str = Query(default="recent", pattern="^(recent|created|name|risk)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_clinician_role(current_user)

    query = (
        db.query(Patient)
        .join(PatientClinicianAssignment, PatientClinicianAssignment.patient_id == Patient.id)
        .filter(PatientClinicianAssignment.clinician_user_id == current_user.id)
    )
    if q:
        search_term = q.strip().lower()
        patient_code_term = search_term.removeprefix("fg-")
        query = query.filter(
            or_(
                func.lower(Patient.name).like(f"%{search_term}%"),
                func.lower(Patient.id).like(f"{patient_code_term}%"),
            )
        )

    active_session_exists = (
        db.query(MonitoringSession.id)
        .filter(MonitoringSession.patient_id == Patient.id)
        .filter(MonitoringSession.status == "active")
        .exists()
    )
    high_alert_exists = (
        db.query(Notification.id)
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(MonitoringSession.patient_id == Patient.id)
        .filter(Notification.risk_level == "high")
        .exists()
    )
    medium_alert_exists = (
        db.query(Notification.id)
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(MonitoringSession.patient_id == Patient.id)
        .filter(Notification.risk_level == "medium")
        .exists()
    )
    open_alert_exists = (
        db.query(Notification.id)
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(MonitoringSession.patient_id == Patient.id)
        .filter(Notification.risk_level.in_(("medium", "high")))
        .filter(Notification.is_acknowledged.is_(False))
        .exists()
    )

    if session_status == "active":
        query = query.filter(active_session_exists)
    elif session_status == "inactive":
        query = query.filter(~active_session_exists)

    if risk == "alerts":
        query = query.filter(open_alert_exists)
    elif risk == "high":
        query = query.filter(high_alert_exists)
    elif risk == "medium":
        query = query.filter(medium_alert_exists, ~high_alert_exists)
    elif risk == "low":
        query = query.filter(~high_alert_exists, ~medium_alert_exists)

    total = query.count()
    latest_session_time = (
        db.query(func.max(MonitoringSession.start_time))
        .filter(MonitoringSession.patient_id == Patient.id)
        .scalar_subquery()
    )
    risk_order = case((high_alert_exists, 0), (medium_alert_exists, 1), else_=2)

    if sort == "name":
        query = query.order_by(func.lower(Patient.name).asc(), Patient.created_at.desc())
    elif sort == "risk":
        query = query.order_by(risk_order.asc(), func.coalesce(latest_session_time, Patient.created_at).desc())
    elif sort == "created":
        query = query.order_by(Patient.created_at.desc())
    else:
        query = query.order_by(func.coalesce(latest_session_time, Patient.created_at).desc(), Patient.created_at.desc())

    patients = (
        query.options(joinedload(Patient.sessions).joinedload(MonitoringSession.sensor_summary))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [build_patient_summary(patient) for patient in patients],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/alerts", response_model=list[NotificationResponse])
def list_clinician_alerts(
    risk: str = Query(default="clinical", pattern="^(clinical|all|low|medium|high)$"),
    acknowledged: str = Query(default="all", pattern="^(all|open|acknowledged)$"),
    alert_status: str = Query(
        default="all",
        alias="status",
        pattern="^(all|open|acknowledged|in_review|resolved|false_positive|archived)$",
    ),
    patient_id: str | None = Query(default=None),
    sort: str = Query(default="priority", pattern="^(priority|recent)$"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_clinician_role(current_user)

    query = (
        db.query(Notification)
        .options(joinedload(Notification.session).joinedload(MonitoringSession.patient))
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .join(PatientClinicianAssignment, PatientClinicianAssignment.patient_id == MonitoringSession.patient_id)
        .filter(PatientClinicianAssignment.clinician_user_id == current_user.id)
    )
    if patient_id:
        query = query.filter(MonitoringSession.patient_id == patient_id)
    if risk == "clinical":
        query = query.filter(Notification.risk_level.in_(("medium", "high")))
    elif risk != "all":
        query = query.filter(Notification.risk_level == risk)
    if acknowledged == "open":
        query = query.filter(Notification.is_acknowledged.is_(False))
    elif acknowledged == "acknowledged":
        query = query.filter(Notification.is_acknowledged.is_(True))
    if alert_status != "all":
        query = query.filter(Notification.status == alert_status)

    if sort == "priority":
        query = query.order_by(
            case((Notification.risk_level == "high", 0), (Notification.risk_level == "medium", 1), else_=2),
            Notification.created_at.desc(),
        )
    else:
        query = query.order_by(Notification.created_at.desc())

    return query.offset(offset).limit(limit).all()


@router.post("/alerts/{alert_id}/acknowledge", response_model=NotificationResponse)
def acknowledge_clinician_alert(
    alert_id: str,
    acknowledgement: AlertAcknowledgeRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_clinician_role(current_user)

    alert = (
        db.query(Notification)
        .options(joinedload(Notification.session).joinedload(MonitoringSession.patient))
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .join(PatientClinicianAssignment, PatientClinicianAssignment.patient_id == MonitoringSession.patient_id)
        .filter(Notification.id == alert_id)
        .filter(PatientClinicianAssignment.clinician_user_id == current_user.id)
        .first()
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    apply_alert_lifecycle_update(
        alert,
        NotificationStatus.acknowledged,
        current_user,
        acknowledgement.note if acknowledgement else None,
    )

    db.commit()
    db.refresh(alert)

    return alert


@router.patch("/alerts/{alert_id}/status", response_model=NotificationResponse)
def update_clinician_alert_status(
    alert_id: str,
    status_update: AlertStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_clinician_role(current_user)

    alert = (
        db.query(Notification)
        .options(joinedload(Notification.session).joinedload(MonitoringSession.patient))
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .join(PatientClinicianAssignment, PatientClinicianAssignment.patient_id == MonitoringSession.patient_id)
        .filter(Notification.id == alert_id)
        .filter(PatientClinicianAssignment.clinician_user_id == current_user.id)
        .first()
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    apply_alert_lifecycle_update(alert, status_update.status, current_user, status_update.note)
    db.commit()
    db.refresh(alert)
    return alert
