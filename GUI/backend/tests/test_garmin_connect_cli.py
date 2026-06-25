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
from app.planned_prescriptions import replace_planned_session_prescription


def make_test_prescription(
    planned_session_id: int,
    prescription_type: str,
    estimated_duration_min: int | None,
    estimated_duration_max: int | None,
    blocks: list[dict[str, object]],
    *,
    title: str | None = None,
    focus_primary: str | None = None,
    focus_secondary: str | None = None,
) -> dict[str, object]:
    return {
        "planned_session_id": planned_session_id,
        "prescription_type": prescription_type,
        "discipline_family": None,
        "title": title,
        "focus_primary": focus_primary,
        "focus_secondary": focus_secondary,
        "estimated_duration_min": estimated_duration_min,
        "estimated_duration_max": estimated_duration_max,
        "target_rpe_min": None,
        "target_rpe_max": None,
        "warmup_notes": None,
        "cooldown_notes": None,
        "execution_notes": None,
        "adaptation_notes": None,
        "source_kind": "test",
        "structure_version": "v1",
        "source_markdown_path": None,
        "blocks": blocks,
    }


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
        ) as storage_cls, patch(
            "app.activity_weather.backfill_activity_weather_for_external_ids"
        ) as weather_backfill, redirect_stdout(stdout), redirect_stderr(stderr):
            pipeline_cls.return_value.run.return_value = batch
            storage = storage_cls.return_value
            storage.start_import_job.return_value = 99
            storage.persist_batch.return_value = summary
            weather_backfill.return_value = {
                "activity_count": 1,
                "processed_count": 1,
                "completed_count": 1,
                "results": [{"activity_id": 1, "status": "created_new_run", "sample_count": 2}],
            }

            exit_code = run_cli(
                ["--season", "2026", "--from", "2026-05-05", "--to", "2026-05-05", "--apply", "--no-daily-metrics"]
            )

        self.assertEqual(exit_code, 0)
        storage.start_import_job.assert_called_once()
        storage.persist_batch.assert_called_once_with(batch, import_job_id=99)
        storage.fail_import_job.assert_not_called()
        weather_backfill.assert_called_once_with(
            season_id=2026,
            source_system="garmin",
            external_activity_ids=["123"],
        )
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "apply")
        self.assertEqual(payload["import_job"]["import_job_id"], 99)
        self.assertEqual(payload["import_job"]["retry_suitability"], "safe_to_retry")
        self.assertEqual(payload["import_job"]["request_scope"]["season_id"], 2026)
        self.assertEqual(payload["metadata"]["weather_summary"]["completed_count"], 1)

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


class GarminImportStorageAutoLinkTests(unittest.TestCase):
    def test_auto_link_prefers_structured_components_over_free_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                storage = GarminImportStorage()

                with storage_module_connection(database_path) as connection:
                    create_minimal_exec_tables(connection)
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_meso_blocks (
                            block_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS plan_micro_weeks (
                            week_id INTEGER PRIMARY KEY,
                            block_id INTEGER NOT NULL,
                            start_date TEXT,
                            end_date TEXT
                        );
                        CREATE TABLE IF NOT EXISTS plan_planned_sessions (
                            planned_session_id INTEGER PRIMARY KEY,
                            week_id INTEGER NOT NULL,
                            session_date TEXT NOT NULL,
                            planned_type TEXT,
                            objective TEXT,
                            primary_session TEXT,
                            complementary_session TEXT,
                            duration_min INTEGER,
                            duration_max INTEGER,
                            intensity_class TEXT
                        );
                        CREATE TABLE IF NOT EXISTS link_plan_execution (
                            link_id INTEGER PRIMARY KEY,
                            planned_session_id INTEGER NOT NULL,
                            activity_id INTEGER NOT NULL,
                            link_type TEXT NOT NULL,
                            compliance_status TEXT,
                            rationale TEXT
                        );
                        """
                    )
                    connection.execute("INSERT INTO plan_meso_blocks (block_id, season_id) VALUES (?, ?)", (1, 2026))
                    connection.execute(
                        "INSERT INTO plan_micro_weeks (week_id, block_id, start_date, end_date) VALUES (?, ?, ?, ?)",
                        (201, 1, "2026-06-15", "2026-06-21"),
                    )
                    connection.execute(
                        """
                        INSERT INTO plan_planned_sessions (
                            planned_session_id, week_id, session_date, planned_type, objective,
                            primary_session, complementary_session, duration_min, duration_max, intensity_class
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            20101,
                            201,
                            "2026-06-15",
                            "recuperacion",
                            "Soltar carga residual.",
                            "texto irrelevante para el enlazado",
                            "fuerza ligera de soporte",
                            60,
                            90,
                            "Z1",
                        ),
                    )
                    replace_planned_session_prescription(
                        connection,
                        make_test_prescription(
                            20101,
                            "recuperacion",
                            60,
                            90,
                            [
                                {
                                    "sequence_order": 1,
                                    "block_role": "primary",
                                    "relation_group": 1,
                                    "relation_mode": "one_of",
                                    "is_optional": 0,
                                    "block_type": "endurance",
                                    "block_name": "paseo",
                                    "objective": "Soltar carga residual.",
                                    "rounds": None,
                                    "rest_seconds": None,
                                    "discipline_family": "walking",
                                    "duration_min": 60,
                                    "duration_max": 90,
                                    "target_basis": None,
                                    "target_zone_min_code": None,
                                    "target_zone_max_code": None,
                                    "condition_key": None,
                                    "condition_value": None,
                                    "notes": None,
                                    "exercises": [],
                                },
                                {
                                    "sequence_order": 2,
                                    "block_role": "primary",
                                    "relation_group": 1,
                                    "relation_mode": "one_of",
                                    "is_optional": 0,
                                    "block_type": "endurance",
                                    "block_name": "bicicleta",
                                    "objective": None,
                                    "rounds": None,
                                    "rest_seconds": None,
                                    "discipline_family": "cycling",
                                    "duration_min": 60,
                                    "duration_max": 90,
                                    "target_basis": "heart_rate",
                                    "target_zone_min_code": "Z1",
                                    "target_zone_max_code": "Z1",
                                    "condition_key": None,
                                    "condition_value": None,
                                    "notes": None,
                                    "exercises": [],
                                },
                                {
                                    "sequence_order": 3,
                                    "block_role": "support",
                                    "relation_group": 2,
                                    "relation_mode": "all_of",
                                    "is_optional": 1,
                                    "block_type": "strength",
                                    "block_name": "fuerza ligera",
                                    "objective": None,
                                    "rounds": None,
                                    "rest_seconds": None,
                                    "discipline_family": "strength_training",
                                    "duration_min": 20,
                                    "duration_max": 20,
                                    "target_basis": None,
                                    "target_zone_min_code": None,
                                    "target_zone_max_code": None,
                                    "condition_key": None,
                                    "condition_value": None,
                                    "notes": None,
                                    "exercises": [],
                                },
                            ],
                            title="recuperacion",
                        ),
                    )
                    connection.executemany(
                        """
                        INSERT INTO exec_activities (
                            activity_id, season_id, source_system, external_activity_id, activity_date, started_at, discipline,
                            activity_type, duration_seconds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (1, 2026, "garmin", "walk-1", "2026-06-15", "2026-06-15 08:00:00", "walking", "Caminar", 3100),
                            (2, 2026, "garmin", "bike-1", "2026-06-15", "2026-06-15 10:00:00", "road_biking", "Ciclismo", 4200),
                            (3, 2026, "garmin", "strength-1", "2026-06-15", "2026-06-15 18:00:00", "strength_training", "Fuerza", 1200),
                        ],
                    )

                    inserted, retained = storage._auto_link_garmin_activities(connection, 2026, ["2026-06-15"])

                    self.assertEqual((inserted, retained), (2, 0))
                    rows = connection.execute(
                        "SELECT activity_id FROM link_plan_execution WHERE planned_session_id = ? ORDER BY activity_id",
                        (20101,),
                    ).fetchall()

                self.assertEqual([row["activity_id"] for row in rows], [2, 3])

    def test_auto_link_treats_activation_support_as_strength(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                storage = GarminImportStorage()

                with storage_module_connection(database_path) as connection:
                    create_minimal_exec_tables(connection)
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_meso_blocks (
                            block_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS plan_micro_weeks (
                            week_id INTEGER PRIMARY KEY,
                            block_id INTEGER NOT NULL,
                            start_date TEXT,
                            end_date TEXT
                        );
                        CREATE TABLE IF NOT EXISTS plan_planned_sessions (
                            planned_session_id INTEGER PRIMARY KEY,
                            week_id INTEGER NOT NULL,
                            session_date TEXT NOT NULL,
                            planned_type TEXT,
                            objective TEXT,
                            primary_session TEXT,
                            complementary_session TEXT
                        );
                        CREATE TABLE IF NOT EXISTS link_plan_execution (
                            link_id INTEGER PRIMARY KEY,
                            planned_session_id INTEGER NOT NULL,
                            activity_id INTEGER NOT NULL,
                            link_type TEXT NOT NULL,
                            compliance_status TEXT,
                            rationale TEXT
                        );
                        """
                    )
                    connection.execute("INSERT INTO plan_meso_blocks (block_id, season_id) VALUES (?, ?)", (1, 2026))
                    connection.execute(
                        "INSERT INTO plan_micro_weeks (week_id, block_id, start_date, end_date) VALUES (?, ?, ?, ?)",
                        (101, 1, "2026-05-04", "2026-05-10"),
                    )
                    connection.execute(
                        """
                        INSERT INTO plan_planned_sessions (
                            planned_session_id, week_id, session_date, planned_type, objective, primary_session, complementary_session
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            10101,
                            101,
                            "2026-05-04",
                            "activacion",
                            "Abrir la semana con fuerza ligera y sin fatiga.",
                            "Paseo 45-60 minutos o descanso activo.",
                            "Pecho, triceps y hombro 15-20 minutos.",
                        ),
                    )
                    replace_planned_session_prescription(
                        connection,
                        make_test_prescription(
                            10101,
                            "activacion",
                            45,
                            60,
                            [
                                {
                                    "sequence_order": 1,
                                    "block_role": "primary",
                                    "relation_group": 1,
                                    "relation_mode": "one_of",
                                    "is_optional": 0,
                                    "block_type": "endurance",
                                    "block_name": "paseo",
                                    "objective": "Abrir la semana con fuerza ligera y sin fatiga.",
                                    "rounds": None,
                                    "rest_seconds": None,
                                    "discipline_family": "walking",
                                    "duration_min": 45,
                                    "duration_max": 60,
                                    "target_basis": None,
                                    "target_zone_min_code": None,
                                    "target_zone_max_code": None,
                                    "condition_key": None,
                                    "condition_value": None,
                                    "notes": None,
                                    "exercises": [],
                                },
                                {
                                    "sequence_order": 2,
                                    "block_role": "support",
                                    "relation_group": 2,
                                    "relation_mode": "all_of",
                                    "is_optional": 1,
                                    "block_type": "strength",
                                    "block_name": "fuerza ligera",
                                    "objective": None,
                                    "rounds": None,
                                    "rest_seconds": None,
                                    "discipline_family": "strength_training",
                                    "duration_min": 15,
                                    "duration_max": 20,
                                    "target_basis": None,
                                    "target_zone_min_code": None,
                                    "target_zone_max_code": None,
                                    "condition_key": None,
                                    "condition_value": None,
                                    "notes": None,
                                    "exercises": [],
                                },
                            ],
                            title="activacion",
                        ),
                    )
                    connection.executemany(
                        """
                        INSERT INTO exec_activities (
                            activity_id, season_id, source_system, external_activity_id, activity_date, started_at, discipline,
                            activity_type, duration_seconds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (1, 2026, "garmin", "walk-1", "2026-05-04", "2026-05-04 08:00:00", "walking", "Caminar", 3200),
                            (2, 2026, "garmin", "strength-1", "2026-05-04", "2026-05-04 09:00:00", "strength_training", "Fuerza", 1200),
                        ],
                    )

                    inserted, retained = storage._auto_link_garmin_activities(connection, 2026, ["2026-05-04"])

                    self.assertEqual((inserted, retained), (2, 0))
                    rows = connection.execute(
                        "SELECT activity_id FROM link_plan_execution WHERE planned_session_id = ? ORDER BY activity_id",
                        (10101,),
                    ).fetchall()

                self.assertEqual([row["activity_id"] for row in rows], [1, 2])

    def test_auto_link_treats_planned_core_as_strength_support(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                storage = GarminImportStorage()

                with storage_module_connection(database_path) as connection:
                    create_minimal_exec_tables(connection)
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_meso_blocks (
                            block_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS plan_micro_weeks (
                            week_id INTEGER PRIMARY KEY,
                            block_id INTEGER NOT NULL,
                            start_date TEXT,
                            end_date TEXT
                        );
                        CREATE TABLE IF NOT EXISTS plan_planned_sessions (
                            planned_session_id INTEGER PRIMARY KEY,
                            week_id INTEGER NOT NULL,
                            session_date TEXT NOT NULL,
                            planned_type TEXT,
                            objective TEXT,
                            primary_session TEXT,
                            complementary_session TEXT
                        );
                        CREATE TABLE IF NOT EXISTS link_plan_execution (
                            link_id INTEGER PRIMARY KEY,
                            planned_session_id INTEGER NOT NULL,
                            activity_id INTEGER NOT NULL,
                            link_type TEXT NOT NULL,
                            compliance_status TEXT,
                            rationale TEXT
                        );
                        """
                    )
                    connection.execute("INSERT INTO plan_meso_blocks (block_id, season_id) VALUES (?, ?)", (1, 2026))
                    connection.execute(
                        "INSERT INTO plan_micro_weeks (week_id, block_id, start_date, end_date) VALUES (?, ?, ?, ?)",
                        (105, 1, "2026-06-01", "2026-06-07"),
                    )
                    connection.execute(
                        """
                        INSERT INTO plan_planned_sessions (
                            planned_session_id, week_id, session_date, planned_type, objective, primary_session, complementary_session
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            10503,
                            105,
                            "2026-06-03",
                            "complementaria",
                            "Mantener fuerza estructurada ligera con foco en core.",
                            "Paseo suave 20-45 minutos o descanso activo.",
                            "Core 15-20 minutos.",
                        ),
                    )
                    replace_planned_session_prescription(
                        connection,
                        make_test_prescription(
                            10503,
                            "complementaria",
                            20,
                            45,
                            [
                                {
                                    "sequence_order": 1,
                                    "block_role": "primary",
                                    "relation_group": 1,
                                    "relation_mode": "one_of",
                                    "is_optional": 0,
                                    "block_type": "endurance",
                                    "block_name": "paseo",
                                    "objective": "Mantener fuerza estructurada ligera con foco en core.",
                                    "rounds": None,
                                    "rest_seconds": None,
                                    "discipline_family": "walking",
                                    "duration_min": 20,
                                    "duration_max": 45,
                                    "target_basis": None,
                                    "target_zone_min_code": None,
                                    "target_zone_max_code": None,
                                    "condition_key": None,
                                    "condition_value": None,
                                    "notes": None,
                                    "exercises": [],
                                },
                                {
                                    "sequence_order": 2,
                                    "block_role": "support",
                                    "relation_group": 2,
                                    "relation_mode": "all_of",
                                    "is_optional": 1,
                                    "block_type": "strength",
                                    "block_name": "core",
                                    "objective": None,
                                    "rounds": None,
                                    "rest_seconds": None,
                                    "discipline_family": "strength_training",
                                    "duration_min": 15,
                                    "duration_max": 20,
                                    "target_basis": None,
                                    "target_zone_min_code": None,
                                    "target_zone_max_code": None,
                                    "condition_key": None,
                                    "condition_value": None,
                                    "notes": None,
                                    "exercises": [],
                                },
                            ],
                            title="complementaria",
                        ),
                    )
                    connection.executemany(
                        """
                        INSERT INTO exec_activities (
                            activity_id, season_id, source_system, external_activity_id, activity_date, started_at, discipline,
                            activity_type, duration_seconds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (1, 2026, "garmin", "walk-1", "2026-06-03", "2026-06-03 16:01:21", "walking", "Caminar", 5101),
                            (2, 2026, "garmin", "strength-1", "2026-06-03", "2026-06-03 23:18:44", "strength_training", "Fuerza", 2035),
                            (3, 2026, "garmin", "yoga-1", "2026-06-03", "2026-06-03 23:54:33", "yoga", "Yoga", 1979),
                        ],
                    )

                    inserted, retained = storage._auto_link_garmin_activities(connection, 2026, ["2026-06-03"])

                    self.assertEqual((inserted, retained), (2, 0))
                    rows = connection.execute(
                        "SELECT activity_id, link_type FROM link_plan_execution WHERE planned_session_id = ? ORDER BY activity_id",
                        (10503,),
                    ).fetchall()

                self.assertEqual([(row["activity_id"], row["link_type"]) for row in rows], [(1, "garmin_auto"), (2, "garmin_auto")])



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
                            total_steps=12345,
                            total_distance_m=9876.0,
                            step_goal=10000,
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
                    metric_row = connection.execute(
                        "SELECT total_steps, total_distance_m, step_goal FROM exec_daily_metrics"
                    ).fetchone()
                    metric_total = connection.execute("SELECT COUNT(*) AS total FROM exec_daily_metrics").fetchone()["total"]

                self.assertEqual(activity_total, 1)
                self.assertEqual(metric_total, 1)
                self.assertEqual(metric_row["total_steps"], 12345)
                self.assertEqual(metric_row["total_distance_m"], 9876.0)
                self.assertEqual(metric_row["step_goal"], 10000)


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
            weight_measured_at TEXT,
            weight_measurement_source TEXT,
            body_fat_pct REAL,
            body_water_pct REAL,
            bone_mass_kg REAL,
            muscle_mass_kg REAL,
            bmi REAL,
            visceral_fat REAL,
            metabolic_age REAL,
            physique_rating REAL,
            sleep_hours REAL,
            sleep_quality TEXT,
            resting_hr REAL,
            vo2max_cycling REAL,
            vo2max_running REAL,
            lactate_threshold_hr REAL,
            hrv REAL,
            body_battery REAL,
            total_steps INTEGER,
            total_distance_m REAL,
            step_goal INTEGER,
            stress_avg REAL,
            stress_max REAL,
            spo2_avg REAL,
            spo2_sleep_avg REAL,
            spo2_7d_avg REAL,
            spo2_lowest REAL,
            subjective_energy INTEGER,
            subjective_fatigue INTEGER,
            notes TEXT,
            UNIQUE (season_id, metric_date, source_system)
        );
        """
    )