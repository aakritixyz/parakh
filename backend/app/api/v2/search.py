from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.evidence import Event
from app.models.investigation import Bookmark, EventTag, SavedSearch, Tag
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.event_search_service import EventSearchService, SearchError

router = APIRouter(tags=["v2 shared search"])


class SearchInput(BaseModel):
    q: str = Field(default="", max_length=200)
    regex: str = Field(default="", max_length=160)
    phrases: list[str] = Field(default_factory=list, max_length=50)
    time: dict = Field(default_factory=dict)
    facets: dict = Field(default_factory=dict)
    page: dict = Field(default_factory=dict)


class SavedSearchInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    filter_spec: dict


class NoteInput(BaseModel):
    note: str = Field(default="", max_length=2000)


class TagInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.post("/cases/{case_id}/search/events")
def search_events(
    case_id: int,
    payload: SearchInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    try:
        result = EventSearchService(db).search(case_id, payload.model_dump())
        db.commit()  # Persist incremental derived search indexes.
        return result
    except SearchError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/cases/{case_id}/events/{event_id}/detail")
def event_detail(
    case_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    try:
        return EventSearchService(db).detail(case_id, event_id)
    except SearchError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/cases/{case_id}/saved-searches")
def saved_searches(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    return [
        {"id": item.id, "name": item.name, "filter_spec": item.filter_spec}
        for item in db.scalars(
            select(SavedSearch).where(
                SavedSearch.case_id == case_id, SavedSearch.user_id == user.id
            )
        )
    ]


@router.post("/cases/{case_id}/saved-searches", status_code=201)
def save_search(
    case_id: int,
    payload: SavedSearchInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id, write=True)
    item = SavedSearch(
        case_id=case_id,
        user_id=user.id,
        name=payload.name,
        filter_spec=payload.filter_spec,
    )
    db.add(item)
    db.flush()
    AuditService(db).log(
        action="search.saved",
        actor=user.username,
        case_id=case_id,
        target_type="saved_search",
        target_id=str(item.id),
    )
    db.commit()
    return {"id": item.id, "name": item.name, "filter_spec": item.filter_spec}


@router.post("/cases/{case_id}/events/{event_id}/bookmark", status_code=201)
def bookmark_event(
    case_id: int,
    event_id: int,
    payload: NoteInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id, write=True)
    event = db.get(Event, event_id)
    if not event or event.case_id != case_id:
        raise HTTPException(404, "Event not found")
    item = Bookmark(
        case_id=case_id,
        target_type="event",
        target_id=event_id,
        user_id=user.id,
        note=payload.note,
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "event_id": event_id, "note": item.note}


@router.post("/cases/{case_id}/events/{event_id}/tags", status_code=201)
def tag_event(
    case_id: int,
    event_id: int,
    payload: TagInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id, write=True)
    event = db.get(Event, event_id)
    if not event or event.case_id != case_id:
        raise HTTPException(404, "Event not found")
    tag = db.scalar(select(Tag).where(Tag.case_id == case_id, Tag.name == payload.name))
    if tag is None:
        tag = Tag(case_id=case_id, name=payload.name)
        db.add(tag)
        db.flush()
    link = db.scalar(
        select(EventTag).where(EventTag.event_id == event_id, EventTag.tag_id == tag.id)
    )
    if link is None:
        db.add(EventTag(event_id=event_id, tag_id=tag.id))
    db.commit()
    return {"event_id": event_id, "tag": tag.name}
