from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from app.imports.contracts import GarminImportBatch, GarminImportRequest, ImportFetchMetadata, NormalizedActivity
from app.imports.garmin_connect import GarminConnectImportError, run_cli
from app.imports.pipeline import GarminImportPreview
from app.imports.storage import ImportJobSummary
from app.imports.contracts import ImportJobBreakdown


class GarminConnectCliTests(unittest.TestCase):
    def test_dry_run_prints_preview_summary(self) -> None:
        request = GarminImportRequest(
            season_id=2026,
            date_from="2026-05-04",
            date_to="2026-05-10",
            include_daily_metrics=True,
        )
        preview = GarminImportPreview(
            request=request,
            source_system="garmin",
            source_label="garminconnect",
            notes=["preview ok"],
            activities_detected=3,
            daily_metrics_detected=7,
            ready=True,
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("app.imports.pipeline.GarminImportPipeline") as pipeline_cls, patch(
            "app.imports.storage.GarminImportStorage"
        ) as storage_cls, redirect_stdout(stdout), redirect_stderr(stderr):
            pipeline_cls.return_value.preview.return_value = preview

            exit_code = run_cli(["--season", "2026", "--from", "2026-05-04", "--to", "2026-05-10", "--dry-run"])

        self.assertEqual(exit_code, 0)
        pipeline_cls.return_value.preview.assert_called_once()
        storage_cls.assert_called_once()
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["activities_detected"], 3)
        self.assertEqual(payload["daily_metrics_detected"], 7)

    def test_apply_persists_batch_and_prints_job_summary(self) -> None:
        request = GarminImportRequest(
            season_id=2026,
            date_from="2026-05-05",
            date_to="2026-05-05",
            include_daily_metrics=False,
        )
        batch = GarminImportBatch(
            request=request,
            metadata=ImportFetchMetadata(
                source_system="garmin",
                source_label="garminconnect",
                date_from="2026-05-05",
                date_to="2026-05-05",
                notes=["batch ok"],
            ),
            activities=[
                NormalizedActivity(
                    external_activity_id="123",
                    activity_date="2026-05-05",
                    started_at=None,
                    discipline="strength_training",
                    activity_type="Fuerza",
                    duration_seconds=1800,
                    distance_meters=None,
                    ascent_meters=None,
                    calories=200,
                    avg_hr=None,
                    max_hr=None,
                    avg_power=None,
                    normalized_power=None,
                    training_load=None,
                    avg_pace_seconds_per_km=None,
                )
            ],
            daily_metrics=[],
        )
        summary = ImportJobSummary(
            import_job_id=99,
            status="completed",
            rows_detected=1,
            rows_loaded=1,
            request_scope=request.to_scope_dict(),
            retry_suitability="safe_to_retry",
            notes=["done"],
            breakdown=ImportJobBreakdown(),
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("app.imports.pipeline.GarminImportPipeline") as pipeline_cls, patch(
            "app.imports.storage.GarminImportStorage"
        ) as storage_cls, redirect_stdout(stdout), redirect_stderr(stderr):
            pipeline_cls.return_value.run.return_value = batch
            storage = storage_cls.return_value
            storage.start_import_job.return_value = 99
            storage.persist_batch.return_value = summary

            exit_code = run_cli(
                ["--season", "2026", "--from", "2026-05-05", "--to", "2026-05-05", "--apply", "--no-daily-metrics"]
            )

        self.assertEqual(exit_code, 0)
        storage.start_import_job.assert_called_once()
        storage.persist_batch.assert_called_once_with(batch, import_job_id=99)
        storage.fail_import_job.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "apply")
        self.assertEqual(payload["import_job"]["import_job_id"], 99)
        self.assertEqual(payload["import_job"]["retry_suitability"], "safe_to_retry")
        self.assertEqual(payload["import_job"]["request_scope"]["season_id"], 2026)

    def test_apply_marks_job_failed_when_fetch_errors(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("app.imports.pipeline.GarminImportPipeline") as pipeline_cls, patch(
            "app.imports.storage.GarminImportStorage"
        ) as storage_cls, redirect_stdout(stdout), redirect_stderr(stderr):
            pipeline_cls.return_value.run.side_effect = GarminConnectImportError("fetch roto")
            storage = storage_cls.return_value
            storage.start_import_job.return_value = 41

            exit_code = run_cli(["--season", "2026", "--from", "2026-05-05", "--to", "2026-05-05", "--apply"])

        self.assertEqual(exit_code, 1)
        storage.start_import_job.assert_called_once()
        storage.fail_import_job.assert_called_once_with(
            41,
            notes=["Importacion Garmin fallida durante fetch.", "fetch roto"],
            failure_stage="fetch",
            failure_class="transport_rate_limit",
            operator_detail="fetch roto",
        )
        self.assertEqual(stdout.getvalue(), "")
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["detail"], "fetch roto")


if __name__ == "__main__":
    unittest.main()