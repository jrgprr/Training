from sqlalchemy.orm import Session
from app.models.base_models import WeeklyMetric
from app.repositories.base_repository import BaseRepository


class WeekRepository(BaseRepository):
    def __init__(self, db: Session = None):
        super().__init__(db)

    def get_week_summary(self, week_id: int) -> dict:
        # For MVP, return default if no data
        metric = self.db.query(WeeklyMetric).filter(WeeklyMetric.planned_week_id == week_id).first()
        if not metric:
            return {
                "weekId": week_id,
                "objective": "Repetir semana tipo con control",
                "status": "planned",
                "riskToWatch": "Aumentar demasiado pronto",
            }

        # If data exists, return based on metric
        return {
            "weekId": week_id,
            "objective": f"Week {week_id} metrics",
            "status": "completed" if metric.completion_rate_pct and metric.completion_rate_pct > 80 else "in_progress",
            "riskToWatch": "Monitor consistency" if metric.consistency_label == "low" else "None",
        }