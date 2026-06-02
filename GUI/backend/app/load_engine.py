from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from math import exp
from typing import Any

from .db import get_connection


CYCLING_DISCIPLINES = {"cycling", "road_biking", "indoor_cycling", "mountain_biking"}
WALKING_DISCIPLINES = {"walking", "hiking"}
ENDURANCE_DISCIPLINES = CYCLING_DISCIPLINES | {"running", "treadmill_running"} | WALKING_DISCIPLINES
STRENGTH_DISCIPLINES = {"strength_training"}
MOBILITY_DISCIPLINES = {"yoga"}
LOCOMOTION_KEYWORDS = {
    "walk",
    "walking",
    "caminar",
    "hike",
    "hiking",
    "senderismo",
    "trek",
    "trekking",
    "run",
    "running",
    "carrera",
    "treadmill",
    "cinta",
    "trail_run",
    "trail_running",
    "nordic_walking",
}


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _activity_moment_key(activity_row: dict[str, Any]) -> str:
    started_at = _parse_iso_datetime(activity_row.get("started_at"))
    if started_at is not None:
        return started_at.date().isoformat()
    return str(activity_row.get("activity_date") or "")


def _fetch_anchor_profile(*, season_id: int, metric_basis: str, activity_date: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT zone_metric_profile_id, metric_basis, model_key, resting_hr, max_hr, ftp,
                   effective_start_date, effective_end_date
            FROM zone_metric_profiles
            WHERE season_id = ?
              AND discipline = 'cycling'
              AND metric_basis = ?
              AND effective_start_date <= ?
              AND (effective_end_date IS NULL OR effective_end_date = '' OR effective_end_date >= ?)
            ORDER BY effective_start_date DESC, zone_metric_profile_id DESC
            LIMIT 1
            """,
            (season_id, metric_basis, activity_date, activity_date),
        ).fetchone()
        if row is None:
            row = connection.execute(
                """
                SELECT zone_metric_profile_id, metric_basis, model_key, resting_hr, max_hr, ftp,
                       effective_start_date, effective_end_date
                FROM zone_metric_profiles
                WHERE season_id = ?
                  AND discipline = 'cycling'
                  AND metric_basis = ?
                ORDER BY ABS(julianday(effective_start_date) - julianday(?)) ASC,
                         effective_start_date DESC,
                         zone_metric_profile_id DESC
                LIMIT 1
                """,
                (season_id, metric_basis, activity_date),
            ).fetchone()
    return dict(row) if row else None


def _compute_power_tss(*, duration_seconds: float | int | None, normalized_power: float | int | None, average_power: float | int | None, ftp: float | int | None) -> float | None:
    if duration_seconds in (None, 0) or ftp in (None, 0):
        return None
    power_value = normalized_power if normalized_power not in (None, 0) else average_power
    if power_value in (None, 0):
        return None
    intensity_factor = float(power_value) / float(ftp)
    duration_hours = float(duration_seconds) / 3600.0
    return round(duration_hours * intensity_factor * intensity_factor * 100.0, 2)


def _compute_hr_trimp(*, duration_seconds: float | int | None, average_hr: float | int | None, resting_hr: float | int | None, max_hr: float | int | None) -> float | None:
    if duration_seconds in (None, 0) or average_hr in (None, 0) or resting_hr in (None, 0) or max_hr in (None, 0):
        return None
    if float(max_hr) <= float(resting_hr):
        return None
    relative_intensity = (float(average_hr) - float(resting_hr)) / (float(max_hr) - float(resting_hr))
    relative_intensity = min(max(relative_intensity, 0.0), 1.0)
    duration_minutes = float(duration_seconds) / 60.0
    return round(duration_minutes * relative_intensity * 0.64 * exp(1.92 * relative_intensity), 2)


def _compute_respiration_rate_load(*, duration_seconds: float | int | None, average_respiration_rate: float | int | None) -> float | None:
    if duration_seconds in (None, 0) or average_respiration_rate in (None, 0):
        return None
    baseline_breaths_per_minute = 12.0
    high_breaths_per_minute = 45.0
    relative_intensity = (float(average_respiration_rate) - baseline_breaths_per_minute) / (
        high_breaths_per_minute - baseline_breaths_per_minute
    )
    relative_intensity = min(max(relative_intensity, 0.0), 1.0)
    if relative_intensity == 0.0:
        return None
    duration_minutes = float(duration_seconds) / 60.0
    return round(duration_minutes * relative_intensity, 2)


def _compute_session_rpe_load(*, duration_seconds: float | int | None, perceived_exertion: float | int | None) -> float | None:
    if duration_seconds in (None, 0) or perceived_exertion in (None, 0):
        return None
    duration_minutes = float(duration_seconds) / 60.0
    return round(duration_minutes * float(perceived_exertion) / 10.0, 2)


def _compute_duration_heuristic_load(*, duration_seconds: float | int | None, factor_per_minute: float) -> float | None:
    if duration_seconds in (None, 0):
        return None
    return round(float(duration_seconds) / 60.0 * factor_per_minute, 2)


def _is_locomotion_activity(activity_row: dict[str, Any]) -> bool:
    discipline = str(activity_row.get("discipline") or "").strip().lower()
    activity_type = str(activity_row.get("activity_type") or "").strip().lower()

    if discipline in ENDURANCE_DISCIPLINES:
        return True
    if discipline in STRENGTH_DISCIPLINES or discipline in MOBILITY_DISCIPLINES:
        return False

    activity_signature = {discipline, activity_type}
    for token in LOCOMOTION_KEYWORDS:
        if any(token in value for value in activity_signature if value):
            return True
    return False


def compute_activity_load(activity_row: dict[str, Any], *, season_id: int) -> dict[str, Any]:
    discipline = str(activity_row.get("discipline") or "").strip().lower()
    activity_date = _activity_moment_key(activity_row)
    hr_profile = _fetch_anchor_profile(season_id=season_id, metric_basis="heart_rate", activity_date=activity_date)
    power_profile = _fetch_anchor_profile(season_id=season_id, metric_basis="power", activity_date=activity_date)

    duration_seconds = activity_row.get("duration_seconds")
    average_hr = activity_row.get("avg_hr")
    normalized_power = activity_row.get("normalized_power")
    average_power = activity_row.get("avg_power")
    average_respiration_rate = activity_row.get("avg_respiration_rate")
    perceived_exertion = activity_row.get("perceived_exertion")
    vendor_load = activity_row.get("training_load")

    if discipline in CYCLING_DISCIPLINES:
        power_tss = _compute_power_tss(
            duration_seconds=duration_seconds,
            normalized_power=normalized_power,
            average_power=average_power,
            ftp=power_profile.get("ftp") if power_profile else None,
        )
        if power_tss is not None:
            return {"load_value": power_tss, "load_source": "power_tss", "discipline": discipline}

    if _is_locomotion_activity(activity_row):
        hr_trimp = _compute_hr_trimp(
            duration_seconds=duration_seconds,
            average_hr=average_hr,
            resting_hr=hr_profile.get("resting_hr") if hr_profile else None,
            max_hr=hr_profile.get("max_hr") if hr_profile else None,
        )
        if hr_trimp is not None:
            return {"load_value": hr_trimp, "load_source": "hr_trimp", "discipline": discipline}
        respiration_load = _compute_respiration_rate_load(
            duration_seconds=duration_seconds,
            average_respiration_rate=average_respiration_rate,
        )
        if respiration_load is not None:
            return {"load_value": respiration_load, "load_source": "respiration_rate_heuristic", "discipline": discipline}

    if discipline in STRENGTH_DISCIPLINES:
        hr_trimp = _compute_hr_trimp(
            duration_seconds=duration_seconds,
            average_hr=average_hr,
            resting_hr=hr_profile.get("resting_hr") if hr_profile else None,
            max_hr=hr_profile.get("max_hr") if hr_profile else None,
        )
        if hr_trimp is not None:
            return {"load_value": hr_trimp, "load_source": "hr_trimp", "discipline": discipline}
        respiration_load = _compute_respiration_rate_load(
            duration_seconds=duration_seconds,
            average_respiration_rate=average_respiration_rate,
        )
        if respiration_load is not None:
            return {"load_value": respiration_load, "load_source": "respiration_rate_heuristic", "discipline": discipline}
        if vendor_load not in (None, 0):
            return {"load_value": round(float(vendor_load), 2), "load_source": "garmin_training_load", "discipline": discipline}
        heuristic = _compute_duration_heuristic_load(duration_seconds=duration_seconds, factor_per_minute=0.45)
        if heuristic is not None:
            return {"load_value": heuristic, "load_source": "strength_duration_heuristic", "discipline": discipline}

    if discipline in MOBILITY_DISCIPLINES:
        hr_trimp = _compute_hr_trimp(
            duration_seconds=duration_seconds,
            average_hr=average_hr,
            resting_hr=hr_profile.get("resting_hr") if hr_profile else None,
            max_hr=hr_profile.get("max_hr") if hr_profile else None,
        )
        if hr_trimp is not None:
            return {"load_value": hr_trimp, "load_source": "hr_trimp", "discipline": discipline}
        respiration_load = _compute_respiration_rate_load(
            duration_seconds=duration_seconds,
            average_respiration_rate=average_respiration_rate,
        )
        if respiration_load is not None:
            return {"load_value": respiration_load, "load_source": "respiration_rate_heuristic", "discipline": discipline}
        if vendor_load not in (None, 0):
            return {"load_value": round(float(vendor_load), 2), "load_source": "garmin_training_load", "discipline": discipline}
        heuristic = _compute_duration_heuristic_load(duration_seconds=duration_seconds, factor_per_minute=0.2)
        if heuristic is not None:
            return {"load_value": heuristic, "load_source": "mobility_duration_heuristic", "discipline": discipline}

    if vendor_load not in (None, 0):
        return {"load_value": round(float(vendor_load), 2), "load_source": "garmin_training_load", "discipline": discipline}

    return {"load_value": 0.0, "load_source": "no_load_signal", "discipline": discipline}


def build_daily_loads(*, season_id: int, through_date: str) -> tuple[dict[str, float], list[dict[str, Any]]]:
    with get_connection() as connection:
        metric_summaries_available = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'exec_activity_metric_summaries'"
        ).fetchone() is not None
        avg_respiration_rate_select = (
            """
                   (
                       SELECT trusted_value
                       FROM exec_activity_metric_summaries summary
                       WHERE summary.activity_id = exec_activities.activity_id
                         AND summary.metric_name = 'respiration_rate'
                         AND summary.summary_kind = 'average'
                       LIMIT 1
                   ) AS avg_respiration_rate
            """
            if metric_summaries_available
            else "NULL AS avg_respiration_rate"
        )
        rows = connection.execute(
            f"""
            SELECT activity_id, activity_date, started_at, discipline, duration_seconds,
                   avg_hr, avg_power, normalized_power, training_load, perceived_exertion,
                   {avg_respiration_rate_select}
            FROM exec_activities
            WHERE season_id = ?
              AND activity_date <= ?
            ORDER BY activity_date ASC, COALESCE(started_at, activity_date) ASC, activity_id ASC
            """,
            (season_id, through_date),
        ).fetchall()

    daily_loads: dict[str, float] = defaultdict(float)
    activity_loads: list[dict[str, Any]] = []
    for row in rows:
        activity = dict(row)
        load = compute_activity_load(activity, season_id=season_id)
        metric_date = str(activity["activity_date"])
        daily_loads[metric_date] += float(load["load_value"])
        activity_loads.append(
            {
                "activity_id": activity["activity_id"],
                "activity_date": metric_date,
                "discipline": load["discipline"],
                "load_value": round(float(load["load_value"]), 2),
                "load_source": load["load_source"],
            }
        )
    return {key: round(value, 2) for key, value in daily_loads.items()}, activity_loads


def _compute_load_model_series(
    daily_loads: dict[str, float],
    *,
    through_date: str,
    atl_time_constant_days: int = 7,
    ctl_time_constant_days: int = 42,
) -> dict[str, float]:
    target_date = _parse_iso_date(through_date)
    first_date = min((_parse_iso_date(metric_date) for metric_date in daily_loads), default=target_date)

    atl = 0.0
    ctl = 0.0
    current_date = first_date
    previous_atl = 0.0
    previous_ctl = 0.0
    while current_date <= target_date:
        load_value = float(daily_loads.get(current_date.isoformat(), 0.0) or 0.0)
        previous_atl = atl
        previous_ctl = ctl
        atl += (load_value - atl) / atl_time_constant_days
        ctl += (load_value - ctl) / ctl_time_constant_days
        current_date += timedelta(days=1)

    return {
        "daily_training_load": round(float(daily_loads.get(through_date, 0.0) or 0.0), 2),
        "atl": round(atl, 2),
        "ctl": round(ctl, 2),
        "tsb": round(previous_ctl - previous_atl, 2),
        "atl_time_constant_days": atl_time_constant_days,
        "ctl_time_constant_days": ctl_time_constant_days,
    }


def _compute_load_model_history(
    daily_loads: dict[str, float],
    *,
    through_date: str,
    trailing_days: int = 14,
    atl_time_constant_days: int = 7,
    ctl_time_constant_days: int = 42,
) -> list[dict[str, float | str]]:
    target_date = _parse_iso_date(through_date)
    first_date = min((_parse_iso_date(metric_date) for metric_date in daily_loads), default=target_date)
    history_start_date = max(first_date, target_date - timedelta(days=max(trailing_days - 1, 0)))

    atl = 0.0
    ctl = 0.0
    current_date = first_date
    history: list[dict[str, float | str]] = []
    while current_date <= target_date:
        load_value = float(daily_loads.get(current_date.isoformat(), 0.0) or 0.0)
        previous_atl = atl
        previous_ctl = ctl
        atl += (load_value - atl) / atl_time_constant_days
        ctl += (load_value - ctl) / ctl_time_constant_days
        if current_date >= history_start_date:
            history.append(
                {
                    "metric_date": current_date.isoformat(),
                    "daily_training_load": round(load_value, 2),
                    "atl": round(atl, 2),
                    "ctl": round(ctl, 2),
                    "tsb": round(previous_ctl - previous_atl, 2),
                }
            )
        current_date += timedelta(days=1)
    return history


def get_load_model_snapshot(season_id: int, metric_date: str) -> dict[str, Any]:
    daily_loads, activity_loads = build_daily_loads(season_id=season_id, through_date=metric_date)
    source_totals: dict[str, float] = defaultdict(float)
    for activity_load in activity_loads:
        source_totals[str(activity_load["load_source"])] += float(activity_load["load_value"])

    snapshot = _compute_load_model_series(daily_loads, through_date=metric_date)
    snapshot["trend"] = _compute_load_model_history(daily_loads, through_date=metric_date)
    snapshot["source_totals"] = {key: round(value, 2) for key, value in sorted(source_totals.items())}
    return snapshot

    return {
        "load_value": 0.0,
        "load_source": "unavailable",
        "load_source_label": "Sin carga usable",
    }


def _compute_load_model_series(
    daily_loads: dict[str, float],
    *,
    through_date: str,
    atl_time_constant_days: int = 7,
    ctl_time_constant_days: int = 42,
) -> dict[str, float]:
    target_date = _parse_iso_date(through_date)
    first_date = min((_parse_iso_date(metric_date) for metric_date in daily_loads), default=target_date)

    atl = 0.0
    ctl = 0.0
    current_date = first_date
    previous_atl = 0.0
    previous_ctl = 0.0
    while current_date <= target_date:
        load_value = float(daily_loads.get(current_date.isoformat(), 0.0) or 0.0)
        previous_atl = atl
        previous_ctl = ctl
        atl += (load_value - atl) / atl_time_constant_days
        ctl += (load_value - ctl) / ctl_time_constant_days
        current_date += timedelta(days=1)

    return {
        "daily_training_load": round(float(daily_loads.get(through_date, 0.0) or 0.0), 2),
        "atl": round(atl, 2),
        "ctl": round(ctl, 2),
        "tsb": round(previous_ctl - previous_atl, 2),
        "atl_time_constant_days": atl_time_constant_days,
        "ctl_time_constant_days": ctl_time_constant_days,
    }


def _compute_load_model_history(
    daily_loads: dict[str, float],
    *,
    through_date: str,
    trailing_days: int = 14,
    atl_time_constant_days: int = 7,
    ctl_time_constant_days: int = 42,
) -> list[dict[str, float | str]]:
    target_date = _parse_iso_date(through_date)
    first_date = min((_parse_iso_date(metric_date) for metric_date in daily_loads), default=target_date)
    history_start_date = max(first_date, target_date - timedelta(days=max(trailing_days - 1, 0)))

    atl = 0.0
    ctl = 0.0
    current_date = first_date
    history: list[dict[str, float | str]] = []
    while current_date <= target_date:
        load_value = float(daily_loads.get(current_date.isoformat(), 0.0) or 0.0)
        previous_atl = atl
        previous_ctl = ctl
        atl += (load_value - atl) / atl_time_constant_days
        ctl += (load_value - ctl) / ctl_time_constant_days
        if current_date >= history_start_date:
            history.append(
                {
                    "metric_date": current_date.isoformat(),
                    "daily_training_load": round(load_value, 2),
                    "atl": round(atl, 2),
                    "ctl": round(ctl, 2),
                    "tsb": round(previous_ctl - previous_atl, 2),
                }
            )
        current_date += timedelta(days=1)
    return history

