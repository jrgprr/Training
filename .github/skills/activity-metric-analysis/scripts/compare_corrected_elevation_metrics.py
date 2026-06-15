#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"
sys.path.insert(0, str(REPO_ROOT / "GUI" / "backend"))

from app.elevation_enrichment import apply_activity_elevation_enrichment, load_corrected_altitudes, load_route_points

compute_module_path = Path(__file__).resolve().with_name("compute_activity_metric_analysis.py")
spec = importlib.util.spec_from_file_location("compute_activity_metric_analysis", compute_module_path)
assert spec is not None and spec.loader is not None
compute_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compute_module)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare raw versus corrected elevation-derived metrics for one or more activities.")
    parser.add_argument("--activity-id", action="append", required=True, type=int, help="Activity id to validate. Repeatable.")
    parser.add_argument("--provider-config-json", help="Optional provider config JSON object.")
    parser.add_argument("--force", action="store_true", help="Recompute enrichment even when a matching run already exists.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    return parser.parse_args()


def compute_ascent(altitudes: list[float]) -> float | None:
    if len(altitudes) < 2:
        return None
    total = 0.0
    for prev, curr in zip(altitudes, altitudes[1:]):
        delta = curr - prev
        if delta > 0:
            total += delta
    return round(total, 2)


def compute_average_vertical_speed(altitudes: list[float], elapsed_seconds: list[float]) -> float | None:
    if len(altitudes) < 2 or len(elapsed_seconds) < 2:
        return None
    samples = []
    for prev_alt, curr_alt, prev_t, curr_t in zip(altitudes, altitudes[1:], elapsed_seconds, elapsed_seconds[1:]):
        delta_t = curr_t - prev_t
        if delta_t <= 0:
            continue
        samples.append((curr_alt - prev_alt) / delta_t)
    if not samples:
        return None
    return round(mean(samples), 4)


def build_corrected_elevation_readings(route_points, corrected_points):
    corrected_by_index = {item["point_index"]: item["corrected_altitude_meters"] for item in corrected_points}
    readings = []
    for point in route_points:
        if point.point_index not in corrected_by_index:
            continue
        readings.append({
            "sample_index": point.point_index,
            "raw_value": corrected_by_index[point.point_index],
            "elapsed_seconds": point.elapsed_seconds,
        })
    return readings


def main() -> None:
    args = parse_args()
    provider_config = json.loads(args.provider_config_json) if args.provider_config_json else {}

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    results = []
    try:
        for activity_id in args.activity_id:
            enrichment_result = apply_activity_elevation_enrichment(
                activity_id,
                provider_config=provider_config,
                force=args.force,
            )
            route_points = load_route_points(activity_id)
            corrected_points = load_corrected_altitudes(activity_id)
            activity = compute_module.load_activity_context(connection, activity_id)
            speed_readings = compute_module.load_metric_readings(connection, activity_id, "speed")
            vertical_speed_readings = compute_module.load_metric_readings(connection, activity_id, "vertical_speed")
            raw_elevation_readings = compute_module.load_metric_readings(connection, activity_id, "elevation")
            raw_gap = compute_module.build_grade_adjusted_pace_summary(activity, speed_readings, vertical_speed_readings, raw_elevation_readings)

            raw_altitudes = [float(point.altitude_meters) for point in route_points if point.altitude_meters is not None]
            corrected_elevation_readings = build_corrected_elevation_readings(route_points, corrected_points)
            corrected_altitudes = [float(item["raw_value"]) for item in corrected_elevation_readings]
            elapsed_seconds = [float(point.elapsed_seconds) for point in route_points if point.elapsed_seconds is not None]

            corrected_activity = dict(activity)
            corrected_ascent = compute_ascent(corrected_altitudes)
            if corrected_ascent is not None:
                corrected_activity["ascent_meters"] = corrected_ascent
            corrected_gap = compute_module.build_grade_adjusted_pace_summary(
                corrected_activity,
                speed_readings,
                [],
                corrected_elevation_readings,
            )

            results.append({
                "activity_id": activity_id,
                "provider_key": enrichment_result["provider_key"],
                "enrichment": enrichment_result,
                "raw": {
                    "route_point_count": len(route_points),
                    "ascent_meters_from_route": compute_ascent(raw_altitudes),
                    "avg_vertical_speed_mps": compute_average_vertical_speed(raw_altitudes, elapsed_seconds),
                    "gap": raw_gap,
                },
                "corrected": {
                    "route_point_count": len(corrected_points),
                    "ascent_meters_from_route": corrected_ascent,
                    "avg_vertical_speed_mps": compute_average_vertical_speed(corrected_altitudes, elapsed_seconds),
                    "gap": corrected_gap,
                },
            })
    finally:
        connection.close()

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
