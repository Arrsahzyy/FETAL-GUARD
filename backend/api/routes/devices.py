from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.audit import add_access_audit_event
from core.authorization import Principal, get_current_staff_principal, require_permission
from core.device_auth import generate_device_secret
from core.device_claim import generate_claim_code, hash_claim_code, verify_claim_code
from core.device_claim_rate_limit import (
    assert_claim_allowed,
    clear_failed_claims,
    record_failed_claim,
)
from core.realtime import enqueue_realtime_event
from db.database import get_db
from models.device import Device
from models.device_assignment import DeviceAssignment
from models.patient import Patient
from models.session import MonitoringSession
from models.user import User
from schemas.device import (
    DeviceClaimCodeResponse,
    DeviceClaimRequest,
    DeviceCreate,
    DeviceListResponse,
    DeviceResponse,
    DeviceSigningKeyResponse,
    DeviceUpdate,
)

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


CLAIMABLE_DEVICE_STATUSES = frozenset({"registered", "active"})


@router.post("/claim", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def claim_device(
    claim_in: DeviceClaimRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bind an unclaimed belt to the calling patient using its printed code.

    The code proves physical possession, which is the property a device UID alone
    cannot establish: UIDs are broadcast in BLE advertising, so without this a
    patient could bind a belt strapped to someone else and send that pregnancy's
    readings into their own record.

    Every failure -- unknown UID, no code provisioned, wrong code -- returns the
    same 404. Distinguishing them would turn this endpoint into an oracle for
    enumerating which device UIDs exist and which are unclaimed.
    """
    require_patient_role(current_user)
    patient = (
        db.query(Patient)
        .filter(Patient.user_id == current_user.id)
        .first()
    )
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complete your patient profile before pairing a device",
        )

    client_key = assert_claim_allowed(db, device_uid=claim_in.device_uid, request=request)

    def reject_unverified() -> None:
        record_failed_claim(
            db,
            device_uid=claim_in.device_uid,
            client_key=client_key,
            patient_id=patient.id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found, or the claim code does not match",
        )

    device = (
        db.query(Device)
        .filter(
            Device.device_uid == claim_in.device_uid,
            Device.organization_id == patient.organization_id,
        )
        .with_for_update()
        .first()
    )
    if device is None or not verify_claim_code(claim_in.claim_code, device.claim_code_hash):
        reject_unverified()

    if device.status not in CLAIMABLE_DEVICE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This device is not available for pairing. Contact your health facility.",
        )

    now = datetime.now(timezone.utc)
    active_assignment = get_active_device_assignment(
        db, device.id, patient.organization_id, lock=True
    )
    if active_assignment is not None:
        if active_assignment.patient_id == patient.id:
            # Re-entering the code for a belt you already hold is a no-op rather
            # than an error, so a retry after a dropped response is harmless.
            clear_failed_claims(db, device_uid=claim_in.device_uid, client_key=client_key)
            db.commit()
            db.refresh(device)
            return device
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This device is already paired to another patient and must be released first.",
        )

    device.patient_id = patient.id
    device.assigned_at = now
    # A belt shipped as 'registered' becomes usable the moment a patient claims it.
    device.status = "active"
    db.add(
        DeviceAssignment(
            organization_id=patient.organization_id,
            device_id=device.id,
            patient_id=patient.id,
            assigned_by_user_id=current_user.id,
            starts_at=next_assignment_transition_time(None),
        )
    )
    clear_failed_claims(db, device_uid=claim_in.device_uid, client_key=client_key)

    add_access_audit_event(
        db,
        action="device.claimed",
        resource_type="device",
        outcome="success",
        actor_user_id=current_user.id,
        organization_id=patient.organization_id,
        patient_id=patient.id,
        resource_id=device.id,
        request=request,
        details={"device_uid": device.device_uid, "self_service": True},
    )
    enqueue_realtime_event(
        db,
        organization_id=patient.organization_id,
        patient_id=patient.id,
        event_type="device.updated",
        resource_id=device.id,
        # Epoch milliseconds, not isoformat: a UTC offset carries a '+', which the
        # idempotency key pattern rejects. A belt may be claimed again after
        # release, so the key has to vary per event rather than per device.
        idempotency_key=f"device.claimed:{device.id}:{int(now.timestamp() * 1000)}",
        payload={"assignment_state": "assigned", "status": device.status},
        occurred_at=now,
    )

    try:
        db.commit()
    except IntegrityError:
        # Two patients racing for the same unclaimed belt: the partial unique
        # index on active assignments lets exactly one win.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This device is already paired to another patient and must be released first.",
        )
    db.refresh(device)
    return device


@router.post("/me/{device_id}/release", response_model=DeviceResponse)
def release_my_device(
    device_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Release a belt the calling patient holds, so it can be claimed again."""
    require_patient_role(current_user)
    patient = (
        db.query(Patient)
        .filter(Patient.user_id == current_user.id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

    device = (
        db.query(Device)
        .filter(
            Device.id == device_id,
            Device.organization_id == patient.organization_id,
        )
        .with_for_update()
        .first()
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    assignment = get_active_device_assignment(db, device.id, patient.organization_id, lock=True)
    if assignment is None or assignment.patient_id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This device is not paired to your account",
        )

    active_session = (
        db.query(MonitoringSession)
        .filter(
            MonitoringSession.device_id == device.id,
            MonitoringSession.organization_id == patient.organization_id,
            MonitoringSession.status == "active",
        )
        .first()
    )
    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finish the active monitoring session before unpairing this device",
        )

    now = datetime.now(timezone.utc)
    assignment.ends_at = next_assignment_transition_time(assignment)
    assignment.ended_by_user_id = current_user.id
    assignment.version = 2
    device.patient_id = None
    device.assigned_at = None

    add_access_audit_event(
        db,
        action="device.released",
        resource_type="device",
        outcome="success",
        actor_user_id=current_user.id,
        organization_id=patient.organization_id,
        patient_id=patient.id,
        resource_id=device.id,
        request=request,
        details={"device_uid": device.device_uid, "self_service": True},
    )
    enqueue_realtime_event(
        db,
        organization_id=patient.organization_id,
        patient_id=patient.id,
        event_type="device.updated",
        resource_id=device.id,
        idempotency_key=f"device.released:{device.id}:{int(now.timestamp() * 1000)}",
        payload={"assignment_state": "unassigned", "status": device.status},
        occurred_at=now,
    )
    db.commit()
    db.refresh(device)
    return device


@router.post(
    "/{device_id}/claim-code",
    response_model=DeviceClaimCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
def provision_device_claim_code(
    device_id: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    """Issue the claim code to print on a device, disclosing it exactly once.

    Issuing a new code invalidates the previous one. Existing pairings are not
    affected -- the code establishes a pairing, it does not maintain one.
    """
    require_permission(principal, "devices:manage")
    device = get_device_or_404(db, device_id, principal.organization_id)

    now = datetime.now(timezone.utc)
    claim_code = generate_claim_code()
    was_rotation = device.claim_code_hash is not None
    device.claim_code_hash = hash_claim_code(claim_code)
    device.claim_code_set_at = now

    add_access_audit_event(
        db,
        action="device.claim_code.rotated" if was_rotation else "device.claim_code.provisioned",
        resource_type="device",
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        patient_id=device.patient_id,
        resource_id=device.id,
        request=request,
        details={"device_uid": device.device_uid, "rotated": was_rotation},
    )
    db.commit()
    db.refresh(device)

    return DeviceClaimCodeResponse(
        device_id=device.id,
        device_uid=device.device_uid,
        claim_code=claim_code,
        claim_code_set_at=device.claim_code_set_at,
    )


@router.post(
    "/{device_id}/signing-key",
    response_model=DeviceSigningKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def provision_device_signing_key(
    device_id: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    """Issue a new packet signing key and disclose it exactly once.

    Rotating a key immediately invalidates telemetry signed with the previous one,
    so the device must be reflashed before it can upload again. Rotation during an
    active session is refused rather than silently cutting that session off.
    """
    require_permission(principal, "devices:manage")
    device = get_device_or_404(db, device_id, principal.organization_id)

    active_session = (
        db.query(MonitoringSession)
        .filter(
            MonitoringSession.device_id == device.id,
            MonitoringSession.organization_id == principal.organization_id,
            MonitoringSession.status == "active",
        )
        .first()
    )
    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finish the active monitoring session before rotating this device key",
        )

    now = datetime.now(timezone.utc)
    secret = generate_device_secret()
    was_rotation = device.packet_secret is not None
    device.packet_secret = secret
    device.packet_secret_provisioned_at = now

    add_access_audit_event(
        db,
        action="device.signing_key.rotated" if was_rotation else "device.signing_key.provisioned",
        resource_type="device",
        outcome="success",
        actor_user_id=principal.user.id,
        actor_membership_id=principal.membership.id,
        organization_id=principal.organization_id,
        patient_id=device.patient_id,
        resource_id=device.id,
        request=request,
        details={"device_uid": device.device_uid, "rotated": was_rotation},
    )
    db.commit()
    db.refresh(device)

    return DeviceSigningKeyResponse(
        device_id=device.id,
        device_uid=device.device_uid,
        packet_secret=secret,
        packet_secret_provisioned_at=device.packet_secret_provisioned_at,
    )


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
