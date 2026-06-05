#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
WEIGHT_ASSESSMENT_ROOT_NAME = "Weight-Assessment-Logbook"
WEIGHT_CONTEXT_SCRIPT = REPO_ROOT / ".github" / "skills" / "weight-control-assessment" / "scripts" / "build_weight_context.py"
REVIEW_FIELDS = (
    "classification",
    "summary_text",
    "recommendation_text",
    "reference_weight_kg",
    "target_weight_kg",
    "latest_weight_kg",
    "latest_7d_avg_kg",
    "delta_7d_avg_kg",
    "latest_14d_avg_kg",
    "delta_14d_avg_kg",
    "volatility_7d_kg",
    "gap_to_target_kg",
)


def build_assessment_markdown_path(season_id: int, review_date: str) -> Path:
    season_root = REPO_ROOT / str(season_id) / WEIGHT_ASSESSMENT_ROOT_NAME
    return season_root / f"{review_date}.md"


def build_default_markdown_document(row: dict[str, Any], payload: dict[str, Any]) -> str:
    detailed_assessment = str(payload.get("detailed_assessment_markdown") or "").strip()
    appendix_lines = [
        "## Assessment Metadata",
        f"- season_id: {row['season_id']}",
        f"- review_date: {row['review_date']}",
        f"- week_id: {row['week_id'] if row['week_id'] is not None else 'unknown'}",
        f"- block_id: {row['block_id'] if row['block_id'] is not None else 'unknown'}",
        "",
        "## Structured Weight Review Snapshot",
        f"- Reference Weight: {row.get('reference_weight_kg') if row.get('reference_weight_kg') is not None else '-'}",
        f"- Target Weight: {row.get('target_weight_kg') if row.get('target_weight_kg') is not None else '-'}",
        f"- Latest Weight: {row.get('latest_weight_kg') if row.get('latest_weight_kg') is not None else '-'}",
        f"- 7d Avg: {row.get('latest_7d_avg_kg') if row.get('latest_7d_avg_kg') is not None else '-'}",
        f"- 7d Avg Delta: {row.get('delta_7d_avg_kg') if row.get('delta_7d_avg_kg') is not None else '-'}",
        f"- 14d Avg: {row.get('latest_14d_avg_kg') if row.get('latest_14d_avg_kg') is not None else '-'}",
        f"- 14d Avg Delta: {row.get('delta_14d_avg_kg') if row.get('delta_14d_avg_kg') is not None else '-'}",
        f"- 7d Volatility: {row.get('volatility_7d_kg') if row.get('volatility_7d_kg') is not None else '-'}",
        f"- Gap To Target: {row.get('gap_to_target_kg') if row.get('gap_to_target_kg') is not None else '-'}",
        f"- Classification: {row.get('classification') or '-'}",
        f"- Recommendation: {row.get('recommendation_text') or '-'}",
        f"- Summary: {row.get('summary_text') or '-'}",
    ]
    if detailed_assessment:
        return detailed_assessment.rstrip() + "\n\n---\n\n" + "\n".join(appendix_lines) + "\n"

    title = f"# Weight Assessment {row['review_date']}"
    return "\n".join([title, "", *appendix_lines]) + "\n"


def write_assessment_markdown(row: dict[str, Any], payload: dict[str, Any]) -> Path:
    path = build_assessment_markdown_path(int(row["season_id"]), str(row["review_date"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_default_markdown_document(row, payload), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or upsert one row into review_weight_reviews.")
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


def load_weight_context(review_date: str, season_id: int, db_path: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            "python",
            str(WEIGHT_CONTEXT_SCRIPT),
            "--date",
            review_date,
            "--season",
            str(season_id),
            "--db",
            db_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


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

    week_context = infer_week_context(connection, review_date)
    block_id = payload.get("block_id")
    if block_id is None and week_context is not None:
        block_id = week_context["block_id"]
        warnings.append("block_id inferred from week context")

    week_id = payload.get("week_id")
    if week_id is None and week_context is not None:
        week_id = week_context["week_id"]
        warnings.append("week_id inferred from week context")

    context = load_weight_context(review_date, int(season_id), args.db)
    weight_summary = context.get("weight_summary") or {}
    profile = context.get("profile") or {}

    resolved = {
        "season_id": int(season_id),
        "review_date": review_date,
        "block_id": block_id,
        "week_id": week_id,
        "reference_weight_kg": payload.get("reference_weight_kg", profile.get("reference_weight_kg")),
        "target_weight_kg": payload.get("target_weight_kg", profile.get("target_weight_kg")),
        "latest_weight_kg": payload.get("latest_weight_kg", weight_summary.get("latest_weight_kg")),
        "latest_7d_avg_kg": payload.get("latest_7d_avg_kg", weight_summary.get("latest_7d_avg_kg")),
        "delta_7d_avg_kg": payload.get("delta_7d_avg_kg", weight_summary.get("delta_7d_avg_kg")),
        "latest_14d_avg_kg": payload.get("latest_14d_avg_kg", weight_summary.get("latest_14d_avg_kg")),
        "delta_14d_avg_kg": payload.get("delta_14d_avg_kg", weight_summary.get("delta_14d_avg_kg")),
        "volatility_7d_kg": payload.get("volatility_7d_kg", weight_summary.get("volatility_7d_kg")),
        "gap_to_target_kg": payload.get("gap_to_target_kg", weight_summary.get("gap_to_target_kg")),
        "classification": payload.get("classification"),
        "recommendation_text": payload.get("recommendation_text"),
        "summary_text": payload.get("summary_text"),
    }
    inferred_fields = [
        field
        for field in (
            "reference_weight_kg",
            "target_weight_kg",
            "latest_weight_kg",
            "latest_7d_avg_kg",
            "delta_7d_avg_kg",
            "latest_14d_avg_kg",
            "delta_14d_avg_kg",
            "volatility_7d_kg",
            "gap_to_target_kg",
        )
        if payload.get(field) in (None, "") and resolved.get(field) is not None
    ]
    if inferred_fields:
        warnings.append("weight summary fields inferred from weight-control context")

    validate_payload(resolved)
    return resolved, warnings


def load_existing_row(connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any] | None:
    return fetch_one(
        connection,
        """
        SELECT weight_review_id, season_id, review_date, block_id, week_id,
             reference_weight_kg, target_weight_kg, latest_weight_kg,
             latest_7d_avg_kg, delta_7d_avg_kg,
             latest_14d_avg_kg, delta_14d_avg_kg, volatility_7d_kg,
               gap_to_target_kg, classification, recommendation_text, summary_text,
               created_at, updated_at
        FROM review_weight_reviews
        WHERE season_id = ? AND review_date = ?
        """,
        (row["season_id"], row["review_date"]),
    )


def upsert_row(connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any] | None:
    connection.execute(
        """
        INSERT INTO review_weight_reviews (
            season_id, review_date, block_id, week_id,
            reference_weight_kg, target_weight_kg, latest_weight_kg,
            latest_7d_avg_kg, delta_7d_avg_kg,
            latest_14d_avg_kg, delta_14d_avg_kg, volatility_7d_kg,
            gap_to_target_kg, classification, recommendation_text, summary_text, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(season_id, review_date) DO UPDATE SET
            block_id = excluded.block_id,
            week_id = excluded.week_id,
            reference_weight_kg = excluded.reference_weight_kg,
            target_weight_kg = excluded.target_weight_kg,
            latest_weight_kg = excluded.latest_weight_kg,
            latest_7d_avg_kg = excluded.latest_7d_avg_kg,
            delta_7d_avg_kg = excluded.delta_7d_avg_kg,
            latest_14d_avg_kg = excluded.latest_14d_avg_kg,
            delta_14d_avg_kg = excluded.delta_14d_avg_kg,
            volatility_7d_kg = excluded.volatility_7d_kg,
            gap_to_target_kg = excluded.gap_to_target_kg,
            classification = excluded.classification,
            recommendation_text = excluded.recommendation_text,
            summary_text = excluded.summary_text,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            row["season_id"],
            row["review_date"],
            row["block_id"],
            row["week_id"],
            row["reference_weight_kg"],
            row["target_weight_kg"],
            row["latest_weight_kg"],
            row["latest_7d_avg_kg"],
            row["delta_7d_avg_kg"],
            row["latest_14d_avg_kg"],
            row["delta_14d_avg_kg"],
            row["volatility_7d_kg"],
            row["gap_to_target_kg"],
            row["classification"],
            row["recommendation_text"],
            row["summary_text"],
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
    assessment_markdown_path = build_assessment_markdown_path(resolved_row["season_id"], resolved_row["review_date"])
    if args.write:
        stored_row = upsert_row(connection, resolved_row) or resolved_row
        assessment_markdown_path = write_assessment_markdown(stored_row, payload)
        action = "updated" if existing_row is not None else "inserted"

    result = {
        "action": action,
        "target": {
            "season_id": resolved_row["season_id"],
            "review_date": resolved_row["review_date"],
            "week_id": resolved_row["week_id"],
            "block_id": resolved_row["block_id"],
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