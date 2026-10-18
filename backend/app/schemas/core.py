from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.common import ORMModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "investigator"

    @field_validator("password")
    @classmethod
    def password_length(cls, value: str) -> str:
        if not 1 <= len(value.encode("utf-8")) <= 72:
            raise ValueError("Passwords must contain between 1 and 72 UTF-8 bytes.")
        return value


class CaseCreate(BaseModel):
    title: str
    description: str = ""


class CaseOut(ORMModel):
    id: int
    title: str
    description: str
    status: str
    created_at: datetime


class EvidenceOut(ORMModel):
    id: int
    case_id: int
    filename: str
    content_type: str
    source_type: str
    sha256: str
    md5: str
    size_bytes: int
    metadata_json: dict
    created_at: datetime


class EventOut(ORMModel):
    id: int
    case_id: int
    evidence_id: int
    source_type: str
    timestamp_utc: datetime | None
    original_timestamp: str | None
    actor_entities: list
    action: str
    content: str
    location: dict | None
    raw_ref: str
    confidence: float
