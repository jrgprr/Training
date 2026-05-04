from fastapi import APIRouter

from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as health_router
from app.api.v1.imports import router as imports_router
from app.api.v1.profile import router as profile_router
from app.api.v1.weeks import router as weeks_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(profile_router, prefix="/profile", tags=["profile"])
router.include_router(weeks_router, prefix="/weeks", tags=["weeks"])
router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
router.include_router(imports_router, prefix="/imports", tags=["imports"])
