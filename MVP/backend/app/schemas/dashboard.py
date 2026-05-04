from pydantic import BaseModel


class DashboardTodayResponse(BaseModel):
    date: str
    dayStatus: str
    primaryObjective: str
    pendingFields: list[str]
