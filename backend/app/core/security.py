import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum

try:
    from jose import jwt
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback
    jwt = None

try:
    from passlib.context import CryptContext
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback
    CryptContext = None

from app.core.config import get_settings


class Role(StrEnum):
    admin = "admin"
    investigator = "investigator"
    analyst = "analyst"
    prosecutor = "prosecutor"


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


def hash_password(password: str) -> str:
    if pwd_context:
        return pwd_context.hash(password)
    salt = "parakh-dev"
    return "sha256$" + hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    if pwd_context:
        return pwd_context.verify(password, hashed)
    return hmac.compare_digest(hash_password(password), hashed)


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
