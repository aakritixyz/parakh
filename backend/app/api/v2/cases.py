from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.rbac import require_case_access
from app.core.security import Role, hash_password
from app.models.audit import AuditLog
from app.models.case import Case, CaseMembership
from app.models.evidence import Evidence
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter(tags=["v2 case administration"])
CaseRole = Literal["admin", "investigator", "analyst", "prosecutor"]


class MemberInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    role: CaseRole


class CaseInput(BaseModel):
    title: str = Field(min_length=1, max_length=200, pattern=r".*\S.*")
    case_number: str = Field(default="", max_length=120)
    jurisdiction: str = Field(default="", max_length=200)
    offence_type: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=10000)
    lead_investigator: str = Field(min_length=1, max_length=80)
    team_members: list[MemberInput] = Field(default_factory=list, max_length=100)


class AccountInput(MemberInput):
    password: str = Field(min_length=12, max_length=72)


def account(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(422, "Unknown team account; an admin must provision it first")
    return user


def check_grant(actor: User, target: User, role: str):
    allowed = {"admin": {"admin", "investigator", "analyst", "prosecutor"},
               "investigator": {"investigator", "analyst", "prosecutor"},
               "analyst": {"analyst", "prosecutor"}, "prosecutor": {"prosecutor"}}
    if role not in allowed.get(target.role, set()) or (role == "admin" and actor.role != "admin"):
        raise HTTPException(403, "Membership cannot exceed the account's role")


def manage(db: Session, user: User, case_id: int) -> Case:
    require_case_access(db, user, case_id, write=True)
    member = db.scalar(select(CaseMembership).where(CaseMembership.case_id == case_id, CaseMembership.user_id == user.id))
    if user.role != "admin" and (user.role != "investigator" or not member or member.role != "investigator"):
        raise HTTPException(403, "Only case investigators or an admin may manage access")
    case = db.get(Case, case_id)
    assert case is not None
    return case


def case_out(db: Session, case: Case, user: User) -> dict:
    member = db.scalar(select(CaseMembership).where(CaseMembership.case_id == case.id, CaseMembership.user_id == user.id))
    lead = db.get(User, case.lead_investigator_id) if case.lead_investigator_id else None
    last = db.scalar(select(func.max(AuditLog.created_at)).where(AuditLog.case_id == case.id, AuditLog.action != "api.requested"))
    def aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
    effective = "admin" if user.role == "admin" else member.role if member else "prosecutor"
    return {"id": case.id, "title": case.title, "case_number": case.case_number or "", "jurisdiction": case.jurisdiction or "",
            "offence_type": case.offence_type or "", "description": case.description, "status": case.status,
            "lead_investigator": lead.username if lead else None, "created_at": aware(case.created_at),
            "last_activity": max(aware(case.updated_at), aware(last)) if last else aware(case.updated_at),
            "evidence_count": db.scalar(select(func.count(Evidence.id)).where(Evidence.case_id == case.id)) or 0,
            "effective_role": effective, "can_manage": user.role == "admin" or (user.role == "investigator" and effective == "investigator"),
            "can_edit": user.role != "prosecutor" and effective in {"admin", "investigator", "analyst"}}


@router.get("/users")
def users(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin, Role.investigator))):
    return [{"id": u.id, "username": u.username, "role": u.role} for u in db.scalars(select(User).order_by(User.username))]


@router.post("/users", status_code=201)
def create_user(payload: AccountInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.admin))):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(409, "Account already exists")
    if len(payload.password.encode()) > 72:
        raise HTTPException(422, "Password exceeds 72 UTF-8 bytes")
    user = User(username=payload.username, role=payload.role, hashed_password=hash_password(payload.password))
    db.add(user)
    db.flush()
    AuditService(db).log(action="user.created", actor=actor.username, target_type="user", target_id=str(user.id), payload={"username": user.username, "role": user.role})
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.get("/cases")
def list_cases(status: str = "open", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Case).where(Case.status == status)
    if user.role != "admin":
        query = query.where(Case.id.in_(select(CaseMembership.case_id).where(CaseMembership.user_id == user.id)))
    result = [case_out(db, c, user) for c in db.scalars(query.order_by(Case.updated_at.desc(), Case.id.desc()).offset(offset).limit(limit))]
    AuditService(db).log(action="case.listed", actor=user.username, target_type="case_list", payload={"status": status})
    db.commit()
    return result


@router.post("/cases", status_code=201)
def create_case(payload: CaseInput, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin, Role.investigator))):
    lead = account(db, payload.lead_investigator)
    if lead.role not in {"admin", "investigator"}:
        raise HTTPException(422, "The lead must be an investigator or admin")
    members: dict[int, tuple[User, str]] = {user.id: (user, "admin" if user.role == "admin" else "investigator"), lead.id: (lead, "investigator")}
    for member in payload.team_members:
        target = account(db, member.username)
        check_grant(user, target, member.role)
        if target.id in members:
            raise HTTPException(422, "Duplicate team member or lead")
        members[target.id] = (target, member.role)
    case = Case(title=payload.title.strip(), case_number=payload.case_number, jurisdiction=payload.jurisdiction,
                offence_type=payload.offence_type, description=payload.description, created_by=user.id,
                lead_investigator_id=lead.id, status="open")
    db.add(case)
    db.flush()
    AuditService(db).log(action="case.created", actor=user.username, case_id=case.id, target_type="case", target_id=str(case.id), payload={"title": case.title, "case_number": case.case_number, "lead": lead.username})
    for target, role in members.values():
        db.add(CaseMembership(case_id=case.id, user_id=target.id, role=role, granted_by=user.id))
        AuditService(db).log(action="case.member_added", actor=user.username, case_id=case.id, target_type="user", target_id=str(target.id), payload={"username": target.username, "role": role})
    db.commit()
    return case_out(db, case, user)


@router.get("/cases/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    case = db.get(Case, case_id)
    assert case is not None
    return case_out(db, case, user)


@router.patch("/cases/{case_id}")
def update_case(case_id: int, payload: CaseInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = manage(db, user, case_id)
    if payload.team_members:
        raise HTTPException(422, "Use membership endpoints to change the team")
    lead = account(db, payload.lead_investigator)
    if lead.role not in {"admin", "investigator"}:
        raise HTTPException(422, "Invalid lead investigator")
    membership = db.scalar(select(CaseMembership).where(CaseMembership.case_id == case_id, CaseMembership.user_id == lead.id))
    if not membership or membership.role not in {"admin", "investigator"}:
        raise HTTPException(422, "Add the lead as a case investigator first")
    for field in ["title", "case_number", "jurisdiction", "offence_type", "description"]:
        setattr(case, field, getattr(payload, field))
    case.lead_investigator_id = lead.id
    AuditService(db).log(action="case.updated", actor=user.username, case_id=case_id, payload=payload.model_dump(exclude={"team_members"}))
    db.commit()
    return case_out(db, case, user)


@router.get("/cases/{case_id}/members")
def members(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    rows = db.execute(select(CaseMembership, User).join(User, User.id == CaseMembership.user_id).where(CaseMembership.case_id == case_id))
    return [{"user_id": u.id, "username": u.username, "system_role": u.role, "role": m.role} for m, u in rows]


@router.post("/cases/{case_id}/members", status_code=201)
def add_member(case_id: int, payload: MemberInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = manage(db, user, case_id)
    target = account(db, payload.username)
    check_grant(user, target, payload.role)
    if target.id == case.lead_investigator_id and payload.role not in {"admin", "investigator"}:
        raise HTTPException(422, "The lead must retain investigator access")
    item = db.scalar(select(CaseMembership).where(CaseMembership.case_id == case_id, CaseMembership.user_id == target.id))
    action = "case.member_updated" if item else "case.member_added"
    if item:
        item.role = payload.role
        item.granted_by = user.id
    else:
        db.add(CaseMembership(case_id=case_id, user_id=target.id, role=payload.role, granted_by=user.id))
    AuditService(db).log(action=action, actor=user.username, case_id=case_id, target_type="user", target_id=str(target.id), payload=payload.model_dump())
    db.commit()
    return {"username": target.username, "role": payload.role}


@router.delete("/cases/{case_id}/members/{user_id}")
def remove_member(case_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = manage(db, user, case_id)
    if user_id == case.lead_investigator_id:
        raise HTTPException(422, "Assign a different lead before removing this member")
    item = db.scalar(select(CaseMembership).where(CaseMembership.case_id == case_id, CaseMembership.user_id == user_id))
    if not item:
        raise HTTPException(404, "Membership not found")
    db.delete(item)
    AuditService(db).log(action="case.member_removed", actor=user.username, case_id=case_id, target_type="user", target_id=str(user_id))
    db.commit()
    return {"removed": True}


@router.get("/cases/{case_id}/audit")
def audit(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    rows = db.scalars(select(AuditLog).where((AuditLog.case_id == case_id) | ((AuditLog.case_id.is_(None)) & (AuditLog.actor == user.username) & (AuditLog.target_type == "auth_session"))).order_by(AuditLog.id))
    return {"chain_verified": AuditService(db).verify_chain()["valid"], "scope": "case entries and your session entries; global chain verified server-side",
            "entries": [{"id": a.id, "action": a.action, "actor": a.actor, "created_at": a.created_at.replace(tzinfo=UTC) if a.created_at.tzinfo is None else a.created_at, "payload": a.payload, "previous_hash": a.previous_hash, "entry_hash": a.entry_hash} for a in rows]}
