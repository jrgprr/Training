#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
BLOCK_ASSESSMENT_ROOT_NAME = "Block-Assessment-Logbook"
BLOCK_CONTEXT_SCRIPT = REPO_ROOT / ".github" / "skills" / "block-performance-assessment" / "scripts" / "build_block_context.py"
REVIEW_FIELDS = (
    "summary_text",
    "recommendation_text",
    "risk_level",
)


def build_assessment_markdown_path(season_id: int, block_code: str, block_id: int) -> Path:
    season_root = REPO_ROOT / str(season_id) / BLOCK_ASSESSMENT_ROOT_NAME
    return season_root / f"{block_code}-block-{block_id}.md"


def build_default_markdown_document(row: dict[str, Any], payload: dict[str, Any]) -> str:
    detailed_assessment = str(payload.get("detailed_assessment_markdown") or "").strip()
    appendix_lines = [
        "## Assessment Metadata",
        f"- season_id: {row['season_id']}",
        f"- block_id: {row['block_id']}",
        f"- block_code: {row['block_code']}",
        "",
        "## Structured Block Review Snapshot",
        f"- Summary: {row.get('summary_text') or '-'}",
        f"- Risk Level: {row.get('risk_level') or '-'}",
        f"- Recommendation: {row.get('recommendation_text') or '-'}",
        f"- Weeks In Block: {row.get('weeks_in_block') if row.get('weeks_in_block') is not None else '-'}",
        f"- Adherence Rate: {row.get('adherence_rate') if row.get('adherence_rate') is not None else '-'}",
        f"- Traceability Rate: {row.get('traceability_rate') if row.get('traceability_rate') is not None else '-'}",
        f"- Actual Minutes: {row.get('actual_minutes') if row.get('actual_minutes') is not None else '-'}",
        f"- Planned Reference Minutes: {row.get('planned_reference_minutes') if row.get('planned_reference_minutes') is not None else '-'}",
        f"- Volume Delta Minutes: {row.get('volume_delta_minutes') if row.get('volume_delta_minutes') is not None else '-'}",
        f"- Key Sessions Closed: {row.get('key_sessions_closed') if row.get('key_sessions_closed') is not None else '-'} / {row.get('key_sessions_total') if row.get('key_sessions_total') is not None else '-'}",
        f"- Starting TSB: {row.get('starting_tsb') if row.get('starting_tsb') is not None else '-'}",
        f"- Ending TSB: {row.get('ending_tsb') if row.get('ending_tsb') is not None else '-'}",
        f"- Weight Delta Kg: {row.get('weight_delta_kg') if row.get('weight_delta_kg') is not None else '-'}",
    ]
    if detailed_assessment:
        return detailed_assessment.rstrip() + "\n\n---\n\n" + "\n".join(appendix_lines) + "\n"

    title = f"# Block Assessment {row['block_code']}"
    return "\n".join([title, "", *appendix_lines]) + "\n"


def write_assessment_markdown(row: dict[str, Any], payload: dict[str, Any]) -> Path:
    path = build_assessment_markdown_path(int(row["season_id"]), str(row["block_code"]), int(row["block_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_default_markdown_document(row, payload), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or upsert one row into review_block_reviews.")
    parser.add_argument("--block-id", required=True, type=int, help="Block id to review")
    parser.add_argument("--season", type=int, help="Optional season id. If omitted, infer from block.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    parser.add_argument("--input-json", help="Path to a JSON payload file. If omitted, stdin is used.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate and resolve without writing")
    mode.add_argument("--write", action="store_true", help="Perform the upsert")
    return parser.parse_args()


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_json:
        raw = Path(args.input_json).read_text()
    else:
        raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")
    return payload


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return row_to_dict(connection.execute(query, params).fetchone())


def validate_payload(payload: dict[str, Any]) -> None:
    if not any(payload.get(field) not in (None, "") for field in REVIEW_FIELDS):
        raise ValueError("At least one review field must be provided")


def load_block_context(block_id: int, season_id: int | None, db_path: str) -> dict[str, Any]:
    command = [sys.executable, str(BLOCK_CONTEXT_SCRIPT), "--block-id", str(block_id), "--db", db_path]
    if season_id is not None:
        command.extend(["--season", str(season_id)])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def build_row(connection: sqlite3.Connection, payload: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    context = load_block_context(args.block_id, args.season or payload.get("season_id"), args.db)
    season_id = int(args.season or payload.get("season_id") or context["season"]["season_id"])
    block = context["block_context"]
    summary = context["block_summary"]

    if payload.get("season_id") is None and args.season is None:
        warnings.append("season_id inferred from block context")

    resolved = {
        "season_id": season_id,
        "block_id": int(block["block_id"]),
        "block_code": str(block["block_code"]),
        "review_status": "closed",
        "weeks_in_block": summary.get("weeks_in_block"),
        "total_sessions": summary.get("total_sessions"),
        "completed_sessions": summary.get("completed_sessions"),
        "partial_sessions": summary.get("partial_sessions"),
        "pending_sessions": summary.get("pending_sessions"),
        "skipped_sessions": summary.get("skipped_sessions"),
        "replaced_sessions": summary.get("replaced_sessions"),
        "adherence_rate": summary.get("adherence_rate"),
        "traceability_rate": summary.get("traceability_rate"),
        "planned_reference_minutes": summary.get("planned_reference_minutes"),
        "actual_minutes": summary.get("actual_minutes"),
        "volume_delta_minutes": summary.get("volume_delta_minutes"),
        "key_sessions_total": summary.get("key_sessions_total"),
        "key_sessions_closed": summary.get("key_sessions_closed"),
        "aligned_zone_sessions": summary.get("aligned_zone_sessions"),
        "limited_zone_sessions": summary.get("limited_zone_sessions"),
        "misaligned_zone_sessions": summary.get("misaligned_zone_sessions"),
        "daily_training_load_total": summary.get("daily_training_load_total"),
        "daily_training_load_peak": summary.get("daily_training_load_peak"),
        "starting_tsb": summary.get("starting_tsb"),
        "ending_tsb": summary.get("ending_tsb"),
        "lowest_tsb": summary.get("lowest_tsb"),
        "starting_atl": summary.get("starting_atl"),
        "ending_atl": summary.get("ending_atl"),
        "starting_ctl": summary.get("starting_ctl"),
        "ending_ctl": summary.get("ending_ctl"),
        "avg_sleep_hours": summary.get("avg_sleep_hours"),
        "avg_resting_hr": summary.get("avg_resting_hr"),
        "avg_stress": summary.get("avg_stress"),
        "starting_weight_kg": summary.get("starting_weight_kg"),
        "ending_weight_kg": summary.get("ending_weight_kg"),
        "weight_delta_kg": summary.get("weight_delta_kg"),
        "risk_level": payload.get("risk_level"),
        "recommendation_text": payload.get("recommendation_text"),
        "summary_text": payload.get("summary_text"),
    }
    validate_payload(resolved)
    return resolved, warnings


def load_existing_row(connection: sqlite3.Connection, block_id: int) -> dict[str, Any] | None:
    return fetch_one(
        connection,
        """
        SELECT block_review_id, season_id, block_id, review_status, closed_at,
               weeks_in_block, total_sessions, completed_sessions, partial_sessions,
               pending_sessions, skipped_sessions, replaced_sessions,
               adherence_rate, traceability_rate, planned_reference_minutes,
               actual_minutes, volume_delta_minutes, key_sessions_total,
               key_sessions_closed, aligned_zone_sessions, limited_zone_sessions,
               misaligned_zone_sessions, daily_training_load_total,
               daily_training_load_peak, starting_tsb, ending_tsb, lowest_tsb,
               starting_atl, ending_atl, starting_ctl, ending_ctl,
               avg_sleep_hours, avg_resting_hr, avg_stress,
               starting_weight_kg, ending_weight_kg, weight_delta_kg,
               risk_level, recommendation_text, summary_text,
               created_at, updated_at
        FROM review_block_reviews
        WHERE block_id = ?
        """,
        (block_id,),
    )


def upsert_row(connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any] | None:
    connection.execute(
        """
        INSERT INTO review_block_reviews (
            season_id, block_id, review_status, closed_at,
            weeks_in_block, total_sessions, completed_sessions, partial_sessions,
            pending_sessions, skipped_sessions, replaced_sessions,
            adherence_rate, traceability_rate, planned_reference_minutes,
            actual_minutes, volume_delta_minutes, key_sessions_total,
            key_sessions_closed, aligned_zone_sessions, limited_zone_sessions,
            misaligned_zone_sessions, daily_training_load_total,
            daily_training_load_peak, starting_tsb, ending_tsb, lowest_tsb,
            starting_atl, ending_atl, starting_ctl, ending_ctl,
            avg_sleep_hours, avg_resting_hr, avg_stress,
            starting_weight_kg, ending_weight_kg, weight_delta_kg,
            risk_level, recommendation_text, summary_text, updated_at
        ) VALUES (?, ?, 'closed', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(block_id) DO UPDATE SET
            season_id = excluded.season_id,
            review_status = 'closed',
            closed_at = CURRENT_TIMESTAMP,
            weeks_in_block = excluded.weeks_in_block,
            total_sessions = excluded.total_sessions,
            completed_sessions = excluded.completed_sessions,
            partial_sessions = excluded.partial_sessions,
            pending_sessions = excluded.pending_sessions,
            skipped_sessions = excluded.skipped_sessions,
            replaced_sessions = excluded.replaced_sessions,
            adherence_rate = excluded.adherence_rate,
            traceability_rate = excluded.traceability_rate,
            planned_reference_minutes = excluded.planned_reference_minutes,
            actual_minutes = excluded.actual_minutes,
            volume_delta_minutes = excluded.volume_delta_minutes,
            key_sessions_total = excluded.key_sessions_total,
            key_sessions_closed = excluded.key_sessions_closed,
            aligned_zone_sessions = excluded.aligned_zone_sessions,
            limited_zone_sessions = excluded.limited_zone_sessions,
            misaligned_zone_sessions = excluded.misaligned_zone_sessions,
            daily_training_load_total = excluded.daily_training_load_total,
            daily_training_load_peak = excluded.daily_training_load_peak,
            starting_tsb = excluded.starting_tsb,
            ending_tsb = excluded.ending_tsb,
            lowest_tsb = excluded.lowest_tsb,
            starting_atl = excluded.starting_atl,
            ending_atl = excluded.ending_atl,
            starting_ctl = excluded.starting_ctl,
            ending_ctl = excluded.ending_ctl,
            avg_sleep_hours = excluded.avg_sleep_hours,
            avg_resting_hr = excluded.avg_resting_hr,
            avg_stress = excluded.avg_stress,
            starting_weight_kg = excluded.starting_weight_kg,
            ending_weight_kg = excluded.ending_weight_kg,
            weight_delta_kg = excluded.weight_delta_kg,
            risk_level = excluded.risk_level,
            recommendation_text = excluded.recommendation_text,
            summary_text = excluded.summary_text,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            row["season_id"], row["block_id"], row["weeks_in_block"], row["total_sessions"], row["completed_sessions"], row["partial_sessions"],
            row["pending_sessions"], row["skipped_sessions"], row["replaced_sessions"], row["adherence_rate"], row["traceability_rate"],
            row["planned_reference_minutes"], row["actual_minutes"], row["volume_delta_minutes"], row["key_sessions_total"],
            row["key_sessions_closed"], row["aligned_zone_sessions"], row["limited_zone_sessions"], row["misaligned_zone_sessions"],
            row["daily_training_load_total"], row["daily_training_load_peak"], row["starting_tsb"], row["ending_tsb"], row["lowest_tsb"],
            row["starting_atl"], row["ending_atl"], row["starting_ctl"], row["ending_ctl"], row["avg_sleep_hours"], row["avg_resting_hr"],
            row["avg_stress"], row["starting_weight_kg"], row["ending_weight_kg"], row["weight_delta_kg"], row["risk_level"],
            row["recommendation_text"], row["summary_text"],
        ),
    )
    connection.commit()
    return load_existing_row(connection, int(row["block_id"]))


def main() -> int:
    args = parse_args()
    payload = load_payload(args)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    resolved_row, warnings = build_row(connection, payload, args)
    existing_row = load_existing_row(connection, int(resolved_row["block_id"]))

    action = "dry-run"
    stored_row = resolved_row
    assessment_markdown_path = build_assessment_markdown_path(int(resolved_row["season_id"]), str(resolved_row["block_code"]), int(resolved_row["block_id"]))
    if args.write:
        stored_row = upsert_row(connection, resolved_row) or resolved_row
        stored_row["block_code"] = resolved_row["block_code"]
        assessment_markdown_path = write_assessment_markdown(stored_row, payload)
        action = "updated" if existing_row is not None else "inserted"

    result = {
        "action": action,
        "target": {
            "season_id": resolved_row["season_id"],
            "block_id": resolved_row["block_id"],
            "block_code": resolved_row["block_code"],
        },
        "existing_row": existing_row,
        "stored_row": stored_row,
        "assessment_markdown_path": str(assessment_markdown_path),
        "assessment_markdown_exists": assessment_markdown_path.exists(),
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
