from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from db.database import get_db
from models.patient import Patient
from models.user import User
from schemas.patient import PatientCreate, PatientResponse, PatientUpdate

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

    patient = Patient(
        user_id=current_user.id,
        name=patient_in.name,
        age=patient_in.age,
        gestational_age_weeks=patient_in.gestational_age_weeks,
        medical_history=patient_in.medical_history,
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
    for field, value in update_data.items():
        setattr(patient, field, value)

    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/me/alerts", response_model=list)
def list_my_alerts(
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
        .all()
    )
    
    # We can use a generic dict or redefine a schema if needed
    # for simplicity, we return dicts that can be validated
    return alerts

