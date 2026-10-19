from __future__ import annotations

import base64
import hashlib
from datetime import UTC
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.board import BoardSnapshot, EvidenceBoard
from app.models.report import Report
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.board_service import (
    BOARD_SCHEMA_VERSION,
    BoardState,
    auto_arrange,
    canonical_hash,
    communities_and_centrality,
    connect_selected,
    empty_board,
    find_gaps,
    neighbours,
    shortest_path,
    time_respecting_path,
)

router = APIRouter(tags=["v2 evidence board"])
BoardAction = Literal[
    "card.added", "card.moved", "card.deleted", "card.restored", "link.drawn",
    "link.updated", "link.deleted", "zone.added", "zone.moved", "zone.deleted",
    "selection.changed", "exhibit.changed", "board.arranged", "board.restored",
]


class BoardUpdate(BaseModel):
    expected_revision: int = Field(ge=0)
    action: BoardAction
    target_id: str = Field(default="", max_length=120)
    detail: dict = Field(default_factory=dict)
    state: BoardState


class SnapshotInput(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")


class SelectionInput(BaseModel):
    selected: list[str] = Field(min_length=1, max_length=100)
    source: str | None = None
    target: str | None = None
    depth: int = Field(default=1, ge=1, le=5)
    time_limit_ms: int = Field(default=1000, ge=50, le=5000)


class BoardExportInput(BaseModel):
    format: Literal["png", "pdf"]
    png_data_url: str = Field(min_length=30, max_length=15_000_000)
    caption: str = Field(default="", max_length=1000)
    receipt_ids: list[str] = Field(default_factory=list, max_length=1000)


def _board(db: Session, case_id: int) -> EvidenceBoard | None:
    return db.scalar(select(EvidenceBoard).where(EvidenceBoard.case_id == case_id))


def _out(board: EvidenceBoard | None, *, can_edit: bool) -> dict:
    state = board.state if board else empty_board()
    return {
        "schema_version": BOARD_SCHEMA_VERSION,
        "revision": board.revision if board else 0,
        "updated_by": board.updated_by if board else None,
        "updated_at": board.updated_at.replace(tzinfo=UTC) if board and board.updated_at and board.updated_at.tzinfo is None else (board.updated_at if board else None),
        "board_hash": canonical_hash(state),
        "can_edit": can_edit,
        "realtime": {"status": "planned", "tier": "T3"},
        "state": state,
    }


@router.get("/cases/{case_id}/board")
def get_board(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    can_edit = user.role != "prosecutor"
    return _out(_board(db, case_id), can_edit=can_edit)


@router.put("/cases/{case_id}/board")
def save_board(case_id: int, payload: BoardUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id, write=True)
    board = _board(db, case_id)
    revision = board.revision if board else 0
    if payload.expected_revision != revision:
        raise HTTPException(409, f"Board changed since revision {payload.expected_revision}; reload revision {revision}")
    state = payload.state.model_dump(mode="json")
    if board is None:
        board = EvidenceBoard(case_id=case_id, schema_version=BOARD_SCHEMA_VERSION, revision=1, state=state, updated_by=user.username)
        db.add(board)
    else:
        board.state = state
        board.revision += 1
        board.updated_by = user.username
    db.flush()
    board_hash = canonical_hash(state)
    AuditService(db).log(
        action=f"board.{payload.action}", actor=user.username, case_id=case_id,
        target_type="evidence_board", target_id=payload.target_id,
        payload={"revision": board.revision, "board_hash": board_hash, **payload.detail},
    )
    db.commit()
    db.refresh(board)
    return _out(board, can_edit=True)


@router.get("/cases/{case_id}/board/snapshots")
def list_snapshots(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    board = _board(db, case_id)
    if not board:
        return []
    rows = db.scalars(select(BoardSnapshot).where(BoardSnapshot.board_id == board.id).order_by(BoardSnapshot.created_at, BoardSnapshot.id))
    return [{"id": item.id, "name": item.name, "revision": item.revision, "board_hash": item.board_hash,
             "created_by": item.created_by, "created_at": item.created_at} for item in rows]


@router.post("/cases/{case_id}/board/snapshots", status_code=201)
def create_snapshot(case_id: int, payload: SnapshotInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id, write=True)
    board = _board(db, case_id)
    if not board:
        raise HTTPException(422, "Save the board before creating a snapshot")
    if db.scalar(select(BoardSnapshot).where(BoardSnapshot.board_id == board.id, BoardSnapshot.name == payload.name.strip())):
        raise HTTPException(409, "A snapshot with this name already exists")
    digest = canonical_hash(board.state)
    snapshot = BoardSnapshot(board_id=board.id, name=payload.name.strip(), board_hash=digest, state=board.state,
                             revision=board.revision, created_by=user.username)
    db.add(snapshot)
    db.flush()
    AuditService(db).log(action="board.snapshot_saved", actor=user.username, case_id=case_id,
                         target_type="board_snapshot", target_id=str(snapshot.id),
                         payload={"name": snapshot.name, "revision": board.revision, "board_hash": digest})
    db.commit()
    return {"id": snapshot.id, "name": snapshot.name, "revision": snapshot.revision, "board_hash": digest, "created_by": snapshot.created_by}


@router.get("/cases/{case_id}/board/snapshots/{snapshot_id}")
def get_snapshot(case_id: int, snapshot_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    board = _board(db, case_id)
    item = db.get(BoardSnapshot, snapshot_id)
    if not board or not item or item.board_id != board.id:
        raise HTTPException(404, "Board snapshot not found")
    return {"id": item.id, "name": item.name, "revision": item.revision, "board_hash": item.board_hash, "state": item.state}


@router.post("/cases/{case_id}/board/analysis/{operation}")
def analyse_board(case_id: int, operation: Literal["connect", "shortest-path", "expand-neighbours", "communities", "time-respecting-path", "find-gaps", "auto-arrange"],
                  payload: SelectionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    board = _board(db, case_id)
    state = BoardState.model_validate(board.state if board else empty_board())
    if operation == "connect":
        result = connect_selected(state, payload.selected, payload.time_limit_ms)
    elif operation == "shortest-path":
        if not payload.source or not payload.target:
            raise HTTPException(422, "Shortest path requires source and target")
        result = shortest_path(state, payload.source, payload.target)
    elif operation == "expand-neighbours":
        result = neighbours(state, payload.selected, payload.depth)
    elif operation == "communities":
        result = communities_and_centrality(state)
    elif operation == "time-respecting-path":
        if not payload.source or not payload.target:
            raise HTTPException(422, "Time-respecting path requires source and target")
        result = time_respecting_path(state, payload.source, payload.target)
    elif operation == "find-gaps":
        result = {"leads": find_gaps(state), "notice": "Suggestions are leads, never findings."}
    else:
        result = auto_arrange(state, payload.time_limit_ms)
    AuditService(db).log(action=f"board.analysis.{operation}", actor=user.username, case_id=case_id,
                         target_type="evidence_board", payload={"selected": payload.selected, "result_count": len(result.get("nodes", result.get("leads", []))),
                                                                 "complete": result.get("complete", True), "seed": state.seed, "time_limit_ms": payload.time_limit_ms})
    db.commit()
    return result


def _decode_png(value: str) -> bytes:
    prefix = "data:image/png;base64,"
    if not value.startswith(prefix):
        raise HTTPException(422, "Board export must be a PNG data URL")
    try:
        data = base64.b64decode(value[len(prefix):], validate=True)
    except ValueError as exc:
        raise HTTPException(422, "Invalid PNG data") from exc
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(422, "Invalid PNG signature")
    return data


@router.post("/cases/{case_id}/board/export")
def export_board(case_id: int, payload: BoardExportInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id, write=True)
    board = _board(db, case_id)
    if not board:
        raise HTTPException(422, "Save the board before exporting")
    png = _decode_png(payload.png_data_url)
    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    extension = payload.format
    path = out_dir / f"case-{case_id}-board-{uuid4().hex}.{extension}"
    if payload.format == "png":
        path.write_bytes(png)
    else:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas

        output = canvas.Canvas(str(path), pagesize=landscape(A4))
        width, height = landscape(A4)
        output.setFont("Helvetica-Bold", 13)
        output.drawString(30, height - 30, payload.caption or "Evidence board")
        output.drawImage(ImageReader(BytesIO(png)), 30, 80, width=width - 60, height=height - 130, preserveAspectRatio=True, anchor="c")
        output.setFont("Helvetica", 7)
        receipts = ", ".join(payload.receipt_ids) or "No receipts selected"
        output.drawString(30, 55, f"Receipts: {receipts[:180]}")
        output.drawString(30, 42, f"Board SHA-256: {canonical_hash(board.state)}")
        output.drawString(30, 29, "A line shows a record relationship or hypothesis; it does not prove involvement.")
        output.save()
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    board_hash = canonical_hash(board.state)
    report = Report(case_id=case_id, kind=f"evidence_board_{payload.format}", path=str(path), sha256=digest,
                    metadata_json={"caption": payload.caption, "receipt_ids": payload.receipt_ids, "board_hash": board_hash,
                                   "schema_version": BOARD_SCHEMA_VERSION})
    db.add(report)
    db.flush()
    AuditService(db).log(action="board.exported", actor=user.username, case_id=case_id, target_type="report", target_id=str(report.id),
                         payload={"format": payload.format, "sha256": digest, "board_hash": board_hash,
                                  "receipt_ids": payload.receipt_ids, "caption": payload.caption})
    db.commit()
    return {"filename": path.name, "content_base64": base64.b64encode(data).decode(), "sha256": digest,
            "board_hash": board_hash, "receipts": payload.receipt_ids}
