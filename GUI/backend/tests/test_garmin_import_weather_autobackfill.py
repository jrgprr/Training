from __future__ import annotations

import unittest
from unittest.mock import patch

from app.imports.contracts import GarminImportBatch, GarminImportRequest, ImportFetchMetadata, NormalizedActivity
from app.imports.storage import ImportJobBreakdown, ImportJobSummary
from app.main import GarminConnectImportPayload, run_garmin_connect_import


class GarminImportWeatherAutoBackfillTests(unittest.TestCase):
    def test_run_import_triggers_weather_backfill_for_imported_garmin_activities(self) -> None:
        payload = GarminConnectImportPayload(
            season_id=2026,
            date_from="2026-05-05",
            date_to="2026-05-05",
            include_daily_metrics=False,
        )
        batch = GarminImportBatch(
            request=GarminImportRequest(
                season_id=2026,
                date_from="2026-05-05",
                date_to="2026-05-05",
                include_daily_metrics=False,
            ),
            metadata=ImportFetchMetadata(
                source_system="garmin",
                source_label="garminconnect",
                date_from="2026-05-05",
                date_to="2026-05-05",
                notes=["batch ok"],
            ),
            activities=[
                NormalizedActivity(
                    external_activity_id="abc123",
                    activity_date="2026-05-05",
                    started_at="2026-05-05T08:00:00",
                    discipline="road_biking",
                    activity_type="Salida",
                    duration_seconds=3600,
                    distance_meters=25000,
                    ascent_meters=400,
                    calories=700,
                    avg_hr=150,
                    max_hr=175,
                    avg_power=220,
                    normalized_power=235,
                    training_load=90,
                    avg_pace_seconds_per_km=None,
                )
            ],
            daily_metrics=[],
        )
        summary = ImportJobSummary(
            import_job_id=77,
            status="completed",
            rows_detected=1,
            rows_loaded=1,
            request_scope=batch.request.to_scope_dict(),
            retry_suitability="safe_to_retry",
            notes=["done"],
            breakdown=ImportJobBreakdown(),
        )

        with patch("app.main.GarminImportPipeline") as pipeline_cls, patch("app.main.GarminImportStorage") as storage_cls, patch(
            "app.main.backfill_activity_weather_for_external_ids"
        ) as weather_backfill:
            pipeline_cls.return_value.run.return_value = batch
            storage = storage_cls.return_value
            storage.start_import_job.return_value = 77
            storage.persist_batch.return_value = summary
            weather_backfill.return_value = {
                "activity_count": 1,
                "processed_count": 1,
                "completed_count": 1,
                "results": [{"activity_id": 9001, "status": "created_new_run", "sample_count": 3}],
            }

            response = run_garmin_connect_import(payload)

        weather_backfill.assert_called_once_with(
            season_id=2026,
            source_system="garmin",
            external_activity_ids=["abc123"],
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["counts"]["weather_activities_processed"], 1)
        self.assertEqual(response["counts"]["weather_activities_completed"], 1)
        self.assertEqual(response["metadata"]["weather_summary"]["completed_count"], 1)


if __name__ == "__main__":
    unittest.main()