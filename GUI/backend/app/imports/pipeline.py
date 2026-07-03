from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import GarminImportBatch, GarminImportRequest
from .garmin_connect import GarminConnectAdapter


@dataclass(slots=True)
class GarminImportPreview:
    request: GarminImportRequest
    source_system: str
    source_label: str
    notes: list[str]
    activities_detected: int
    daily_metrics_detected: int
    ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": {
                "season_id": self.request.season_id,
                "date_from": self.request.date_from,
                "date_to": self.request.date_to,
                "include_daily_metrics": self.request.include_daily_metrics,
            },
            "source_system": self.source_system,
            "source_label": self.source_label,
            "notes": self.notes,
            "activities_detected": self.activities_detected,
            "daily_metrics_detected": self.daily_metrics_detected,
            "ready": self.ready,
        }


class GarminImportPipeline:
    def __init__(self, adapter: GarminConnectAdapter | None = None) -> None:
        self.adapter = adapter or GarminConnectAdapter()

    def sync_profile(self, season_id: int, effective_start_date: str | None = None) -> dict[str, Any]:
        return self.adapter.sync_profile_values(season_id=season_id, effective_start_date=effective_start_date)

    def preview(self, request: GarminImportRequest) -> GarminImportPreview:
        batch = self.adapter.fetch(request)
        metadata = batch.metadata
        counts = batch.counts()
        return GarminImportPreview(
            request=request,
            source_system=metadata.source_system,
            source_label=metadata.source_label,
            notes=metadata.notes,
            activities_detected=counts["activities_detected"],
            daily_metrics_detected=counts["daily_metrics_detected"],
            ready=True,
        )

    def run(self, request: GarminImportRequest) -> GarminImportBatch:
        profile_sync_notes: list[str] = []
        try:
            profile_sync = self.sync_profile(request.season_id)
            profile_sync_notes.extend(profile_sync.get("notes", []))
        except Exception as error:
            profile_sync_notes.append(f"No se pudo sincronizar el perfil Garmin con la app: {error}")

        batch = self.adapter.fetch(request)
        batch.metadata.notes.extend(profile_sync_notes)
        return batch
