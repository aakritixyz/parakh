from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Page(BaseModel):
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class Citation(BaseModel):
    evidence_id: int
    event_id: int | None = None


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobStatus(ORMModel):
    id: str
    status: str
    result: dict[str, Any] | None = None


class Health(BaseModel):
    name: str
    status: str
    time: datetime
