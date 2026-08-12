from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_current_user
from core.authorization import ROLE_PERMISSIONS
from db.database import get_db
from models.organization_membership import OrganizationMembership
from models.organization import Organization
from models.user import User
from schemas.organization import OrganizationMembershipListResponse


router = APIRouter()


@router.get("/me", response_model=OrganizationMembershipListResponse)
def list_my_organization_memberships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"clinician", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "STAFF_ACCESS_REQUIRED", "message": "Staff access is required"},
        )

    memberships = (
        db.query(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .options(joinedload(OrganizationMembership.organization))
        .filter(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.ended_at.is_(None),
            OrganizationMembership.role.in_(tuple(ROLE_PERMISSIONS)),
            Organization.is_active.is_(True),
        )
        .order_by(OrganizationMembership.created_at.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": membership.id,
                "role": membership.role,
                "permissions": sorted(ROLE_PERMISSIONS.get(membership.role, frozenset())),
                "created_at": membership.created_at,
                "organization": membership.organization,
            }
            for membership in memberships
        ]
    }
