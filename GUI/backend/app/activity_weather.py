from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .db import _ensure_exec_activity_route_points_schema, _ensure_exec_activity_weather_schema, get_connection
from .imports.contracts import NormalizedRoutePoint


OPEN_METEO_PROVIDER_KEY = "open_meteo"
OPEN_METEO_PROVIDER_VERSION = "v1"
OPEN_METEO_DEFAULT_MODEL = "auto"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_TIMEZONE = "GMT"
WEATHER_SAMPLE_STRATEGY = "interval_15min_or_5km"
WEATHER_INTERVAL_SECONDS = 15 * 60
WEATHER_DISTANCE_METERS = 5000.0
HOURLY_VARIABLES = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "shortwave_radiation",
)


@dataclass(slots=True)
class WeatherSamplePoint:
    route_point_index: int
    sampled_at: str
    weather_hour: str
    elapsed_seconds: float | None
    distance_meters: float | None
    latitude_degrees: float
    longitude_degrees: float
    values: dict[str, Any]


def route_point_fingerprint(route_points: list[NormalizedRoutePoint]) -> str:
    digest = hashlib.sha1()
    for point in route_points:
        digest.update(
            f"{point.point_index}|{point.latitude_degrees:.7f}|{point.longitude_degrees:.7f}|{point.distance_meters}|{point.recorded_at}|{point.elapsed_seconds}".encode("utf-8")
        )
    return digest.hexdigest()


def _load_activity_context(connection: Any, activity_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT activity_id, season_id, activity_date, started_at, source_system
        FROM exec_activities
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchone()
    return dict(row) if row is not None else None


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


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    candidate = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass
    normalized = raw.replace(" ", "T")
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    return None


def _format_hour_key(value: datetime) -> str:
    return value.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00")


def _resolve_sampled_at(point: NormalizedRoutePoint, started_at: str | None) -> str | None:
    if point.recorded_at:
        parsed = _parse_datetime(point.recorded_at)
        if parsed is not None:
            parsed = parsed.replace(microsecond=0)
            return parsed.isoformat() if parsed.tzinfo is not None else parsed.strftime("%Y-%m-%dT%H:%M:%S")
    started_dt = _parse_datetime(started_at)
    if started_dt is None or point.elapsed_seconds is None:
        return None
    resolved = (started_dt + timedelta(seconds=float(point.elapsed_seconds))).replace(microsecond=0)
    return resolved.isoformat() if resolved.tzinfo is not None else resolved.strftime("%Y-%m-%dT%H:%M:%S")


def select_weather_sample_points(
    route_points: list[NormalizedRoutePoint],
    *,
    interval_seconds: int = WEATHER_INTERVAL_SECONDS,
    distance_meters: float = WEATHER_DISTANCE_METERS,
) -> list[NormalizedRoutePoint]:
    if not route_points:
        return []
    selected: list[NormalizedRoutePoint] = [route_points[0]]
    last = route_points[0]
    last_elapsed = float(last.elapsed_seconds or 0.0)
    last_distance = float(last.distance_meters or 0.0)
    for point in route_points[1:-1]:
        point_elapsed = float(point.elapsed_seconds or last_elapsed)
        point_distance = float(point.distance_meters or last_distance)
        if point_elapsed - last_elapsed >= interval_seconds or point_distance - last_distance >= distance_meters:
            selected.append(point)
            last = point
            last_elapsed = point_elapsed
            last_distance = point_distance
    if route_points[-1].point_index != selected[-1].point_index:
        selected.append(route_points[-1])
    return selected


def _fetch_open_meteo_hourly(latitude: float, longitude: float, activity_date: str) -> dict[str, Any]:
    params = {
        "latitude": f"{latitude:.6f}",
        "longitude": f"{longitude:.6f}",
        "start_date": activity_date,
        "end_date": activity_date,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": OPEN_METEO_TIMEZONE,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }
    url = f"{OPEN_METEO_ARCHIVE_URL}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Open-Meteo HTTP error {error.code} for coordinates {latitude:.5f},{longitude:.5f}.") from error
    except URLError as error:
        raise RuntimeError(f"Open-Meteo connection error for coordinates {latitude:.5f},{longitude:.5f}.") from error
    if payload.get("error"):
        raise RuntimeError(f"Open-Meteo error: {payload.get('reason') or 'unknown reason'}." )
    return payload


def _build_hourly_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    lookup: dict[str, dict[str, Any]] = {}
    for index, hour_key in enumerate(times):
        sample = {}
        for field in HOURLY_VARIABLES:
            values = hourly.get(field) or []
            sample[field] = values[index] if index < len(values) else None
        lookup[str(hour_key)] = sample
    return lookup


def _nearest_weather_hour(sampled_at: str) -> str:
    parsed = _parse_datetime(sampled_at)
    if parsed is None:
        raise ValueError(f"Cannot resolve weather hour for sampled_at={sampled_at}.")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    truncated = parsed.replace(minute=0, second=0, microsecond=0)
    if parsed.minute >= 30:
        truncated += timedelta(hours=1)
    return _format_hour_key(truncated)


def _summarize_samples(activity_id: int, weather_enrichment_run_id: int, samples: list[WeatherSamplePoint]) -> dict[str, Any]:
    def numeric(field: str) -> list[float]:
        values = [sample.values.get(field) for sample in samples]
        return [float(value) for value in values if isinstance(value, (int, float))]

    weather_codes = [int(sample.values["weather_code"]) for sample in samples if isinstance(sample.values.get("weather_code"), (int, float))]
    dominant_weather_code = Counter(weather_codes).most_common(1)[0][0] if weather_codes else None
    precipitation_values = numeric("precipitation")
    rain_values = numeric("rain")
    snowfall_values = numeric("snowfall")
    summary = {
        "activity_id": activity_id,
        "weather_enrichment_run_id": weather_enrichment_run_id,
        "temperature_mean": mean(numeric("temperature_2m")) if numeric("temperature_2m") else None,
        "temperature_min": min(numeric("temperature_2m")) if numeric("temperature_2m") else None,
        "temperature_max": max(numeric("temperature_2m")) if numeric("temperature_2m") else None,
        "apparent_temperature_mean": mean(numeric("apparent_temperature")) if numeric("apparent_temperature") else None,
        "precipitation_sum_est": sum(precipitation_values) if precipitation_values else None,
        "rain_sum_est": sum(rain_values) if rain_values else None,
        "snowfall_sum_est": sum(snowfall_values) if snowfall_values else None,
        "cloud_cover_mean": mean(numeric("cloud_cover")) if numeric("cloud_cover") else None,
        "wind_speed_mean": mean(numeric("wind_speed_10m")) if numeric("wind_speed_10m") else None,
        "wind_speed_max": max(numeric("wind_speed_10m")) if numeric("wind_speed_10m") else None,
        "wind_gusts_max": max(numeric("wind_gusts_10m")) if numeric("wind_gusts_10m") else None,
        "shortwave_radiation_mean": mean(numeric("shortwave_radiation")) if numeric("shortwave_radiation") else None,
        "dominant_weather_code": dominant_weather_code,
        "sample_count": len(samples),
    }
    return summary


def enrich_activity_weather(activity_id: int, *, force: bool = False) -> dict[str, Any]:
    with get_connection() as connection:
        _ensure_exec_activity_route_points_schema(connection)
        _ensure_exec_activity_weather_schema(connection)

        activity = _load_activity_context(connection, activity_id)
        if activity is None:
            raise LookupError(f"No activity found for activity {activity_id}.")

        route_points = _load_route_points(connection, activity_id)
        if not route_points:
            raise LookupError(f"No route points found for activity {activity_id}.")

        fingerprint = route_point_fingerprint(route_points)
        existing_run = connection.execute(
            """
            SELECT weather_enrichment_run_id
            FROM exec_activity_weather_enrichment_runs
            WHERE activity_id = ?
              AND provider_key = ?
              AND provider_version = ?
              AND sample_strategy = ?
              AND source_route_fingerprint = ?
            ORDER BY requested_at DESC, weather_enrichment_run_id DESC
            LIMIT 1
            """,
            (activity_id, OPEN_METEO_PROVIDER_KEY, OPEN_METEO_PROVIDER_VERSION, WEATHER_SAMPLE_STRATEGY, fingerprint),
        ).fetchone()
        if existing_run is not None and not force:
            return {
                "activity_id": activity_id,
                "weather_enrichment_run_id": int(existing_run["weather_enrichment_run_id"]),
                "provider_key": OPEN_METEO_PROVIDER_KEY,
                "sample_strategy": WEATHER_SAMPLE_STRATEGY,
                "status": "reused_existing_run",
            }

        selected_points = select_weather_sample_points(route_points)
        started_at = activity.get("started_at")
        samples: list[WeatherSamplePoint] = []
        payload_metadata: list[dict[str, Any]] = []
        for point in selected_points:
            sampled_at = _resolve_sampled_at(point, started_at)
            if sampled_at is None:
                continue
            weather_hour = _nearest_weather_hour(sampled_at)
            payload = _fetch_open_meteo_hourly(point.latitude_degrees, point.longitude_degrees, str(activity["activity_date"]))
            hourly_lookup = _build_hourly_lookup(payload)
            values = hourly_lookup.get(weather_hour)
            if values is None:
                continue
            payload_metadata.append(
                {
                    "route_point_index": point.point_index,
                    "weather_hour": weather_hour,
                    "latitude": point.latitude_degrees,
                    "longitude": point.longitude_degrees,
                    "timezone": payload.get("timezone"),
                    "elevation": payload.get("elevation"),
                }
            )
            samples.append(
                WeatherSamplePoint(
                    route_point_index=point.point_index,
                    sampled_at=sampled_at,
                    weather_hour=weather_hour,
                    elapsed_seconds=point.elapsed_seconds,
                    distance_meters=point.distance_meters,
                    latitude_degrees=point.latitude_degrees,
                    longitude_degrees=point.longitude_degrees,
                    values=values,
                )
            )

        if not samples:
            raise LookupError(f"No weather samples could be resolved for activity {activity_id}.")

        metadata_json = json.dumps(
            {
                "provider_model": OPEN_METEO_DEFAULT_MODEL,
                "hourly_variables": HOURLY_VARIABLES,
                "sampling_interval_seconds": WEATHER_INTERVAL_SECONDS,
                "sampling_distance_meters": WEATHER_DISTANCE_METERS,
                "queries": payload_metadata,
            },
            ensure_ascii=True,
            sort_keys=True,
        )

        if existing_run is None:
            cursor = connection.execute(
                """
                INSERT INTO exec_activity_weather_enrichment_runs (
                    activity_id, provider_key, provider_version, provider_model,
                    sample_strategy, source_route_fingerprint, status,
                    point_count, sample_count, notes, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity_id,
                    OPEN_METEO_PROVIDER_KEY,
                    OPEN_METEO_PROVIDER_VERSION,
                    OPEN_METEO_DEFAULT_MODEL,
                    WEATHER_SAMPLE_STRATEGY,
                    fingerprint,
                    "completed",
                    len(route_points),
                    len(samples),
                    "Hourly weather enrichment from Open-Meteo archive.",
                    metadata_json,
                ),
            )
            weather_enrichment_run_id = int(cursor.lastrowid)
            run_status = "created_new_run"
        else:
            weather_enrichment_run_id = int(existing_run["weather_enrichment_run_id"])
            connection.execute(
                """
                UPDATE exec_activity_weather_enrichment_runs
                SET provider_model = ?,
                    requested_at = CURRENT_TIMESTAMP,
                    status = ?,
                    point_count = ?,
                    sample_count = ?,
                    notes = ?,
                    metadata_json = ?
                WHERE weather_enrichment_run_id = ?
                """,
                (
                    OPEN_METEO_DEFAULT_MODEL,
                    "completed",
                    len(route_points),
                    len(samples),
                    "Hourly weather enrichment from Open-Meteo archive.",
                    metadata_json,
                    weather_enrichment_run_id,
                ),
            )
            connection.execute(
                "DELETE FROM exec_activity_weather_samples WHERE weather_enrichment_run_id = ?",
                (weather_enrichment_run_id,),
            )
            connection.execute(
                "DELETE FROM exec_activity_weather_summaries WHERE weather_enrichment_run_id = ?",
                (weather_enrichment_run_id,),
            )
            run_status = "updated_existing_run"

        for sample in samples:
            connection.execute(
                """
                INSERT INTO exec_activity_weather_samples (
                    weather_enrichment_run_id, activity_id, route_point_index,
                    sampled_at, weather_hour, elapsed_seconds, distance_meters,
                    latitude_degrees, longitude_degrees, temperature_2m,
                    apparent_temperature, precipitation, rain, snowfall,
                    weather_code, cloud_cover, wind_speed_10m,
                    wind_gusts_10m, wind_direction_10m, shortwave_radiation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    weather_enrichment_run_id,
                    activity_id,
                    sample.route_point_index,
                    sample.sampled_at,
                    sample.weather_hour,
                    sample.elapsed_seconds,
                    sample.distance_meters,
                    sample.latitude_degrees,
                    sample.longitude_degrees,
                    sample.values.get("temperature_2m"),
                    sample.values.get("apparent_temperature"),
                    sample.values.get("precipitation"),
                    sample.values.get("rain"),
                    sample.values.get("snowfall"),
                    sample.values.get("weather_code"),
                    sample.values.get("cloud_cover"),
                    sample.values.get("wind_speed_10m"),
                    sample.values.get("wind_gusts_10m"),
                    sample.values.get("wind_direction_10m"),
                    sample.values.get("shortwave_radiation"),
                ),
            )

        summary = _summarize_samples(activity_id, weather_enrichment_run_id, samples)
        connection.execute(
            """
            INSERT INTO exec_activity_weather_summaries (
                weather_enrichment_run_id, activity_id, temperature_mean,
                temperature_min, temperature_max, apparent_temperature_mean,
                precipitation_sum_est, rain_sum_est, snowfall_sum_est,
                cloud_cover_mean, wind_speed_mean, wind_speed_max,
                wind_gusts_max, shortwave_radiation_mean,
                dominant_weather_code, sample_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                weather_enrichment_run_id,
                activity_id,
                summary["temperature_mean"],
                summary["temperature_min"],
                summary["temperature_max"],
                summary["apparent_temperature_mean"],
                summary["precipitation_sum_est"],
                summary["rain_sum_est"],
                summary["snowfall_sum_est"],
                summary["cloud_cover_mean"],
                summary["wind_speed_mean"],
                summary["wind_speed_max"],
                summary["wind_gusts_max"],
                summary["shortwave_radiation_mean"],
                summary["dominant_weather_code"],
                summary["sample_count"],
            ),
        )
        connection.commit()

    return {
        "activity_id": activity_id,
        "weather_enrichment_run_id": weather_enrichment_run_id,
        "provider_key": OPEN_METEO_PROVIDER_KEY,
        "provider_version": OPEN_METEO_PROVIDER_VERSION,
        "sample_strategy": WEATHER_SAMPLE_STRATEGY,
        "sample_count": len(samples),
        "status": run_status,
    }


def _normalize_sample_timestamp_for_response(sampled_at: str | None, route_recorded_at: str | None) -> str | None:
    sampled_dt = _parse_datetime(sampled_at)
    route_dt = _parse_datetime(route_recorded_at)

    if route_dt is not None and route_dt.tzinfo is not None and (sampled_dt is None or sampled_dt.tzinfo is None):
        route_dt = route_dt.replace(microsecond=0)
        return route_dt.isoformat()

    if sampled_dt is None:
        return sampled_at

    sampled_dt = sampled_dt.replace(microsecond=0)
    return sampled_dt.isoformat() if sampled_dt.tzinfo is not None else sampled_dt.strftime("%Y-%m-%dT%H:%M:%S")


def get_activity_weather(activity_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        _ensure_exec_activity_weather_schema(connection)
        run = connection.execute(
            """
            SELECT weather_enrichment_run_id, activity_id, provider_key, provider_version,
                   provider_model, sample_strategy, requested_at, status, point_count,
                   sample_count, notes, metadata_json
            FROM exec_activity_weather_enrichment_runs
            WHERE activity_id = ?
            ORDER BY requested_at DESC, weather_enrichment_run_id DESC
            LIMIT 1
            """,
            (activity_id,),
        ).fetchone()
        if run is None:
            return None
        samples = connection.execute(
            """
            SELECT ws.route_point_index, ws.sampled_at, ws.weather_hour, ws.elapsed_seconds,
                   ws.distance_meters, ws.latitude_degrees, ws.longitude_degrees,
                   ws.temperature_2m, ws.apparent_temperature, ws.precipitation, ws.rain,
                   ws.snowfall, ws.weather_code, ws.cloud_cover, ws.wind_speed_10m,
                   ws.wind_gusts_10m, ws.wind_direction_10m, ws.shortwave_radiation,
                   rp.recorded_at AS route_recorded_at
            FROM exec_activity_weather_samples ws
            LEFT JOIN exec_activity_route_points rp
                   ON rp.activity_id = ws.activity_id
                  AND rp.point_index = ws.route_point_index
            WHERE ws.weather_enrichment_run_id = ?
            ORDER BY ws.route_point_index
            """,
            (run["weather_enrichment_run_id"],),
        ).fetchall()
        summary = connection.execute(
            """
            SELECT temperature_mean, temperature_min, temperature_max,
                   apparent_temperature_mean, precipitation_sum_est, rain_sum_est,
                   snowfall_sum_est, cloud_cover_mean, wind_speed_mean,
                   wind_speed_max, wind_gusts_max, shortwave_radiation_mean,
                   dominant_weather_code, sample_count
            FROM exec_activity_weather_summaries
            WHERE weather_enrichment_run_id = ?
            LIMIT 1
            """,
            (run["weather_enrichment_run_id"],),
        ).fetchone()
        payload = dict(run)
        payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
        payload["summary"] = dict(summary) if summary is not None else None
        payload["samples"] = []
        for row in samples:
            sample = dict(row)
            sample["sampled_at"] = _normalize_sample_timestamp_for_response(
                sample.get("sampled_at"), sample.pop("route_recorded_at", None)
            )
            payload["samples"].append(sample)
        return payload


def backfill_activity_weather_batch(
    *,
    activity_ids: list[int] | None = None,
    activity_id: int | None = None,
    season_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    with get_connection() as connection:
        _ensure_exec_activity_weather_schema(connection)
        conditions = [
            "EXISTS (SELECT 1 FROM exec_activity_route_points rp WHERE rp.activity_id = ea.activity_id)"
        ]
        params: list[Any] = []
        if activity_ids:
            placeholders = ",".join("?" for _ in activity_ids)
            conditions.append(f"ea.activity_id IN ({placeholders})")
            params.extend(int(candidate) for candidate in activity_ids)
        if activity_id is not None:
            conditions.append("ea.activity_id = ?")
            params.append(activity_id)
        if season_id is not None:
            conditions.append("ea.season_id = ?")
            params.append(season_id)
        if date_from is not None:
            conditions.append("ea.activity_date >= ?")
            params.append(date_from)
        if date_to is not None:
            conditions.append("ea.activity_date <= ?")
            params.append(date_to)
        if not force:
            conditions.append(
                "NOT EXISTS (SELECT 1 FROM exec_activity_weather_enrichment_runs wr WHERE wr.activity_id = ea.activity_id AND wr.provider_key = 'open_meteo')"
            )
        query = (
            "SELECT ea.activity_id FROM exec_activities ea WHERE " + " AND ".join(conditions) + " ORDER BY ea.activity_date, ea.activity_id"
        )
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        rows = connection.execute(query, tuple(params)).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        target_activity_id = int(row["activity_id"])
        try:
            result = enrich_activity_weather(target_activity_id, force=force)
        except Exception as error:
            results.append({"activity_id": target_activity_id, "status": "failed", "detail": str(error)})
            continue
        results.append({"activity_id": target_activity_id, "status": result["status"], "sample_count": result.get("sample_count", 0)})

    return {
        "activity_count": len(rows),
        "processed_count": len(results),
        "completed_count": sum(1 for item in results if item["status"] in {"created_new_run", "updated_existing_run", "reused_existing_run"}),
        "results": results,
    }


def backfill_activity_weather_for_external_ids(
    *,
    season_id: int,
    source_system: str,
    external_activity_ids: list[str],
    force: bool = False,
) -> dict[str, Any]:
    normalized_external_ids = [str(candidate).strip() for candidate in external_activity_ids if str(candidate).strip()]
    if not normalized_external_ids:
        return {
            "activity_count": 0,
            "processed_count": 0,
            "completed_count": 0,
            "results": [],
        }

    with get_connection() as connection:
        placeholders = ",".join("?" for _ in normalized_external_ids)
        rows = connection.execute(
            f"""
            SELECT activity_id
            FROM exec_activities
            WHERE season_id = ?
              AND source_system = ?
              AND external_activity_id IN ({placeholders})
            ORDER BY activity_date, activity_id
            """,
            (season_id, source_system, *normalized_external_ids),
        ).fetchall()

    return backfill_activity_weather_batch(
        activity_ids=[int(row["activity_id"]) for row in rows],
        force=force,
    )