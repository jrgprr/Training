from app.repositories.dashboard_repository import DashboardRepository


def get_today_dashboard() -> dict[str, object]:
    repo = DashboardRepository()
    return repo.get_today_dashboard()
