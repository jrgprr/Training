#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "GUI" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.planned_sessions import ensure_planned_session_structure, get_planned_session_activity_groups

DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
DAILY_ASSESSMENT_ROOT_NAME = "Daily-Assessment-Logbook"
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


def discipline_family(discipline: str | None) -> str | None:
    if discipline in {"road_biking", "indoor_cycling", "mountain_biking"}:
        return "cycling"
    if discipline in {"walking", "hiking"}:
        return "walking"
    if discipline in {"running", "trail_running"}:
        return "running"
    return discipline


def build_assessment_markdown_path(season_id: int, review_date: str, planned_session_id: int | None) -> Path:
    season_root = REPO_ROOT / str(season_id) / DAILY_ASSESSMENT_ROOT_NAME
    suffix = f"ps-{planned_session_id}" if planned_session_id is not None else "general"
    return season_root / f"{review_date}-{suffix}.md"


def build_default_markdown_document(row: dict[str, Any], payload: dict[str, Any]) -> str:
    detailed_assessment = str(payload.get("detailed_assessment_markdown") or "").strip()
    appendix_lines = [
        "## Assessment Metadata",
        f"- season_id: {row['season_id']}",
        f"- review_date: {row['review_date']}",
        f"- planned_session_id: {row['planned_session_id'] if row['planned_session_id'] is not None else 'general'}",
        f"- week_id: {row['week_id'] if row['week_id'] is not None else 'unknown'}",
        f"- block_id: {row['block_id'] if row['block_id'] is not None else 'unknown'}",
        "",
        "## Structured Review Snapshot",
        f"- Planned Summary: {row.get('planned_summary') or '-'}",
        f"- Actual Summary: {row.get('actual_summary') or '-'}",
        f"- Compliance Status: {row.get('compliance_status') or '-'}",
        f"- General Feeling: {row.get('general_feeling') or '-'}",
        f"- Perceived Recovery: {row.get('perceived_recovery') or '-'}",
        f"- Motivation: {row.get('motivation') or '-'}",
        f"- Observations: {row.get('observations') or '-'}",
        f"- Next Day Decision: {row.get('next_day_decision') or '-'}",
    ]
    if detailed_assessment:
        return detailed_assessment.rstrip() + "\n\n---\n\n" + "\n".join(appendix_lines) + "\n"

    title = f"# Daily Assessment {row['review_date']}"
    lines = [
        title,
        "",
        *appendix_lines,
    ]
    return "\n".join(lines) + "\n"


def write_assessment_markdown(row: dict[str, Any], payload: dict[str, Any]) -> Path:
    path = build_assessment_markdown_path(row["season_id"], row["review_date"], row["planned_session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_default_markdown_document(row, payload), encoding="utf-8")
    return path


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


def fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in connection.execute(query, params).fetchall() if row is not None]


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
        SELECT planned_session_id, primary_session, objective
        FROM plan_planned_sessions
        WHERE planned_session_id = ?
        """,
        (planned_session_id,),
    )
    if row is None:
        return None
    ensure_planned_session_structure(connection, row)
    groups = get_planned_session_activity_groups(connection, int(row["planned_session_id"]))
    structured_summary = render_planned_activity_groups(groups)
    primary_session = row.get("primary_session")
    objective = row.get("objective")
    summary = structured_summary or primary_session or objective
    if summary and objective and objective not in summary:
        return f"{summary} Objetivo: {objective}"
    return summary


def infer_activity_id(connection: sqlite3.Connection, review_date: str, planned_session_id: int | None, activity_id: int | None) -> int | None:
    if activity_id is not None:
        row = connection.execute(
            "SELECT activity_id FROM exec_activities WHERE activity_id = ? AND activity_date = ?",
            (activity_id, review_date),
        ).fetchone()
        return int(row[0]) if row is not None else None

    if planned_session_id is None:
        return None

    linked = connection.execute(
        "SELECT activity_id FROM link_plan_execution WHERE planned_session_id = ? ORDER BY link_id DESC LIMIT 1",
        (planned_session_id,),
    ).fetchone()
    if linked is not None:
        return int(linked[0])

    planned_session = fetch_one(
        connection,
        """
        SELECT planned_session_id, planned_type, primary_session
        FROM plan_planned_sessions
        WHERE planned_session_id = ? AND session_date = ?
        """,
        (planned_session_id, review_date),
    )
    if planned_session is None:
        return None

    ensure_planned_session_structure(connection, planned_session)
    groups = get_planned_session_activity_groups(connection, int(planned_session["planned_session_id"]))
    target_groups = [
        {
            item.get("discipline_family")
            for item in group["items"]
            if item.get("discipline_family") in {"cycling", "walking", "running", "strength_training", "yoga"}
        }
        for group in groups
    ]
    target_groups = [group for group in target_groups if group]
    if not target_groups:
        return None

    candidates = fetch_all(
        connection,
        """
        SELECT activity_id, discipline
        FROM exec_activities
        WHERE activity_date = ?
        ORDER BY COALESCE(started_at, activity_date), activity_id
        """,
        (review_date,),
    )
    used_activity_ids: set[int] = set()
    matched_activity_id: int | None = None
    for target_families in target_groups:
        compatible_candidates = [
            candidate
            for candidate in candidates
            if discipline_family(candidate.get("discipline")) in target_families
            and candidate["activity_id"] not in used_activity_ids
        ]
        if len(compatible_candidates) != 1:
            continue
        matched_activity_id = int(compatible_candidates[0]["activity_id"])
        used_activity_ids.add(matched_activity_id)
        break
    return matched_activity_id


def render_planned_activity_groups(groups: list[dict[str, Any]]) -> str | None:
    if not groups:
        return None
    rendered_groups: list[str] = []
    for group in groups:
        item_labels = [render_planned_activity_item(item) for item in group.get("items", [])]
        item_labels = [label for label in item_labels if label]
        if not item_labels:
            continue
        separator = " + " if group.get("relation_mode") == "all_of" else " o "
        rendered_groups.append(separator.join(item_labels))
    return " + ".join(rendered_groups) if rendered_groups else None


def render_planned_activity_item(item: dict[str, Any]) -> str | None:
    label = str(item.get("display_label") or "").strip()
    if label and "min" in label.lower():
        return label

    base_label = label or {
        "cycling": "Bicicleta",
        "running": "Carrera",
        "strength_training": "Fuerza",
        "walking": "Paseo",
        "yoga": "Movilidad",
    }.get(item.get("discipline_family"), "Descanso activo" if item.get("item_type") == "rest" else None)
    if base_label is None:
        return None

    zone_min = item.get("target_zone_min_code")
    zone_max = item.get("target_zone_max_code")
    if zone_min and zone_max and zone_min != zone_max:
        zone_label = f"{zone_min}-{zone_max}"
    else:
        zone_label = zone_min

    duration_min = item.get("duration_min")
    duration_max = item.get("duration_max")
    if duration_min is None:
        duration_label = None
    elif duration_max is not None and duration_max != duration_min:
        duration_label = f"{duration_min}-{duration_max} min"
    else:
        duration_label = f"{duration_min} min"

    return " ".join(part for part in [base_label, zone_label, duration_label] if part)


def ensure_activity_link(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    activity_id: int | None,
    payload: dict[str, Any],
) -> str | None:
    if row.get("planned_session_id") is None or activity_id is None:
        return None
    if row.get("compliance_status") == "skipped":
        return None

    existing = connection.execute(
        "SELECT link_id FROM link_plan_execution WHERE planned_session_id = ? AND activity_id = ?",
        (row["planned_session_id"], activity_id),
    ).fetchone()
    if existing is not None:
        return None

    connection.execute(
        """
        INSERT INTO link_plan_execution (
            planned_session_id, activity_id, link_type, compliance_status, rationale
        ) VALUES (?, ?, 'garmin_auto', ?, ?)
        """,
        (
            row["planned_session_id"],
            activity_id,
            payload.get("compliance_status") or "completed",
            "Autoenlace desde writeback diario con actividad unica compatible en la fecha.",
        ),
    )
    return "link_plan_execution inserted"


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

    resolved_activity_id = infer_activity_id(connection, review_date, planned_session_id, activity_id)
    if activity_id is None and resolved_activity_id is not None:
        warnings.append("activity_id inferred from unique compatible day activity")

    resolved = {
        "season_id": int(season_id),
        "review_date": review_date,
        "block_id": block_id,
        "week_id": week_id,
        "planned_session_id": planned_session_id,
        "activity_id": resolved_activity_id,
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
    link_action = None
    assessment_markdown_path = build_assessment_markdown_path(
        resolved_row["season_id"],
        resolved_row["review_date"],
        resolved_row["planned_session_id"],
    )
    if args.write:
        stored_row = upsert_row(connection, resolved_row) or resolved_row
        link_action = ensure_activity_link(connection, resolved_row, resolved_row.get("activity_id"), payload)
        if link_action is not None:
            connection.commit()
        assessment_markdown_path = write_assessment_markdown(stored_row, payload)
        action = "updated" if existing_row is not None else "inserted"

    result = {
        "action": action,
        "target": {
            "review_date": resolved_row["review_date"],
            "season_id": resolved_row["season_id"],
            "planned_session_id": resolved_row["planned_session_id"],
            "activity_id": resolved_row.get("activity_id"),
            "week_id": resolved_row["week_id"],
            "block_id": resolved_row["block_id"],
        },
        "existing_row": existing_row,
        "stored_row": stored_row,
        "assessment_markdown_path": str(assessment_markdown_path),
        "assessment_markdown_exists": assessment_markdown_path.exists(),
        "link_action": link_action,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
