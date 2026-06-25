#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
DAY_CONTEXT_SCRIPT = REPO_ROOT / ".github" / "skills" / "daily-performance-assessment" / "scripts" / "build_day_context.py"
BACKEND_ROOT = REPO_ROOT / "GUI" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.planned_prescriptions import get_planned_session_prescription, project_planned_session_row_from_prescription


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a normalized JSON context bundle for one training week.")
    parser.add_argument("--week-id", type=int, help="Target week id. If omitted, infer from date.")
    parser.add_argument("--date", help="Any ISO date inside the target week, for example 2026-05-29")
    parser.add_argument("--season", type=int, help="Optional season id. If omitted, infer from week.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    return parser.parse_args()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return row_to_dict(connection.execute(query, params).fetchone())


def fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    rows = connection.execute(query, params).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]


def resolve_week(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    if args.week_id is not None:
        row = fetch_one(connection, """
            SELECT mw.week_id, mw.week_code, mw.week_role, mw.objective_primary, mw.start_date, mw.end_date,
                   mw.target_volume_hours_min, mw.target_volume_hours_max,
                   mb.block_id, mb.block_code, mb.block_name, mb.phase_name, mb.season_id
            FROM plan_micro_weeks mw
            JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
            WHERE mw.week_id = ?
        """, (args.week_id,))
        if row is None:
            raise SystemExit(f"No existe la semana {args.week_id}")
        return row

    if not args.date:
        raise SystemExit("Provide --week-id or --date")

    row = fetch_one(connection, """
        SELECT mw.week_id, mw.week_code, mw.week_role, mw.objective_primary, mw.start_date, mw.end_date,
               mw.target_volume_hours_min, mw.target_volume_hours_max,
               mb.block_id, mb.block_code, mb.block_name, mb.phase_name, mb.season_id
        FROM plan_micro_weeks mw
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        WHERE mw.start_date <= ? AND mw.end_date >= ?
        ORDER BY mw.start_date DESC
        LIMIT 1
    """, (args.date, args.date))
    if row is None:
        raise SystemExit(f"No existe semana para la fecha {args.date}")
    return row


def load_weekly_metrics(week_id: int) -> dict[str, Any]:
    backend_path = str(REPO_ROOT / "GUI" / "backend")
    sys.path.insert(0, backend_path)
    try:
        from app.main import calculate_weekly_review_metrics, get_week_plan_vs_real_rows  # type: ignore
        from app.training_zones import get_week_zone_coherence_assessment, get_week_zone_comparison_summary  # type: ignore
        return {
            "review_metrics": calculate_weekly_review_metrics(week_id),
            "plan_vs_real_rows": get_week_plan_vs_real_rows(week_id),
            "zone_comparison_summary": get_week_zone_comparison_summary(week_id),
            "zone_coherence_assessment": get_week_zone_coherence_assessment(week_id),
        }
    finally:
        if backend_path in sys.path:
            sys.path.remove(backend_path)


def build_day_bundle(target_date: str, season_id: int, db_path: str) -> dict[str, Any]:
    result = subprocess.run([
        "python", str(DAY_CONTEXT_SCRIPT), "--date", target_date, "--season", str(season_id), "--db", db_path
    ], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def iter_week_dates(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def main() -> int:
    args = parse_args()
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    week = resolve_week(connection, args)
    season_id = args.season or int(week["season_id"])
    season = fetch_one(connection, "SELECT season_id, season_code, season_name, start_date, end_date, status FROM plan_seasons WHERE season_id = ?", (season_id,))
    weekly_review = fetch_one(connection, """
        SELECT weekly_review_id, season_id, block_id, week_id, review_status, closed_at,
               adherence_rate, traceability_rate, actual_minutes, planned_reference_minutes,
               volume_delta_minutes, risk_level, recommendation_text, summary_text,
               created_at, updated_at
        FROM review_weekly_reviews
        WHERE week_id = ?
    """, (week["week_id"],))
    planned_sessions = fetch_all(connection, """
        SELECT planned_session_id, session_date, day_name, sequence_in_week, planned_type,
               objective, primary_session, complementary_session, notes, is_key_session,
               intensity_class, duration_min, duration_max, adjustment_rule
        FROM plan_planned_sessions
        WHERE week_id = ?
        ORDER BY sequence_in_week, planned_session_id
    """, (week["week_id"],))
    for session in planned_sessions:
        prescription = get_planned_session_prescription(connection, int(session["planned_session_id"]))
        session.update(project_planned_session_row_from_prescription(session, prescription))
    next_week = fetch_one(connection, """
        SELECT mw.week_id, mw.week_code, mw.week_role, mw.objective_primary, mw.start_date, mw.end_date,
               mw.target_volume_hours_min, mw.target_volume_hours_max,
               mb.block_id, mb.block_code, mb.block_name, mb.phase_name, mb.season_id
        FROM plan_micro_weeks mw
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        WHERE mb.season_id = ? AND mw.start_date > ?
        ORDER BY mw.start_date ASC
        LIMIT 1
    """, (season_id, week["end_date"]))
    next_week_sessions = []
    if next_week is not None:
        next_week_sessions = fetch_all(connection, """
            SELECT planned_session_id, session_date, day_name, sequence_in_week, planned_type,
                   objective, primary_session, complementary_session, notes, is_key_session,
                   intensity_class, duration_min, duration_max, adjustment_rule
            FROM plan_planned_sessions
            WHERE week_id = ?
            ORDER BY sequence_in_week, planned_session_id
        """, (next_week["week_id"],))
        for session in next_week_sessions:
            prescription = get_planned_session_prescription(connection, int(session["planned_session_id"]))
            session.update(project_planned_session_row_from_prescription(session, prescription))

    metrics_bundle = load_weekly_metrics(int(week["week_id"]))
    day_bundles = [build_day_bundle(day, season_id, args.db) for day in iter_week_dates(str(week["start_date"]), str(week["end_date"]))]

    payload = {
        "metadata": {
            "week_id": week["week_id"],
            "season_id": season_id,
            "database_path": str(Path(args.db).resolve()),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "season": season,
        "week_context": week,
        "planned_sessions": planned_sessions,
        "weekly_review": weekly_review,
        "review_metrics": metrics_bundle["review_metrics"],
        "plan_vs_real_rows": metrics_bundle["plan_vs_real_rows"],
        "zone_comparison_summary": metrics_bundle["zone_comparison_summary"],
        "zone_coherence_assessment": metrics_bundle["zone_coherence_assessment"],
        "days": day_bundles,
        "next_week_context": next_week,
        "next_week_planned_sessions": next_week_sessions,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
