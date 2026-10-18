import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    Role,
    decode_token,
    encode_token,
    hash_password,
    password_needs_upgrade,
    verify_password,
)
from app.models.session import AuthSession
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["v2 sessions"])
COOKIE = "parakh_refresh"


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue(response: Response, user: User, session: AuthSession, minutes: int = 15) -> dict:
    refresh = encode_token(user.username, Role(user.role), "refresh", 7 * 24 * 60, session.id)
    session.refresh_hash = fingerprint(refresh)
    response.set_cookie(COOKIE, refresh, httponly=True, secure=get_settings().is_production,
                        samesite="strict", max_age=7 * 86400, path="/api/v2/auth")
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": encode_token(user.username, Role(user.role), "access", minutes, session.id),
            "token_type": "bearer", "expires_in": minutes * 60,
            "user": {"id": user.id, "username": user.username, "role": user.role}}


@router.post("/login")
def login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        AuditService(db).log(action="auth.sign_in_failed", actor=form.username[:80], target_type="auth_session")
        db.commit()
        raise HTTPException(401, "Sign-in failed. Check your username and password.")
    if password_needs_upgrade(user.hashed_password):
        user.hashed_password = hash_password(form.password)
    return start_session(response, user, db)


def start_session(response: Response, user: User, db: Session, *, legacy: bool = False) -> dict:
    session = AuthSession(id=str(uuid4()), user_id=user.id, refresh_hash="", expires_at=datetime.now(UTC) + timedelta(days=7))
    db.add(session)
    result = issue(response, user, session, get_settings().access_token_expire_minutes if legacy else 15)
    AuditService(db).log(action="auth.signed_in", actor=user.username, target_type="auth_session", target_id=session.id)
    db.commit()
    return result


def cookie_session(request: Request, db: Session) -> tuple[AuthSession, User, str]:
    origin = request.headers.get("origin")
    trusted = {str(request.base_url).rstrip("/"), *get_settings().cors_origin_list}
    if origin and origin not in trusted:
        raise HTTPException(403, "Untrusted session request origin")
    token = request.cookies.get(COOKIE, "")
    try:
        claims = decode_token(token)
        if claims.get("token_use") != "refresh":
            raise ValueError()
        session = db.get(AuthSession, claims.get("sid"))
        if not session or session.revoked_at or session.expires_at <= datetime.now(UTC):
            raise ValueError()
        user = db.get(User, session.user_id)
        if not user or claims.get("sub") != user.username:
            raise ValueError()
        return session, user, token
    except (ValueError, TypeError) as exc:
        raise HTTPException(401, "Session expired. Sign in again.") from exc


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    session, user, token = cookie_session(request, db)
    old = fingerprint(token)
    # Atomic one-time consumption prevents refresh replay across concurrent requests.
    changed = db.execute(update(AuthSession).where(AuthSession.id == session.id,
                         AuthSession.refresh_hash == old, AuthSession.revoked_at.is_(None))
                         .values(refresh_hash=secrets.token_hex(32)).returning(AuthSession.id)).scalar_one_or_none()
    if changed is None:
        session.revoked_at = datetime.now(UTC)
        AuditService(db).log(action="auth.refresh_replay_rejected", actor=user.username, target_type="auth_session", target_id=session.id)
        db.commit()
        raise HTTPException(401, "Refresh token already used. Sign in again.")
    result = issue(response, user, session)
    AuditService(db).log(action="auth.refreshed", actor=user.username, target_type="auth_session", target_id=session.id)
    db.commit()
    return result


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session, user, _ = cookie_session(request, db)
    session.revoked_at = datetime.now(UTC)
    AuditService(db).log(action="auth.signed_out", actor=user.username, target_type="auth_session", target_id=session.id)
    db.commit()
    response.delete_cookie(COOKIE, path="/api/v2/auth")
    return {"signed_out": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}
