from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from models.organization import Organization


# Stable bootstrap boundary for local development, tests, and existing
# single-facility installations. Production deployments must provision this
# organization through migration/configuration before accepting users.
DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_ORGANIZATION_SLUG = "fetal-guard-primary"
DEFAULT_ORGANIZATION_NAME = "FETAL-GUARD Primary Facility"


def get_default_organization(db: Session) -> Organization | None:
    return db.query(Organization).filter(Organization.id == DEFAULT_ORGANIZATION_ID).first()


def ensure_default_organization(db: Session) -> Organization:
    organization = get_default_organization(db)
    if organization is not None:
        return organization

    organization = Organization(
        id=DEFAULT_ORGANIZATION_ID,
        slug=DEFAULT_ORGANIZATION_SLUG,
        name=DEFAULT_ORGANIZATION_NAME,
        is_active=True,
    )
    db.add(organization)
    db.flush()
    return organization


def resolve_patient_registration_organization(db: Session) -> Organization:
    """Resolve a server-controlled tenant for patient self-registration.

    A client-supplied organization identifier is never accepted. Shared
    multi-facility deployments must disable self-registration until a one-time
    admission/invitation workflow is configured; otherwise a patient could be
    silently enrolled into the wrong hospital.
    """

    if settings.PATIENT_SELF_REGISTRATION_MODE == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PATIENT_REGISTRATION_DISABLED",
                "message": "Patient self-registration is not enabled for this deployment",
            },
        )

    configured_organization_id = settings.PATIENT_REGISTRATION_ORGANIZATION_ID
    if configured_organization_id:
        organization = (
            db.query(Organization)
            .filter(
                Organization.id == configured_organization_id,
                Organization.is_active.is_(True),
            )
            .first()
        )
        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "PATIENT_REGISTRATION_FACILITY_UNAVAILABLE",
                    "message": "The configured patient registration facility is unavailable",
                },
            )
        return organization

    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PATIENT_REGISTRATION_NOT_CONFIGURED",
                "message": "Patient registration is not configured",
            },
        )
    return ensure_default_organization(db)
