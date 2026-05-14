from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database
from app.imports.contracts import GarminImportBatch, GarminImportRequest, ImportFetchMetadata, NormalizedActivity, NormalizedDailyMetric
from app.imports.garmin_connect import GarminConnectImportError, run_cli
from app.imports.pipeline import GarminImportPreview
from app.imports.storage import GarminImportStorage, ImportJobSummary
from app.imports.contracts import ImportJobBreakdown
from app.main import get_import_job, get_import_jobs


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


class GarminImportStorageStateTests(unittest.TestCase):
    def test_list_and_get_import_job_expose_reliability_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                storage = GarminImportStorage()
                import_job_id = storage.start_import_job(
                    season_id=2026,
                    source_system="garmin",
                    import_type="garminconnect",
                    source_path="2026-05-04:2026-05-10",
                    request_date_from="2026-05-04",
                    request_date_to="2026-05-10",
                    include_daily_metrics=True,
                    notes=["Importacion Garmin iniciada."],
                )

                breakdown = ImportJobBreakdown(
                    activity_rows_detected=3,
                    activity_rows_inserted=1,
                    activity_rows_updated=1,
                    activity_rows_skipped=1,
                    daily_metric_rows_detected=2,
                    daily_metric_rows_inserted=0,
                    daily_metric_rows_updated=1,
                    daily_metric_rows_skipped=1,
                )
                storage.fail_import_job(
                    import_job_id,
                    notes=["Importacion Garmin fallida durante persistencia.", "db roto"],
                    rows_detected=5,
                    rows_loaded=3,
                    failure_stage="persist",
                    failure_class="persistence_transaction",
                    partial_completion=True,
                    operator_detail="db roto",
                    breakdown=breakdown,
                )

                jobs = storage.list_import_jobs()
                self.assertEqual(len(jobs), 1)
                job = jobs[0]
                self.assertEqual(job["request_scope"]["season_id"], 2026)
                self.assertEqual(job["request_scope"]["date_from"], "2026-05-04")
                self.assertTrue(job["request_scope"]["include_daily_metrics"])
                self.assertEqual(job["failure_stage"], "persist")
                self.assertEqual(job["failure_class"], "persistence_transaction")
                self.assertEqual(job["retry_suitability"], "inspect_before_retry")
                self.assertTrue(job["partial_completion"])
                self.assertEqual(job["operator_detail"], "db roto")
                self.assertEqual(job["breakdown"]["activity_rows_skipped"], 1)
                self.assertEqual(job["breakdown"]["daily_metric_rows_detected"], 2)

                detailed_job = storage.get_import_job(import_job_id)
                self.assertIsNotNone(detailed_job)
                assert detailed_job is not None
                self.assertEqual(detailed_job["request_scope"]["date_to"], "2026-05-10")
                self.assertEqual(detailed_job["failure_stage"], "persist")
                self.assertEqual(detailed_job["retry_suitability"], "inspect_before_retry")
                self.assertEqual(detailed_job["staging_counts"], {"activities": 0, "daily_metrics": 0})

    def test_persist_batch_marks_partial_completed_when_daily_metrics_persist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                storage = GarminImportStorage()

                with storage_module_connection(database_path) as connection:
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            started_at TEXT,
                            discipline TEXT,
                            activity_type TEXT,
                            duration_seconds INTEGER,
                            distance_meters REAL,
                            ascent_meters REAL,
                            calories REAL,
                            avg_hr REAL,
                            max_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            training_load REAL,
                            avg_pace_seconds_per_km REAL,
                            raw_payload_path TEXT,
                            notes TEXT,
                            UNIQUE (source_system, external_activity_id)
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            weight_kg REAL,
                            sleep_hours REAL,
                            sleep_quality TEXT,
                            resting_hr REAL,
                            hrv REAL,
                            body_battery REAL,
                            subjective_energy INTEGER,
                            subjective_fatigue INTEGER,
                            UNIQUE (season_id, metric_date, source_system)
                        );
                        """
                    )

                request = GarminImportRequest(
                    season_id=2026,
                    date_from="2026-05-05",
                    date_to="2026-05-05",
                    include_daily_metrics=True,
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
                    daily_metrics=[
                        NormalizedDailyMetric(
                            metric_date="2026-05-05",
                            resting_hr=50,
                        )
                    ],
                )

                summary = storage.persist_batch(batch)
                self.assertEqual(summary.status, "partial_completed")
                self.assertEqual(summary.failure_stage, "persist")
                self.assertEqual(summary.failure_class, "persistence_transaction")
                self.assertEqual(summary.retry_suitability, "inspect_before_retry")
                self.assertTrue(summary.partial_completion)
                self.assertEqual(summary.rows_loaded, 1)
                self.assertEqual(summary.breakdown.activity_rows_inserted, 1)
                self.assertEqual(summary.breakdown.daily_metric_rows_inserted, 0)

                jobs = storage.list_import_jobs()
                self.assertEqual(jobs[0]["status"], "partial_completed")
                self.assertTrue(jobs[0]["partial_completion"])
                self.assertEqual(jobs[0]["retry_suitability"], "inspect_before_retry")

    def test_persist_batch_retry_creates_new_attempt_and_preserves_canonical_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                storage = GarminImportStorage()

                with storage_module_connection(database_path) as connection:
                    create_minimal_exec_tables(connection)

                request = GarminImportRequest(
                    season_id=2026,
                    date_from="2026-05-05",
                    date_to="2026-05-05",
                    include_daily_metrics=True,
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
                    daily_metrics=[
                        NormalizedDailyMetric(
                            metric_date="2026-05-05",
                            resting_hr=50,
                        )
                    ],
                )

                first_summary = storage.persist_batch(batch)
                second_summary = storage.persist_batch(batch)

                self.assertNotEqual(first_summary.import_job_id, second_summary.import_job_id)
                self.assertEqual(first_summary.status, "completed")
                self.assertEqual(second_summary.status, "completed")
                self.assertEqual(first_summary.breakdown.activity_rows_inserted, 1)
                self.assertEqual(first_summary.breakdown.activity_rows_updated, 0)
                self.assertEqual(second_summary.breakdown.activity_rows_inserted, 0)
                self.assertEqual(second_summary.breakdown.activity_rows_updated, 1)
                self.assertEqual(first_summary.breakdown.daily_metric_rows_inserted, 1)
                self.assertEqual(second_summary.breakdown.daily_metric_rows_updated, 1)
                self.assertEqual(second_summary.retry_suitability, "safe_to_retry")

                jobs = storage.list_import_jobs()
                self.assertEqual(len(jobs), 2)
                self.assertEqual(jobs[0]["import_job_id"], second_summary.import_job_id)
                self.assertEqual(jobs[1]["import_job_id"], first_summary.import_job_id)

                with storage_module_connection(database_path) as connection:
                    activity_total = connection.execute("SELECT COUNT(*) AS total FROM exec_activities").fetchone()["total"]
                    metric_total = connection.execute("SELECT COUNT(*) AS total FROM exec_daily_metrics").fetchone()["total"]

                self.assertEqual(activity_total, 1)
                self.assertEqual(metric_total, 1)


class GarminImportApiPayloadTests(unittest.TestCase):
    def test_import_job_endpoints_return_history_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                storage = GarminImportStorage()
                import_job_id = storage.start_import_job(
                    season_id=2026,
                    source_system="garmin",
                    import_type="garminconnect",
                    source_path="2026-05-04:2026-05-10",
                    request_date_from="2026-05-04",
                    request_date_to="2026-05-10",
                    include_daily_metrics=True,
                    notes=["Importacion Garmin iniciada."],
                )
                storage.fail_import_job(
                    import_job_id,
                    notes=["Importacion Garmin fallida durante fetch.", "auth rota"],
                    rows_detected=4,
                    rows_loaded=1,
                    failure_stage="configuration",
                    failure_class="configuration_authentication",
                    operator_detail="auth rota",
                    breakdown=ImportJobBreakdown(
                        activity_rows_detected=3,
                        activity_rows_inserted=1,
                        activity_rows_updated=0,
                        activity_rows_skipped=2,
                        daily_metric_rows_detected=1,
                        daily_metric_rows_inserted=0,
                        daily_metric_rows_updated=0,
                        daily_metric_rows_skipped=1,
                    ),
                )

                jobs = get_import_jobs()
                self.assertEqual(len(jobs), 1)
                job = jobs[0]
                self.assertEqual(job["import_job_id"], import_job_id)
                self.assertEqual(job["status"], "failed")
                self.assertEqual(job["failure_stage"], "configuration")
                self.assertEqual(job["failure_class"], "configuration_authentication")
                self.assertEqual(job["retry_suitability"], "safe_to_retry")
                self.assertFalse(job["partial_completion"])
                self.assertEqual(job["operator_detail"], "auth rota")
                self.assertEqual(
                    job["request_scope"],
                    {
                        "season_id": 2026,
                        "date_from": "2026-05-04",
                        "date_to": "2026-05-10",
                        "include_daily_metrics": True,
                    },
                )
                self.assertEqual(job["breakdown"]["activity_rows_detected"], 3)
                self.assertEqual(job["breakdown"]["activity_rows_skipped"], 2)
                self.assertEqual(job["breakdown"]["daily_metric_rows_detected"], 1)

                detail_job = get_import_job(import_job_id)
                self.assertEqual(detail_job["import_job_id"], import_job_id)
                self.assertEqual(detail_job["request_scope"]["season_id"], 2026)
                self.assertEqual(detail_job["request_scope"]["date_from"], "2026-05-04")
                self.assertEqual(detail_job["request_scope"]["date_to"], "2026-05-10")
                self.assertTrue(detail_job["request_scope"]["include_daily_metrics"])
                self.assertEqual(detail_job["failure_stage"], "configuration")
                self.assertEqual(detail_job["failure_class"], "configuration_authentication")
                self.assertEqual(detail_job["retry_suitability"], "safe_to_retry")
                self.assertEqual(detail_job["operator_detail"], "auth rota")
                self.assertEqual(detail_job["staging_counts"], {"activities": 0, "daily_metrics": 0})


@contextmanager
def storage_module_connection(database_path: Path):
    import sqlite3

    connection = sqlite3.connect(database_path)
    try:
        connection.row_factory = sqlite3.Row
        yield connection
        connection.commit()
    finally:
        connection.close()


def create_minimal_exec_tables(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS exec_activities (
            activity_id INTEGER PRIMARY KEY,
            season_id INTEGER NOT NULL,
            source_system TEXT NOT NULL,
            external_activity_id TEXT,
            activity_date TEXT NOT NULL,
            started_at TEXT,
            discipline TEXT,
            activity_type TEXT,
            duration_seconds INTEGER,
            distance_meters REAL,
            ascent_meters REAL,
            calories REAL,
            avg_hr REAL,
            max_hr REAL,
            avg_power REAL,
            normalized_power REAL,
            training_load REAL,
            avg_pace_seconds_per_km REAL,
            raw_payload_path TEXT,
            notes TEXT,
            UNIQUE (source_system, external_activity_id)
        );
        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
            daily_metric_id INTEGER PRIMARY KEY,
            season_id INTEGER NOT NULL,
            metric_date TEXT NOT NULL,
            source_system TEXT NOT NULL,
            weight_kg REAL,
            sleep_hours REAL,
            sleep_quality TEXT,
            resting_hr REAL,
            hrv REAL,
            body_battery REAL,
            subjective_energy INTEGER,
            subjective_fatigue INTEGER,
            notes TEXT,
            UNIQUE (season_id, metric_date, source_system)
        );
        """
    )