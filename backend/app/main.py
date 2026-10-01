import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.errors import install_error_handlers
from app.core.rbac import can_access_case
from app.core.security import decode_access_token
from app.models.evidence import Evidence
from app.models.investigation import Job
from app.models.user import User
from app.schemas.common import Health


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )
    Base.metadata.create_all(bind=engine)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Offline-capable AI-powered indigenous digital forensics investigation framework.",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(api_router)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.middleware("http")
    async def case_rbac_middleware(request: Request, call_next):
        denial = _rbac_denial(request)
        if denial:
            return denial
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return "<h1>Parakh</h1><p>Backend API is running. Open <a href='/api/docs'>OpenAPI docs</a>.</p>"

    @app.get("/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health(name=settings.app_name, status="ok", time=datetime.now(UTC))

    @app.get("/healthz", response_model=Health, tags=["system"])
    def healthz() -> Health:
        return Health(name=settings.app_name, status="ok", time=datetime.now(UTC))

    @app.get("/readyz", tags=["system"])
    def readyz() -> dict:
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("select 1")
        except Exception as exc:  # pragma: no cover - defensive readiness guard
            return {"status": "not_ready", "database": str(exc)}
        return {"status": "ready", "database": "ok"}

    return app


app = create_app()


def _rbac_denial(request: Request):
    path = request.url.path
    if not path.startswith("/api/v1/"):
        return None
    case_id = _case_id_from_path(path)
    evidence_id = _id_after(path, "evidence")
    job_id = _id_after(path, "jobs")
    if case_id is None and evidence_id is None and job_id is None:
        return None
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        payload = decode_access_token(auth.split(" ", 1)[1])
    except ValueError:
        return None
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == payload.get("sub")))
        if not user:
            return None
        resolved_case_id = case_id
        if resolved_case_id is None and evidence_id is not None:
            evidence = db.get(Evidence, evidence_id)
            resolved_case_id = evidence.case_id if evidence else None
        if resolved_case_id is None and job_id is not None:
            job = db.get(Job, job_id)
            resolved_case_id = job.case_id if job else None
        if resolved_case_id is None:
            return None
        write = _is_write_request(request)
        if not can_access_case(db, user, resolved_case_id, write=write):
            from app.core.errors import error_response

            return error_response(403, "case_access_denied", "Case access denied")
    finally:
        db.close()
    return None


def _case_id_from_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[0:3] == ["api", "v1", "cases"]:
        try:
            return int(parts[3])
        except ValueError:
            return None
    return None


def _id_after(path: str, segment: str) -> int | None:
    parts = path.strip("/").split("/")
    if segment not in parts:
        return None
    index = parts.index(segment)
    if len(parts) <= index + 1:
        return None
    try:
        return int(parts[index + 1])
    except ValueError:
        return None


def _is_write_request(request: Request) -> bool:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return False
    read_markers = [
        "/events/search",
        "/facets/",
        "/adjacent",
        "/graph",
        "/geo",
        "/media/search",
        "/dashboard",
        "/communications",
        "/emails",
        "/reconstruction",
        "/assistant",
    ]
    return not any(marker in request.url.path for marker in read_markers)
