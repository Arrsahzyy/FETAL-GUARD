from datetime import datetime, timedelta, timezone
import hashlib
import hmac

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.config import settings
from models.auth_login_attempt import AuthLoginAttempt


def normalize_login_email(email: str) -> str:
    return email.strip().lower()[:255]


def get_login_client_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for and client_host in settings.TRUSTED_PROXY_IPS:
        client_host = forwarded_for.split(",", 1)[0].strip() or client_host

    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        client_host.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def prune_stale_login_attempts(db: Session, now: datetime | None = None) -> None:
    reference_time = now or datetime.now(timezone.utc)
    retention_minutes = max(
        settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES,
        settings.LOGIN_RATE_LIMIT_LOCKOUT_MINUTES,
    )
    cutoff = reference_time - timedelta(minutes=retention_minutes)
    db.query(AuthLoginAttempt).filter(AuthLoginAttempt.created_at < cutoff).delete(synchronize_session=False)


def _recent_failure_query(db: Session, now: datetime):
    cutoff = now - timedelta(minutes=settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES)
    return (
        db.query(AuthLoginAttempt)
        .filter(AuthLoginAttempt.was_successful.is_(False))
        .filter(AuthLoginAttempt.created_at >= cutoff)
    )


def _lock_login_rate_limit_scope(db: Session, normalized_email: str, client_key: str) -> None:
    """Serialize production checks so parallel failures cannot outrun the limit.

    The locks are transaction scoped and acquired in deterministic order to
    avoid deadlocks when two requests share only an email or only a client.
    SQLite remains suitable for local tests; production is required to use
    PostgreSQL by configuration.
    """

    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    lock_names = sorted((f"client:{client_key}", f"email:{normalized_email}"))
    for lock_name in lock_names:
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_name, 0))"),
            {"lock_name": f"fetal_guard_login:{lock_name}"},
        )


def assert_login_allowed(db: Session, *, email: str, request: Request) -> tuple[str, str]:
    normalized_email = normalize_login_email(email)
    client_key = get_login_client_key(request)
    _lock_login_rate_limit_scope(db, normalized_email, client_key)
    now = datetime.now(timezone.utc)
    prune_stale_login_attempts(db, now)

    failures = _recent_failure_query(db, now)
    client_failures = failures.filter(AuthLoginAttempt.client_key == client_key)
    email_failures = failures.filter(AuthLoginAttempt.email == normalized_email)
    client_blocked = client_failures.count() >= settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
    email_blocked = email_failures.count() >= settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS * 3
    if not client_blocked and not email_blocked:
        return normalized_email, client_key

    blocking_failures = client_failures if client_blocked else email_failures
    oldest_failure = blocking_failures.order_by(AuthLoginAttempt.created_at.asc()).first()
    retry_after_seconds = settings.LOGIN_RATE_LIMIT_LOCKOUT_MINUTES * 60
    if oldest_failure:
        oldest_created_at = oldest_failure.created_at
        if oldest_created_at.tzinfo is None:
            oldest_created_at = oldest_created_at.replace(tzinfo=timezone.utc)
        retry_at = oldest_created_at + timedelta(minutes=settings.LOGIN_RATE_LIMIT_LOCKOUT_MINUTES)
        retry_after_seconds = max(1, int((retry_at - now).total_seconds()))

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed login attempts. Please try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def record_failed_login(db: Session, *, email: str, client_key: str) -> None:
    db.add(
        AuthLoginAttempt(
            email=normalize_login_email(email),
            client_key=client_key,
            was_successful=False,
        )
    )
    db.commit()


def clear_failed_logins(db: Session, *, email: str, client_key: str) -> None:
    normalized_email = normalize_login_email(email)
    db.query(AuthLoginAttempt).filter(
        AuthLoginAttempt.was_successful.is_(False),
        AuthLoginAttempt.email == normalized_email,
        AuthLoginAttempt.client_key == client_key,
    ).delete(synchronize_session=False)
    db.commit()
