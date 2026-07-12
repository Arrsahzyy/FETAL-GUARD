import json
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_current_admin
from core.security import get_password_hash
from db.database import get_db
from models.admin_audit_log import AdminAuditLog
from models.patient import Patient
from models.patient_clinician_assignment import PatientClinicianAssignment
from models.user import User
from schemas.admin import (
    AdminAuditLogSummary,
    AdminClinicianBulkCreate,
    AdminClinicianBulkProvisionResponse,
    AdminClinicianCreate,
    AdminClinicianListResponse,
    AdminClinicianPasswordReset,
    AdminClinicianProvisionResponse,
    AdminAssignedClinicianSummary,
    AdminPatientAssignmentCreate,
    AdminPatientAssignmentResponse,
    AdminPatientListResponse,
    AdminPatientSummary,
    AdminUserSummary,
)

router = APIRouter()


def generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_emails_are_available(db: Session, emails: list[str]) -> None:
    existing_emails = {
        email for (email,) in db.query(User.email).filter(User.email.in_(emails)).all()
    }
    if existing_emails:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Some emails already exist in the system: {', '.join(sorted(existing_emails))}",
        )


def add_admin_audit_log(
    db: Session,
    *,
    actor: User,
    action: str,
    target_user: User | None = None,
    target_email: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action=action,
            target_user_id=target_user.id if target_user else None,
            target_email=target_email or (target_user.email if target_user else None),
            details=json.dumps(details, sort_keys=True) if details else None,
        )
    )


def get_clinician_or_404(db: Session, clinician_id: str) -> User:
    clinician = db.query(User).filter(User.id == clinician_id, User.role == "clinician").first()
    if clinician is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinician account not found",
        )
    return clinician


def get_patient_or_404(db: Session, patient_id: str) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


def build_admin_patient_summary(patient: Patient) -> AdminPatientSummary:
    return AdminPatientSummary(
        id=patient.id,
        user_id=patient.user_id,
        name=patient.name,
        age=patient.age,
        gestational_age_weeks=patient.gestational_age_weeks,
        created_at=patient.created_at,
        assigned_clinicians=[
            AdminAssignedClinicianSummary(
                assignment_id=assignment.id,
                id=assignment.clinician.id,
                email=assignment.clinician.email,
                role=assignment.clinician.role,
                is_active=assignment.clinician.is_active,
                must_reset_password=assignment.clinician.must_reset_password,
                password_changed_at=assignment.clinician.password_changed_at,
                created_at=assignment.clinician.created_at,
            )
            for assignment in patient.clinician_assignments
            if assignment.clinician is not None
        ],
    )


def build_assignment_response(assignment: PatientClinicianAssignment) -> AdminPatientAssignmentResponse:
    return AdminPatientAssignmentResponse(
        id=assignment.id,
        patient_id=assignment.patient_id,
        clinician_id=assignment.clinician_user_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        created_at=assignment.created_at,
        patient=build_admin_patient_summary(assignment.patient),
        clinician=assignment.clinician,
    )


@router.get("/clinicians", response_model=AdminClinicianListResponse)
def list_clinicians(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    query = db.query(User).filter(User.role == "clinician")
    if q:
        search = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(User.email).like(search))

    total = query.count()
    items = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/patients", response_model=AdminPatientListResponse)
def list_patients_for_admin(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    query = db.query(Patient)
    if q:
        search = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(Patient.name).like(search))

    total = query.count()
    patients = (
        query.options(
            joinedload(Patient.clinician_assignments).joinedload(PatientClinicianAssignment.clinician)
        )
        .order_by(Patient.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [build_admin_patient_summary(patient) for patient in patients],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit-logs", response_model=list[AdminAuditLogSummary])
def list_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    return (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post(
    "/clinicians",
    response_model=AdminClinicianProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def provision_clinician(
    clinician_in: AdminClinicianCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    ensure_emails_are_available(db, [clinician_in.email])

    temporary_password = clinician_in.temporary_password or generate_temporary_password()
    clinician = User(
        email=clinician_in.email,
        hashed_password=get_password_hash(temporary_password),
        role="clinician",
        must_reset_password=True,
    )
    db.add(clinician)
    try:
        db.flush()
        add_admin_audit_log(
            db,
            actor=current_admin,
            action="clinician.provisioned",
            target_user=clinician,
            details={"provisioning_mode": "single", "temporary_password_generated": clinician_in.temporary_password is None},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system",
        )

    db.refresh(clinician)
    return {"user": clinician, "temporary_password": temporary_password}


@router.post(
    "/clinicians/bulk",
    response_model=AdminClinicianBulkProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def bulk_provision_clinicians(
    clinicians_in: AdminClinicianBulkCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin
    emails = [str(email) for email in clinicians_in.emails]
    ensure_emails_are_available(db, emails)

    provisioned = []
    for email in emails:
        temporary_password = generate_temporary_password()
        clinician = User(
            email=email,
            hashed_password=get_password_hash(temporary_password),
            role="clinician",
            must_reset_password=True,
        )
        db.add(clinician)
        provisioned.append((clinician, temporary_password))

    try:
        db.flush()
        for clinician, _temporary_password in provisioned:
            add_admin_audit_log(
                db,
                actor=current_admin,
                action="clinician.provisioned",
                target_user=clinician,
                details={"provisioning_mode": "bulk", "temporary_password_generated": True},
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more clinician emails already exist in the system",
        )

    clinicians = []
    for clinician, temporary_password in provisioned:
        db.refresh(clinician)
        clinicians.append({"user": clinician, "temporary_password": temporary_password})

    return {"clinicians": clinicians}


@router.post(
    "/patient-assignments",
    response_model=AdminPatientAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_patient_to_clinician(
    assignment_in: AdminPatientAssignmentCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    patient = get_patient_or_404(db, assignment_in.patient_id)
    clinician = get_clinician_or_404(db, assignment_in.clinician_id)
    if not clinician.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign an inactive clinician account",
        )

    existing_assignment = (
        db.query(PatientClinicianAssignment)
        .filter(
            PatientClinicianAssignment.patient_id == patient.id,
            PatientClinicianAssignment.clinician_user_id == clinician.id,
        )
        .first()
    )
    if existing_assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient is already assigned to this clinician",
        )

    assignment = PatientClinicianAssignment(
        patient_id=patient.id,
        clinician_user_id=clinician.id,
        assigned_by_user_id=current_admin.id,
    )
    db.add(assignment)
    try:
        db.flush()
        add_admin_audit_log(
            db,
            actor=current_admin,
            action="patient.assigned_to_clinician",
            target_user=clinician,
            details={"patient_id": patient.id, "patient_name": patient.name},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient is already assigned to this clinician",
        )

    assignment = (
        db.query(PatientClinicianAssignment)
        .options(
            joinedload(PatientClinicianAssignment.patient)
            .joinedload(Patient.clinician_assignments)
            .joinedload(PatientClinicianAssignment.clinician),
            joinedload(PatientClinicianAssignment.clinician),
        )
        .filter(PatientClinicianAssignment.id == assignment.id)
        .first()
    )
    return build_assignment_response(assignment)


@router.delete("/patient-assignments/{assignment_id}", response_model=AdminPatientAssignmentResponse)
def unassign_patient_from_clinician(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    assignment = (
        db.query(PatientClinicianAssignment)
        .options(
            joinedload(PatientClinicianAssignment.patient)
            .joinedload(Patient.clinician_assignments)
            .joinedload(PatientClinicianAssignment.clinician),
            joinedload(PatientClinicianAssignment.clinician),
        )
        .filter(PatientClinicianAssignment.id == assignment_id)
        .first()
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient-clinician assignment not found",
        )

    response = build_assignment_response(assignment)
    add_admin_audit_log(
        db,
        actor=current_admin,
        action="patient.unassigned_from_clinician",
        target_user=assignment.clinician,
        details={"patient_id": assignment.patient_id, "patient_name": assignment.patient.name},
    )
    db.delete(assignment)
    db.commit()
    return response


@router.post("/clinicians/{clinician_id}/deactivate", response_model=AdminUserSummary)
def deactivate_clinician(
    clinician_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    clinician = get_clinician_or_404(db, clinician_id)
    if not clinician.is_active:
        return clinician

    clinician.is_active = False
    add_admin_audit_log(
        db,
        actor=current_admin,
        action="clinician.deactivated",
        target_user=clinician,
    )
    db.commit()
    db.refresh(clinician)
    return clinician


@router.post("/clinicians/{clinician_id}/activate", response_model=AdminUserSummary)
def activate_clinician(
    clinician_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    clinician = get_clinician_or_404(db, clinician_id)
    if clinician.is_active:
        return clinician

    clinician.is_active = True
    add_admin_audit_log(
        db,
        actor=current_admin,
        action="clinician.activated",
        target_user=clinician,
    )
    db.commit()
    db.refresh(clinician)
    return clinician


@router.post("/clinicians/{clinician_id}/reset-password", response_model=AdminClinicianProvisionResponse)
def reset_clinician_password(
    clinician_id: str,
    reset_in: AdminClinicianPasswordReset | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    clinician = get_clinician_or_404(db, clinician_id)
    temporary_password = (
        reset_in.temporary_password
        if reset_in and reset_in.temporary_password
        else generate_temporary_password()
    )
    clinician.hashed_password = get_password_hash(temporary_password)
    clinician.must_reset_password = True
    clinician.password_changed_at = None

    add_admin_audit_log(
        db,
        actor=current_admin,
        action="clinician.password_reset",
        target_user=clinician,
        details={"temporary_password_generated": not (reset_in and reset_in.temporary_password)},
    )
    db.commit()
    db.refresh(clinician)
    return {"user": clinician, "temporary_password": temporary_password}
