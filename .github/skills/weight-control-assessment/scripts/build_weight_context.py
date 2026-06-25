#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import pstdev
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
BACKEND_ROOT = REPO_ROOT / "GUI" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.planned_prescriptions import get_planned_session_prescription, project_planned_session_row_from_prescription


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a normalized JSON context bundle for weight-control assessment.")
    parser.add_argument("--date", required=True, help="Target ISO date, for example 2026-06-05")
    parser.add_argument("--season", type=int, help="Optional season id. If omitted, infer from date.")
    parser.add_argument("--history-days", type=int, default=42, help="History window in days for trend context")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    return parser.parse_args()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return row_to_dict(connection.execute(query, params).fetchone())


def fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def resolve_season(connection: sqlite3.Connection, target_date: str, season_id: int | None) -> dict[str, Any]:
    if season_id is not None:
        row = fetch_one(
            connection,
            "SELECT season_id, season_code, season_name, start_date, end_date, status FROM plan_seasons WHERE season_id = ?",
            (season_id,),
        )
    else:
        row = fetch_one(
            connection,
            """
            SELECT season_id, season_code, season_name, start_date, end_date, status
            FROM plan_seasons
            WHERE start_date <= ? AND end_date >= ?
            ORDER BY start_date DESC
            LIMIT 1
            """,
            (target_date, target_date),
        )
    if row is None:
        raise SystemExit(f"No season found for date {target_date}")
    return row


def resolve_week_context(connection: sqlite3.Connection, target_date: str, season_id: int) -> dict[str, Any] | None:
    return fetch_one(
        connection,
        """
        SELECT mw.week_id, mw.week_code, mw.week_role, mw.objective_primary, mw.key_risk, mw.weight_goal,
               mw.start_date, mw.end_date, mw.target_volume_hours_min, mw.target_volume_hours_max,
               mb.block_id, mb.block_code, mb.block_name, mb.phase_name,
               mb.objective_primary AS block_objective_primary,
               mb.objective_complementary AS block_objective_complementary
        FROM plan_micro_weeks mw
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        WHERE mb.season_id = ?
          AND mw.start_date <= ?
          AND mw.end_date >= ?
        ORDER BY mw.start_date DESC
        LIMIT 1
        """,
        (season_id, target_date, target_date),
    )


def compute_rolling_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def compute_previous_rolling_average(values: list[float], window: int) -> float | None:
    if len(values) < window * 2:
        return None
    return sum(values[-window * 2 : -window]) / window


def parse_measurement_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if "T" not in text and " " not in text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def select_weight_rows_for_trend(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred_by_date: dict[str, dict[str, Any]] = {}

    def rank(row: dict[str, Any]) -> tuple[int, datetime, int, int]:
        measured_at = parse_measurement_timestamp(row.get("weight_measured_at"))
        system_rank = 0 if row.get("source_system") == "garmin" else 1
        sort_dt = measured_at or datetime.max.replace(tzinfo=timezone.utc)
        row_id = int(row.get("daily_metric_id") or 0)
        return (0 if measured_at is not None else 1, sort_dt, system_rank, row_id)

    for row in rows:
        metric_date = row["metric_date"]
        existing = preferred_by_date.get(metric_date)
        if existing is None or rank(row) < rank(existing):
            preferred_by_date[metric_date] = row

    return [preferred_by_date[key] for key in sorted(preferred_by_date)]


def summarize_series(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return {
            "samples": 0,
            "latest": None,
            "first": None,
            "net_change": None,
            "latest_7d_avg": None,
            "previous_7d_avg": None,
            "delta_7d_avg": None,
            "latest_14d_avg": None,
            "previous_14d_avg": None,
            "delta_14d_avg": None,
            "volatility_7d": None,
        }

    latest_7d_avg = compute_rolling_average(values, 7)
    previous_7d_avg = compute_previous_rolling_average(values, 7)
    latest_14d_avg = compute_rolling_average(values, 14)
    previous_14d_avg = compute_previous_rolling_average(values, 14)
    volatility_7d = pstdev(values[-7:]) if len(values) >= 7 else None
    return {
        "samples": len(values),
        "latest": round(values[-1], 2),
        "first": round(values[0], 2),
        "net_change": round(values[-1] - values[0], 2) if len(values) >= 2 else None,
        "latest_7d_avg": round(latest_7d_avg, 2) if latest_7d_avg is not None else None,
        "previous_7d_avg": round(previous_7d_avg, 2) if previous_7d_avg is not None else None,
        "delta_7d_avg": round(latest_7d_avg - previous_7d_avg, 2)
        if latest_7d_avg is not None and previous_7d_avg is not None
        else None,
        "latest_14d_avg": round(latest_14d_avg, 2) if latest_14d_avg is not None else None,
        "previous_14d_avg": round(previous_14d_avg, 2) if previous_14d_avg is not None else None,
        "delta_14d_avg": round(latest_14d_avg - previous_14d_avg, 2)
        if latest_14d_avg is not None and previous_14d_avg is not None
        else None,
        "volatility_7d": round(volatility_7d, 2) if volatility_7d is not None else None,
    }


def summarize_weight_history(weight_rows: list[dict[str, Any]], target_weight: float | None, reference_weight: float | None) -> dict[str, Any]:
    weights = [float(row["weight_kg"]) for row in weight_rows if row.get("weight_kg") is not None]
    dates = [row["metric_date"] for row in weight_rows]
    latest_row = weight_rows[-1] if weight_rows else None
    latest_weight = weights[-1] if weights else None
    latest_7d_avg = compute_rolling_average(weights, 7)
    previous_7d_avg = compute_previous_rolling_average(weights, 7)
    latest_14d_avg = compute_rolling_average(weights, 14)
    previous_14d_avg = compute_previous_rolling_average(weights, 14)
    volatility_7d = pstdev(weights[-7:]) if len(weights) >= 7 else None
    timestamped_sample_days = sum(1 for row in weight_rows if row.get("weight_measured_at") is not None)
    return {
        "samples": len(weights),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "latest_weight_kg": round(latest_weight, 2) if latest_weight is not None else None,
        "latest_weight_measured_at": latest_row.get("weight_measured_at") if latest_row else None,
        "latest_weight_measurement_source": latest_row.get("weight_measurement_source") if latest_row else None,
        "timestamped_sample_days": timestamped_sample_days,
        "aggregate_sample_days": len(weights) - timestamped_sample_days,
        "selection_policy": "earliest_timestamp_then_aggregate",
        "first_weight_kg": round(weights[0], 2) if weights else None,
        "net_change_kg": round(weights[-1] - weights[0], 2) if len(weights) >= 2 else None,
        "latest_7d_avg_kg": round(latest_7d_avg, 2) if latest_7d_avg is not None else None,
        "previous_7d_avg_kg": round(previous_7d_avg, 2) if previous_7d_avg is not None else None,
        "delta_7d_avg_kg": round(latest_7d_avg - previous_7d_avg, 2)
        if latest_7d_avg is not None and previous_7d_avg is not None
        else None,
        "latest_14d_avg_kg": round(latest_14d_avg, 2) if latest_14d_avg is not None else None,
        "previous_14d_avg_kg": round(previous_14d_avg, 2) if previous_14d_avg is not None else None,
        "delta_14d_avg_kg": round(latest_14d_avg - previous_14d_avg, 2)
        if latest_14d_avg is not None and previous_14d_avg is not None
        else None,
        "volatility_7d_kg": round(volatility_7d, 2) if volatility_7d is not None else None,
        "gap_to_target_kg": round(latest_weight - target_weight, 2)
        if latest_weight is not None and target_weight is not None
        else None,
        "gap_to_reference_kg": round(latest_weight - reference_weight, 2)
        if latest_weight is not None and reference_weight is not None
        else None,
        "body_composition": {
            "body_fat_pct": summarize_series(weight_rows, "body_fat_pct"),
            "body_water_pct": summarize_series(weight_rows, "body_water_pct"),
            "muscle_mass_kg": summarize_series(weight_rows, "muscle_mass_kg"),
            "bone_mass_kg": summarize_series(weight_rows, "bone_mass_kg"),
            "bmi": summarize_series(weight_rows, "bmi"),
            "visceral_fat": summarize_series(weight_rows, "visceral_fat"),
            "metabolic_age": summarize_series(weight_rows, "metabolic_age"),
            "physique_rating": summarize_series(weight_rows, "physique_rating"),
        },
    }


def load_recent_load_context(target_date: str, season_id: int, history_days: int) -> dict[str, Any]:
    backend_path = str(REPO_ROOT / "GUI" / "backend")
    sys.path.insert(0, backend_path)
    try:
        from app.load_engine import get_load_model_snapshot  # type: ignore

        snapshot = get_load_model_snapshot(season_id=season_id, metric_date=target_date)
    finally:
        if backend_path in sys.path:
            sys.path.remove(backend_path)

    cutoff = (date.fromisoformat(target_date) - timedelta(days=history_days - 1)).isoformat()
    snapshot["trend"] = [row for row in snapshot.get("trend", []) if row["metric_date"] >= cutoff]
    return snapshot


def build_daily_metric_projection(connection: sqlite3.Connection) -> tuple[str, str]:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(exec_daily_metrics)").fetchall()}
    weight_measured_at_expr = "weight_measured_at" if "weight_measured_at" in columns else "NULL AS weight_measured_at"
    weight_measurement_source_expr = (
        "weight_measurement_source" if "weight_measurement_source" in columns else "NULL AS weight_measurement_source"
    )
    return weight_measured_at_expr, weight_measurement_source_expr


def main() -> int:
    args = parse_args()
    target_day = date.fromisoformat(args.date)
    window_start = (target_day - timedelta(days=args.history_days - 1)).isoformat()

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    season = resolve_season(connection, args.date, args.season)
    season_id = int(season["season_id"])
    profile = fetch_one(
        connection,
        """
        SELECT season_id, alias, age_years, height_cm, reference_weight_kg, target_weight_kg,
               current_form, baseline_fatigue, current_strength, recovery_profile,
               primary_sport, secondary_sports, best_tolerated_training, worst_tolerated_training,
               availability_notes, support_routine
        FROM plan_user_profiles
        WHERE season_id = ?
        """,
        (season_id,),
    )
    macro = fetch_one(
        connection,
        """
        SELECT macro_id, title, objective_statement, priorities, progression_rules,
               weight_rules, success_criteria, prudence_criteria
        FROM plan_macro_cycles
        WHERE season_id = ?
        ORDER BY macro_id ASC
        LIMIT 1
        """,
        (season_id,),
    )
    week_context = resolve_week_context(connection, args.date, season_id)
    weight_measured_at_expr, weight_measurement_source_expr = build_daily_metric_projection(connection)

    target_metric = fetch_one(
        connection,
        f"""
         SELECT daily_metric_id, metric_date, source_system, weight_kg,
             {weight_measured_at_expr}, {weight_measurement_source_expr},
             body_fat_pct, body_water_pct, bone_mass_kg, muscle_mass_kg,
             bmi, visceral_fat, metabolic_age, physique_rating,
             sleep_hours, sleep_quality,
             resting_hr, hrv, body_battery, stress_avg, stress_max, subjective_energy,
               subjective_fatigue, soreness, notes
        FROM exec_daily_metrics
        WHERE season_id = ? AND metric_date = ?
        ORDER BY CASE
                                     WHEN weight_measured_at IS NOT NULL THEN 0
                                     WHEN source_system = 'garmin' THEN 1
                                     ELSE 2
                 END,
                 weight_measured_at ASC,
                 daily_metric_id DESC
        LIMIT 1
        """,
        (season_id, args.date),
    )
    weight_history = fetch_all(
        connection,
        f"""
         SELECT daily_metric_id, metric_date, source_system, weight_kg,
             {weight_measured_at_expr}, {weight_measurement_source_expr},
             body_fat_pct, body_water_pct, bone_mass_kg, muscle_mass_kg,
             bmi, visceral_fat, metabolic_age, physique_rating,
             sleep_hours, resting_hr, hrv,
               body_battery, stress_avg, subjective_energy, subjective_fatigue, soreness
        FROM exec_daily_metrics
        WHERE season_id = ?
          AND metric_date >= ?
          AND metric_date <= ?
          AND weight_kg IS NOT NULL
        ORDER BY metric_date ASC, daily_metric_id ASC
                """,
        (season_id, window_start, args.date),
    )
    weight_history = select_weight_rows_for_trend(weight_history)
    daily_dashboard = fetch_all(
        connection,
        """
        SELECT metric_date, weight_kg, sleep_hours, resting_hr, hrv, subjective_energy,
               subjective_fatigue, activities_count, total_activity_hours
        FROM vw_exec_daily_dashboard
        WHERE metric_date >= ? AND metric_date <= ?
        ORDER BY metric_date ASC
        """,
        (window_start, args.date),
    )
    recent_reviews = fetch_all(
        connection,
        """
        SELECT review_date, compliance_status, general_feeling, perceived_recovery,
               motivation, observations, next_day_decision
        FROM review_daily_reviews
        WHERE season_id = ?
          AND review_date >= ?
          AND review_date <= ?
        ORDER BY review_date ASC, daily_review_id ASC
        """,
        (season_id, window_start, args.date),
    )
    current_week_sessions = []
    if week_context is not None:
        current_week_sessions = fetch_all(
            connection,
            """
            SELECT planned_session_id, session_date, day_name, planned_type, objective,
                   primary_session, complementary_session, is_key_session, duration_min, duration_max
            FROM plan_planned_sessions
            WHERE week_id = ?
            ORDER BY sequence_in_week ASC
            """,
            (week_context["week_id"],),
        )
        for session in current_week_sessions:
            prescription = get_planned_session_prescription(connection, int(session["planned_session_id"]))
            session.update(project_planned_session_row_from_prescription(session, prescription))
    weight_summary = summarize_weight_history(
        weight_history,
        target_weight=float(profile["target_weight_kg"]) if profile and profile.get("target_weight_kg") is not None else None,
        reference_weight=float(profile["reference_weight_kg"]) if profile and profile.get("reference_weight_kg") is not None else None,
    )
    load_context = load_recent_load_context(args.date, season_id, args.history_days)

    payload = {
        "metadata": {
            "target_date": args.date,
            "season_id": season_id,
            "database_path": str(Path(args.db).resolve()),
            "history_days": args.history_days,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "season": season,
        "profile": profile,
        "macro_context": macro,
        "week_context": week_context,
        "target_day_metrics": target_metric,
        "weight_history": weight_history,
        "weight_summary": weight_summary,
        "daily_dashboard": daily_dashboard,
        "load_context": load_context,
        "recent_daily_reviews": recent_reviews,
        "current_week_sessions": current_week_sessions,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())