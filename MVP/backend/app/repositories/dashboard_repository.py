from datetime import date
from sqlalchemy.orm import Session
from app.repositories.base_repository import BaseRepository


class DashboardRepository(BaseRepository):
    def __init__(self, db: Session = None):
        super().__init__(db)

    def get_today_dashboard(self) -> dict:
        # For MVP, return default dashboard
        return {
            "date": date.today().isoformat(),
            "dayStatus": "ready",
            "primaryObjective": "Ejecutar el plan del dia",
            "pendingFields": ["checkin", "nutrition"],
        }