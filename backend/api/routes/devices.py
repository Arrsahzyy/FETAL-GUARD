from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.authorization import Principal, get_current_staff_principal, require_permission
from core.realtime import enqueue_realtime_event
from db.database import get_db
from models.device import Device
from models.device_assignment import DeviceAssignment
from models.patient import Patient
from models.session import MonitoringSession
from models.user import User
from schemas.device import DeviceCreate, DeviceListResponse, DeviceResponse, DeviceUpdate

router = APIRouter()


def require_patient_role(current_user: User) -> None:
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patient users can access their registered devices",
        )


def get_patient_or_404(db: Session, patient_id: str, organization_id: str) -> Patient:
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.organization_id == organization_id,
    ).first()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


def get_device_or_404(db: Session, device_id: str, organization_id: str) -> Device:
    device = (
        db.query(Device)
        .filter(Device.id == device_id, Device.organization_id == organization_id)
        .with_for_update()
        .first()
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return device


def get_active_device_assignment(
    db: Session,
    device_id: str,
    organization_id: str,
    *,
    lock: bool = False,
) -> DeviceAssignment | None:
    query = db.query(DeviceAssignment).filter(
        DeviceAssignment.device_id == device_id,
        DeviceAssignment.organization_id == organization_id,
        DeviceAssignment.ends_at.is_(None),
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def ensure_assignment_cache_consistent(
    device: Device,
    assignment: DeviceAssignment | None,
) -> None:
    assignment_patient_id = assignment.patient_id if assignment else None
    if device.patient_id != assignment_patient_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DEVICE_ASSIGNMENT_CACHE_CONFLICT",
                "message": "Device registry ownership does not match its active assignment",
            },
        )


def ensure_device_page_assignment_consistency(
    db: Session,
    devices: list[Device],
    organization_id: str,
) -> None:
    if not devices:
        return
    device_ids = [device.id for device in devices]
    assignments = (
        db.query(DeviceAssignment)
        .filter(
            DeviceAssignment.organization_id == organization_id,
            DeviceAssignment.device_id.in_(device_ids),
            DeviceAssignment.ends_at.is_(None),
        )
        .all()
    )
    assignment_by_device_id = {assignment.device_id: assignment for assignment in assignments}
    for device in devices:
        ensure_assignment_cache_consistent(device, assignment_by_device_id.get(device.id))


def next_assignment_transition_time(
    active_assignment: DeviceAssignment | None,
) -> datetime:
    now = datetime.now(timezone.utc)
    if active_assignment is None:
        return now
    starts_at = active_assignment.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    else:
        starts_at = starts_at.astimezone(timezone.utc)
    if now <= starts_at:
        return starts_at + timedelta(microseconds=1)
    return now


@router.get("/me", response_model=list[DeviceResponse])
def list_my_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_patient_role(current_user)
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    return (
        db.query(Device)
        .join(
            DeviceAssignment,
            and_(
                DeviceAssignment.device_id == Device.id,
                DeviceAssignment.organization_id == Device.organization_id,
                DeviceAssignment.patient_id == Device.patient_id,
                DeviceAssignment.ends_at.is_(None),
            ),
        )
        .filter(
            Device.organization_id == patient.organization_id,
            DeviceAssignment.patient_id == patient.id,
        )
        .order_by(Device.registered_at.desc())
        .all()
    )


@router.get("", response_model=DeviceListResponse)
def list_devices(
    q: str | None = Query(default=None, max_length=120),
    patient_id: str | None = Query(default=None),
    status_filter: str = Query(
        default="all",
        alias="status",
        pattern="^(all|registered|active|maintenance|retired|lost)$",
    ),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "devices:manage")
    query = db.query(Device).filter(Device.organization_id == principal.organization_id)
    if q:
        search = f"%{q.strip().lower()}%"
        query = query.filter(
            func.lower(Device.device_uid).like(search)
            | func.lower(Device.display_name).like(search)
        )
    if patient_id:
        query = query.join(
            DeviceAssignment,
            and_(
                DeviceAssignment.device_id == Device.id,
                DeviceAssignment.organization_id == Device.organization_id,
                DeviceAssignment.patient_id == Device.patient_id,
                DeviceAssignment.ends_at.is_(None),
            ),
        ).filter(DeviceAssignment.patient_id == patient_id)
    if status_filter != "all":
        query = query.filter(Device.status == status_filter)

    total = query.count()
    items = (
        query.order_by(Device.registered_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    ensure_device_page_assignment_consistency(db, items, principal.organization_id)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    device_in: DeviceCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "devices:manage")
    if device_in.patient_id:
        get_patient_or_404(db, device_in.patient_id, principal.organization_id)

    now = datetime.now(timezone.utc)
    device = Device(
        organization_id=principal.organization_id,
        device_uid=device_in.device_uid,
        patient_id=device_in.patient_id,
        display_name=device_in.display_name,
        hardware_revision=device_in.hardware_revision,
        firmware_version=device_in.firmware_version,
        status=device_in.status.value,
        assigned_at=now if device_in.patient_id else None,
    )
    db.add(device)
    try:
        if device_in.patient_id:
            db.flush()
            db.add(
                DeviceAssignment(
                    organization_id=principal.organization_id,
                    device_id=device.id,
                    patient_id=device_in.patient_id,
                    assigned_by_user_id=principal.user.id,
                    starts_at=now,
                )
            )
            enqueue_realtime_event(
                db,
                organization_id=principal.organization_id,
                patient_id=device_in.patient_id,
                event_type="device.updated",
                resource_id=device.id,
                idempotency_key=f"device.registered:{device.id}",
                payload={"assignment_state": "assigned", "status": device.status},
                occurred_at=now,
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device UID already exists",
        )
    db.refresh(device)
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: str,
    device_in: DeviceUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "devices:manage")
    device = get_device_or_404(db, device_id, principal.organization_id)
    active_assignment = get_active_device_assignment(
        db,
        device.id,
        principal.organization_id,
        lock=True,
    )
    ensure_assignment_cache_consistent(device, active_assignment)
    previous_patient_id = device.patient_id
    update_data = device_in.model_dump(exclude_unset=True)

    active_session = (
        db.query(MonitoringSession.id)
        .filter(
            MonitoringSession.device_id == device.id,
            MonitoringSession.organization_id == principal.organization_id,
            MonitoringSession.status == "active",
        )
        .first()
    )

    if "patient_id" in update_data:
        patient_id = update_data["patient_id"]
        if patient_id:
            get_patient_or_404(db, patient_id, principal.organization_id)
        if patient_id != device.patient_id:
            if active_session is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Device cannot be reassigned while it has an active monitoring session",
                )
            now = next_assignment_transition_time(active_assignment)
            if active_assignment is not None:
                active_assignment.ends_at = now
                active_assignment.ended_by_user_id = principal.user.id
                active_assignment.version = 2
                db.add(active_assignment)
            if patient_id:
                db.add(
                    DeviceAssignment(
                        organization_id=principal.organization_id,
                        device_id=device.id,
                        patient_id=patient_id,
                        assigned_by_user_id=principal.user.id,
                        starts_at=now,
                    )
                )
            device.assigned_at = now if patient_id else None
            device.patient_id = patient_id

    for field in ("display_name", "hardware_revision", "firmware_version"):
        if field in update_data:
            setattr(device, field, update_data[field])

    if "status" in update_data and update_data["status"]:
        next_status = update_data["status"].value
        if active_session is not None and next_status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ACTIVE_SESSION_DEVICE_STATE_CONFLICT",
                    "message": "Complete the active monitoring session before changing device availability",
                },
            )
        device.status = next_status

    db.add(device)
    try:
        event_time = datetime.now(timezone.utc)
        if previous_patient_id and previous_patient_id != device.patient_id:
            enqueue_realtime_event(
                db,
                organization_id=principal.organization_id,
                patient_id=previous_patient_id,
                event_type="device.updated",
                resource_id=device.id,
                idempotency_key=(
                    f"device.unassigned:{device.id}:{event_time.timestamp()}"
                ),
                payload={"assignment_state": "unassigned", "status": device.status},
                occurred_at=event_time,
            )
        if device.patient_id:
            enqueue_realtime_event(
                db,
                organization_id=principal.organization_id,
                patient_id=device.patient_id,
                event_type="device.updated",
                resource_id=device.id,
                idempotency_key=(
                    f"device.updated:{device.id}:{device.patient_id}:{event_time.timestamp()}"
                ),
                payload={"assignment_state": "assigned", "status": device.status},
                occurred_at=event_time,
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DEVICE_ASSIGNMENT_CONFLICT",
                "message": "Device assignment changed concurrently; reload and retry",
            },
        )
    db.refresh(device)
    return device
