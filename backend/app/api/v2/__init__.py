from fastapi import APIRouter

from app.api.v2.auth import router as auth_router
from app.api.v2.cases import router as cases_router
from app.api.v2.intake import router as intake_router

api_router = APIRouter(prefix="/api/v2")
api_router.include_router(auth_router)
api_router.include_router(cases_router)
api_router.include_router(intake_router)
