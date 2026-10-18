from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v2.auth import start_session
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.security import (
    Role,
    hash_password,
    password_needs_upgrade,
    verify_password,
)
from app.models.user import User
from app.schemas.core import Token, UserCreate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/bootstrap", response_model=Token)
def bootstrap(payload: UserCreate, response: Response, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))) -> Token:
    if payload.role not in {role.value for role in Role}:
        raise HTTPException(422, "Invalid role")
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(username=payload.username, hashed_password=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.flush()
    AuditService(db).log(action="user.created", actor=_.username, target_type="user", target_id=str(user.id), payload={"username": user.username, "role": user.role})
    result = start_session(response, user, db, legacy=True)
    return Token(access_token=result["access_token"])


@router.post("/token", response_model=Token)
def token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        AuditService(db).log(action="auth.sign_in_failed", actor=form.username[:80], target_type="auth_session")
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if password_needs_upgrade(user.hashed_password):
        user.hashed_password = hash_password(form.password)
    result = start_session(response, user, db, legacy=True)
    return Token(access_token=result["access_token"])
