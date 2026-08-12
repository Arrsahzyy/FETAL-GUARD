from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Query, Session

from api.dependencies import get_current_user
from core.db_context import set_postgresql_request_context
from db.database import get_db
from models.organization_membership import OrganizationMembership
from models.organization import Organization
from models.patient import Patient
from models.patient_clinician_assignment import PatientClinicianAssignment
from models.user import User


ROLE_PERMISSIONS = MappingProxyType(
    {
        "clinician": frozenset(
            {
                "patients:read:assigned",
                "alerts:read:assigned",
                "alerts:update:assigned",
            }
        ),
        "supervisor": frozenset(
            {
                "patients:read:facility",
                "alerts:read:facility",
                "alerts:update:facility",
            }
        ),
        "org_admin": frozenset(
            {
                "staff:manage",
                "assignments:manage",
                "devices:manage",
                "patients:directory:read",
                "audit:read",
            }
        ),
        "auditor": frozenset({"audit:read"}),
    }
)


@dataclass(frozen=True, slots=True)
class Principal:
    user: User
    membership: OrganizationMembership
    permissions: frozenset[str]

    @property
    def organization_id(self) -> str:
        return self.membership.organization_id

    def has(self, permission: str) -> bool:
        return permission in self.permissions


def resolve_staff_principal(
    db: Session,
    user: User,
    requested_organization_id: str | None = None,
) -> Principal:
    query = (
        db.query(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.ended_at.is_(None),
            Organization.is_active.is_(True),
        )
    )
    if requested_organization_id:
        query = query.filter(OrganizationMembership.organization_id == requested_organization_id)

    memberships = query.order_by(OrganizationMembership.created_at.asc()).limit(2).all()
    if not memberships:
        error_code = "SCOPE_REVOKED" if requested_organization_id else "NO_ACTIVE_FACILITY_MEMBERSHIP"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": error_code, "message": "No active facility access"},
        )
    if requested_organization_id is None and len(memberships) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "FACILITY_CONTEXT_REQUIRED",
                "message": "X-Organization-ID is required for users with multiple facilities",
            },
        )

    membership = memberships[0]
    permissions = ROLE_PERMISSIONS.get(membership.role)
    if permissions is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INVALID_MEMBERSHIP_ROLE", "message": "Membership role is not permitted"},
        )
    set_postgresql_request_context(
        db,
        user_id=user.id,
        membership_id=membership.id,
        organization_id=membership.organization_id,
        membership_role=membership.role,
    )
    return Principal(user=user, membership=membership, permissions=permissions)


def get_current_staff_principal(
    organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Principal:
    if current_user.role not in {"clinician", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "STAFF_ACCESS_REQUIRED", "message": "Staff access is required"},
        )
    if current_user.must_reset_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PASSWORD_RESET_REQUIRED", "message": "Password reset is required"},
        )
    return resolve_staff_principal(db, current_user, organization_id)


def require_permission(principal: Principal, *permissions: str) -> None:
    if any(principal.has(permission) for permission in permissions):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "PERMISSION_DENIED", "message": "The requested action is not permitted"},
    )


def scoped_patient_query(db: Session, principal: Principal) -> Query:
    base = db.query(Patient).filter(Patient.organization_id == principal.organization_id)
    if principal.has("patients:read:facility"):
        return base
    if principal.has("patients:read:assigned"):
        now = datetime.now(timezone.utc)
        return base.join(
            PatientClinicianAssignment,
            PatientClinicianAssignment.patient_id == Patient.id,
        ).filter(
            PatientClinicianAssignment.organization_id == principal.organization_id,
            PatientClinicianAssignment.clinician_membership_id == principal.membership.id,
            PatientClinicianAssignment.clinician_user_id == principal.user.id,
            PatientClinicianAssignment.starts_at <= now,
            PatientClinicianAssignment.ends_at.is_(None),
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "PERMISSION_DENIED", "message": "Patient records are not available"},
    )


def scoped_patient_or_404(db: Session, principal: Principal, patient_id: str) -> Patient:
    patient = scoped_patient_query(db, principal).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PATIENT_NOT_FOUND", "message": "Patient record not found"},
        )
    return patient
