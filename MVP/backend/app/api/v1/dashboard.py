from fastapi import APIRouter

from app.schemas.dashboard import DashboardTodayResponse
from app.services.dashboard_service import get_today_dashboard

router = APIRouter()


@router.get("/today", response_model=DashboardTodayResponse)
def read_today_dashboard() -> DashboardTodayResponse:
    return DashboardTodayResponse(**get_today_dashboard())
