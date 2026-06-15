#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "GUI" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.planned_sessions import delete_planned_session_structure, ensure_planned_session_structure_schema, replace_planned_session_structure

DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
SCHEMA_PATH = REPO_ROOT / "Sistema" / "schema.sql"
SNAPSHOT_COLUMNS = (
    "planned_session_id",
    "week_id",
    "session_date",
    "day_name",
    "sequence_in_week",
    "planned_type",
    "objective",
    "primary_session",
    "complementary_session",
    "notes",
    "is_key_session",
    "intensity_class",
    "duration_min",
    "duration_max",
    "adjustment_rule",
    "markdown_path",
)
STRUCTURE_COLUMNS = (
    "planned_session_id",
    "planned_type",
    "primary_session",
    "complementary_session",
    "objective",
    "duration_min",
    "duration_max",
    "intensity_class",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply planning seed SQL and update deterministic session structure for changed sessions.")
    parser.add_argument("seed_paths", nargs="+", help="One or more SQL seed files to apply in order.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    return parser.parse_args()


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_base_planning_schema(connection: sqlite3.Connection) -> None:
    plan_table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plan_planned_sessions'"
    ).fetchone()
    if plan_table_exists is not None:
        return
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def snapshot_planned_sessions(connection: sqlite3.Connection) -> dict[int, tuple[Any, ...]]:
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plan_planned_sessions'"
    ).fetchone()
    if table_exists is None:
        return {}

    rows = connection.execute(
        f"SELECT {', '.join(SNAPSHOT_COLUMNS)} FROM plan_planned_sessions ORDER BY planned_session_id"
    ).fetchall()
    return {int(row["planned_session_id"]): tuple(row[column] for column in SNAPSHOT_COLUMNS[1:]) for row in rows}


def get_changed_planned_session_ids(
    before: dict[int, tuple[Any, ...]],
    after: dict[int, tuple[Any, ...]],
) -> tuple[list[int], list[int]]:
    deleted_ids = sorted(set(before) - set(after))
    upserted_ids = sorted(
        planned_session_id
        for planned_session_id, after_value in after.items()
        if before.get(planned_session_id) != after_value
    )
    return (deleted_ids, upserted_ids)


def fetch_structure_source_row(connection: sqlite3.Connection, planned_session_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        f"SELECT {', '.join(STRUCTURE_COLUMNS)} FROM plan_planned_sessions WHERE planned_session_id = ?",
        (planned_session_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def apply_seed_file(connection: sqlite3.Connection, seed_path: Path) -> dict[str, Any]:
    before = snapshot_planned_sessions(connection)
    connection.executescript(seed_path.read_text(encoding="utf-8"))
    after = snapshot_planned_sessions(connection)
    deleted_ids, upserted_ids = get_changed_planned_session_ids(before, after)

    for planned_session_id in deleted_ids:
        delete_planned_session_structure(connection, planned_session_id)

    for planned_session_id in upserted_ids:
        session_row = fetch_structure_source_row(connection, planned_session_id)
        if session_row is None:
            continue
        replace_planned_session_structure(connection, session_row)

    return {
        "seed_path": str(seed_path),
        "deleted_planned_session_ids": deleted_ids,
        "upserted_planned_session_ids": upserted_ids,
    }


def main() -> int:
    args = parse_args()
    database_path = Path(args.db).expanduser().resolve()
    seed_paths = [Path(seed_path).expanduser().resolve() for seed_path in args.seed_paths]

    with connect(database_path) as connection:
        ensure_base_planning_schema(connection)
        ensure_planned_session_structure_schema(connection)
        results = [apply_seed_file(connection, seed_path) for seed_path in seed_paths]

    print(
        json.dumps(
            {
                "status": "ok",
                "database_path": str(database_path),
                "applied_seed_count": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())