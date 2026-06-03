#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
REVIEW_FIELDS = (
    "planned_summary",
    "actual_summary",
    "compliance_status",
    "general_feeling",
    "perceived_recovery",
    "motivation",
    "observations",
    "next_day_decision",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or upsert one row into review_daily_reviews.")
    parser.add_argument("--date", required=True, help="Review date in ISO format")
    parser.add_argument("--season", type=int, help="Optional season id. If omitted, infer from date.")
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
        import sys

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


def infer_season_id(connection: sqlite3.Connection, review_date: str) -> int:
    row = connection.execute(
        """
        SELECT season_id
        FROM plan_seasons
        WHERE start_date <= ? AND end_date >= ?
        ORDER BY start_date DESC
        LIMIT 1
        """,
        (review_date, review_date),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unable to infer season for {review_date}")
    return int(row[0])


def infer_week_context(connection: sqlite3.Connection, review_date: str) -> dict[str, Any] | None:
    return fetch_one(
        connection,
        """
        SELECT mw.week_id, mb.block_id, mw.week_code, mb.block_code
        FROM plan_micro_weeks mw
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        WHERE mw.start_date <= ? AND mw.end_date >= ?
        ORDER BY mw.start_date DESC
        LIMIT 1
        """,
        (review_date, review_date),
    )


def infer_planned_session_id(connection: sqlite3.Connection, review_date: str, activity_id: int | None) -> int | None:
    if activity_id is not None:
        linked = fetch_one(
            connection,
            """
            SELECT l.planned_session_id
            FROM link_plan_execution l
            JOIN exec_activities ea ON ea.activity_id = l.activity_id
            JOIN plan_planned_sessions ps ON ps.planned_session_id = l.planned_session_id
            WHERE l.activity_id = ? AND ps.session_date = ?
            ORDER BY l.link_id DESC
            LIMIT 1
            """,
            (activity_id, review_date),
        )
        if linked is not None:
            return int(linked["planned_session_id"])

    rows = connection.execute(
        "SELECT planned_session_id FROM plan_planned_sessions WHERE session_date = ? ORDER BY planned_session_id",
        (review_date,),
    ).fetchall()
    if len(rows) == 1:
        return int(rows[0][0])
    return None


def infer_planned_summary(connection: sqlite3.Connection, planned_session_id: int | None) -> str | None:
    if planned_session_id is None:
        return None
    row = fetch_one(
        connection,
        """
        SELECT primary_session, objective
        FROM plan_planned_sessions
        WHERE planned_session_id = ?
        """,
        (planned_session_id,),
    )
    if row is None:
        return None
    primary_session = row.get("primary_session")
    objective = row.get("objective")
    if primary_session and objective:
        return f"{primary_session} Objetivo: {objective}"
    return primary_session or objective


def validate_payload(payload: dict[str, Any]) -> None:
    if not any(payload.get(field) not in (None, "") for field in REVIEW_FIELDS):
        raise ValueError("At least one review field must be provided")


def build_row(connection: sqlite3.Connection, payload: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    review_date = args.date
    datetime.strptime(review_date, "%Y-%m-%d")

    season_id = args.season or payload.get("season_id")
    if season_id is None:
        season_id = infer_season_id(connection, review_date)
        warnings.append("season_id inferred from review_date")

    activity_id = payload.get("activity_id")
    planned_session_id = payload.get("planned_session_id")
    if planned_session_id is None:
        planned_session_id = infer_planned_session_id(connection, review_date, activity_id)
        if planned_session_id is not None:
            warnings.append("planned_session_id inferred")

    week_context = infer_week_context(connection, review_date)
    block_id = payload.get("block_id")
    if block_id is None and week_context is not None:
        block_id = week_context["block_id"]
        warnings.append("block_id inferred from week context")

    week_id = payload.get("week_id")
    if week_id is None and week_context is not None:
        week_id = week_context["week_id"]
        warnings.append("week_id inferred from week context")

    planned_summary = payload.get("planned_summary")
    if planned_summary in (None, ""):
        planned_summary = infer_planned_summary(connection, planned_session_id)
        if planned_summary is not None:
            warnings.append("planned_summary inferred from planned session")

    resolved = {
        "season_id": int(season_id),
        "review_date": review_date,
        "block_id": block_id,
        "week_id": week_id,
        "planned_session_id": planned_session_id,
        "planned_summary": planned_summary,
        "actual_summary": payload.get("actual_summary"),
        "compliance_status": payload.get("compliance_status"),
        "general_feeling": payload.get("general_feeling"),
        "perceived_recovery": payload.get("perceived_recovery"),
        "motivation": payload.get("motivation"),
        "observations": payload.get("observations"),
        "next_day_decision": payload.get("next_day_decision"),
    }
    validate_payload(resolved)
    return resolved, warnings


def load_existing_row(connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any] | None:
    return fetch_one(
        connection,
        """
        SELECT daily_review_id, season_id, review_date, block_id, week_id, planned_session_id,
               planned_summary, actual_summary, compliance_status, general_feeling,
               perceived_recovery, motivation, observations, next_day_decision
        FROM review_daily_reviews
        WHERE season_id = ? AND review_date = ? AND planned_session_id IS ?
        """,
        (row["season_id"], row["review_date"], row["planned_session_id"]),
    )


def upsert_row(connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any] | None:
    connection.execute(
        """
        INSERT INTO review_daily_reviews (
            season_id, review_date, block_id, week_id, planned_session_id,
            planned_summary, actual_summary, compliance_status, general_feeling,
            perceived_recovery, motivation, observations, next_day_decision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(season_id, review_date, planned_session_id) DO UPDATE SET
            block_id = excluded.block_id,
            week_id = excluded.week_id,
            planned_summary = excluded.planned_summary,
            actual_summary = excluded.actual_summary,
            compliance_status = excluded.compliance_status,
            general_feeling = excluded.general_feeling,
            perceived_recovery = excluded.perceived_recovery,
            motivation = excluded.motivation,
            observations = excluded.observations,
            next_day_decision = excluded.next_day_decision
        """,
        (
            row["season_id"],
            row["review_date"],
            row["block_id"],
            row["week_id"],
            row["planned_session_id"],
            row["planned_summary"],
            row["actual_summary"],
            row["compliance_status"],
            row["general_feeling"],
            row["perceived_recovery"],
            row["motivation"],
            row["observations"],
            row["next_day_decision"],
        ),
    )
    connection.commit()
    return load_existing_row(connection, row)


def main() -> int:
    args = parse_args()
    payload = load_payload(args)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    resolved_row, warnings = build_row(connection, payload, args)
    existing_row = load_existing_row(connection, resolved_row)

    action = "dry-run"
    stored_row = resolved_row
    if args.write:
        stored_row = upsert_row(connection, resolved_row) or resolved_row
        action = "updated" if existing_row is not None else "inserted"

    result = {
        "action": action,
        "target": {
            "review_date": resolved_row["review_date"],
            "season_id": resolved_row["season_id"],
            "planned_session_id": resolved_row["planned_session_id"],
            "week_id": resolved_row["week_id"],
            "block_id": resolved_row["block_id"],
        },
        "existing_row": existing_row,
        "stored_row": stored_row,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
