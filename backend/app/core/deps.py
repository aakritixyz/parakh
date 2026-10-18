from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, decode_access_token
from app.models.session import AuthSession
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if not payload.get("sid"):
        raise HTTPException(status_code=401, detail="Sign in again to establish a revocable session")
    session = db.get(AuthSession, payload["sid"])
    if not session or session.revoked_at or session.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Session expired or revoked")
    user = db.scalar(select(User).where(User.username == username))
    if not user or session.user_id != user.id:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_roles(*roles: Role):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in [role.value for role in roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
