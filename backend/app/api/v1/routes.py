from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import authorize_request
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.audit import Comment, Lead
from app.models.case import Case, CaseMembership
from app.models.entity import Entity
from app.models.evidence import Event, Evidence
from app.models.investigation import Job
from app.models.user import User
from app.schemas.core import CaseCreate, CaseOut, EventOut, EvidenceOut
from app.services.analysis_service import AnalysisService
from app.services.audit_service import AuditService
from app.services.authenticity_service import AuthenticityService
from app.services.case_service import CaseService
from app.services.evidence_service import EvidenceService
from app.services.intelligence_service import IntelligenceService
from app.services.report_service import ReportService

router = APIRouter(dependencies=[Depends(authorize_request)])


class FilterPayload(BaseModel):
    q: str | None = None
    mode: str = "search"
    advanced: dict | None = None
    time: dict | None = None
    facets: dict | None = None
    group_duplicates: bool = True
    sort: dict | None = None
    page: dict | None = None


@router.post("/cases", response_model=CaseOut, tags=["cases"])
def create_case(payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = CaseService(db).create_case(payload.title, payload.description, user.username)
    db.commit()
    return case


@router.get("/cases", response_model=list[CaseOut], tags=["cases"])
def list_cases(limit: int = 50, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "admin":
        return list(db.scalars(select(Case).offset(offset).limit(limit)))
    permitted_case_ids = select(CaseMembership.case_id).where(CaseMembership.user_id == user.id)
    return list(db.scalars(select(Case).where(Case.id.in_(permitted_case_ids)).offset(offset).limit(limit)))


@router.get("/cases/stats", tags=["cases"])
def case_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return IntelligenceService(db).case_stats()


@router.post("/cases/{case_id}/evidence", response_model=EvidenceOut, tags=["evidence"])
async def upload_evidence(
    case_id: int,
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not db.get(Case, case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    evidence = await EvidenceService(db).ingest(case_id, file, user.username, idempotency_key)
    db.commit()
    return evidence


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceOut], tags=["evidence"])
def list_evidence(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list(db.scalars(select(Evidence).where(Evidence.case_id == case_id)))


@router.get("/cases/{case_id}/events", response_model=list[EventOut], tags=["events"])
def list_events(case_id: int, limit: int = 100, offset: int = 0, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list(db.scalars(select(Event).where(Event.case_id == case_id).offset(offset).limit(limit)))


@router.post("/cases/{case_id}/events/search", tags=["events"])
def event_search(
    case_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).event_search(case_id, payload.model_dump())


@router.post("/cases/{case_id}/facets/{facet}", tags=["events"])
def lazy_facet(
    case_id: int,
    facet: str,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = IntelligenceService(db).event_search(case_id, payload.model_dump())
    return {"facet": facet, "items": search["facets"].get(facet, [])}


@router.post("/cases/{case_id}/events/{event_id}/adjacent", tags=["events"])
def adjacent_events(
    case_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).adjacent_events(case_id, event_id)


@router.get("/evidence/{evidence_id}/integrity", tags=["evidence"])
def verify_evidence(evidence_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return EvidenceService(db).verify_integrity(evidence)


@router.post("/evidence/{evidence_id}/reparse", tags=["evidence"])
def reparse_evidence(evidence_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = EvidenceService(db).reparse(evidence_id, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/evidence/{evidence_id}/authenticity", tags=["authenticity"])
def authenticity(evidence_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return AuthenticityService(db).report(evidence)


@router.post("/cases/{case_id}/entities/extract", tags=["entities"])
def extract_entities(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    created = AnalysisService(db).materialize_entities(case_id)
    db.commit()
    return {"created": len(created)}


@router.get("/cases/{case_id}/entities", tags=["entities"])
def entities(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list(db.scalars(select(Entity).where(Entity.case_id == case_id)))


@router.get("/cases/{case_id}/owners", tags=["persons"])
def owners(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return IntelligenceService(db).owners(case_id)


@router.get("/cases/{case_id}/search", tags=["search"])
def search(case_id: int, q: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AnalysisService(db).search(case_id, q)


@router.get("/cases/{case_id}/anomalies", tags=["anomalies"])
def anomalies(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AnalysisService(db).anomalies(case_id)


@router.get("/cases/{case_id}/fraud", tags=["fraud"])
def fraud(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AnalysisService(db).fraud_rules(case_id)


@router.get("/cases/{case_id}/graph", tags=["graph"])
def graph(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AnalysisService(db).graph(case_id)


@router.post("/cases/{case_id}/graph", tags=["graph"])
def graph_filtered(
    case_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return AnalysisService(db).graph(case_id)


@router.post("/cases/{case_id}/geo", tags=["map"])
def geo(
    case_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).geo(case_id)


@router.post("/cases/{case_id}/geo/track", tags=["map"])
def geo_track(
    case_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).geo(case_id)


@router.post("/cases/{case_id}/media/search", tags=["gallery"])
def media_search(
    case_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).media_search(case_id)


@router.post("/cases/{case_id}/media/search-by-image", tags=["gallery"])
def media_search_by_image(
    case_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = IntelligenceService(db).media_search(case_id)
    return {**result, "mode": "simulated_similarity_stub"}


@router.get("/cases/{case_id}/dashboard", tags=["investigator"])
def dashboard(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return IntelligenceService(db).dashboard(case_id)


@router.post("/cases/{case_id}/dashboard/{owner_id}", tags=["investigator"])
def owner_dashboard(
    case_id: int,
    owner_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).dashboard_owner(case_id, owner_id)


@router.get("/cases/{case_id}/timeline", tags=["timeline"])
def timeline(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AnalysisService(db).timeline(case_id)


@router.post("/cases/{case_id}/reconstruction", tags=["reconstruction"])
def reconstruction(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AnalysisService(db).reconstruction(case_id)


@router.get("/cases/{case_id}/contradictions", tags=["reconstruction"])
def contradictions(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AnalysisService(db).contradictions(case_id)


@router.post("/cases/{case_id}/assistant", tags=["ai"])
def assistant(
    case_id: int,
    question: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).cited_assistant(case_id, question)


@router.get("/cases/{case_id}/osint", tags=["osint"])
def osint(
    case_id: int,
    entity: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).osint_enrichment(case_id, entity)


@router.post("/cases/{case_id}/communications", tags=["communications"])
def communications(
    case_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).communications(case_id)


@router.post("/cases/{case_id}/emails", tags=["emails"])
def emails(
    case_id: int,
    payload: FilterPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).emails(case_id)


@router.post("/cases/{case_id}/leads", tags=["leads"])
def create_lead(case_id: int, title: str, rationale: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    lead = Lead(case_id=case_id, title=title, rationale=rationale, citations=[])
    db.add(lead)
    db.commit()
    return lead


@router.patch("/leads/{lead_id}", tags=["leads"])
def update_lead(lead_id: int, status: str, rejection_reason: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.status = status
    lead.rejection_reason = rejection_reason
    db.commit()
    return lead


@router.post("/cases/{case_id}/comments", tags=["collaboration"])
def comment(case_id: int, target_type: str, target_id: int, body: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = Comment(case_id=case_id, target_type=target_type, target_id=target_id, body=body, author=user.username)
    db.add(item)
    db.commit()
    return item


@router.post("/cases/{case_id}/reports", tags=["reports"])
def report(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = ReportService(db).generate_case_report(case_id)
    db.commit()
    return item


@router.post("/cases/{case_id}/export-bundle", tags=["reports"])
def export_bundle(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = ReportService(db).export_case_bundle(case_id)
    db.commit()
    return item


@router.post("/cases/{case_id}/reports/items", tags=["reports"])
def capture_report_item(
    case_id: int,
    kind: str,
    ref: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    AuditService(db).log(
        action="report.item_captured",
        actor=user.username,
        case_id=case_id,
        target_type="report_item",
        target_id=ref,
        payload={"kind": kind, "snapshot": "structured_view_state"},
    )
    db.commit()
    return {"captured": True, "kind": kind, "ref": ref}


@router.get("/cases/{case_id}/bsa63-draft", tags=["reports"])
def bsa63_draft(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return IntelligenceService(db).bsa63_draft(case_id)


@router.get("/parsers/capabilities", tags=["evidence"])
def parser_capabilities(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return IntelligenceService(db).parser_capabilities()


@router.get("/cases/{case_id}/chain-of-custody", tags=["audit"])
def chain_of_custody(
    case_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).chain_of_custody(case_id)


@router.get("/identifiers", tags=["identifiers"])
def identifiers(
    source: str = "cross_case",
    q: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return IntelligenceService(db).identifier_search(source=source, q=q)


@router.get("/jobs", tags=["jobs"])
def jobs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return IntelligenceService(db).jobs()


@router.get("/jobs/{job_id}", tags=["jobs"])
def job_detail(job_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/audit/verify", tags=["audit"])
def verify_audit(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return AuditService(db).verify_chain()
