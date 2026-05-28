from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_assessment_models import AssessmentCadence, AssessmentRunTriggerRequest, AssessmentRunStatus, RunTriggerMode
from app.ai_assessments import prepare_assessment_run
from app.db import get_connection, initialize_database


class AssessmentContextTests(unittest.TestCase):
    def test_prepare_daily_assessment_run_builds_context_and_deduplicates_unchanged_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                first_run = prepare_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                self.assertEqual(first_run.run_status, AssessmentRunStatus.QUEUED)
                self.assertEqual(first_run.context_snapshot.window.subject_scope_key, "day:2026-05-28")
                self.assertEqual(len(first_run.context_snapshot.context["planned_sessions"]), 1)
                self.assertEqual(len(first_run.context_snapshot.context["activities"]), 1)
                self.assertEqual(len(first_run.context_snapshot.context["daily_metrics"]), 1)
                self.assertTrue(first_run.context_snapshot.evidence_fingerprint)

                second_run = prepare_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                self.assertEqual(second_run.run_status, AssessmentRunStatus.NO_NEW_DATA)
                self.assertEqual(second_run.reused_run_id, first_run.assessment_run_id)

                rerun = prepare_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                        trigger_mode=RunTriggerMode.RERUN,
                    )
                )

                self.assertEqual(rerun.run_status, AssessmentRunStatus.QUEUED)

                with get_connection() as connection:
                    run_total = connection.execute(
                        "SELECT COUNT(*) AS total FROM agent_assessment_runs"
                    ).fetchone()["total"]
                    rerun_row = connection.execute(
                        "SELECT supersedes_run_id FROM agent_assessment_runs WHERE assessment_run_id = ?",
                        (rerun.assessment_run_id,),
                    ).fetchone()

                self.assertEqual(run_total, 2)
                self.assertEqual(rerun_row["supersedes_run_id"], first_run.assessment_run_id)


def create_minimal_assessment_source_tables() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS plan_seasons (
                season_id INTEGER PRIMARY KEY,
                season_code TEXT NOT NULL UNIQUE,
                season_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS plan_meso_blocks (
                block_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                block_code TEXT NOT NULL UNIQUE,
                block_name TEXT NOT NULL,
                phase_name TEXT,
                sequence_order INTEGER NOT NULL,
                start_date TEXT,
                end_date TEXT,
                objective_primary TEXT
            );

            CREATE TABLE IF NOT EXISTS plan_micro_weeks (
                week_id INTEGER PRIMARY KEY,
                block_id INTEGER NOT NULL,
                week_code TEXT NOT NULL,
                sequence_in_block INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                week_role TEXT,
                objective_primary TEXT,
                UNIQUE (block_id, week_code)
            );

            CREATE TABLE IF NOT EXISTS plan_planned_sessions (
                planned_session_id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                day_name TEXT NOT NULL,
                sequence_in_week INTEGER NOT NULL,
                planned_type TEXT,
                objective TEXT,
                primary_session TEXT,
                complementary_session TEXT,
                notes TEXT,
                is_key_session INTEGER NOT NULL DEFAULT 0,
                intensity_class TEXT,
                duration_min INTEGER,
                duration_max INTEGER,
                UNIQUE (week_id, sequence_in_week)
            );

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
                segment_data_status TEXT NOT NULL DEFAULT 'not_checked',
                segment_effort_count INTEGER NOT NULL DEFAULT 0,
                segment_checked_at TEXT,
                quality_status TEXT NOT NULL DEFAULT 'not_checked',
                quality_checked_at TEXT,
                quality_rule_version TEXT,
                quality_decision_count INTEGER NOT NULL DEFAULT 0,
                quality_limited_metric_count INTEGER NOT NULL DEFAULT 0,
                perceived_exertion INTEGER,
                subjective_feeling TEXT,
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
                soreness TEXT,
                notes TEXT,
                UNIQUE (season_id, metric_date, source_system)
            );

            CREATE TABLE IF NOT EXISTS link_plan_execution (
                link_id INTEGER PRIMARY KEY,
                planned_session_id INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                link_type TEXT NOT NULL DEFAULT 'direct',
                compliance_status TEXT NOT NULL,
                rationale TEXT,
                UNIQUE (planned_session_id, activity_id)
            );

            CREATE TABLE IF NOT EXISTS review_daily_reviews (
                daily_review_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                review_date TEXT NOT NULL,
                block_id INTEGER,
                week_id INTEGER,
                planned_session_id INTEGER,
                planned_summary TEXT,
                actual_summary TEXT,
                compliance_status TEXT,
                general_feeling TEXT,
                perceived_recovery TEXT,
                motivation TEXT,
                observations TEXT,
                next_day_decision TEXT,
                UNIQUE (season_id, review_date, planned_session_id)
            );

            CREATE TABLE IF NOT EXISTS review_weekly_reviews (
                weekly_review_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                block_id INTEGER NOT NULL,
                week_id INTEGER NOT NULL UNIQUE,
                review_status TEXT NOT NULL DEFAULT 'open',
                closed_at TEXT,
                adherence_rate REAL,
                traceability_rate REAL,
                actual_minutes INTEGER,
                planned_reference_minutes INTEGER,
                volume_delta_minutes INTEGER,
                risk_level TEXT,
                recommendation_text TEXT,
                summary_text TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS exec_segments (
                segment_id INTEGER PRIMARY KEY,
                source_system TEXT NOT NULL,
                external_segment_id TEXT NOT NULL,
                segment_name TEXT,
                discipline TEXT,
                UNIQUE (source_system, external_segment_id)
            );

            CREATE TABLE IF NOT EXISTS exec_segment_efforts (
                segment_effort_id INTEGER PRIMARY KEY,
                source_system TEXT NOT NULL,
                external_segment_effort_id TEXT NOT NULL,
                segment_id INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                activity_date TEXT NOT NULL,
                started_at TEXT,
                elapsed_time_seconds INTEGER,
                avg_power REAL,
                avg_cadence REAL,
                avg_heart_rate REAL,
                max_heart_rate REAL,
                UNIQUE (source_system, external_segment_effort_id)
            );
            """
        )


def seed_assessment_context_data() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date, status)
            VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31', 'active')
            """
        )
        connection.execute(
            """
            INSERT INTO plan_meso_blocks (
                block_id, season_id, block_code, block_name, sequence_order, start_date, end_date, objective_primary
            ) VALUES (1, 2026, 'B1', 'Reconstruccion', 1, '2026-05-26', '2026-06-22', 'Base aerobica')
            """
        )
        connection.execute(
            """
            INSERT INTO plan_micro_weeks (
                week_id, block_id, week_code, sequence_in_block, start_date, end_date, week_role, objective_primary
            ) VALUES (11, 1, '2026-B1-W04', 4, '2026-05-26', '2026-06-01', 'stabilization', 'Absorber carga')
            """
        )
        connection.execute(
            """
            INSERT INTO plan_planned_sessions (
                planned_session_id, week_id, session_date, day_name, sequence_in_week, planned_type, objective,
                primary_session, is_key_session, intensity_class, duration_min, duration_max
            ) VALUES (101, 11, '2026-05-28', 'Thursday', 4, 'bike', 'Aerobic maintenance', 'Easy endurance ride', 0, 'easy', 75, 90)
            """
        )
        connection.execute(
            """
            INSERT INTO exec_activities (
                activity_id, season_id, source_system, external_activity_id, activity_date, started_at,
                discipline, activity_type, duration_seconds, distance_meters, training_load, avg_hr,
                max_hr, avg_power, normalized_power, segment_data_status, segment_effort_count,
                quality_status, quality_decision_count, quality_limited_metric_count, perceived_exertion
            ) VALUES (
                201, 2026, 'garmin', 'activity-201', '2026-05-28', '2026-05-28T07:00:00',
                'road_biking', 'Endurance', 5100, 32000, 68, 138,
                158, 210, 220, 'available', 0,
                'clean', 0, 0, 4
            )
            """
        )
        connection.execute(
            """
            INSERT INTO exec_daily_metrics (
                daily_metric_id, season_id, metric_date, source_system, sleep_hours, resting_hr,
                hrv, body_battery, subjective_energy, subjective_fatigue
            ) VALUES (301, 2026, '2026-05-28', 'garmin', 7.5, 52, 61, 73, 4, 2)
            """
        )
        connection.execute(
            """
            INSERT INTO link_plan_execution (
                planned_session_id, activity_id, link_type, compliance_status, rationale
            ) VALUES (101, 201, 'direct', 'completed', 'Matched by date and discipline')
            """
        )
        connection.execute(
            """
            INSERT INTO review_daily_reviews (
                daily_review_id, season_id, review_date, block_id, week_id, planned_session_id,
                actual_summary, compliance_status, general_feeling, next_day_decision
            ) VALUES (401, 2026, '2026-05-28', 1, 11, 101, 'Ride completed as planned', 'completed', 'good', 'maintain')
            """
        )


if __name__ == "__main__":
    unittest.main()