from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from core.audit import add_access_audit_event
from core.realtime import enqueue_realtime_event
from core.authorization import (
    Principal,
    get_current_staff_principal,
    require_permission,
    scoped_patient_or_404,
    scoped_patient_query,
)
from db.database import get_db
from models.alert_event import AlertEvent
from models.notification import Notification
from models.patient import Patient
from models.session import MonitoringSession
from schemas.clinician import (
    AlertAcknowledgeRequest,
    AlertStatusUpdateRequest,
    ClinicianStatisticsResponse,
    NotificationResponse,
    NotificationStatus,
    PatientListResponse,
    PatientSummaryResponse,
)

router = APIRouter()


def build_patient_summary(
    patient: Patient,
    latest_session: MonitoringSession | None,
    active_session: MonitoringSession | None,
) -> PatientSummaryResponse:
    return PatientSummaryResponse(
        id=patient.id,
        patient_code=patient.patient_code,
        name=patient.name,
        age=patient.age,
        gestational_age_weeks=patient.gestational_age_weeks,
        latest_session=latest_session,
        active_sessions=[active_session] if active_session else [],
    )


ALLOWED_ALERT_TRANSITIONS = {
    NotificationStatus.open: {
        NotificationStatus.acknowledged,
        NotificationStatus.in_review,
        NotificationStatus.false_positive,
        NotificationStatus.archived,
    },
    NotificationStatus.acknowledged: {
        NotificationStatus.open,
        NotificationStatus.in_review,
        NotificationStatus.resolved,
        NotificationStatus.false_positive,
        NotificationStatus.archived,
    },
    NotificationStatus.in_review: {
        NotificationStatus.open,
        NotificationStatus.resolved,
        NotificationStatus.false_positive,
        NotificationStatus.archived,
    },
    NotificationStatus.resolved: {NotificationStatus.open, NotificationStatus.archived},
    NotificationStatus.false_positive: {NotificationStatus.open, NotificationStatus.archived},
    NotificationStatus.archived: {NotificationStatus.open},
}


@router.get("/statistics", response_model=ClinicianStatisticsResponse)
def read_clinician_statistics(
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "patients:read:assigned", "patients:read:facility")
    authorized_patients = scoped_patient_query(db, principal).with_entities(Patient.id).subquery()
    authorized_ids = select(authorized_patients.c.id)
    active_alert_statuses = ("open", "acknowledged", "in_review")

    total_patients = db.query(func.count()).select_from(authorized_patients).scalar() or 0
    active_monitoring = (
        db.query(func.count(func.distinct(MonitoringSession.patient_id)))
        .filter(
            MonitoringSession.patient_id.in_(authorized_ids),
            MonitoringSession.status == "active",
        )
        .scalar()
        or 0
    )
    high_priority_patients = (
        db.query(func.count(func.distinct(MonitoringSession.patient_id)))
        .join(Notification, Notification.session_id == MonitoringSession.id)
        .filter(
            MonitoringSession.patient_id.in_(authorized_ids),
            Notification.risk_level == "high",
            Notification.status.in_(active_alert_statuses),
        )
        .scalar()
        or 0
    )
    open_alerts = (
        db.query(func.count(Notification.id))
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(
            MonitoringSession.patient_id.in_(authorized_ids),
            Notification.risk_level.in_(("medium", "high")),
            Notification.status.in_(active_alert_statuses),
        )
        .scalar()
        or 0
    )

    response = {
        "total_patients": total_patients,
        "active_monitoring": active_monitoring,
        "high_priority_patients": high_priority_patients,
        "open_alerts": open_alerts,
    }
    add_access_audit_event(
        db,
        action="clinical.statistics.read",
        resource_type="clinical_statistics",
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        purpose="care_delivery",
        request=request,
    )
    db.commit()
    return response


def apply_alert_lifecycle_update(
    alert: Notification,
    next_status: NotificationStatus,
    principal: Principal,
    note: str | None = None,
    expected_version: int = 1,
    request_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    current_status = NotificationStatus(alert.status)
    if expected_version != alert.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ALERT_VERSION_CONFLICT",
                "message": "Alert was changed by another clinician",
                "current_version": alert.version,
            },
        )
    if next_status == current_status:
        return
    if next_status not in ALLOWED_ALERT_TRANSITIONS[current_status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "INVALID_ALERT_TRANSITION",
                "message": f"Alert cannot transition from {current_status.value} to {next_status.value}",
            },
        )

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
            alert.acknowledged_by_user_id = principal.user.id

    if next_status == NotificationStatus.in_review:
        alert.reviewed_by_user_id = principal.user.id
        alert.reviewed_at = now
    if next_status in {NotificationStatus.resolved, NotificationStatus.false_positive}:
        alert.resolved_by_user_id = principal.user.id
        alert.resolved_at = now
    if next_status == NotificationStatus.open:
        alert.reviewed_by_user_id = None
        alert.reviewed_at = None
        alert.resolved_by_user_id = None
        alert.resolved_at = None

    if note:
        alert.acknowledgement_note = note.strip() or None

    alert.version = (alert.version or 1) + 1
    alert.updated_at = now
    alert.events.append(
        AlertEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user.id,
            from_status=current_status.value,
            to_status=next_status.value,
            note=note.strip() if note and note.strip() else None,
            version=alert.version,
            request_id=request_id,
        )
    )


@router.get("/patients", response_model=PatientListResponse)
def list_patients_for_clinician(
    q: str | None = Query(default=None, max_length=120),
    risk: str = Query(default="all", pattern="^(all|alerts|low|medium|high)$"),
    session_status: str = Query(default="all", alias="status", pattern="^(all|active|inactive)$"),
    sort: str = Query(default="recent", pattern="^(recent|created|name|risk)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "patients:read:assigned", "patients:read:facility")
    query = scoped_patient_query(db, principal)
    if q:
        search_term = q.strip().lower()
        patient_code_term = search_term.removeprefix("fg-")
        query = query.filter(
            or_(
                func.lower(Patient.name).like(f"%{search_term}%"),
                func.lower(Patient.patient_code).like(f"{search_term}%"),
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
        .filter(Notification.status.in_(("open", "acknowledged", "in_review")))
        .exists()
    )
    medium_alert_exists = (
        db.query(Notification.id)
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(MonitoringSession.patient_id == Patient.id)
        .filter(Notification.risk_level == "medium")
        .filter(Notification.status.in_(("open", "acknowledged", "in_review")))
        .exists()
    )
    open_alert_exists = (
        db.query(Notification.id)
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(MonitoringSession.patient_id == Patient.id)
        .filter(Notification.risk_level.in_(("medium", "high")))
        .filter(Notification.status.in_(("open", "acknowledged", "in_review")))
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

    patients = query.offset(offset).limit(limit).all()
    patient_ids = [patient.id for patient in patients]
    latest_by_patient: dict[str, MonitoringSession] = {}
    active_by_patient: dict[str, MonitoringSession] = {}
    if patient_ids:
        latest_start = (
            db.query(
                MonitoringSession.patient_id.label("patient_id"),
                func.max(MonitoringSession.start_time).label("latest_start"),
            )
            .filter(MonitoringSession.patient_id.in_(patient_ids))
            .group_by(MonitoringSession.patient_id)
            .subquery()
        )
        latest_sessions = (
            db.query(MonitoringSession)
            .options(joinedload(MonitoringSession.sensor_summary))
            .join(
                latest_start,
                (MonitoringSession.patient_id == latest_start.c.patient_id)
                & (MonitoringSession.start_time == latest_start.c.latest_start),
            )
            .order_by(MonitoringSession.id.desc())
            .all()
        )
        for session in latest_sessions:
            latest_by_patient.setdefault(session.patient_id, session)

        active_sessions = (
            db.query(MonitoringSession)
            .options(joinedload(MonitoringSession.sensor_summary))
            .filter(
                MonitoringSession.patient_id.in_(patient_ids),
                MonitoringSession.status == "active",
            )
            .all()
        )
        active_by_patient = {session.patient_id: session for session in active_sessions}

    response = {
        "items": [
            build_patient_summary(
                patient,
                latest_by_patient.get(patient.id),
                active_by_patient.get(patient.id),
            )
            for patient in patients
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    add_access_audit_event(
        db,
        action="clinical.patient_list.read",
        resource_type="patient_collection",
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        purpose="care_delivery",
        request=request,
        details={"result_count": len(patients), "limit": limit, "offset": offset},
    )
    db.commit()
    return response


@router.get("/patients/{patient_id}", response_model=PatientSummaryResponse)
def read_patient_for_clinician(
    patient_id: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "patients:read:assigned", "patients:read:facility")
    patient = scoped_patient_or_404(db, principal, patient_id)
    latest_session = (
        db.query(MonitoringSession)
        .options(joinedload(MonitoringSession.sensor_summary))
        .filter(MonitoringSession.patient_id == patient.id)
        .order_by(MonitoringSession.start_time.desc(), MonitoringSession.id.desc())
        .first()
    )
    active_session = (
        db.query(MonitoringSession)
        .options(joinedload(MonitoringSession.sensor_summary))
        .filter(
            MonitoringSession.patient_id == patient.id,
            MonitoringSession.status == "active",
        )
        .first()
    )
    response = build_patient_summary(patient, latest_session, active_session)
    add_access_audit_event(
        db,
        action="clinical.patient_detail.read",
        resource_type="patient",
        resource_id=patient.id,
        patient_id=patient.id,
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        purpose="care_delivery",
        request=request,
    )
    db.commit()
    return response


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
    request: Request = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "alerts:read:assigned", "alerts:read:facility")
    authorized_patients = scoped_patient_query(db, principal).with_entities(Patient.id).subquery()

    query = (
        db.query(Notification)
        .options(joinedload(Notification.session).joinedload(MonitoringSession.patient))
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(MonitoringSession.patient_id.in_(select(authorized_patients.c.id)))
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

    alerts = query.offset(offset).limit(limit).all()
    response = [NotificationResponse.model_validate(alert) for alert in alerts]
    add_access_audit_event(
        db,
        action="clinical.alert_list.read",
        resource_type="alert_collection",
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        purpose="care_delivery",
        request=request,
        details={"result_count": len(alerts), "limit": limit, "offset": offset},
    )
    db.commit()
    return response


@router.post("/alerts/{alert_id}/acknowledge", response_model=NotificationResponse)
def acknowledge_clinician_alert(
    alert_id: str,
    acknowledgement: AlertAcknowledgeRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "alerts:update:assigned", "alerts:update:facility")
    authorized_patients = scoped_patient_query(db, principal).with_entities(Patient.id).subquery()

    alert = (
        db.query(Notification)
        .options(joinedload(Notification.session).joinedload(MonitoringSession.patient))
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(Notification.id == alert_id)
        .filter(MonitoringSession.patient_id.in_(select(authorized_patients.c.id)))
        .with_for_update(of=Notification)
        .first()
    )
    if alert is None:
        add_access_audit_event(
            db,
            action="clinical.alert.acknowledge",
            resource_type="alert",
            resource_id=alert_id,
            outcome="denied",
            actor_user_id=principal.user.id,
            actor_membership_id=principal.membership.id,
            organization_id=principal.organization_id,
            purpose="care_delivery",
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ALERT_NOT_FOUND", "message": "Alert not found"},
        )

    previous_version = alert.version
    apply_alert_lifecycle_update(
        alert,
        NotificationStatus.acknowledged,
        principal,
        acknowledgement.note,
        acknowledgement.expected_version,
        getattr(request.state, "request_id", None) if request else None,
    )
    if alert.version != previous_version:
        enqueue_realtime_event(
            db,
            organization_id=alert.organization_id,
            patient_id=alert.session.patient_id,
            event_type="alert.updated",
            resource_id=alert.id,
            idempotency_key=f"alert.updated:{alert.id}:{alert.version}",
            payload={
                "risk_level": alert.risk_level,
                "status": alert.status,
                "version": alert.version,
            },
            occurred_at=alert.updated_at,
        )
    add_access_audit_event(
        db,
        action="clinical.alert.acknowledge",
        resource_type="alert",
        resource_id=alert.id,
        patient_id=alert.session.patient_id,
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        purpose="care_delivery",
        request=request,
        details={"version": alert.version},
    )
    db.commit()
    db.refresh(alert)

    return alert


@router.patch("/alerts/{alert_id}/status", response_model=NotificationResponse)
def update_clinician_alert_status(
    alert_id: str,
    status_update: AlertStatusUpdateRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "alerts:update:assigned", "alerts:update:facility")
    authorized_patients = scoped_patient_query(db, principal).with_entities(Patient.id).subquery()

    alert = (
        db.query(Notification)
        .options(joinedload(Notification.session).joinedload(MonitoringSession.patient))
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(Notification.id == alert_id)
        .filter(MonitoringSession.patient_id.in_(select(authorized_patients.c.id)))
        .with_for_update(of=Notification)
        .first()
    )
    if alert is None:
        add_access_audit_event(
            db,
            action="clinical.alert.status_update",
            resource_type="alert",
            resource_id=alert_id,
            outcome="denied",
            actor_user_id=principal.user.id,
            actor_membership_id=principal.membership.id,
            organization_id=principal.organization_id,
            purpose="care_delivery",
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ALERT_NOT_FOUND", "message": "Alert not found"},
        )

    previous_version = alert.version
    apply_alert_lifecycle_update(
        alert,
        status_update.status,
        principal,
        status_update.note,
        status_update.expected_version,
        getattr(request.state, "request_id", None) if request else None,
    )
    if alert.version != previous_version:
        enqueue_realtime_event(
            db,
            organization_id=alert.organization_id,
            patient_id=alert.session.patient_id,
            event_type="alert.updated",
            resource_id=alert.id,
            idempotency_key=f"alert.updated:{alert.id}:{alert.version}",
            payload={
                "risk_level": alert.risk_level,
                "status": alert.status,
                "version": alert.version,
            },
            occurred_at=alert.updated_at,
        )
    add_access_audit_event(
        db,
        action="clinical.alert.status_update",
        resource_type="alert",
        resource_id=alert.id,
        patient_id=alert.session.patient_id,
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        purpose="care_delivery",
        request=request,
        details={"status": alert.status, "version": alert.version},
    )
    db.commit()
    db.refresh(alert)
    return alert
