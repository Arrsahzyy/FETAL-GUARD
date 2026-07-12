from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_admin, get_current_user
from db.database import get_db
from models.device import Device
from models.patient import Patient
from models.user import User
from schemas.device import DeviceCreate, DeviceListResponse, DeviceResponse, DeviceUpdate

router = APIRouter()


def require_patient_role(current_user: User) -> None:
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patient users can access their registered devices",
        )


def get_patient_or_404(db: Session, patient_id: str) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


def get_device_or_404(db: Session, device_id: str) -> Device:
    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return device


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
        .filter(Device.patient_id == patient.id)
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
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    query = db.query(Device)
    if q:
        search = f"%{q.strip().lower()}%"
        query = query.filter(
            func.lower(Device.device_uid).like(search)
            | func.lower(Device.display_name).like(search)
        )
    if patient_id:
        query = query.filter(Device.patient_id == patient_id)
    if status_filter != "all":
        query = query.filter(Device.status == status_filter)

    total = query.count()
    items = (
        query.order_by(Device.registered_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    device_in: DeviceCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    if device_in.patient_id:
        get_patient_or_404(db, device_in.patient_id)

    now = datetime.now(timezone.utc)
    device = Device(
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
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    device = get_device_or_404(db, device_id)
    update_data = device_in.model_dump(exclude_unset=True)

    if "patient_id" in update_data:
        patient_id = update_data["patient_id"]
        if patient_id:
            get_patient_or_404(db, patient_id)
        if patient_id != device.patient_id:
            device.assigned_at = datetime.now(timezone.utc) if patient_id else None
        device.patient_id = patient_id

    for field in ("display_name", "hardware_revision", "firmware_version"):
        if field in update_data:
            setattr(device, field, update_data[field])

    if "status" in update_data and update_data["status"]:
        device.status = update_data["status"].value

    db.add(device)
    db.commit()
    db.refresh(device)
    return device
