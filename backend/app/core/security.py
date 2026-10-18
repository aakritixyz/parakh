from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from app.core.config import get_settings

password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


class Role(StrEnum):
    admin = "admin"
    investigator = "investigator"
    analyst = "analyst"
    prosecutor = "prosecutor"


def hash_password(password: str) -> str:
    if not 1 <= len(password.encode("utf-8")) <= 72:
        raise ValueError("Passwords must contain between 1 and 72 UTF-8 bytes.")
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if not 1 <= len(password.encode("utf-8")) <= 72:
        return False
    try:
        if hashed.startswith("$argon2"):
            return password_hasher.verify(hashed, password)
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (VerificationError, InvalidHashError, ValueError, UnicodeError):
        return False


def password_needs_upgrade(hashed: str) -> bool:
    return not hashed.startswith("$argon2") or password_hasher.check_needs_rehash(hashed)


def create_access_token(subject: str, role: Role, *, session_id: str | None = None) -> str:
    settings = get_settings()
    minutes = 15 if session_id else settings.access_token_expire_minutes
    return encode_token(subject, role, "access", minutes, session_id)


def encode_token(subject: str, role: Role, token_use: str, minutes: int, session_id: str | None) -> str:
    now = datetime.now(UTC)
    return jwt.encode({"sub": subject, "role": role.value, "token_use": token_use,
                       "sid": session_id, "jti": str(uuid4()), "iat": int(now.timestamp()),
                       "exp": int((now + timedelta(minutes=minutes)).timestamp())},
                      get_settings().secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"],
                             options={"require_exp": True, "require_sub": True})
        return payload
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def decode_access_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("token_use", "access") != "access":
        raise ValueError("Not an access token")
    return payload
