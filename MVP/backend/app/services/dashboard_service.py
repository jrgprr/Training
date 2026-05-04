from datetime import date


def get_today_dashboard() -> dict[str, object]:
    return {
        "date": date.today().isoformat(),
        "dayStatus": "ready",
        "primaryObjective": "Ejecutar el plan del dia",
        "pendingFields": ["checkin", "nutrition"],
    }
