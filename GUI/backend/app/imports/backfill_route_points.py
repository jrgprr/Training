#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

from .storage import GarminImportStorage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill canonical route points from stored TCX artifacts.")
    parser.add_argument("--activity-id", type=int, help="Optional single activity id to backfill")
    parser.add_argument("--season-id", type=int, help="Optional season id filter")
    parser.add_argument("--date-from", help="Optional inclusive date lower bound")
    parser.add_argument("--date-to", help="Optional inclusive date upper bound")
    parser.add_argument("--limit", type=int, help="Optional max activity count")
    parser.add_argument("--force", action="store_true", help="Rebuild route points even when they already exist")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    storage = GarminImportStorage()
    result = storage.backfill_route_points_batch(
        activity_id=args.activity_id,
        season_id=args.season_id,
        date_from=args.date_from,
        date_to=args.date_to,
        limit=args.limit,
        force=args.force,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
