from pydantic import BaseModel


class ProfileResponse(BaseModel):
    displayName: str
    primarySport: str
    activeGoals: list[str]
