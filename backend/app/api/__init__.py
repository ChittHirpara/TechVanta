"""API router aggregator – single import point for all sub-routers."""
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.dashboard import router as dashboard_router
from app.api.integrations import router as integrations_router
from app.api.demo import router as demo_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(dashboard_router)
api_router.include_router(integrations_router)
api_router.include_router(demo_router)

