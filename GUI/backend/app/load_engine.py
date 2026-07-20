from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from math import exp
from statistics import median
from typing import Any

from .db import get_connection


CYCLING_DISCIPLINES = {"cycling", "road_biking", "indoor_cycling", "mountain_biking"}
WALKING_DISCIPLINES = {"walking", "hiking", "trail_walking", "nordic_walking"}
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


def _is_endurance_load_activity(activity_row: dict[str, Any]) -> bool:
    discipline = str(activity_row.get("discipline") or "").strip().lower()
    if discipline in CYCLING_DISCIPLINES:
        return True
    return _is_locomotion_activity(activity_row)


def _default_projection_factor(session_row: dict[str, Any]) -> float:
    planned_type = str(session_row.get("planned_type") or "").strip().lower()
    planned_role = str(session_row.get("planned_role") or "").strip().lower()

    factors = {
        "recuperacion": 0.53,
        "bicicleta-z2": 0.96,
        "trote-suave": 1.15,
        "salida-larga": 0.85,
        "complementaria": 0.42,
    }
    factor = factors.get(planned_type)
    if factor is None:
        if "carrera" in planned_role:
            factor = 1.15
        elif "extensiva" in planned_role:
            factor = 0.85
        elif "principal" in planned_role:
            factor = 0.96
        elif "suave" in planned_role or "recuperacion" in planned_role:
            factor = 0.53
        else:
            factor = 0.6
    return factor


def _is_recovery_calibration_sample(activity_row: dict[str, Any], *, midpoint_duration: float) -> bool:
    compliance_status = str(activity_row.get("compliance_status") or "").strip().lower()
    if compliance_status != "completed":
        return False

    duration_seconds = activity_row.get("duration_seconds")
    if duration_seconds in (None, 0) or midpoint_duration <= 0:
        return False

    actual_minutes = float(duration_seconds) / 60.0
    adherence_ratio = actual_minutes / midpoint_duration
    return 0.75 <= adherence_ratio <= 1.25


def _collect_projection_calibration(*, season_id: int, season_block_sequence: int, metric_date: str) -> dict[str, dict[str, float]]:
    with get_connection() as connection:
        linked_rows = connection.execute(
            """
                 SELECT ps.planned_type, ps.planned_role, ps.duration_min, ps.duration_max,
                     l.compliance_status,
                   e.activity_date, e.started_at, e.discipline, e.activity_type,
                   e.duration_seconds, e.avg_hr, e.avg_power, e.normalized_power,
                   e.training_load, e.perceived_exertion
            FROM link_plan_execution l
            JOIN plan_planned_sessions ps ON ps.planned_session_id = l.planned_session_id
            JOIN plan_micro_weeks mw ON mw.week_id = ps.week_id
            JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
            JOIN exec_activities e ON e.activity_id = l.activity_id
            WHERE mb.season_id = ?
              AND mb.sequence_order BETWEEN ? AND ?
              AND ps.session_date < ?
            ORDER BY ps.session_date ASC, l.link_id ASC
            """,
            (season_id, max(season_block_sequence - 1, 1), season_block_sequence, metric_date),
        ).fetchall()

    samples_by_type: dict[str, list[float]] = defaultdict(list)
    samples_by_role: dict[str, list[float]] = defaultdict(list)
    for row in linked_rows:
        activity_row = dict(row)
        if not _is_endurance_load_activity(activity_row):
            continue
        duration_min = activity_row.get("duration_min")
        duration_max = activity_row.get("duration_max")
        lower_bound = float(duration_min if duration_min is not None else duration_max if duration_max is not None else 0)
        upper_bound = float(duration_max if duration_max is not None else duration_min if duration_min is not None else 0)
        midpoint_duration = (lower_bound + upper_bound) / 2 if lower_bound or upper_bound else 0.0
        if midpoint_duration <= 0:
            continue

        planned_type = str(activity_row.get("planned_type") or "").strip().lower()
        if planned_type == "recuperacion" and not _is_recovery_calibration_sample(activity_row, midpoint_duration=midpoint_duration):
            continue

        load_value = float(compute_activity_load(activity_row, season_id=season_id)["load_value"])
        load_per_minute = load_value / midpoint_duration
        if load_per_minute <= 0:
            continue

        planned_role = str(activity_row.get("planned_role") or "").strip().lower()
        if planned_type:
            samples_by_type[planned_type].append(load_per_minute)
        if planned_role:
            samples_by_role[planned_role].append(load_per_minute)

    return {
        "type": {key: round(median(values), 3) for key, values in samples_by_type.items() if len(values) >= 2},
        "role": {key: round(median(values), 3) for key, values in samples_by_role.items() if len(values) >= 2},
    }


def _estimate_planned_session_load(session_row: dict[str, Any], calibration: dict[str, dict[str, float]] | None = None) -> float:
    duration_min = session_row.get("duration_min")
    duration_max = session_row.get("duration_max")
    lower_bound = float(duration_min if duration_min is not None else duration_max if duration_max is not None else 0)
    upper_bound = float(duration_max if duration_max is not None else duration_min if duration_min is not None else 0)
    midpoint_duration = (lower_bound + upper_bound) / 2 if lower_bound or upper_bound else 0.0

    planned_type = str(session_row.get("planned_type") or "").strip().lower()
    planned_role = str(session_row.get("planned_role") or "").strip().lower()
    factor = None
    if calibration:
        factor = calibration.get("type", {}).get(planned_type)
        if factor is None:
            factor = calibration.get("role", {}).get(planned_role)
    if factor is None:
        factor = _default_projection_factor(session_row)
    return round(midpoint_duration * factor, 2)


def _build_block_projection_loads(*, season_id: int, metric_date: str) -> tuple[dict[str, float], str | None]:
    with get_connection() as connection:
        planning_tables_available = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plan_micro_weeks'"
        ).fetchone() is not None and connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plan_planned_sessions'"
        ).fetchone() is not None and connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plan_meso_blocks'"
        ).fetchone() is not None
        if not planning_tables_available:
            return {}, None

        week_row = connection.execute(
            """
            SELECT mw.week_id, mw.block_id, mb.season_id, mb.sequence_order
            FROM plan_micro_weeks mw
            JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
            WHERE mw.start_date <= ? AND mw.end_date >= ?
            ORDER BY mw.start_date DESC, mw.week_id DESC
            LIMIT 1
            """,
            (metric_date, metric_date),
        ).fetchone()
        if week_row is None:
            return {}, None

        block_end_row = connection.execute(
            """
            SELECT MAX(end_date) AS block_end_date
            FROM plan_micro_weeks
            WHERE block_id = ?
            """,
            (week_row["block_id"],),
        ).fetchone()
        block_end_date = str(block_end_row["block_end_date"]) if block_end_row and block_end_row["block_end_date"] else None
        if not block_end_date or block_end_date <= metric_date:
            return {}, block_end_date

        calibration = _collect_projection_calibration(
            season_id=int(week_row["season_id"]),
            season_block_sequence=int(week_row["sequence_order"]),
            metric_date=metric_date,
        )

        session_rows = connection.execute(
            """
            SELECT session_date, planned_type, planned_role, duration_min, duration_max
            FROM plan_planned_sessions
            WHERE session_date > ?
              AND week_id IN (
                  SELECT week_id
                  FROM plan_micro_weeks
                  WHERE block_id = ?
              )
            ORDER BY session_date ASC, planned_session_id ASC
            """,
            (metric_date, week_row["block_id"]),
        ).fetchall()

    projected_loads: dict[str, float] = {}
    for row in session_rows:
        session = dict(row)
        projected_loads[str(session["session_date"])] = _estimate_planned_session_load(session, calibration)
    return projected_loads, block_end_date


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
        if not _is_endurance_load_activity(activity):
            continue

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
    projection_loads, projection_end_date = _build_block_projection_loads(season_id=season_id, metric_date=metric_date)
    if projection_loads and projection_end_date:
        projected_daily_loads = dict(daily_loads)
        projected_daily_loads.update(projection_loads)
        projected_history = _compute_load_model_history(projected_daily_loads, through_date=projection_end_date, trailing_days=365)
        snapshot["projection"] = [entry for entry in projected_history if str(entry["metric_date"]) > metric_date]
    else:
        snapshot["projection"] = []
    snapshot["projection_end_date"] = projection_end_date
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

