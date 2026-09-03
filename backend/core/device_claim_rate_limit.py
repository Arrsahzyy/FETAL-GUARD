"""Throttling for device claim-code guessing.

A claim code is eight Base32 characters, which is far too small to leave
unthrottled: without a limit an authenticated caller could walk the space against
a known device UID and bind someone else's belt to themselves.

Failures are counted along two axes, because each blocks a different attack:

* per caller -- one account grinding codes against many devices,
* per device UID -- many accounts grinding codes against one device.

Successes clear the counters for that pair, so a patient who mistypes twice and
then gets it right is not left locked out.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.auth_rate_limit import get_login_client_key
from core.config import settings
from models.device_claim_attempt import DeviceClaimAttempt


def prune_stale_claim_attempts(db: Session, now: datetime | None = None) -> None:
    reference_time = now or datetime.now(timezone.utc)
    retention_minutes = max(
        settings.DEVICE_CLAIM_RATE_LIMIT_WINDOW_MINUTES,
        settings.DEVICE_CLAIM_RATE_LIMIT_LOCKOUT_MINUTES,
    )
    cutoff = reference_time - timedelta(minutes=retention_minutes)
    db.query(DeviceClaimAttempt).filter(
        DeviceClaimAttempt.created_at < cutoff
    ).delete(synchronize_session=False)


def _lock_claim_scope(db: Session, device_uid: str, client_key: str) -> None:
    """Serialize checks so parallel guesses cannot outrun the limit.

    Locks are transaction scoped and taken in sorted order so two requests that
    share only a device or only a caller cannot deadlock against each other.
    """
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    for lock_name in sorted((f"client:{client_key}", f"device:{device_uid}")):
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_name, 0))"),
            {"lock_name": f"fetal_guard_device_claim:{lock_name}"},
        )


def assert_claim_allowed(
    db: Session,
    *,
    device_uid: str,
    request: Request,
) -> str:
    """Raise 429 when this caller or this device has too many recent failures."""
    client_key = get_login_client_key(request)
    _lock_claim_scope(db, device_uid, client_key)
    now = datetime.now(timezone.utc)
    prune_stale_claim_attempts(db, now)

    cutoff = now - timedelta(minutes=settings.DEVICE_CLAIM_RATE_LIMIT_WINDOW_MINUTES)
    failures = (
        db.query(DeviceClaimAttempt)
        .filter(DeviceClaimAttempt.was_successful.is_(False))
        .filter(DeviceClaimAttempt.created_at >= cutoff)
    )
    client_failures = failures.filter(DeviceClaimAttempt.client_key == client_key)
    device_failures = failures.filter(DeviceClaimAttempt.device_uid == device_uid)

    limit = settings.DEVICE_CLAIM_RATE_LIMIT_MAX_ATTEMPTS
    client_blocked = client_failures.count() >= limit
    device_blocked = device_failures.count() >= limit
    if not client_blocked and not device_blocked:
        return client_key

    blocking = client_failures if client_blocked else device_failures
    oldest = blocking.order_by(DeviceClaimAttempt.created_at.asc()).first()
    retry_after_seconds = settings.DEVICE_CLAIM_RATE_LIMIT_LOCKOUT_MINUTES * 60
    if oldest is not None:
        created_at = oldest.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        retry_at = created_at + timedelta(
            minutes=settings.DEVICE_CLAIM_RATE_LIMIT_LOCKOUT_MINUTES
        )
        retry_after_seconds = max(1, int((retry_at - now).total_seconds()))

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed device claim attempts. Please try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def record_failed_claim(
    db: Session,
    *,
    device_uid: str,
    client_key: str,
    patient_id: str | None,
) -> None:
    db.add(
        DeviceClaimAttempt(
            device_uid=device_uid,
            client_key=client_key,
            patient_id=patient_id,
            was_successful=False,
        )
    )
    db.commit()


def clear_failed_claims(db: Session, *, device_uid: str, client_key: str) -> None:
    db.query(DeviceClaimAttempt).filter(
        DeviceClaimAttempt.was_successful.is_(False),
        DeviceClaimAttempt.device_uid == device_uid,
        DeviceClaimAttempt.client_key == client_key,
    ).delete(synchronize_session=False)
