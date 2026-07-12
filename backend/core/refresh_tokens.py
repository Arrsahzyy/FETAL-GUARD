from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from core.auth_rate_limit import get_login_client_key
from core.config import settings
from models.auth_refresh_token import AuthRefreshToken
from models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _invalid_refresh_token_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh session is invalid or expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


def hash_refresh_token(raw_token: str) -> str:
    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _token_metadata(request: Request) -> tuple[str, str | None]:
    user_agent = request.headers.get("user-agent")
    if user_agent:
        user_agent = user_agent[:255]
    return get_login_client_key(request), user_agent


def _build_refresh_token(db: Session, user: User, request: Request, now: datetime) -> tuple[str, AuthRefreshToken]:
    raw_token = secrets.token_urlsafe(48)
    client_key, user_agent = _token_metadata(request)
    token = AuthRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        client_key=client_key,
        user_agent=user_agent,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(token)
    return raw_token, token


def issue_refresh_token(db: Session, user: User, request: Request) -> str:
    raw_token, token = _build_refresh_token(db, user, request, _now())
    db.commit()
    db.refresh(token)
    return raw_token


def rotate_refresh_token(db: Session, raw_token: str, request: Request) -> tuple[User, str]:
    now = _now()
    token_hash = hash_refresh_token(raw_token)
    current_token = (
        db.query(AuthRefreshToken)
        .filter(AuthRefreshToken.token_hash == token_hash)
        .first()
    )
    if current_token is None:
        raise _invalid_refresh_token_error()

    if current_token.revoked_at is not None or _aware(current_token.expires_at) <= now:
        raise _invalid_refresh_token_error()

    user = db.query(User).filter(User.id == current_token.user_id).first()
    if user is None:
        raise _invalid_refresh_token_error()
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive",
        )

    next_raw_token, next_token = _build_refresh_token(db, user, request, now)
    db.flush()
    current_token.revoked_at = now
    current_token.replaced_by_token_id = next_token.id
    db.commit()
    db.refresh(user)
    return user, next_raw_token


def revoke_refresh_token(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return

    token = (
        db.query(AuthRefreshToken)
        .filter(AuthRefreshToken.token_hash == hash_refresh_token(raw_token))
        .first()
    )
    if token is None or token.revoked_at is not None:
        return

    token.revoked_at = _now()
    db.commit()
