from fastapi import APIRouter

from app.schemas.week import WeekResponse
from app.services.week_service import get_week_summary

router = APIRouter()


@router.get("/{week_id}", response_model=WeekResponse)
def read_week(week_id: int) -> WeekResponse:
    return WeekResponse(**get_week_summary(week_id))
