from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class GarminImportRequest:
    season_id: int
    date_from: str
    date_to: str
    include_daily_metrics: bool = True

    def to_scope_dict(self) -> dict[str, Any]:
        return {
            "season_id": self.season_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "include_daily_metrics": self.include_daily_metrics,
        }


@dataclass(slots=True)
class ImportFetchMetadata:
    source_system: str
    source_label: str
    date_from: str
    date_to: str
    raw_payload_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedActivity:
    external_activity_id: str
    activity_date: str
    started_at: str | None
    discipline: str | None
    activity_type: str | None
    duration_seconds: int | None
    distance_meters: float | None
    ascent_meters: float | None
    calories: float | None
    avg_hr: float | None
    max_hr: float | None
    avg_power: float | None
    normalized_power: float | None
    training_load: float | None
    avg_pace_seconds_per_km: float | None
    segment_data_status: str = "not_checked"
    segment_effort_count: int = 0
    segment_checked_at: str | None = None
    segments: list["NormalizedSegmentEffort"] = field(default_factory=list)
    metric_readings: list["NormalizedMetricReading"] = field(default_factory=list)
    route_points: list["NormalizedRoutePoint"] = field(default_factory=list)
    quality_status: str = "not_checked"
    quality_rule_version: str | None = None
    quality_checked_at: str | None = None
    quality_decision_count: int = 0
    quality_limited_metric_count: int = 0
    source_reading_fingerprint: str | None = None
    source_file: str | None = None
    raw_payload_path: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedDailyMetric:
    metric_date: str
    weight_kg: float | None = None
    weight_measured_at: str | None = None
    weight_measurement_source: str | None = None
    weight_measurements: list["NormalizedWeightMeasurement"] = field(default_factory=list)
    body_fat_pct: float | None = None
    body_water_pct: float | None = None
    bone_mass_kg: float | None = None
    muscle_mass_kg: float | None = None
    bmi: float | None = None
    visceral_fat: float | None = None
    metabolic_age: float | None = None
    physique_rating: float | None = None
    sleep_hours: float | None = None
    sleep_quality: str | None = None
    resting_hr: float | None = None
    vo2max_cycling: float | None = None
    vo2max_running: float | None = None
    lactate_threshold_hr: float | None = None
    hrv: float | None = None
    body_battery: float | None = None
    total_steps: int | None = None
    total_distance_m: float | None = None
    step_goal: int | None = None
    stress_avg: float | None = None
    stress_max: float | None = None
    spo2_avg: float | None = None
    spo2_sleep_avg: float | None = None
    spo2_7d_avg: float | None = None
    spo2_lowest: float | None = None
    subjective_energy: int | None = None
    subjective_fatigue: int | None = None
    notes: str | None = None
    raw_payload_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedWeightMeasurement:
    metric_date: str
    measurement_key: str
    measured_at: str | None
    weight_kg: float
    measurement_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedMetricReading:
    metric_name: str
    sample_index: int
    raw_value: float
    recorded_at: str | None = None
    elapsed_seconds: float | None = None
    source_payload_kind: str = "activity_detail_stream"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedRoutePoint:
    point_index: int
    latitude_degrees: float
    longitude_degrees: float
    altitude_meters: float | None = None
    distance_meters: float | None = None
    recorded_at: str | None = None
    elapsed_seconds: float | None = None
    source_payload_kind: str = "activity_detail_stream"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedSegmentDefinition:
    external_segment_id: str
    segment_name: str | None
    discipline: str | None
    distance_meters: float | None = None
    ascent_meters: float | None = None
    average_grade_percent: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedSegmentEffort:
    definition: NormalizedSegmentDefinition
    external_segment_effort_id: str
    started_at: str | None
    elapsed_time_seconds: int | None
    avg_power: float | None = None
    avg_cadence: float | None = None
    avg_heart_rate: float | None = None
    max_heart_rate: float | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["definition"] = self.definition.to_dict()
        return payload


@dataclass(slots=True)
class GarminImportBatch:
    request: GarminImportRequest
    metadata: ImportFetchMetadata
    activities: list[NormalizedActivity]
    daily_metrics: list[NormalizedDailyMetric]

    def counts(self) -> dict[str, int]:
        segment_activities_checked = 0
        segment_activities_with_data = 0
        segment_efforts_detected = 0
        quality_activities_checked = 0
        quality_activities_with_exclusions = 0
        quality_decisions_recorded = 0
        quality_limited_metrics = 0
        for activity in self.activities:
            if activity.segment_data_status != "not_checked":
                segment_activities_checked += 1
            if activity.segment_effort_count > 0:
                segment_activities_with_data += 1
            segment_efforts_detected += activity.segment_effort_count
            if activity.quality_status != "not_checked":
                quality_activities_checked += 1
            if activity.quality_status == "filtered":
                quality_activities_with_exclusions += 1
            quality_decisions_recorded += activity.quality_decision_count
            quality_limited_metrics += activity.quality_limited_metric_count
        return {
            "activities_detected": len(self.activities),
            "daily_metrics_detected": len(self.daily_metrics),
            "segment_activities_checked": segment_activities_checked,
            "segment_activities_with_data": segment_activities_with_data,
            "segment_efforts_detected": segment_efforts_detected,
            "quality_activities_checked": quality_activities_checked,
            "quality_activities_with_exclusions": quality_activities_with_exclusions,
            "quality_decisions_recorded": quality_decisions_recorded,
            "quality_limited_metrics": quality_limited_metrics,
        }


@dataclass(slots=True)
class ImportJobBreakdown:
    activity_rows_detected: int = 0
    activity_rows_inserted: int = 0
    activity_rows_updated: int = 0
    activity_rows_skipped: int = 0
    daily_metric_rows_detected: int = 0
    daily_metric_rows_inserted: int = 0
    daily_metric_rows_updated: int = 0
    daily_metric_rows_skipped: int = 0
    segment_activities_checked: int = 0
    segment_activities_with_data: int = 0
    segment_efforts_detected: int = 0
    segment_efforts_inserted: int = 0
    segment_efforts_updated: int = 0
    segment_efforts_skipped: int = 0
    quality_activities_checked: int = 0
    quality_activities_filtered: int = 0
    quality_runs_created: int = 0
    quality_runs_reused: int = 0
    quality_decisions_recorded: int = 0
    quality_limited_metrics: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ImportJobBreakdown":
        if not isinstance(payload, dict):
            return cls()
        values: dict[str, int] = {}
        for field_name in cls.__dataclass_fields__:
            raw_value = payload.get(field_name, 0)
            values[field_name] = int(raw_value) if raw_value is not None else 0
        return cls(**values)


@dataclass(slots=True)
class ImportJobState:
    source_system: str
    import_type: str
    source_path: str | None
    imported_at: str | None
    finished_at: str | None
    request_scope: dict[str, Any]
    status: str
    rows_detected: int
    rows_loaded: int
    failure_stage: str | None = None
    failure_class: str | None = None
    retry_suitability: str | None = None
    partial_completion: bool = False
    operator_detail: str | None = None
    notes: list[str] = field(default_factory=list)
    breakdown: ImportJobBreakdown = field(default_factory=ImportJobBreakdown)
    has_breakdown_details: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["breakdown"] = self.breakdown.to_dict()
        return payload


def iter_dates(date_from: str, date_to: str) -> list[str]:
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    if end < start:
        raise ValueError("date_to no puede ser anterior a date_from")
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current = date.fromordinal(current.toordinal() + 1)
    return days
