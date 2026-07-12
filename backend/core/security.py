from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from core.config import settings

BCRYPT_MAX_PASSWORD_BYTES = 72


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (TypeError, ValueError):
        return False

def get_password_hash(password: str) -> str:
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long for bcrypt")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(subject: str, role: str, expires_delta: timedelta | None = None) -> str:
    expire_delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    expire = now + expire_delta

    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
        "role": role,
        "type": "access",
    }
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.ALGORITHM)
    return encoded_jwt
