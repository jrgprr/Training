from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .db import get_connection
from .imports.contracts import NormalizedActivity, NormalizedMetricReading, NormalizedRoutePoint

RULE_SET_KEY = "bad_reading_filter"
RULE_SET_VERSION = "bad_reading_filter/v1"
HEART_RATE_HARD_CAP = 235.0


def _normalize_descriptor_metric_value(metric_name: str, raw_value: float) -> float:
    if metric_name == "stride_length" and raw_value > 10:
        return raw_value / 100.0
    return raw_value


@dataclass(slots=True)
class ActivityQualityDecision:
    metric_name: str
    decision_status: str
    start_sample_index: int
    end_sample_index: int
    reason_code: str
    rule_key: str
    threshold_low: float | None = None
    threshold_high: float | None = None
    evidence_json: str | None = None
    impacted_summary_kinds: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ActivityMetricSummary:
    metric_name: str
    summary_kind: str
    source_value: float | None
    trusted_value: float | None
    summary_status: str
    evaluated_reading_count: int
    accepted_reading_count: int
    excluded_reading_count: int
    changed_by_filter: bool


@dataclass(slots=True)
class ActivityQualityEvaluation:
    rule_set_key: str
    rule_set_version: str
    source_reading_fingerprint: str
    status: str
    evaluated_metric_names: list[str]
    skipped_metric_names: list[str]
    evaluated_reading_count: int
    excluded_reading_count: int
    limited_metric_count: int
    decisions: list[ActivityQualityDecision] = field(default_factory=list)
    summaries: list[ActivityMetricSummary] = field(default_factory=list)
    impacted_metric_names: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _coerce_numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _parse_recorded_at(timestamp_raw: Any) -> str | None:
    timestamp_value = _coerce_numeric(timestamp_raw)
    if timestamp_value is None:
        return None
    if timestamp_value > 10_000_000_000:
        timestamp_value /= 1000
    return datetime.fromtimestamp(timestamp_value, tz=timezone.utc).isoformat()


def _parse_tcx_time(time_text: str | None) -> datetime | None:
    if not time_text:
        return None
    normalized = time_text.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _build_passthrough_metric_summaries(readings: list[NormalizedMetricReading]) -> tuple[list[ActivityMetricSummary], list[str]]:
    summaries: list[ActivityMetricSummary] = []
    metric_names: list[str] = []
    readings_by_metric: dict[str, list[NormalizedMetricReading]] = {}
    for reading in readings:
        if reading.metric_name == "heart_rate":
            continue
        readings_by_metric.setdefault(reading.metric_name, []).append(reading)

    for metric_name in sorted(readings_by_metric):
        metric_readings = readings_by_metric[metric_name]
        values = [reading.raw_value for reading in metric_readings]
        if not values:
            continue
        metric_names.append(metric_name)
        summaries.extend(
            [
                ActivityMetricSummary(
                    metric_name=metric_name,
                    summary_kind="average",
                    source_value=round(sum(values) / len(values), 2),
                    trusted_value=round(sum(values) / len(values), 2),
                    summary_status="clean",
                    evaluated_reading_count=len(metric_readings),
                    accepted_reading_count=len(metric_readings),
                    excluded_reading_count=0,
                    changed_by_filter=False,
                ),
                ActivityMetricSummary(
                    metric_name=metric_name,
                    summary_kind="maximum",
                    source_value=max(values),
                    trusted_value=max(values),
                    summary_status="clean",
                    evaluated_reading_count=len(metric_readings),
                    accepted_reading_count=len(metric_readings),
                    excluded_reading_count=0,
                    changed_by_filter=False,
                ),
            ]
        )
    return summaries, metric_names


def normalize_route_points_from_activity_detail(payload: dict[str, Any] | None) -> list[NormalizedRoutePoint]:
    if not isinstance(payload, dict):
        return []
    metric_descriptors = payload.get("metricDescriptors")
    metric_rows = payload.get("activityDetailMetrics")
    if not isinstance(metric_descriptors, list) or not isinstance(metric_rows, list):
        return []

    descriptor_indexes: dict[str, int] = {}
    for item in metric_descriptors:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        index = item.get("metricsIndex")
        if isinstance(key, str) and isinstance(index, int):
            descriptor_indexes[key] = index

    latitude_index = descriptor_indexes.get("directLatitude")
    longitude_index = descriptor_indexes.get("directLongitude")
    if latitude_index is None or longitude_index is None:
        return []

    timestamp_index = descriptor_indexes.get("directTimestamp")
    elapsed_index = descriptor_indexes.get("sumElapsedDuration")
    distance_index = descriptor_indexes.get("sumDistance")
    altitude_index = descriptor_indexes.get("directElevation")

    route_points: list[NormalizedRoutePoint] = []
    for row in metric_rows:
        if not isinstance(row, dict):
            continue
        metrics = row.get("metrics")
        if not isinstance(metrics, list):
            continue
        if latitude_index >= len(metrics) or longitude_index >= len(metrics):
            continue
        latitude = _coerce_numeric(metrics[latitude_index])
        longitude = _coerce_numeric(metrics[longitude_index])
        if latitude is None or longitude is None:
            continue

        recorded_at = _parse_recorded_at(metrics[timestamp_index]) if timestamp_index is not None and timestamp_index < len(metrics) else None
        elapsed_seconds = _coerce_numeric(metrics[elapsed_index]) if elapsed_index is not None and elapsed_index < len(metrics) else None
        altitude_meters = _coerce_numeric(metrics[altitude_index]) if altitude_index is not None and altitude_index < len(metrics) else None
        distance_meters = _coerce_numeric(metrics[distance_index]) if distance_index is not None and distance_index < len(metrics) else None
        route_points.append(
            NormalizedRoutePoint(
                point_index=len(route_points),
                latitude_degrees=latitude,
                longitude_degrees=longitude,
                altitude_meters=altitude_meters,
                distance_meters=distance_meters,
                recorded_at=recorded_at,
                elapsed_seconds=elapsed_seconds,
            )
        )

    return route_points


def normalize_metric_readings_from_activity_detail(payload: dict[str, Any] | None) -> list[NormalizedMetricReading]:
    if not isinstance(payload, dict):
        return []
    metric_descriptors = payload.get("metricDescriptors")
    metric_rows = payload.get("activityDetailMetrics")
    if not isinstance(metric_descriptors, list) or not isinstance(metric_rows, list):
        return []

    descriptor_indexes: dict[str, int] = {}
    for item in metric_descriptors:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        index = item.get("metricsIndex")
        if isinstance(key, str) and isinstance(index, int):
            descriptor_indexes[key] = index

    timestamp_index = descriptor_indexes.get("directTimestamp")
    elapsed_index = descriptor_indexes.get("sumElapsedDuration")
    metric_keys = {
        "directHeartRate": "heart_rate",
        "directPower": "power",
        "directBikeCadence": "bike_cadence",
        "directRunCadence": "run_cadence",
        "directDoubleCadence": "cadence_double",
        "directFractionalCadence": "cadence_fractional",
        "directRespirationRate": "respiration_rate",
        "directVerticalRatio": "vertical_ratio",
        "directGroundContactTime": "ground_contact_time",
        "directGroundContactBalanceLeft": "ground_contact_balance_left",
        "directVerticalOscillation": "vertical_oscillation",
        "directStrideLength": "stride_length",
        "directPerformanceCondition": "performance_condition",
        "directAirTemperature": "air_temperature",
        "directSpeed": "speed",
        "directElevation": "elevation",
        "directVerticalSpeed": "vertical_speed",
    }
    sample_index_by_metric: dict[str, int] = {metric_name: 0 for metric_name in metric_keys.values()}
    readings: list[NormalizedMetricReading] = []

    for row in metric_rows:
        if not isinstance(row, dict):
            continue
        metrics = row.get("metrics")
        if not isinstance(metrics, list):
            continue

        recorded_at = _parse_recorded_at(metrics[timestamp_index]) if timestamp_index is not None and timestamp_index < len(metrics) else None

        elapsed_seconds = _coerce_numeric(metrics[elapsed_index]) if elapsed_index is not None and elapsed_index < len(metrics) else None

        for source_key, metric_name in metric_keys.items():
            metric_index = descriptor_indexes.get(source_key)
            if metric_index is None or metric_index >= len(metrics):
                continue
            raw_value = metrics[metric_index]
            if not isinstance(raw_value, (int, float)) or isinstance(raw_value, bool):
                continue
            normalized_value = _normalize_descriptor_metric_value(metric_name, float(raw_value))
            readings.append(
                NormalizedMetricReading(
                    metric_name=metric_name,
                    sample_index=sample_index_by_metric[metric_name],
                    raw_value=normalized_value,
                    recorded_at=recorded_at,
                    elapsed_seconds=elapsed_seconds,
                )
            )
            sample_index_by_metric[metric_name] += 1

    return readings


def build_source_reading_fingerprint(readings: list[NormalizedMetricReading]) -> str:
    digest = hashlib.sha1()
    for reading in sorted(readings, key=lambda item: (item.metric_name, item.sample_index)):
        raw_value = format(float(reading.raw_value), ".12g")
        elapsed_seconds = None if reading.elapsed_seconds is None else format(float(reading.elapsed_seconds), ".12g")
        digest.update(
            f"{reading.metric_name}|{reading.sample_index}|{raw_value}|{reading.recorded_at}|{elapsed_seconds}".encode(
                "utf-8"
            )
        )
    return digest.hexdigest()


def evaluate_activity_quality(activity: NormalizedActivity) -> ActivityQualityEvaluation:
    source_reading_fingerprint = build_source_reading_fingerprint(activity.metric_readings)
    heart_rate_readings = [reading for reading in activity.metric_readings if reading.metric_name == "heart_rate"]
    passthrough_summaries, passthrough_metric_names = _build_passthrough_metric_summaries(activity.metric_readings)
    checked_at = datetime.now(timezone.utc).isoformat()

    if not heart_rate_readings:
        activity.quality_status = "not_checked"
        activity.quality_rule_version = RULE_SET_VERSION
        activity.quality_checked_at = None
        activity.quality_decision_count = 0
        activity.quality_limited_metric_count = 0
        activity.source_reading_fingerprint = source_reading_fingerprint
        return ActivityQualityEvaluation(
            rule_set_key=RULE_SET_KEY,
            rule_set_version=RULE_SET_VERSION,
            source_reading_fingerprint=source_reading_fingerprint,
            status="not_checked",
            evaluated_metric_names=passthrough_metric_names,
            skipped_metric_names=["heart_rate:missing_stream"],
            evaluated_reading_count=0,
            excluded_reading_count=0,
            limited_metric_count=0,
            summaries=passthrough_summaries,
            checked_at=checked_at,
        )

    excluded_indexes = [reading.sample_index for reading in heart_rate_readings if reading.raw_value > HEART_RATE_HARD_CAP]
    excluded_index_set = set(excluded_indexes)
    accepted_readings = [reading for reading in heart_rate_readings if reading.sample_index not in excluded_index_set]

    decisions: list[ActivityQualityDecision] = []
    if excluded_indexes:
        range_start = excluded_indexes[0]
        range_end = excluded_indexes[0]
        for sample_index in excluded_indexes[1:]:
            if sample_index == range_end + 1:
                range_end = sample_index
                continue
            decisions.append(
                ActivityQualityDecision(
                    metric_name="heart_rate",
                    decision_status="excluded",
                    start_sample_index=range_start,
                    end_sample_index=range_end,
                    reason_code="hr_above_hard_cap",
                    rule_key="hr_absolute_ceiling",
                    threshold_high=HEART_RATE_HARD_CAP,
                    evidence_json=json.dumps({"sample_count": range_end - range_start + 1}, ensure_ascii=True),
                    impacted_summary_kinds=["average", "maximum"],
                )
            )
            range_start = sample_index
            range_end = sample_index
        decisions.append(
            ActivityQualityDecision(
                metric_name="heart_rate",
                decision_status="excluded",
                start_sample_index=range_start,
                end_sample_index=range_end,
                reason_code="hr_above_hard_cap",
                rule_key="hr_absolute_ceiling",
                threshold_high=HEART_RATE_HARD_CAP,
                evidence_json=json.dumps({"sample_count": range_end - range_start + 1}, ensure_ascii=True),
                impacted_summary_kinds=["average", "maximum"],
            )
        )

    source_values = [reading.raw_value for reading in heart_rate_readings]
    accepted_values = [reading.raw_value for reading in accepted_readings]
    source_average = round(sum(source_values) / len(source_values), 2) if source_values else None
    trusted_average = round(sum(accepted_values) / len(accepted_values), 2) if accepted_values else None
    source_maximum = max(source_values) if source_values else None
    trusted_maximum = max(accepted_values) if accepted_values else None

    limited_metric_count = 0
    if not accepted_values:
        summary_status = "quality_limited"
        activity.quality_status = "limited"
        limited_metric_count = 1
    elif decisions:
        summary_status = "filtered"
        activity.quality_status = "filtered"
    else:
        summary_status = "clean"
        activity.quality_status = "clean"

    summaries = [
        ActivityMetricSummary(
            metric_name="heart_rate",
            summary_kind="average",
            source_value=source_average,
            trusted_value=trusted_average,
            summary_status=summary_status,
            evaluated_reading_count=len(heart_rate_readings),
            accepted_reading_count=len(accepted_readings),
            excluded_reading_count=len(heart_rate_readings) - len(accepted_readings),
            changed_by_filter=source_average != trusted_average,
        ),
        ActivityMetricSummary(
            metric_name="heart_rate",
            summary_kind="maximum",
            source_value=source_maximum,
            trusted_value=trusted_maximum,
            summary_status=summary_status,
            evaluated_reading_count=len(heart_rate_readings),
            accepted_reading_count=len(accepted_readings),
            excluded_reading_count=len(heart_rate_readings) - len(accepted_readings),
            changed_by_filter=source_maximum != trusted_maximum,
        ),
    ] + passthrough_summaries

    activity.avg_hr = trusted_average
    activity.max_hr = trusted_maximum
    activity.quality_rule_version = RULE_SET_VERSION
    activity.quality_checked_at = checked_at
    activity.quality_decision_count = len(decisions)
    activity.quality_limited_metric_count = limited_metric_count
    activity.source_reading_fingerprint = source_reading_fingerprint

    return ActivityQualityEvaluation(
        rule_set_key=RULE_SET_KEY,
        rule_set_version=RULE_SET_VERSION,
        source_reading_fingerprint=source_reading_fingerprint,
        status=activity.quality_status,
        evaluated_metric_names=["heart_rate", *passthrough_metric_names],
        skipped_metric_names=[],
        evaluated_reading_count=len(heart_rate_readings),
        excluded_reading_count=len(heart_rate_readings) - len(accepted_readings),
        limited_metric_count=limited_metric_count,
        decisions=decisions,
        summaries=summaries,
        impacted_metric_names=["heart_rate"] if decisions or limited_metric_count else [],
        checked_at=checked_at,
    )


def normalize_metric_readings_from_tcx_artifact(raw_payload_path: str | None) -> list[NormalizedMetricReading]:
    if not raw_payload_path:
        return []
    artifact_path = Path(raw_payload_path)
    if not artifact_path.is_file():
        return []

    try:
        root = ElementTree.parse(artifact_path).getroot()
    except (ElementTree.ParseError, OSError):
        return []

    namespaces = {
        "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    }
    trackpoints = root.findall(".//tcx:Trackpoint", namespaces)
    readings: list[NormalizedMetricReading] = []
    heart_rate_index = 0

    for trackpoint in trackpoints:
        time_text = trackpoint.findtext("tcx:Time", default=None, namespaces=namespaces)
        distance_text = trackpoint.findtext("tcx:DistanceMeters", default=None, namespaces=namespaces)
        heart_rate_text = trackpoint.findtext("tcx:HeartRateBpm/tcx:Value", default=None, namespaces=namespaces)
        cadence_text = trackpoint.findtext("tcx:Cadence", default=None, namespaces=namespaces)
        watts_text = trackpoint.findtext(
            "tcx:Extensions/ns3:TPX/ns3:Watts", default=None, namespaces=namespaces
        )

        elapsed_seconds: float | None = None
        if distance_text is not None:
            try:
                float(distance_text)
            except (TypeError, ValueError):
                pass

        if heart_rate_text is not None:
            try:
                readings.append(
                    NormalizedMetricReading(
                        metric_name="heart_rate",
                        sample_index=heart_rate_index,
                        raw_value=float(heart_rate_text),
                        recorded_at=time_text,
                        elapsed_seconds=elapsed_seconds,
                        source_payload_kind="tcx_artifact",
                    )
                )
                heart_rate_index += 1
            except (TypeError, ValueError):
                pass

        if watts_text is not None:
            try:
                readings.append(
                    NormalizedMetricReading(
                        metric_name="power",
                        sample_index=sum(1 for item in readings if item.metric_name == "power"),
                        raw_value=float(watts_text),
                        recorded_at=time_text,
                        elapsed_seconds=elapsed_seconds,
                        source_payload_kind="tcx_artifact",
                    )
                )
            except (TypeError, ValueError):
                pass

        if cadence_text is not None:
            try:
                readings.append(
                    NormalizedMetricReading(
                        metric_name="bike_cadence",
                        sample_index=sum(1 for item in readings if item.metric_name == "bike_cadence"),
                        raw_value=float(cadence_text),
                        recorded_at=time_text,
                        elapsed_seconds=elapsed_seconds,
                        source_payload_kind="tcx_artifact",
                    )
                )
            except (TypeError, ValueError):
                pass

    return readings


def normalize_route_points_from_tcx_artifact(raw_payload_path: str | None) -> list[NormalizedRoutePoint]:
    if not raw_payload_path:
        return []
    artifact_path = Path(raw_payload_path)
    if not artifact_path.is_file():
        return []

    try:
        root = ElementTree.parse(artifact_path).getroot()
    except (ElementTree.ParseError, OSError):
        return []

    namespaces = {
        "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    }
    trackpoints = root.findall(".//tcx:Trackpoint", namespaces)
    route_points: list[NormalizedRoutePoint] = []
    first_timestamp: datetime | None = None

    for trackpoint in trackpoints:
        latitude_text = trackpoint.findtext("tcx:Position/tcx:LatitudeDegrees", default=None, namespaces=namespaces)
        longitude_text = trackpoint.findtext("tcx:Position/tcx:LongitudeDegrees", default=None, namespaces=namespaces)
        if latitude_text is None or longitude_text is None:
            continue
        try:
            latitude = float(latitude_text)
            longitude = float(longitude_text)
        except (TypeError, ValueError):
            continue

        time_text = trackpoint.findtext("tcx:Time", default=None, namespaces=namespaces)
        timestamp = _parse_tcx_time(time_text)
        if first_timestamp is None and timestamp is not None:
            first_timestamp = timestamp
        elapsed_seconds = (timestamp - first_timestamp).total_seconds() if timestamp is not None and first_timestamp is not None else None

        altitude_text = trackpoint.findtext("tcx:AltitudeMeters", default=None, namespaces=namespaces)
        distance_text = trackpoint.findtext("tcx:DistanceMeters", default=None, namespaces=namespaces)
        altitude_meters = None
        distance_meters = None
        try:
            if altitude_text is not None:
                altitude_meters = float(altitude_text)
        except (TypeError, ValueError):
            altitude_meters = None
        try:
            if distance_text is not None:
                distance_meters = float(distance_text)
        except (TypeError, ValueError):
            distance_meters = None

        route_points.append(
            NormalizedRoutePoint(
                point_index=len(route_points),
                latitude_degrees=latitude,
                longitude_degrees=longitude,
                altitude_meters=altitude_meters,
                distance_meters=distance_meters,
                recorded_at=time_text,
                elapsed_seconds=elapsed_seconds,
                source_payload_kind="tcx_artifact",
            )
        )

    return route_points


def get_activity_quality(activity_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        activity = connection.execute(
            """
            SELECT activity_id, external_activity_id, activity_date, quality_status,
                   quality_checked_at, quality_rule_version
            FROM exec_activities
            WHERE activity_id = ?
            """,
            (activity_id,),
        ).fetchone()
        if activity is None:
            return None

        quality_run = connection.execute(
            """
            SELECT quality_run_id, source_reading_fingerprint
            FROM exec_activity_quality_runs
            WHERE activity_id = ?
            ORDER BY evaluated_at DESC, quality_run_id DESC
            LIMIT 1
            """,
            (activity_id,),
        ).fetchone()

        summary_rows = connection.execute(
            """
            SELECT metric_name, summary_kind, source_value, trusted_value, summary_status,
                   evaluated_reading_count, accepted_reading_count, excluded_reading_count, changed_by_filter
            FROM exec_activity_metric_summaries
            WHERE activity_id = ?
            ORDER BY metric_name, summary_kind
            """,
            (activity_id,),
        ).fetchall()
        decision_rows = connection.execute(
            """
            SELECT quality_decision_id, metric_name, decision_status, start_sample_index,
                   end_sample_index, reason_code, rule_key, threshold_low, threshold_high,
                   impacted_summary_kinds
            FROM exec_activity_quality_decisions
            WHERE activity_id = ?
            ORDER BY metric_name, start_sample_index, quality_decision_id
            """,
            (activity_id,),
        ).fetchall()

    metrics_by_name: dict[str, dict[str, Any]] = {}
    for row in summary_rows:
        metric_name = row["metric_name"]
        metric_entry = metrics_by_name.setdefault(
            metric_name,
            {
                "metric_name": metric_name,
                "metric_status": row["summary_status"],
                "evaluated_reading_count": row["evaluated_reading_count"],
                "accepted_reading_count": row["accepted_reading_count"],
                "excluded_reading_count": row["excluded_reading_count"],
                "summary_impacts": [],
                "decisions": [],
            },
        )
        metric_entry["summary_impacts"].append(
            {
                "summary_kind": row["summary_kind"],
                "source_value": row["source_value"],
                "trusted_value": row["trusted_value"],
                "changed_by_filter": bool(row["changed_by_filter"]),
                "summary_status": row["summary_status"],
            }
        )

    for row in decision_rows:
        metric_entry = metrics_by_name.setdefault(
            row["metric_name"],
            {
                "metric_name": row["metric_name"],
                "metric_status": "filtered",
                "evaluated_reading_count": 0,
                "accepted_reading_count": 0,
                "excluded_reading_count": 0,
                "summary_impacts": [],
                "decisions": [],
            },
        )
        impacted_summary_kinds = json.loads(row["impacted_summary_kinds"] or "[]")
        metric_entry["decisions"].append(
            {
                "quality_decision_id": row["quality_decision_id"],
                "decision_status": row["decision_status"],
                "start_sample_index": row["start_sample_index"],
                "end_sample_index": row["end_sample_index"],
                "reason_code": row["reason_code"],
                "rule_key": row["rule_key"],
                "threshold_low": row["threshold_low"],
                "threshold_high": row["threshold_high"],
                "impacted_summary_kinds": impacted_summary_kinds,
            }
        )

    return {
        "activity": {
            "activity_id": activity["activity_id"],
            "external_activity_id": activity["external_activity_id"],
            "activity_date": activity["activity_date"],
            "quality_status": activity["quality_status"],
            "quality_checked_at": activity["quality_checked_at"],
            "quality_rule_version": activity["quality_rule_version"],
            "source_reading_fingerprint": None if quality_run is None else quality_run["source_reading_fingerprint"],
        },
        "metrics": list(metrics_by_name.values()),
    }