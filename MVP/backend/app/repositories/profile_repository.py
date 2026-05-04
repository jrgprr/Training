from sqlalchemy.orm import Session
from app.models.base_models import UserProfile, UserGoal
from app.repositories.base_repository import BaseRepository


class ProfileRepository(BaseRepository):
    def __init__(self, db: Session = None):
        super().__init__(db)

    def get_profile_summary(self) -> dict:
        # Get user profile (assuming single user for MVP)
        profile = self.db.query(UserProfile).first()
        if not profile:
            return {
                "displayName": "Usuario MVP",
                "primarySport": "cycling",
                "activeGoals": [
                    "Reconstruccion aerobica",
                    "Control de peso",
                ],
            }

        # Get active goals
        active_goals = (
            self.db.query(UserGoal)
            .filter(UserGoal.user_id == profile.id, UserGoal.active == True)
            .order_by(UserGoal.priority_order)
            .all()
        )

        goals = [goal.target_description or goal.goal_type for goal in active_goals]

        return {
            "displayName": profile.display_name,
            "primarySport": profile.primary_sport or "cycling",
            "activeGoals": goals,
        }