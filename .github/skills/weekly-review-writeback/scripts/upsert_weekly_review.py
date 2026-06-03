#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
WEEKLY_ASSESSMENT_ROOT_NAME = "Weekly-Assessment-Logbook"
REVIEW_FIELDS = (
    "summary_text",
    "recommendation_text",
    "risk_level",
)


def build_assessment_markdown_path(season_id: int, week_code: str, week_id: int) -> Path:
    season_root = REPO_ROOT / str(season_id) / WEEKLY_ASSESSMENT_ROOT_NAME
    return season_root / f"{week_code}-week-{week_id}.md"


def build_default_markdown_document(row: dict[str, Any], payload: dict[str, Any]) -> str:
    detailed_assessment = str(payload.get("detailed_assessment_markdown") or "").strip()
    appendix_lines = [
        "## Assessment Metadata",
        f"- season_id: {row['season_id']}",
        f"- block_id: {row['block_id']}",
        f"- week_id: {row['week_id']}",
        f"- week_code: {row['week_code']}",
        "",
        "## Structured Review Snapshot",
        f"- Summary: {row.get('summary_text') or '-'}",
        f"- Risk Level: {row.get('risk_level') or '-'}",
        f"- Recommendation: {row.get('recommendation_text') or '-'}",
        f"- Adherence Rate: {row.get('adherence_rate') if row.get('adherence_rate') is not None else '-'}",
        f"- Traceability Rate: {row.get('traceability_rate') if row.get('traceability_rate') is not None else '-'}",
        f"- Actual Minutes: {row.get('actual_minutes') if row.get('actual_minutes') is not None else '-'}",
        f"- Planned Reference Minutes: {row.get('planned_reference_minutes') if row.get('planned_reference_minutes') is not None else '-'}",
        f"- Volume Delta Minutes: {row.get('volume_delta_minutes') if row.get('volume_delta_minutes') is not None else '-'}",
    ]
    if detailed_assessment:
        return detailed_assessment.rstrip() + "\n\n---\n\n" + "\n".join(appendix_lines) + "\n"

    title = f"# Weekly Assessment {row['week_code']}"
    return "\n".join([title, "", *appendix_lines]) + "\n"
def write_assessment_markdown(row: dict[str, Any], payload: dict[str, Any]) -> Path:
    path = build_assessment_markdown_path(int(row["season_id"]), str(row["week_code"]), int(row["week_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_default_markdown_document(row, payload), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or upsert one row into review_weekly_reviews.")
    parser.add_argument("--week-id", required=True, type=int, help="Week id to review")
    parser.add_argument("--season", type=int, help="Optional season id. If omitted, infer from week.")
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


def load_week_metrics(week_id: int) -> dict[str, Any]:
    backend_path = str(REPO_ROOT / "GUI" / "backend")
    sys.path.insert(0, backend_path)
    try:
        from app.main import calculate_weekly_review_metrics  # type: ignore
        return calculate_weekly_review_metrics(week_id)
    finally:
        if backend_path in sys.path:
            sys.path.remove(backend_path)


def build_row(connection: sqlite3.Connection, payload: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    warnings = []
    week = fetch_one(connection, """
        SELECT mw.week_id, mw.week_code, mb.block_id, mb.season_id
        FROM plan_micro_weeks mw
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        WHERE mw.week_id = ?
    """, (args.week_id,))
    if week is None:
        raise ValueError(f"No existe la semana {args.week_id}")

    metrics = load_week_metrics(args.week_id)
    season_id = args.season or payload.get("season_id") or week["season_id"]
    block_id = payload.get("block_id") or week["block_id"]
    if payload.get("block_id") is None:
        warnings.append("block_id inferred from week context")
    if payload.get("season_id") is None and args.season is None:
        warnings.append("season_id inferred from week context")

    resolved = {
        "season_id": int(season_id),
        "block_id": int(block_id),
        "week_id": int(week["week_id"]),
        "week_code": str(week["week_code"]),
        "review_status": "closed",
        "adherence_rate": metrics.get("adherence_rate"),
        "traceability_rate": metrics.get("traceability_rate"),
        "actual_minutes": metrics.get("actual_minutes"),
        "planned_reference_minutes": metrics.get("planned_reference_minutes"),
        "volume_delta_minutes": metrics.get("volume_delta_minutes"),
        "risk_level": payload.get("risk_level") or metrics.get("risk_level"),
        "recommendation_text": payload.get("recommendation_text") or metrics.get("recommendation_text"),
        "summary_text": payload.get("summary_text") or metrics.get("summary_text"),
    }
    validate_payload(resolved)
    return resolved, warnings


def load_existing_row(connection: sqlite3.Connection, week_id: int) -> dict[str, Any] | None:
    return fetch_one(connection, """
        SELECT weekly_review_id, season_id, block_id, week_id, review_status, closed_at,
               adherence_rate, traceability_rate, actual_minutes, planned_reference_minutes,
               volume_delta_minutes, risk_level, recommendation_text, summary_text,
               created_at, updated_at
        FROM review_weekly_reviews
        WHERE week_id = ?
    """, (week_id,))


def upsert_row(connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any] | None:
    connection.execute("""
        INSERT INTO review_weekly_reviews (
            season_id, block_id, week_id, review_status, closed_at,
            adherence_rate, traceability_rate, actual_minutes, planned_reference_minutes,
            volume_delta_minutes, risk_level, recommendation_text, summary_text, updated_at
        ) VALUES (?, ?, ?, 'closed', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(week_id) DO UPDATE SET
            season_id = excluded.season_id,
            block_id = excluded.block_id,
            review_status = 'closed',
            closed_at = CURRENT_TIMESTAMP,
            adherence_rate = excluded.adherence_rate,
            traceability_rate = excluded.traceability_rate,
            actual_minutes = excluded.actual_minutes,
            planned_reference_minutes = excluded.planned_reference_minutes,
            volume_delta_minutes = excluded.volume_delta_minutes,
            risk_level = excluded.risk_level,
            recommendation_text = excluded.recommendation_text,
            summary_text = excluded.summary_text,
            updated_at = CURRENT_TIMESTAMP
    """, (
        row["season_id"], row["block_id"], row["week_id"], row["adherence_rate"], row["traceability_rate"],
        row["actual_minutes"], row["planned_reference_minutes"], row["volume_delta_minutes"],
        row["risk_level"], row["recommendation_text"], row["summary_text"],
    ))
    connection.commit()
    return load_existing_row(connection, int(row["week_id"]))


def main() -> int:
    args = parse_args()
    payload = load_payload(args)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    resolved_row, warnings = build_row(connection, payload, args)
    existing_row = load_existing_row(connection, int(resolved_row["week_id"]))

    action = "dry-run"
    stored_row = resolved_row
    assessment_markdown_path = build_assessment_markdown_path(int(resolved_row["season_id"]), str(resolved_row["week_code"]), int(resolved_row["week_id"]))
    if args.write:
        stored_row = upsert_row(connection, resolved_row) or resolved_row
        stored_row["week_code"] = resolved_row["week_code"]
        assessment_markdown_path = write_assessment_markdown(stored_row, payload)
        action = "updated" if existing_row is not None else "inserted"

    result = {
        "action": action,
        "target": {
            "season_id": resolved_row["season_id"],
            "block_id": resolved_row["block_id"],
            "week_id": resolved_row["week_id"],
            "week_code": resolved_row["week_code"],
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
