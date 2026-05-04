def get_week_summary(week_id: int) -> dict[str, object]:
    return {
        "weekId": week_id,
        "objective": "Repetir semana tipo con control",
        "status": "planned",
        "riskToWatch": "Aumentar demasiado pronto",
    }
