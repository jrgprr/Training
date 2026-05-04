from fastapi import APIRouter

from app.schemas.profile import ProfileResponse
from app.services.profile_service import get_profile_summary

router = APIRouter()


@router.get("", response_model=ProfileResponse)
def read_profile() -> ProfileResponse:
    return ProfileResponse(**get_profile_summary())
