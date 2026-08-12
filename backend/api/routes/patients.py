from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.tenancy import resolve_patient_registration_organization
from db.database import get_db
from models.patient import Patient
from models.user import User
from schemas.patient import (
    PatientCreate,
    PatientNotificationResponse,
    PatientResponse,
    PatientUpdate,
)

router = APIRouter()


def require_patient_role(current_user: User) -> None:
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patient users can access patient profile endpoints",
        )


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient_profile(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_patient_role(current_user)

    existing_profile = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient profile already exists for this user",
        )

    organization = resolve_patient_registration_organization(db)
    patient = Patient(
        user_id=current_user.id,
        organization_id=organization.id,
        **patient_in.model_dump(),
    )
    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient profile already exists for this user",
        )
    db.refresh(patient)
    return patient


@router.get("/me", response_model=PatientResponse)
def read_my_patient_profile(
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
    return patient


@router.patch("/me", response_model=PatientResponse)
def update_my_patient_profile(
    patient_in: PatientUpdate,
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

    update_data = patient_in.model_dump(exclude_unset=True)
    non_nullable_fields = {"name", "age", "gestational_age_weeks"}
    if any(field in update_data and update_data[field] is None for field in non_nullable_fields):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Name, age, and gestational age cannot be null",
        )

    merged_profile = {
        field_name: getattr(patient, field_name)
        for field_name in PatientUpdate.model_fields
    }
    merged_profile.update(update_data)
    try:
        PatientUpdate.model_validate(merged_profile)
    except ValidationError as validation_error:
        detail = [
            {
                "loc": ["body", *error["loc"]],
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in validation_error.errors()
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        )

    for field, value in update_data.items():
        setattr(patient, field, value)
    patient.updated_at = datetime.now(timezone.utc)

    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient profile conflicts with an existing record",
        )
    db.refresh(patient)
    return patient


@router.get("/me/alerts", response_model=list[PatientNotificationResponse])
def list_my_alerts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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
        
    from models.notification import Notification
    from models.session import MonitoringSession

    alerts = (
        db.query(Notification)
        .join(MonitoringSession, Notification.session_id == MonitoringSession.id)
        .filter(MonitoringSession.patient_id == patient.id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return alerts
