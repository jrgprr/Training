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
    source_file: str | None = None
    raw_payload_path: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedDailyMetric:
    metric_date: str
    weight_kg: float | None = None
    sleep_hours: float | None = None
    sleep_quality: str | None = None
    resting_hr: float | None = None
    hrv: float | None = None
    body_battery: float | None = None
    subjective_energy: int | None = None
    subjective_fatigue: int | None = None
    notes: str | None = None
    raw_payload_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GarminImportBatch:
    request: GarminImportRequest
    metadata: ImportFetchMetadata
    activities: list[NormalizedActivity]
    daily_metrics: list[NormalizedDailyMetric]

    def counts(self) -> dict[str, int]:
        return {
            "activities_detected": len(self.activities),
            "daily_metrics_detected": len(self.daily_metrics),
        }


@dataclass(slots=True)
class ImportJobBreakdown:
    activity_rows_inserted: int = 0
    activity_rows_updated: int = 0
    daily_metric_rows_inserted: int = 0
    daily_metric_rows_updated: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


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
