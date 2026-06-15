from __future__ import annotations

import argparse
import json

from .db import initialize_database
from .elevation_enrichment import backfill_route_points, compare_activity_elevation_metrics, enrich_activity_elevation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Elevation route-point and enrichment tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backfill = subparsers.add_parser("backfill-route-points", help="Backfill canonical route points from stored TCX artifacts")
    backfill.add_argument("--activity-id", dest="activity_ids", action="append", type=int, help="Specific activity id to backfill")
    backfill.add_argument("--season", type=int, help="Optional season filter when backfilling many activities")
    backfill.add_argument("--limit", type=int, help="Optional limit for bulk backfill")
    backfill.add_argument("--overwrite", action="store_true", help="Overwrite existing route points")

    enrich = subparsers.add_parser("enrich-activity", help="Compute smoothed Garmin corrected elevation points")
    enrich.add_argument("--activity-id", required=True, type=int)

    compare = subparsers.add_parser("compare-metrics", help="Compare raw versus smoothed Garmin ascent, vertical speed, and GAP")
    compare.add_argument("--activity-id", required=True, type=int)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    initialize_database()
    if args.command == "backfill-route-points":
        result = backfill_route_points(activity_ids=args.activity_ids, season_id=args.season, limit=args.limit, overwrite=args.overwrite)
    elif args.command == "enrich-activity":
        result = enrich_activity_elevation(args.activity_id)
    else:
        result = compare_activity_elevation_metrics(args.activity_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
