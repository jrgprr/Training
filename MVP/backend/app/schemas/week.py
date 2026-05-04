from pydantic import BaseModel


class WeekResponse(BaseModel):
    weekId: int
    objective: str
    status: str
    riskToWatch: str
