from app.core.config import settings


def get_health_status() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
