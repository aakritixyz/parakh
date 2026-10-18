from fastapi import APIRouter

from app.api.v2.auth import router as auth_router
from app.api.v2.cases import router as cases_router
from app.api.v2.correlation import router as correlation_router
from app.api.v2.fraud import router as fraud_router
from app.api.v2.identity import router as identity_router
from app.api.v2.import_report import router as import_report_router
from app.api.v2.intake import router as intake_router
from app.api.v2.integrity import router as integrity_router
from app.api.v2.models import router as models_router
from app.api.v2.money import router as money_router
from app.api.v2.origin import router as origin_router
from app.api.v2.patterns import router as patterns_router
from app.api.v2.search import router as search_router

api_router = APIRouter(prefix="/api/v2")
api_router.include_router(auth_router)
api_router.include_router(cases_router)
api_router.include_router(intake_router)
api_router.include_router(import_report_router)
api_router.include_router(identity_router)
api_router.include_router(search_router)
api_router.include_router(models_router)
api_router.include_router(money_router)
api_router.include_router(patterns_router)
api_router.include_router(integrity_router)
api_router.include_router(origin_router)
api_router.include_router(fraud_router)
api_router.include_router(correlation_router)
