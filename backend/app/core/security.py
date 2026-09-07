"""Security utilities: password hashing and JWT creation/decoding."""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from jose.exceptions import JWTError  # re-exported for callers
import bcrypt

from app.core.config import get_settings

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "JWTError",
]


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True when *plain* matches the stored bcrypt *hashed* value."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    subject: str | int | Any,
    extra_claims: dict | None = None,
) -> str:
    """
    Mint a signed JWT.

    Args:
        subject:      Typically the user's DB id (stored as ``sub`` claim).
        extra_claims: Any additional payload fields (e.g. role, username).

    Returns:
        A compact-serialised JWT string.
    """
    cfg = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=cfg.jwt_expire_minutes)
    payload: dict = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT.

    Raises:
        jose.JWTError: if the token is invalid, expired, or tampered with.
    """
    cfg = get_settings()
    return jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
