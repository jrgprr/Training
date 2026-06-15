from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from statistics import median
from typing import Any

from .db import _ensure_exec_activity_elevation_enrichment_schema, _ensure_exec_activity_route_points_schema, get_connection
from .imports.contracts import NormalizedRoutePoint


@dataclass(slots=True)
class CorrectedElevationPoint:
    point_index: int
    corrected_altitude_meters: float
    correction_status: str = "corrected"
    provider_confidence: float | None = None


@dataclass(slots=True)
class ElevationProviderResult:
    provider_key: str
    provider_version: str
    points: list[CorrectedElevationPoint]
    status: str = "completed"
    notes: str | None = None


SMOOTHED_PROVIDER_KEY = "smoothed_altitude"
SMOOTHED_PROVIDER_VERSION = "v1"


def route_point_fingerprint(route_points: list[NormalizedRoutePoint]) -> str:
    digest = hashlib.sha1()
    for point in route_points:
        digest.update(
            f"{point.point_index}|{point.latitude_degrees:.7f}|{point.longitude_degrees:.7f}|{point.altitude_meters}|{point.distance_meters}|{point.recorded_at}|{point.elapsed_seconds}".encode("utf-8")
        )
    return digest.hexdigest()


def _load_route_points(connection: Any, activity_id: int) -> list[NormalizedRoutePoint]:
    rows = connection.execute(
        """
        SELECT point_index, latitude_degrees, longitude_degrees, altitude_meters,
               distance_meters, recorded_at, elapsed_seconds, source_payload_kind
        FROM exec_activity_route_points
        WHERE activity_id = ?
        ORDER BY point_index
        """,
        (activity_id,),
    ).fetchall()
    return [
        NormalizedRoutePoint(
            point_index=row["point_index"],
            latitude_degrees=row["latitude_degrees"],
            longitude_degrees=row["longitude_degrees"],
            altitude_meters=row["altitude_meters"],
            distance_meters=row["distance_meters"],
            recorded_at=row["recorded_at"],
            elapsed_seconds=row["elapsed_seconds"],
            source_payload_kind=row["source_payload_kind"] or "activity_detail_stream",
        )
        for row in rows
    ]


def load_route_points(activity_id: int) -> list[NormalizedRoutePoint]:
    with get_connection() as connection:
        _ensure_exec_activity_route_points_schema(connection)
        return _load_route_points(connection, activity_id)


def _fill_missing_altitudes(route_points: list[NormalizedRoutePoint]) -> list[float]:
    altitudes = [point.altitude_meters for point in route_points]
    filled: list[float] = [0.0] * len(altitudes)
    last_known: float | None = None
    next_known_indexes = {}
    next_known: float | None = None
    for index in range(len(altitudes) - 1, -1, -1):
        if altitudes[index] is not None:
            next_known = float(altitudes[index])
        next_known_indexes[index] = next_known
    for index, altitude in enumerate(altitudes):
        if altitude is not None:
            last_known = float(altitude)
            filled[index] = float(altitude)
            continue
        candidate = last_known if last_known is not None else next_known_indexes.get(index)
        filled[index] = float(candidate) if candidate is not None else 0.0
    return filled


def build_smoothed_elevation_enrichment(
    route_points: list[NormalizedRoutePoint], config: dict[str, Any] | None = None
) -> ElevationProviderResult:
    config = config or {}
    window_size = max(int(config.get("window_size", 5)), 3)
    if window_size % 2 == 0:
        window_size += 1
    half_window = window_size // 2
    altitudes = _fill_missing_altitudes(route_points)
    corrected: list[CorrectedElevationPoint] = []
    for index, point in enumerate(route_points):
        start = max(0, index - half_window)
        end = min(len(altitudes), index + half_window + 1)
        corrected.append(
            CorrectedElevationPoint(
                point_index=point.point_index,
                corrected_altitude_meters=float(median(altitudes[start:end])),
                correction_status="smoothed",
            )
        )
    return ElevationProviderResult(
        provider_key=SMOOTHED_PROVIDER_KEY,
        provider_version=SMOOTHED_PROVIDER_VERSION,
        points=corrected,
        notes=f"Median smoothing with window_size={window_size}.",
    )


def apply_activity_elevation_enrichment(
    activity_id: int,
    *,
    provider_config: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    provider_config = provider_config or {}

    with get_connection() as connection:
        _ensure_exec_activity_route_points_schema(connection)
        _ensure_exec_activity_elevation_enrichment_schema(connection)
        route_points = _load_route_points(connection, activity_id)
        if not route_points:
            raise LookupError(f"No route points found for activity {activity_id}.")

        fingerprint = route_point_fingerprint(route_points)
        existing_run = connection.execute(
            """
            SELECT enrichment_run_id
            FROM exec_activity_elevation_enrichment_runs
            WHERE activity_id = ?
              AND provider_key = ?
              AND provider_version = ?
              AND source_route_fingerprint = ?
            ORDER BY queried_at DESC, enrichment_run_id DESC
            LIMIT 1
            """,
            (activity_id, SMOOTHED_PROVIDER_KEY, SMOOTHED_PROVIDER_VERSION, fingerprint),
        ).fetchone()

        if existing_run is not None and not force:
            return {
                "activity_id": activity_id,
                "provider_key": SMOOTHED_PROVIDER_KEY,
                "provider_version": SMOOTHED_PROVIDER_VERSION,
                "enrichment_run_id": int(existing_run["enrichment_run_id"]),
                "status": "reused_existing_run",
            }

        result = build_smoothed_elevation_enrichment(route_points, provider_config)
        if len(result.points) != len(route_points):
            raise ValueError("Smoothed elevation enrichment returned a different point count than the stored route geometry.")

        if existing_run is None:
            cursor = connection.execute(
                """
                INSERT INTO exec_activity_elevation_enrichment_runs (
                    activity_id, provider_key, provider_version, provider_config_json,
                    source_route_fingerprint, status, point_count, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity_id,
                    SMOOTHED_PROVIDER_KEY,
                    SMOOTHED_PROVIDER_VERSION,
                    json.dumps(provider_config, ensure_ascii=True, sort_keys=True),
                    fingerprint,
                    result.status,
                    len(result.points),
                    result.notes,
                ),
            )
            enrichment_run_id = int(cursor.lastrowid)
            run_status = "created_new_run"
        else:
            enrichment_run_id = int(existing_run["enrichment_run_id"])
            connection.execute(
                """
                UPDATE exec_activity_elevation_enrichment_runs
                SET provider_config_json = ?,
                    source_route_fingerprint = ?,
                    queried_at = CURRENT_TIMESTAMP,
                    status = ?,
                    point_count = ?,
                    notes = ?
                WHERE enrichment_run_id = ?
                """,
                (
                    json.dumps(provider_config, ensure_ascii=True, sort_keys=True),
                    fingerprint,
                    result.status,
                    len(result.points),
                    result.notes,
                    enrichment_run_id,
                ),
            )
            connection.execute(
                "DELETE FROM exec_activity_elevation_enrichment_points WHERE enrichment_run_id = ?",
                (enrichment_run_id,),
            )
            run_status = "updated_existing_run"

        for point in result.points:
            connection.execute(
                """
                INSERT INTO exec_activity_elevation_enrichment_points (
                    enrichment_run_id, activity_id, point_index, corrected_altitude_meters, correction_status, provider_confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    enrichment_run_id,
                    activity_id,
                    point.point_index,
                    point.corrected_altitude_meters,
                    point.correction_status,
                    point.provider_confidence,
                ),
            )
        connection.commit()

    return {
        "activity_id": activity_id,
        "provider_key": SMOOTHED_PROVIDER_KEY,
        "provider_version": SMOOTHED_PROVIDER_VERSION,
        "enrichment_run_id": enrichment_run_id,
        "point_count": len(result.points),
        "status": run_status,
    }


def load_corrected_altitudes(activity_id: int) -> list[dict[str, Any]]:
    with get_connection() as connection:
        _ensure_exec_activity_elevation_enrichment_schema(connection)
        rows = connection.execute(
            """
            SELECT p.point_index, p.corrected_altitude_meters, p.correction_status, p.provider_confidence,
                   r.enrichment_run_id, r.provider_key, r.provider_version
            FROM exec_activity_elevation_enrichment_points p
            JOIN exec_activity_elevation_enrichment_runs r ON r.enrichment_run_id = p.enrichment_run_id
            WHERE p.activity_id = ?
              AND r.provider_key = ?
            ORDER BY r.queried_at DESC, r.enrichment_run_id DESC, p.point_index
            """,
                        (activity_id, SMOOTHED_PROVIDER_KEY),
        ).fetchall()
    return [dict(row) for row in rows]
