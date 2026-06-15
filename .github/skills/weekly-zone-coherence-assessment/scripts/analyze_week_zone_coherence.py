#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assess whether active zone definitions still fit the evidence available by the end of a training week.")
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


def resolve_week(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    if args.week_id is not None:
        row = fetch_one(
            connection,
            """
            SELECT mw.week_id, mw.week_code, mw.start_date, mw.end_date,
                   mb.block_id, mb.block_code, mb.season_id
            FROM plan_micro_weeks mw
            JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
            WHERE mw.week_id = ?
            """,
            (args.week_id,),
        )
        if row is None:
            raise SystemExit(f"No existe la semana {args.week_id}")
        return row

    if not args.date:
        raise SystemExit("Provide --week-id or --date")

    row = fetch_one(
        connection,
        """
        SELECT mw.week_id, mw.week_code, mw.start_date, mw.end_date,
               mb.block_id, mb.block_code, mb.season_id
        FROM plan_micro_weeks mw
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        WHERE mw.start_date <= ? AND mw.end_date >= ?
        ORDER BY mw.start_date DESC
        LIMIT 1
        """,
        (args.date, args.date),
    )
    if row is None:
        raise SystemExit(f"No existe semana para la fecha {args.date}")
    return row


def load_zone_coherence_assessment(week_id: int) -> dict[str, Any]:
    backend_path = str(REPO_ROOT / "GUI" / "backend")
    sys.path.insert(0, backend_path)
    try:
        from app.training_zones import get_week_zone_coherence_assessment  # type: ignore

        return get_week_zone_coherence_assessment(week_id)
    finally:
        if backend_path in sys.path:
            sys.path.remove(backend_path)


def build_zone_coherence_payload(args: argparse.Namespace) -> dict[str, Any]:
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    week = resolve_week(connection, args)
    season_id = args.season or int(week["season_id"])
    assessment = load_zone_coherence_assessment(int(week["week_id"]))
    return {
        "metadata": {
            "week_id": week["week_id"],
            "season_id": season_id,
            "database_path": str(Path(args.db).resolve()),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "week_context": week,
        "zone_coherence_assessment": assessment,
    }


def main() -> int:
    args = parse_args()
    payload = build_zone_coherence_payload(args)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())