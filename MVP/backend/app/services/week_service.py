from app.repositories.week_repository import WeekRepository


def get_week_summary(week_id: int) -> dict[str, object]:
    repo = WeekRepository()
    return repo.get_week_summary(week_id)
