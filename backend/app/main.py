import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.v1 import api_router
from app.api.v2 import api_router as v2_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.errors import install_error_handlers
from app.core.hardening import RequestHardening
from app.core.migrations import require_current_schema
from app.schemas.common import Health


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        require_current_schema(engine)
        yield

    app = FastAPI(
        lifespan=lifespan,
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
    app.add_middleware(RequestHardening)
    install_error_handlers(app)
    app.include_router(api_router)
    app.include_router(v2_router)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

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
    def readyz():
        try:
            require_current_schema(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("select 1")
        except Exception as exc:  # pragma: no cover - defensive readiness guard
            logging.getLogger(__name__).warning("Database readiness check failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": "unavailable or migration required"},
            )
        return {"status": "ready", "database": "ok"}

    return app


app = create_app()
