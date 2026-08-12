import json
import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from core.authorization import Principal, get_current_staff_principal, require_permission
from core.realtime import enqueue_realtime_event
from core.refresh_tokens import revoke_all_refresh_tokens
from core.security import get_password_hash
from db.database import get_db
from models.admin_audit_log import AdminAuditLog
from models.organization_membership import OrganizationMembership
from models.patient import Patient
from models.patient_clinician_assignment import PatientClinicianAssignment
from models.user import User
from schemas.admin import (
    AdminAuditLogSummary,
    AdminClinicianBulkCreate,
    AdminClinicianBulkProvisionResponse,
    AdminClinicianCreate,
    AdminClinicianListResponse,
    AdminClinicianMembershipRevocationResponse,
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
            detail={
                "code": "IDENTITY_ALREADY_EXISTS",
                "message": "One or more identities already exist and require the approved invitation workflow",
            },
        )


def add_admin_audit_log(
    db: Session,
    *,
    actor: User,
    organization_id: str | None = None,
    action: str,
    target_user: User | None = None,
    target_email: str | None = None,
    include_target_email: bool = True,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            organization_id=organization_id,
            actor_user_id=actor.id,
            action=action,
            target_user_id=target_user.id if target_user else None,
            target_email=(
                target_email
                if target_email is not None
                else target_user.email if target_user is not None and include_target_email else None
            ),
            details=json.dumps(details, sort_keys=True) if details else None,
        )
    )


def get_clinician_membership_or_404(
    db: Session,
    clinician_id: str,
    organization_id: str,
    *,
    allowed_membership_roles: tuple[str, ...] = ("clinician", "supervisor"),
) -> tuple[User, OrganizationMembership]:
    result = (
        db.query(User, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .filter(
            User.id == clinician_id,
            User.role == "clinician",
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role.in_(allowed_membership_roles),
            OrganizationMembership.ended_at.is_(None),
        )
        .with_for_update(of=[User, OrganizationMembership])
        .first()
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinician account not found",
        )
    return result


def get_patient_or_404(db: Session, patient_id: str, organization_id: str) -> Patient:
    patient = (
        db.query(Patient)
        .filter(
            Patient.id == patient_id,
            Patient.organization_id == organization_id,
        )
        .with_for_update(of=Patient)
        .first()
    )
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


def require_single_facility_identity_management(
    db: Session,
    clinician: User,
    organization_id: str,
) -> None:
    """Prevent a facility admin from mutating a cross-facility identity.

    Account activation and credentials are global User properties. Until a
    central identity-administration role exists, a local organization admin is
    allowed to change them only when no other active facility depends on the
    account.
    """

    has_external_membership = (
        db.query(OrganizationMembership.id)
        .filter(
            OrganizationMembership.user_id == clinician.id,
            OrganizationMembership.organization_id != organization_id,
            OrganizationMembership.ended_at.is_(None),
        )
        .first()
        is not None
    )
    if has_external_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CENTRAL_IDENTITY_ADMIN_REQUIRED",
                "message": "This account is active in another facility and requires central identity administration",
            },
        )


def build_admin_patient_summary(patient: Patient) -> AdminPatientSummary:
    return AdminPatientSummary(
        id=patient.id,
        patient_code=patient.patient_code,
        organization_id=patient.organization_id,
        user_id=patient.user_id,
        name=patient.name,
        age=patient.age,
        gestational_age_weeks=patient.gestational_age_weeks,
        created_at=patient.created_at,
        assigned_clinicians=[
            AdminAssignedClinicianSummary(
                assignment_id=assignment.id,
                care_role=assignment.care_role,
                id=assignment.clinician.id,
                email=assignment.clinician.email,
                role=assignment.clinician.role,
                is_active=assignment.clinician.is_active,
                must_reset_password=assignment.clinician.must_reset_password,
                password_changed_at=assignment.clinician.password_changed_at,
                created_at=assignment.clinician.created_at,
            )
            for assignment in patient.clinician_assignments
            if assignment.clinician is not None and assignment.ends_at is None
        ],
    )


def build_assignment_response(assignment: PatientClinicianAssignment) -> AdminPatientAssignmentResponse:
    return AdminPatientAssignmentResponse(
        id=assignment.id,
        organization_id=assignment.organization_id,
        patient_id=assignment.patient_id,
        clinician_id=assignment.clinician_user_id,
        clinician_membership_id=assignment.clinician_membership_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        ended_by_user_id=assignment.ended_by_user_id,
        care_role=assignment.care_role,
        version=assignment.version,
        starts_at=assignment.starts_at,
        ends_at=assignment.ends_at,
        created_at=assignment.created_at,
        patient=build_admin_patient_summary(assignment.patient),
        clinician=assignment.clinician,
    )


def build_admin_clinician_summary(
    clinician: User,
    membership: OrganizationMembership,
) -> dict[str, object]:
    return {
        "id": clinician.id,
        "email": clinician.email,
        "role": clinician.role,
        "is_active": clinician.is_active,
        "must_reset_password": clinician.must_reset_password,
        "password_changed_at": clinician.password_changed_at,
        "created_at": clinician.created_at,
        "membership_id": membership.id,
        "membership_role": membership.role,
    }


@router.get("/clinicians", response_model=AdminClinicianListResponse)
def list_clinicians(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "staff:manage")
    query = (
        db.query(User, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .filter(
            User.role == "clinician",
            OrganizationMembership.organization_id == principal.organization_id,
            OrganizationMembership.role.in_(("clinician", "supervisor")),
            OrganizationMembership.ended_at.is_(None),
        )
    )
    if q:
        search = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(User.email).like(search))

    total = query.count()
    rows = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [build_admin_clinician_summary(clinician, membership) for clinician, membership in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/patients", response_model=AdminPatientListResponse)
def list_patients_for_admin(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "patients:directory:read")
    query = db.query(Patient).filter(Patient.organization_id == principal.organization_id)
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
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "audit:read")
    return (
        db.query(AdminAuditLog)
        .filter(AdminAuditLog.organization_id == principal.organization_id)
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
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "staff:manage")
    current_admin = principal.user
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
        membership = OrganizationMembership(
            organization_id=principal.organization_id,
            user_id=clinician.id,
            role=clinician_in.membership_role,
            granted_by_user_id=current_admin.id,
        )
        db.add(membership)
        add_admin_audit_log(
            db,
            actor=current_admin,
            organization_id=principal.organization_id,
            action="clinician.provisioned",
            target_user=clinician,
            details={
                "provisioning_mode": "single",
                "membership_role": clinician_in.membership_role,
                "temporary_password_generated": clinician_in.temporary_password is None,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "IDENTITY_ALREADY_EXISTS",
                "message": "One or more identities already exist and require the approved invitation workflow",
            },
        )

    db.refresh(clinician)
    return {
        "user": clinician,
        "membership_id": membership.id,
        "temporary_password": temporary_password,
    }


@router.post(
    "/clinicians/bulk",
    response_model=AdminClinicianBulkProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def bulk_provision_clinicians(
    clinicians_in: AdminClinicianBulkCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "staff:manage")
    current_admin = principal.user
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

    memberships_by_user_id: dict[str, OrganizationMembership] = {}
    try:
        db.flush()
        for clinician, _temporary_password in provisioned:
            membership = OrganizationMembership(
                organization_id=principal.organization_id,
                user_id=clinician.id,
                role="clinician",
                granted_by_user_id=current_admin.id,
            )
            db.add(membership)
            memberships_by_user_id[clinician.id] = membership
            add_admin_audit_log(
                db,
                actor=current_admin,
                organization_id=principal.organization_id,
                action="clinician.provisioned",
                target_user=clinician,
                details={"provisioning_mode": "bulk", "temporary_password_generated": True},
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "IDENTITY_ALREADY_EXISTS",
                "message": "One or more identities already exist and require the approved invitation workflow",
            },
        )

    clinicians = []
    for clinician, temporary_password in provisioned:
        db.refresh(clinician)
        clinicians.append(
            {
                "user": clinician,
                "membership_id": memberships_by_user_id[clinician.id].id,
                "temporary_password": temporary_password,
            }
        )

    return {"clinicians": clinicians}


@router.post(
    "/patient-assignments",
    response_model=AdminPatientAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_patient_to_clinician(
    assignment_in: AdminPatientAssignmentCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "assignments:manage")
    current_admin = principal.user
    patient = get_patient_or_404(db, assignment_in.patient_id, principal.organization_id)
    clinician, clinician_membership = get_clinician_membership_or_404(
        db,
        assignment_in.clinician_id,
        principal.organization_id,
        allowed_membership_roles=("clinician",),
    )
    if not clinician.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign an inactive clinician account",
        )

    if assignment_in.care_role == "primary":
        existing_primary = (
            db.query(PatientClinicianAssignment.id)
            .filter(
                PatientClinicianAssignment.patient_id == patient.id,
                PatientClinicianAssignment.organization_id == principal.organization_id,
                PatientClinicianAssignment.care_role == "primary",
                PatientClinicianAssignment.ends_at.is_(None),
            )
            .first()
        )
        if existing_primary:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "PRIMARY_CLINICIAN_ALREADY_ASSIGNED",
                    "message": "The patient already has an active primary clinician",
                },
            )

    existing_assignment = (
        db.query(PatientClinicianAssignment)
        .filter(
            PatientClinicianAssignment.patient_id == patient.id,
            PatientClinicianAssignment.clinician_user_id == clinician.id,
            PatientClinicianAssignment.organization_id == principal.organization_id,
            PatientClinicianAssignment.ends_at.is_(None),
        )
        .first()
    )
    if existing_assignment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CLINICIAN_ASSIGNMENT_ALREADY_ACTIVE",
                "message": "The patient is already assigned to this clinician",
            },
        )

    assignment = PatientClinicianAssignment(
        organization_id=principal.organization_id,
        patient_id=patient.id,
        clinician_membership_id=clinician_membership.id,
        clinician_user_id=clinician.id,
        assigned_by_user_id=current_admin.id,
        care_role=assignment_in.care_role,
        starts_at=datetime.now(timezone.utc),
    )
    db.add(assignment)
    try:
        db.flush()
        add_admin_audit_log(
            db,
            actor=current_admin,
            organization_id=principal.organization_id,
            action="patient.assigned_to_clinician",
            target_user=clinician,
            details={"patient_id": patient.id, "care_role": assignment.care_role},
        )
        enqueue_realtime_event(
            db,
            organization_id=principal.organization_id,
            patient_id=patient.id,
            event_type="care_assignment.updated",
            resource_id=assignment.id,
            idempotency_key=f"care_assignment.started:{assignment.id}",
            payload={"care_role": assignment.care_role, "state": "active"},
            occurred_at=assignment.starts_at,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        if assignment_in.care_role == "primary":
            detail = {
                "code": "PRIMARY_CLINICIAN_ALREADY_ASSIGNED",
                "message": "The patient already has an active primary clinician",
            }
        else:
            detail = {
                "code": "CLINICIAN_ASSIGNMENT_ALREADY_ACTIVE",
                "message": "The patient is already assigned to this clinician",
            }
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
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
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "assignments:manage")
    current_admin = principal.user
    assignment = (
        db.query(PatientClinicianAssignment)
        .options(
            joinedload(PatientClinicianAssignment.patient)
            .joinedload(Patient.clinician_assignments)
            .joinedload(PatientClinicianAssignment.clinician),
            joinedload(PatientClinicianAssignment.clinician),
        )
        .filter(
            PatientClinicianAssignment.id == assignment_id,
            PatientClinicianAssignment.organization_id == principal.organization_id,
            PatientClinicianAssignment.ends_at.is_(None),
        )
        .with_for_update(of=PatientClinicianAssignment)
        .first()
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient-clinician assignment not found",
        )

    add_admin_audit_log(
        db,
        actor=current_admin,
        organization_id=principal.organization_id,
        action="patient.unassigned_from_clinician",
        target_user=assignment.clinician,
        details={"patient_id": assignment.patient_id},
    )
    assignment.ends_at = datetime.now(timezone.utc)
    assignment.ended_by_user_id = current_admin.id
    assignment.version = (assignment.version or 1) + 1
    response = build_assignment_response(assignment)
    enqueue_realtime_event(
        db,
        organization_id=principal.organization_id,
        patient_id=assignment.patient_id,
        event_type="care_assignment.updated",
        resource_id=assignment.id,
        idempotency_key=f"care_assignment.ended:{assignment.id}:{assignment.version}",
        payload={"care_role": assignment.care_role, "state": "ended"},
        occurred_at=assignment.ends_at,
    )
    db.commit()
    return response


@router.delete(
    "/clinician-memberships/{membership_id}",
    response_model=AdminClinicianMembershipRevocationResponse,
)
def revoke_clinician_facility_access(
    membership_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    """End one facility grant without changing the clinician's global identity.

    The immutable membership identifier is the revocation target. This makes a
    repeated DELETE safe and prevents a delayed retry from ending a later,
    newly granted membership for the same clinician (the ABA problem).
    """

    require_permission(principal, "staff:manage")
    current_admin = principal.user
    membership = (
        db.query(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == principal.organization_id,
            OrganizationMembership.role.in_(("clinician", "supervisor")),
            User.role == "clinician",
        )
        .with_for_update(of=OrganizationMembership)
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CLINICIAN_MEMBERSHIP_NOT_FOUND",
                "message": "Clinician facility membership not found",
            },
        )

    was_already_revoked = membership.ended_at is not None
    active_assignments = (
        db.query(PatientClinicianAssignment)
        .filter(
            PatientClinicianAssignment.organization_id == principal.organization_id,
            PatientClinicianAssignment.clinician_membership_id == membership.id,
            PatientClinicianAssignment.clinician_user_id == membership.user_id,
            PatientClinicianAssignment.ends_at.is_(None),
        )
        .order_by(PatientClinicianAssignment.id.asc())
        .with_for_update(of=PatientClinicianAssignment)
        .all()
    )

    revocation_time = datetime.now(timezone.utc)
    if not was_already_revoked:
        membership.ended_at = revocation_time
        membership.ended_by_user_id = current_admin.id

    for assignment in active_assignments:
        assignment_end = revocation_time
        starts_at = assignment.starts_at
        if starts_at is not None:
            comparable_end = assignment_end
            if starts_at.tzinfo is None:
                comparable_end = comparable_end.replace(tzinfo=None)
            if comparable_end <= starts_at:
                assignment_end = starts_at + (datetime.resolution)
        assignment.ends_at = assignment_end
        assignment.ended_by_user_id = current_admin.id
        assignment.version = (assignment.version or 1) + 1
        enqueue_realtime_event(
            db,
            organization_id=principal.organization_id,
            patient_id=assignment.patient_id,
            event_type="care_assignment.updated",
            resource_id=assignment.id,
            idempotency_key=(
                f"care_assignment.ended:{assignment.id}:{assignment.version}"
            ),
            payload={"care_role": assignment.care_role, "state": "ended"},
            occurred_at=assignment.ends_at,
        )

    changed = not was_already_revoked or bool(active_assignments)
    if changed:
        add_admin_audit_log(
            db,
            actor=current_admin,
            organization_id=principal.organization_id,
            action="clinician.facility_access_revoked",
            target_user=membership.user,
            include_target_email=False,
            details={
                "membership_id": membership.id,
                "ended_assignment_count": len(active_assignments),
                "repaired_previously_ended_membership": was_already_revoked,
            },
        )

    response = AdminClinicianMembershipRevocationResponse(
        membership_id=membership.id,
        organization_id=membership.organization_id,
        clinician_id=membership.user_id,
        ended_at=membership.ended_at or revocation_time,
        ended_by_user_id=membership.ended_by_user_id,
        ended_assignment_count=len(active_assignments),
        already_revoked=was_already_revoked,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "FACILITY_ACCESS_REVOCATION_CONFLICT",
                "message": "Facility access changed concurrently; reload and retry the membership operation",
            },
        )
    return response


@router.post("/clinicians/{clinician_id}/deactivate", response_model=AdminUserSummary)
def deactivate_clinician(
    clinician_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "staff:manage")
    current_admin = principal.user
    clinician, _membership = get_clinician_membership_or_404(
        db, clinician_id, principal.organization_id
    )
    require_single_facility_identity_management(db, clinician, principal.organization_id)
    if not clinician.is_active:
        return clinician

    clinician.is_active = False
    clinician.auth_version = (clinician.auth_version or 0) + 1
    revoke_all_refresh_tokens(db, clinician.id, commit=False)
    add_admin_audit_log(
        db,
        actor=current_admin,
        organization_id=principal.organization_id,
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
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "staff:manage")
    current_admin = principal.user
    clinician, _membership = get_clinician_membership_or_404(
        db, clinician_id, principal.organization_id
    )
    require_single_facility_identity_management(db, clinician, principal.organization_id)
    if clinician.is_active:
        return clinician

    clinician.is_active = True
    add_admin_audit_log(
        db,
        actor=current_admin,
        organization_id=principal.organization_id,
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
    principal: Principal = Depends(get_current_staff_principal),
):
    require_permission(principal, "staff:manage")
    current_admin = principal.user
    clinician, membership = get_clinician_membership_or_404(
        db, clinician_id, principal.organization_id
    )
    require_single_facility_identity_management(db, clinician, principal.organization_id)
    temporary_password = (
        reset_in.temporary_password
        if reset_in and reset_in.temporary_password
        else generate_temporary_password()
    )
    clinician.hashed_password = get_password_hash(temporary_password)
    clinician.must_reset_password = True
    clinician.password_changed_at = None
    clinician.auth_version = (clinician.auth_version or 0) + 1
    revoke_all_refresh_tokens(db, clinician.id, commit=False)

    add_admin_audit_log(
        db,
        actor=current_admin,
        organization_id=principal.organization_id,
        action="clinician.password_reset",
        target_user=clinician,
        details={"temporary_password_generated": not (reset_in and reset_in.temporary_password)},
    )
    db.commit()
    db.refresh(clinician)
    return {
        "user": clinician,
        "membership_id": membership.id,
        "temporary_password": temporary_password,
    }
