#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "GUI" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.planned_prescriptions import get_planned_session_prescription, project_planned_session_row_from_prescription
from app.activity_weather import get_activity_weather

ENDURANCE_DISCIPLINES = {
    "cycling",
    "bike",
    "road_biking",
    "gravel_cycling",
    "mountain_biking",
    "virtual_ride",
    "indoor_cycling",
    "running",
    "trail_running",
    "track_running",
    "treadmill_running",
    "walking",
    "hiking",
    "trail_walking",
    "nordic_walking",
}

WALKING_LIKE_DISCIPLINES = {"walking", "hiking", "trail_walking", "nordic_walking"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a normalized JSON context bundle for one training day.")
    parser.add_argument("--date", required=True, help="Target date in ISO format, for example 2026-06-03")
    parser.add_argument("--season", type=int, help="Optional season id. If omitted, it is inferred from the date.")
    parser.add_argument("--db", default=str(REPO_ROOT / "Sistema" / "training.sqlite"), help="Path to SQLite database")
    parser.add_argument("--history-days", type=int, default=7, help="Number of trailing days of recent activity context")
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows if row is not None]


def fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return row_to_dict(connection.execute(query, params).fetchone())


def fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return rows_to_dicts(connection.execute(query, params).fetchall())


def infer_season_id(connection: sqlite3.Connection, target_date: str) -> int | None:
    row = connection.execute(
        """
        SELECT season_id
        FROM plan_seasons
        WHERE start_date <= ? AND end_date >= ?
        ORDER BY start_date DESC
        LIMIT 1
        """,
        (target_date, target_date),
    ).fetchone()
    if row is not None:
        return int(row[0])
    row = connection.execute(
        "SELECT season_id FROM plan_seasons ORDER BY start_date DESC LIMIT 1"
    ).fetchone()
    return int(row[0]) if row is not None else None


def load_load_model_snapshot(season_id: int, target_date: str) -> dict[str, Any] | None:
    try:
        sys.path.insert(0, str(REPO_ROOT / "GUI" / "backend"))
        from app.load_engine import get_load_model_snapshot  # type: ignore

        return get_load_model_snapshot(season_id=season_id, metric_date=target_date)
    except Exception as exc:  # pragma: no cover - defensive fallback for runtime environments
        return {"error": f"Unable to load load model snapshot: {exc}"}
    finally:
        backend_path = str(REPO_ROOT / "GUI" / "backend")
        if backend_path in sys.path:
            sys.path.remove(backend_path)


def group_zone_summaries(connection: sqlite3.Connection, activity_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not activity_ids:
        return {}
    placeholders = ",".join("?" for _ in activity_ids)
    rows = fetch_all(
        connection,
        f"""
        SELECT zr.activity_id, zr.metric_basis, zr.calculation_status, zr.dominant_zone_code,
               zr.dominant_zone_share, zr.total_supported_seconds, zp.profile_label
        FROM exec_activity_zone_results zr
        LEFT JOIN zone_profiles zp ON zp.zone_profile_id = zr.zone_profile_id
        WHERE zr.activity_id IN ({placeholders})
        ORDER BY zr.activity_id, zr.metric_basis
        """,
        tuple(activity_ids),
    )
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(int(row["activity_id"]), []).append(row)
    return grouped


def load_recent_activities(connection: sqlite3.Connection, season_id: int, target_date: str, history_days: int) -> list[dict[str, Any]]:
    start_date = (parse_iso_date(target_date) - timedelta(days=max(history_days - 1, 0))).isoformat()
    return fetch_all(
        connection,
        """
        SELECT activity_id, activity_date, started_at, discipline, activity_type,
               duration_seconds, distance_meters, ascent_meters, calories,
               avg_hr, max_hr, avg_power, normalized_power, training_load,
               avg_pace_seconds_per_km, perceived_exertion, subjective_feeling,
               quality_status, quality_decision_count, quality_limited_metric_count,
               source_system
        FROM exec_activities
        WHERE season_id = ? AND activity_date BETWEEN ? AND ?
        ORDER BY activity_date DESC, COALESCE(started_at, activity_date) DESC, activity_id DESC
        """,
        (season_id, start_date, target_date),
    )


def is_endurance_activity(activity: dict[str, Any]) -> bool:
    return str(activity.get("discipline") or "").lower() in ENDURANCE_DISCIPLINES


def select_metric_analysis_activity(day_activities: list[dict[str, Any]], linked_rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    linked_activity_ids = {int(row["activity_id"]) for row in linked_rows if row.get("activity_id") is not None}
    candidates = [activity for activity in day_activities if is_endurance_activity(activity)]
    if not candidates:
        return None, []

    candidates.sort(
        key=lambda activity: (
            int(activity["activity_id"]) in linked_activity_ids,
            float(activity.get("modeled_load_value") or 0),
            float(activity.get("duration_seconds") or 0),
        ),
        reverse=True,
    )
    selected = candidates[0]
    selected_discipline = str(selected.get("discipline") or "").lower()

    reasons: list[str] = ["dominant_endurance_session"]
    if int(selected["activity_id"]) in linked_activity_ids:
        reasons.append("linked_to_planned_session")
    if float(selected.get("duration_seconds") or 0) >= 45 * 60:
        reasons.append("meaningful_duration")
    if float(selected.get("modeled_load_value") or 0) >= 50:
        reasons.append("meaningful_modeled_load")

    if selected_discipline in WALKING_LIKE_DISCIPLINES and len(reasons) == 1:
        return None, []

    if len(reasons) == 1:
        return None, []
    return selected, reasons


def load_activity_metric_analysis(connection: sqlite3.Connection, activity_id: int) -> dict[str, Any] | None:
    scripts_path = str(REPO_ROOT / ".github" / "skills" / "activity-metric-analysis" / "scripts")
    try:
        sys.path.insert(0, scripts_path)
        from compute_activity_metric_analysis import compute_activity_metric_analysis  # type: ignore

        return compute_activity_metric_analysis(connection, activity_id)
    except Exception as exc:  # pragma: no cover - defensive fallback for runtime environments
        return {"error": f"Unable to compute activity metric analysis: {exc}"}
    finally:
        if scripts_path in sys.path:
            sys.path.remove(scripts_path)


def load_activity_modeled_load(connection: sqlite3.Connection, activity_id: int, season_id: int) -> dict[str, Any] | None:
    backend_path = str(REPO_ROOT / "GUI" / "backend")
    try:
        sys.path.insert(0, backend_path)
        from app.load_engine import compute_activity_load  # type: ignore

        activity_row = connection.execute("SELECT * FROM exec_activities WHERE activity_id = ?", (activity_id,)).fetchone()
        if activity_row is None:
            return None
        return compute_activity_load(dict(activity_row), season_id=season_id)
    except Exception:  # pragma: no cover - defensive fallback for runtime environments
        return None
    finally:
        if backend_path in sys.path:
            sys.path.remove(backend_path)


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def load_activity_weather(activity_id: int) -> dict[str, Any] | None:
    try:
        return get_activity_weather(activity_id)
    except Exception as exc:  # pragma: no cover - defensive fallback for runtime environments
        return {"error": f"Unable to load activity weather: {exc}"}


def summarize_weather_impact(weather: dict[str, Any] | None) -> dict[str, Any] | None:
    if not weather or not isinstance(weather, dict):
        return None
    summary = weather.get("summary")
    if not isinstance(summary, dict):
        return None

    temperature_mean = _as_float(summary.get("temperature_mean"))
    temperature_max = _as_float(summary.get("temperature_max"))
    apparent_temperature_mean = _as_float(summary.get("apparent_temperature_mean"))
    cloud_cover_mean = _as_float(summary.get("cloud_cover_mean"))
    wind_speed_mean = _as_float(summary.get("wind_speed_mean"))
    shortwave_radiation_mean = _as_float(summary.get("shortwave_radiation_mean"))
    rain_sum_est = _as_float(summary.get("rain_sum_est"))

    if all(value is None for value in (temperature_mean, temperature_max, apparent_temperature_mean)):
        return None

    heat_level = "neutral"
    if (
        (apparent_temperature_mean is not None and apparent_temperature_mean >= 35.0)
        or (temperature_max is not None and temperature_max >= 35.0)
        or (temperature_mean is not None and temperature_mean >= 30.0)
    ):
        heat_level = "high"
    elif (
        (apparent_temperature_mean is not None and apparent_temperature_mean >= 30.0)
        or (temperature_max is not None and temperature_max >= 32.0)
        or (temperature_mean is not None and temperature_mean >= 26.0)
    ):
        heat_level = "moderate"
    elif (
        (temperature_max is not None and temperature_max >= 28.0)
        or (temperature_mean is not None and temperature_mean >= 22.0)
    ):
        heat_level = "warm"

    cooling_level = "normal"
    if (
        (wind_speed_mean is None or wind_speed_mean < 10.0)
        and (cloud_cover_mean is None or cloud_cover_mean < 40.0)
        and (shortwave_radiation_mean is not None and shortwave_radiation_mean >= 250.0)
    ):
        cooling_level = "limited"
    elif wind_speed_mean is not None and wind_speed_mean >= 18.0:
        cooling_level = "supportive"

    moisture_context = "dry"
    if rain_sum_est is not None and rain_sum_est >= 1.0:
        moisture_context = "wet"
    elif rain_sum_est is not None and rain_sum_est > 0:
        moisture_context = "light_precipitation"

    notes: list[str] = []
    if heat_level == "high":
        notes.append("Hot conditions likely elevated cardiovascular strain and hydration demand.")
    elif heat_level == "moderate":
        notes.append("Warm conditions likely added meaningful heat cost.")
    elif heat_level == "warm":
        notes.append("Mild warm-weather strain may have contributed to perceived cost.")

    if cooling_level == "limited":
        notes.append("Low wind with clear sun limited on-bike cooling.")
    elif cooling_level == "supportive":
        notes.append("Wind support likely improved cooling despite the ambient conditions.")

    if moisture_context == "wet":
        notes.append("Rain exposure may have affected comfort, traction, and thermal balance.")

    return {
        "heat_level": heat_level,
        "cooling_level": cooling_level,
        "moisture_context": moisture_context,
        "temperature_mean": temperature_mean,
        "temperature_max": temperature_max,
        "apparent_temperature_mean": apparent_temperature_mean,
        "wind_speed_mean": wind_speed_mean,
        "cloud_cover_mean": cloud_cover_mean,
        "shortwave_radiation_mean": shortwave_radiation_mean,
        "analysis_notes": notes,
    }


def enrich_activities_with_weather(activities: list[dict[str, Any]]) -> None:
    for activity in activities:
        weather = load_activity_weather(int(activity["activity_id"]))
        if weather is not None:
            activity["weather"] = weather
            activity["weather_analysis"] = summarize_weather_impact(weather)


def main() -> int:
    args = parse_args()
    target_date = parse_iso_date(args.date).isoformat()

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    season_id = args.season or infer_season_id(connection, target_date)
    if season_id is None:
        raise SystemExit(f"Unable to infer season for {target_date}")

    season = fetch_one(
        connection,
        """
        SELECT season_id, season_code, season_name, start_date, end_date, status
        FROM plan_seasons
        WHERE season_id = ?
        """,
        (season_id,),
    )

    planned_sessions = fetch_all(
        connection,
        """
        SELECT ps.planned_session_id, ps.session_date, ps.day_name, ps.sequence_in_week,
               ps.planned_type, ps.objective, ps.primary_session, ps.complementary_session,
               ps.notes, ps.is_key_session, ps.intensity_class, ps.duration_min, ps.duration_max,
               ps.adjustment_rule,
               mw.week_id, mw.week_code, mw.week_role, mw.start_date AS week_start_date,
               mw.end_date AS week_end_date, mw.target_volume_hours_min, mw.target_volume_hours_max,
               mb.block_id, mb.block_code, mb.block_name, mb.phase_name,
               pr.prescription_type, pr.title AS prescription_title, pr.focus_primary,
               pr.focus_secondary, pr.estimated_duration_min, pr.estimated_duration_max,
               pr.target_rpe_min, pr.target_rpe_max, pr.execution_notes, pr.adaptation_notes
        FROM plan_planned_sessions ps
        JOIN plan_micro_weeks mw ON mw.week_id = ps.week_id
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        LEFT JOIN plan_session_prescriptions pr ON pr.planned_session_id = ps.planned_session_id
        WHERE ps.session_date = ?
        ORDER BY ps.sequence_in_week, ps.planned_session_id
        """,
        (target_date,),
    )
    for session in planned_sessions:
        prescription = get_planned_session_prescription(connection, int(session["planned_session_id"]))
        session.update(project_planned_session_row_from_prescription(session, prescription))

    linked_rows = fetch_all(
        connection,
        """
        SELECT l.link_id, l.planned_session_id, l.activity_id, l.link_type, l.compliance_status,
               l.rationale, l.created_at,
               ea.activity_date, ea.started_at, ea.discipline, ea.activity_type,
               ea.duration_seconds, ea.distance_meters, ea.ascent_meters, ea.avg_hr,
               ea.max_hr, ea.avg_power, ea.normalized_power, ea.training_load,
               ea.perceived_exertion, ea.subjective_feeling, ea.quality_status,
               ea.quality_decision_count, ea.quality_limited_metric_count, ea.source_system
        FROM link_plan_execution l
        JOIN exec_activities ea ON ea.activity_id = l.activity_id
        JOIN plan_planned_sessions ps ON ps.planned_session_id = l.planned_session_id
        WHERE ps.session_date = ?
        ORDER BY l.planned_session_id, l.created_at DESC, l.link_id DESC
        """,
        (target_date,),
    )

    day_activities = fetch_all(
        connection,
        """
        SELECT activity_id, season_id, source_system, external_activity_id, activity_date, started_at,
               discipline, activity_type, duration_seconds, distance_meters, ascent_meters, calories,
               avg_hr, max_hr, avg_power, normalized_power, training_load,
               avg_pace_seconds_per_km, perceived_exertion, subjective_feeling,
               quality_status, quality_checked_at, quality_rule_version,
               quality_decision_count, quality_limited_metric_count, notes
        FROM exec_activities
        WHERE season_id = ? AND activity_date = ?
        ORDER BY COALESCE(started_at, activity_date) ASC, activity_id ASC
        """,
        (season_id, target_date),
    )

    day_metrics = fetch_all(
        connection,
        """
        SELECT daily_metric_id, season_id, metric_date, source_system, weight_kg, sleep_hours,
               sleep_quality, resting_hr, hrv, body_battery, stress_avg, stress_max,
               spo2_avg, spo2_sleep_avg, spo2_7d_avg, spo2_lowest,
               subjective_energy, subjective_fatigue, soreness, notes,
               vo2max_cycling, vo2max_running, lactate_threshold_hr
        FROM exec_daily_metrics
        WHERE season_id = ? AND metric_date = ?
        ORDER BY CASE WHEN source_system = 'garmin' THEN 0 ELSE 1 END, daily_metric_id DESC
        """,
        (season_id, target_date),
    )

    day_reviews = fetch_all(
        connection,
        """
        SELECT daily_review_id, season_id, review_date, block_id, week_id, planned_session_id,
               planned_summary, actual_summary, compliance_status, general_feeling,
               perceived_recovery, motivation, observations, next_day_decision
        FROM review_daily_reviews
        WHERE season_id = ? AND review_date = ?
        ORDER BY planned_session_id
        """,
        (season_id, target_date),
    )

    week_context = fetch_one(
        connection,
        """
        SELECT mw.week_id, mw.week_code, mw.week_role, mw.start_date, mw.end_date,
               mw.target_volume_hours_min, mw.target_volume_hours_max,
               mb.block_id, mb.block_code, mb.block_name, mb.phase_name
        FROM plan_micro_weeks mw
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        WHERE mw.start_date <= ? AND mw.end_date >= ?
        ORDER BY mw.start_date DESC
        LIMIT 1
        """,
        (target_date, target_date),
    )

    weekly_review = None
    if week_context is not None:
        weekly_review = fetch_one(
            connection,
            """
            SELECT weekly_review_id, season_id, block_id, week_id, review_status, closed_at,
                   adherence_rate, traceability_rate, actual_minutes, planned_reference_minutes,
                   volume_delta_minutes, risk_level, recommendation_text, summary_text,
                   created_at, updated_at
            FROM review_weekly_reviews
            WHERE week_id = ?
            """,
            (week_context["week_id"],),
        )

    recent_activities = load_recent_activities(connection, season_id, target_date, args.history_days)
    all_activity_ids = [int(activity["activity_id"]) for activity in day_activities + recent_activities]
    zone_summaries = group_zone_summaries(connection, sorted(set(all_activity_ids)))

    for activity in day_activities:
        activity["zone_summaries"] = zone_summaries.get(int(activity["activity_id"]), [])
        modeled_load = load_activity_modeled_load(connection, int(activity["activity_id"]), season_id)
        if modeled_load is not None:
            activity["modeled_load_value"] = modeled_load.get("load_value")
            activity["modeled_load_source"] = modeled_load.get("load_source")
    enrich_activities_with_weather(day_activities)
    for activity in recent_activities:
        activity["zone_summaries"] = zone_summaries.get(int(activity["activity_id"]), [])

    load_model = load_load_model_snapshot(season_id, target_date)
    metric_activity, metric_trigger_reasons = select_metric_analysis_activity(day_activities, linked_rows)
    activity_metric_analysis = None
    if metric_activity is not None:
        activity_metric_analysis = {
            "selected_activity_id": int(metric_activity["activity_id"]),
            "trigger_reasons": metric_trigger_reasons,
            "analysis": load_activity_metric_analysis(connection, int(metric_activity["activity_id"])),
        }
    activity_weather_analysis = None
    if metric_activity is not None:
        activity_weather_analysis = {
            "selected_activity_id": int(metric_activity["activity_id"]),
            "trigger_reasons": metric_trigger_reasons,
            "weather": metric_activity.get("weather"),
            "analysis": metric_activity.get("weather_analysis"),
        }

    payload = {
        "metadata": {
            "target_date": target_date,
            "season_id": season_id,
            "database_path": str(Path(args.db).resolve()),
            "history_days": args.history_days,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "season": season,
        "week_context": week_context,
        "planned_sessions": planned_sessions,
        "linked_execution": linked_rows,
        "daily_reviews": day_reviews,
        "weekly_review": weekly_review,
        "daily_metrics": day_metrics,
        "load_model": load_model,
        "activity_metric_analysis": activity_metric_analysis,
        "activity_weather_analysis": activity_weather_analysis,
        "day_activities": day_activities,
        "recent_activities": recent_activities,
        "available_data": {
            "planned_session_count": len(planned_sessions),
            "linked_execution_count": len(linked_rows),
            "day_activity_count": len(day_activities),
            "daily_metric_count": len(day_metrics),
            "daily_review_count": len(day_reviews),
            "has_weekly_review": weekly_review is not None,
            "has_load_model": load_model is not None,
            "has_activity_metric_analysis": activity_metric_analysis is not None,
            "day_activity_weather_count": sum(1 for activity in day_activities if activity.get("weather") is not None),
            "has_activity_weather_analysis": activity_weather_analysis is not None and activity_weather_analysis.get("analysis") is not None,
        },
    }

    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())