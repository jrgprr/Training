#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
WEEK_CONTEXT_SCRIPT = REPO_ROOT / ".github" / "skills" / "weekly-performance-assessment" / "scripts" / "build_week_context.py"

COMPLETED_STATUSES = {"completed", "completed_with_adjustment", "completed_but_over_target"}
ADHERENT_STATUSES = COMPLETED_STATUSES | {"partial"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a normalized JSON context bundle for one training block.")
    parser.add_argument("--block-id", type=int, help="Target block id")
    parser.add_argument("--block-code", help="Target block code, for example B1")
    parser.add_argument("--date", help="Any ISO date inside the target block, for example 2026-06-14")
    parser.add_argument("--season", type=int, help="Optional season id. If omitted, infer from block context.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    return parser.parse_args()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return row_to_dict(connection.execute(query, params).fetchone())


def fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in connection.execute(query, params).fetchall() if row is not None]


def resolve_block(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    if args.block_id is not None:
        row = fetch_one(
            connection,
            """
            SELECT block_id, season_id, block_code, block_name, phase_name, sequence_order,
                   start_date, end_date, duration_weeks_min, duration_weeks_max,
                   objective_primary, objective_secondary, objective_complementary,
                   entry_criteria, exit_criteria, key_risks, micro_pattern,
                   progression_logic, markdown_path
            FROM plan_meso_blocks
            WHERE block_id = ?
            """,
            (args.block_id,),
        )
        if row is None:
            raise SystemExit(f"No existe el bloque {args.block_id}")
        return row

    if args.block_code:
        season_filter = " AND season_id = ?" if args.season is not None else ""
        params: tuple[Any, ...] = (args.block_code, args.season) if args.season is not None else (args.block_code,)
        row = fetch_one(
            connection,
            f"""
            SELECT block_id, season_id, block_code, block_name, phase_name, sequence_order,
                   start_date, end_date, duration_weeks_min, duration_weeks_max,
                   objective_primary, objective_secondary, objective_complementary,
                   entry_criteria, exit_criteria, key_risks, micro_pattern,
                   progression_logic, markdown_path
            FROM plan_meso_blocks
            WHERE block_code = ?{season_filter}
            ORDER BY sequence_order
            LIMIT 1
            """,
            params,
        )
        if row is None:
            raise SystemExit(f"No existe el bloque {args.block_code}")
        return row

    if args.date:
        row = fetch_one(
            connection,
            """
            SELECT mb.block_id, mb.season_id, mb.block_code, mb.block_name, mb.phase_name, mb.sequence_order,
                   mb.start_date, mb.end_date, mb.duration_weeks_min, mb.duration_weeks_max,
                   mb.objective_primary, mb.objective_secondary, mb.objective_complementary,
                   mb.entry_criteria, mb.exit_criteria, mb.key_risks, mb.micro_pattern,
                   mb.progression_logic, mb.markdown_path
            FROM plan_micro_weeks mw
            JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
            WHERE mw.start_date <= ? AND mw.end_date >= ?
            ORDER BY mw.start_date DESC
            LIMIT 1
            """,
            (args.date, args.date),
        )
        if row is None:
            raise SystemExit(f"No existe bloque para la fecha {args.date}")
        return row

    raise SystemExit("Provide --block-id, --block-code, or --date")


def resolve_block_dates(connection: sqlite3.Connection, block: dict[str, Any]) -> tuple[str, str]:
    if block.get("start_date") and block.get("end_date"):
        return str(block["start_date"]), str(block["end_date"])

    row = connection.execute(
        "SELECT MIN(start_date), MAX(end_date) FROM plan_micro_weeks WHERE block_id = ?",
        (block["block_id"],),
    ).fetchone()
    if row is None or row[0] is None or row[1] is None:
        raise SystemExit(f"No hay semanas para resolver las fechas del bloque {block['block_id']}")
    return str(row[0]), str(row[1])


def build_week_bundle(week_id: int, season_id: int, db_path: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(WEEK_CONTEXT_SCRIPT), "--week-id", str(week_id), "--season", str(season_id), "--db", db_path],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def load_daily_trend(connection: sqlite3.Connection, season_id: int, start_date: str, end_date: str) -> list[dict[str, Any]]:
    backend_path = str(REPO_ROOT / "GUI" / "backend")
    sys.path.insert(0, backend_path)
    try:
        from app.load_engine import get_load_model_snapshot  # type: ignore

        rows = fetch_all(
            connection,
            """
            SELECT metric_date, sleep_hours, resting_hr, stress_avg, weight_kg,
                   hrv, body_battery, subjective_energy, subjective_fatigue, soreness
            FROM exec_daily_metrics
            WHERE season_id = ? AND metric_date BETWEEN ? AND ?
            ORDER BY metric_date
            """,
            (season_id, start_date, end_date),
        )
        trend: list[dict[str, Any]] = []
        for row in rows:
            snapshot = get_load_model_snapshot(season_id=season_id, metric_date=str(row["metric_date"]))
            trend.append(
                {
                    **row,
                    "load_model": snapshot,
                }
            )
        return trend
    finally:
        if backend_path in sys.path:
            sys.path.remove(backend_path)


def compute_block_summary(week_bundles: list[dict[str, Any]], daily_trend: list[dict[str, Any]]) -> dict[str, Any]:
    all_rows = [row for bundle in week_bundles for row in bundle.get("plan_vs_real_rows", [])]
    review_metrics = [bundle.get("review_metrics", {}) for bundle in week_bundles]

    total_sessions = len(all_rows)
    completed_sessions = sum(1 for row in all_rows if row.get("compliance_status") in COMPLETED_STATUSES)
    partial_sessions = sum(1 for row in all_rows if row.get("compliance_status") == "partial")
    pending_sessions = sum(1 for row in all_rows if row.get("compliance_status") == "pending")
    skipped_sessions = sum(1 for row in all_rows if row.get("compliance_status") == "skipped")
    replaced_sessions = sum(1 for row in all_rows if row.get("compliance_status") == "replaced")
    adherent_sessions = sum(1 for row in all_rows if row.get("compliance_status") in ADHERENT_STATUSES)
    tracked_sessions = total_sessions - pending_sessions

    key_rows = [row for row in all_rows if row.get("is_key_session")]
    key_sessions_total = len(key_rows)
    key_sessions_closed = sum(1 for row in key_rows if row.get("compliance_status") in ADHERENT_STATUSES)

    planned_reference_minutes = sum(int(metric.get("planned_reference_minutes") or 0) for metric in review_metrics)
    actual_minutes = sum(int(metric.get("actual_minutes") or 0) for metric in review_metrics)
    volume_delta_minutes = actual_minutes - planned_reference_minutes

    zone_summary_items = [item for bundle in week_bundles for item in bundle.get("zone_comparison_summary", {}).get("items", [])]
    aligned_zone_sessions = sum(int(item.get("aligned_count") or 0) for item in zone_summary_items)
    limited_zone_sessions = sum(int(item.get("limited_count") or 0) for item in zone_summary_items)
    misaligned_zone_sessions = sum(int(item.get("misaligned_count") or 0) for item in zone_summary_items)

    load_points = [day for day in daily_trend if isinstance(day.get("load_model"), dict)]
    loads = [float(day["load_model"].get("daily_training_load") or 0) for day in load_points]
    tsb_values = [float(day["load_model"].get("tsb")) for day in load_points if day["load_model"].get("tsb") is not None]
    atl_values = [float(day["load_model"].get("atl")) for day in load_points if day["load_model"].get("atl") is not None]
    ctl_values = [float(day["load_model"].get("ctl")) for day in load_points if day["load_model"].get("ctl") is not None]

    sleep_values = [float(day["sleep_hours"]) for day in daily_trend if day.get("sleep_hours") is not None]
    resting_hr_values = [float(day["resting_hr"]) for day in daily_trend if day.get("resting_hr") is not None]
    stress_values = [float(day["stress_avg"]) for day in daily_trend if day.get("stress_avg") is not None]
    weight_values = [float(day["weight_kg"]) for day in daily_trend if day.get("weight_kg") is not None]

    return {
        "weeks_in_block": len(week_bundles),
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "partial_sessions": partial_sessions,
        "pending_sessions": pending_sessions,
        "skipped_sessions": skipped_sessions,
        "replaced_sessions": replaced_sessions,
        "adherence_rate": round((adherent_sessions / total_sessions) * 100, 2) if total_sessions else 0.0,
        "traceability_rate": round((tracked_sessions / total_sessions) * 100, 2) if total_sessions else 0.0,
        "planned_reference_minutes": planned_reference_minutes,
        "actual_minutes": actual_minutes,
        "volume_delta_minutes": volume_delta_minutes,
        "key_sessions_total": key_sessions_total,
        "key_sessions_closed": key_sessions_closed,
        "aligned_zone_sessions": aligned_zone_sessions,
        "limited_zone_sessions": limited_zone_sessions,
        "misaligned_zone_sessions": misaligned_zone_sessions,
        "daily_training_load_total": round(sum(loads), 2) if loads else None,
        "daily_training_load_peak": round(max(loads), 2) if loads else None,
        "starting_tsb": round(tsb_values[0], 2) if tsb_values else None,
        "ending_tsb": round(tsb_values[-1], 2) if tsb_values else None,
        "lowest_tsb": round(min(tsb_values), 2) if tsb_values else None,
        "starting_atl": round(atl_values[0], 2) if atl_values else None,
        "ending_atl": round(atl_values[-1], 2) if atl_values else None,
        "starting_ctl": round(ctl_values[0], 2) if ctl_values else None,
        "ending_ctl": round(ctl_values[-1], 2) if ctl_values else None,
        "avg_sleep_hours": round(sum(sleep_values) / len(sleep_values), 2) if sleep_values else None,
        "avg_resting_hr": round(sum(resting_hr_values) / len(resting_hr_values), 2) if resting_hr_values else None,
        "avg_stress": round(sum(stress_values) / len(stress_values), 2) if stress_values else None,
        "starting_weight_kg": round(weight_values[0], 2) if weight_values else None,
        "ending_weight_kg": round(weight_values[-1], 2) if weight_values else None,
        "weight_delta_kg": round(weight_values[-1] - weight_values[0], 2) if len(weight_values) >= 2 else None,
    }


def main() -> int:
    args = parse_args()
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    block = resolve_block(connection, args)
    start_date, end_date = resolve_block_dates(connection, block)
    season_id = args.season or int(block["season_id"])

    season = fetch_one(
        connection,
        "SELECT season_id, season_code, season_name, start_date, end_date, status FROM plan_seasons WHERE season_id = ?",
        (season_id,),
    )
    macro_context = fetch_one(
        connection,
        """
        SELECT macro_id, season_id, title, objective_statement, context_summary, priorities,
               progression_rules, weight_rules, success_criteria, prudence_criteria,
               closing_rule, markdown_path
        FROM plan_macro_cycles
        WHERE season_id = ?
        ORDER BY macro_id DESC
        LIMIT 1
        """,
        (season_id,),
    )
    weeks = fetch_all(
        connection,
        """
        SELECT mw.week_id, mw.week_code, mw.sequence_in_block, mw.start_date, mw.end_date,
               mw.week_role, mw.entry_state, mw.objective_primary, mw.objective_secondary,
               mw.key_risk, mw.weight_goal, mw.target_volume_hours_min, mw.target_volume_hours_max,
               mw.key_days, mw.support_days, mw.closure_rule, mw.markdown_path,
               rwr.weekly_review_id, rwr.review_status, rwr.closed_at, rwr.adherence_rate,
               rwr.traceability_rate, rwr.actual_minutes, rwr.planned_reference_minutes,
               rwr.volume_delta_minutes, rwr.risk_level, rwr.recommendation_text, rwr.summary_text
        FROM plan_micro_weeks mw
        LEFT JOIN review_weekly_reviews rwr ON rwr.week_id = mw.week_id
        WHERE mw.block_id = ?
        ORDER BY mw.sequence_in_block, mw.week_id
        """,
        (block["block_id"],),
    )
    previous_block = fetch_one(
        connection,
        """
        SELECT block_id, season_id, block_code, block_name, phase_name, sequence_order,
               start_date, end_date, objective_primary, exit_criteria
        FROM plan_meso_blocks
        WHERE season_id = ? AND sequence_order < ?
        ORDER BY sequence_order DESC
        LIMIT 1
        """,
        (season_id, block["sequence_order"]),
    )
    next_block = fetch_one(
        connection,
        """
        SELECT block_id, season_id, block_code, block_name, phase_name, sequence_order,
               start_date, end_date, objective_primary, exit_criteria
        FROM plan_meso_blocks
        WHERE season_id = ? AND sequence_order > ?
        ORDER BY sequence_order ASC
        LIMIT 1
        """,
        (season_id, block["sequence_order"]),
    )
    weight_reviews = fetch_all(
        connection,
        """
         SELECT weight_review_id, review_date, reference_weight_kg, target_weight_kg,
             latest_weight_kg, latest_7d_avg_kg, delta_7d_avg_kg,
             latest_14d_avg_kg, delta_14d_avg_kg, volatility_7d_kg, gap_to_target_kg,
               classification, recommendation_text, summary_text
        FROM review_weight_reviews
        WHERE season_id = ? AND review_date BETWEEN ? AND ?
        ORDER BY review_date
        """,
        (season_id, start_date, end_date),
    )

    week_bundles = [build_week_bundle(int(week["week_id"]), season_id, args.db) for week in weeks]
    daily_trend = load_daily_trend(connection, season_id, start_date, end_date)
    block_summary = compute_block_summary(week_bundles, daily_trend)

    payload = {
        "metadata": {
            "block_id": block["block_id"],
            "season_id": season_id,
            "database_path": str(Path(args.db).resolve()),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "season": season,
        "macro_context": macro_context,
        "block_context": {
            **block,
            "start_date": start_date,
            "end_date": end_date,
        },
        "block_summary": block_summary,
        "weeks": weeks,
        "weekly_reviews": [week.get("weekly_review") for week in week_bundles if week.get("weekly_review") is not None],
        "week_bundles": week_bundles,
        "daily_trend": daily_trend,
        "weight_reviews": weight_reviews,
        "previous_block_context": previous_block,
        "next_block_context": next_block,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
