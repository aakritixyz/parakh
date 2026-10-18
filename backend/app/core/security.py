import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import bcrypt

try:
    from jose import jwt
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback
    jwt = None

from app.core.config import get_settings


class Role(StrEnum):
    admin = "admin"
    investigator = "investigator"
    analyst = "analyst"
    prosecutor = "prosecutor"


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > 72:
        raise ValueError("Passwords must contain between 1 and 72 UTF-8 bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > 72:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed.encode("ascii"))
    except (ValueError, UnicodeError):
        return False


def create_access_token(subject: str, role: Role) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role.value, "exp": int(expires.timestamp())}
    if jwt:
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"dev.{body}.{sig}"


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    if jwt:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    try:
        prefix, body, sig = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Invalid token") from exc
    if prefix != "dev":
        raise ValueError("Invalid token")
    expected = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid token signature")
    payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise ValueError("Token expired")
    return payload
