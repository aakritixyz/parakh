"""Endpoint-scoped authorization shared by every legacy case API route."""
from typing import cast

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access, require_evidence_access, require_job_access
from app.models.audit import Lead
from app.models.evidence import Event
from app.models.investigation import Owner
from app.models.user import User
from app.services.audit_service import AuditService

READ_POST_SUFFIXES = {"search", "adjacent", "graph", "geo", "track", "search-by-image", "reconstruction", "assistant", "communications", "emails"}


def authorize_request(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    params = request.path_params
    path = request.url.path
    write = request.method not in {"GET", "HEAD", "OPTIONS"}
    if request.method == "POST" and (path.rsplit("/", 1)[-1] in READ_POST_SUFFIXES or "/facets/" in path or "/dashboard/" in path):
        write = False
    if path == "/api/v1/cases" and write and user.role not in {"admin", "investigator"}:
        raise HTTPException(403, "Only investigators and admins may create cases")
    if path in {"/api/v1/cases/stats", "/api/v1/identifiers", "/api/v1/jobs", "/api/v1/audit/verify"} and user.role != "admin":
        raise HTTPException(403, "Cross-case administration requires admin access")
    case_id = params.get("case_id")
    audit_case_id = case_id
    if case_id is not None:
        require_case_access(db, user, int(case_id), write=write)
    if "evidence_id" in params:
        evidence = require_evidence_access(db, user, int(params["evidence_id"]), write=write)
        audit_case_id = evidence.case_id
    if "job_id" in params:
        job = require_job_access(db, user, int(params["job_id"]))
        audit_case_id = job.case_id
    for key, model in [("lead_id", Lead), ("event_id", Event), ("owner_id", Owner)]:
        if key in params:
            item = db.get(model, int(params[key]))
            if not item:
                raise HTTPException(404, "Record not found")
            item_case_id = cast(Lead | Event | Owner, item).case_id
            if case_id is not None and item_case_id != int(case_id):
                raise HTTPException(404, "Record not in this case")
            require_case_access(db, user, item_case_id, write=write)
            audit_case_id = item_case_id
    # Record the request before the handler; do not commit read-handler calculations.
    AuditService(db).log(action="api.requested", actor=user.username, case_id=int(audit_case_id) if audit_case_id else None,
                         target_type="route", target_id=path, payload={"method": request.method})
    db.commit()
