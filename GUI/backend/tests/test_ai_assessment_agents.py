from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_assessment_models import AssessmentCadence, AssessmentRunTriggerRequest
from app.ai_assessments import register_gateway_provider
from app.ai_context import build_assessment_context
from app.db import get_connection, initialize_database
from app.main import create_assessment_run, get_assessment_run
from tests.test_ai_assessment_api import AssessmentApiTests
from tests.test_ai_assessment_context import create_minimal_assessment_source_tables, seed_assessment_context_data


class AssessmentAgentLifecycleTests(unittest.TestCase):
    def test_daily_failure_persists_provider_error_details(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                created = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                self.assertEqual(created["run_status"], "failed")

                with get_connection() as connection:
                    stored_run = connection.execute(
                        """
                        SELECT run_status, provider_key, model_name, failure_code, failure_detail, started_at, completed_at
                        FROM agent_assessment_runs
                        WHERE assessment_run_id = ?
                        """,
                        (created["assessment_run_id"],),
                    ).fetchone()

                self.assertEqual(stored_run["run_status"], "failed")
                self.assertIsNone(stored_run["provider_key"])
                self.assertIsNone(stored_run["model_name"])
                self.assertEqual(stored_run["failure_code"], "provider_error")
                self.assertIn("No AI assessment provider is configured", stored_run["failure_detail"])
                self.assertIsNotNone(stored_run["started_at"])
                self.assertIsNotNone(stored_run["completed_at"])

    def test_daily_changed_evidence_creates_new_run(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                return "The day remains on plan with updated recovery evidence available for review."

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.dict("os.environ", {"AI_ASSESSMENT_PROVIDER": "fake", "AI_ASSESSMENT_MODEL": "fake-model"}):
                register_gateway_provider("fake", FakeProvider())
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                first = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                with get_connection() as connection:
                    connection.execute(
                        "UPDATE exec_daily_metrics SET subjective_fatigue = 3 WHERE daily_metric_id = 301"
                    )

                second = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                self.assertEqual(first["run_status"], "completed")
                self.assertEqual(second["run_status"], "completed")
                self.assertNotEqual(second["assessment_run_id"], first["assessment_run_id"])
                self.assertNotEqual(second["assessment_window_id"], first["assessment_window_id"])

                with get_connection() as connection:
                    totals = connection.execute(
                        "SELECT COUNT(*) AS run_total FROM agent_assessment_runs"
                    ).fetchone()
                    window_totals = connection.execute(
                        "SELECT COUNT(*) AS window_total FROM agent_assessment_windows"
                    ).fetchone()

                self.assertEqual(totals["run_total"], 2)
                self.assertEqual(window_totals["window_total"], 2)

    def test_weekly_and_block_profiles_persist_profile_specific_outputs(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                if invocation.profile_key == "weekly_adherence_adequacy_v1":
                    return "The week broadly followed its intended structure with manageable deviations."
                return "The block direction remains constructive based on recent execution and benchmark signals."

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.dict("os.environ", {"AI_ASSESSMENT_PROVIDER": "fake", "AI_ASSESSMENT_MODEL": "fake-model"}):
                register_gateway_provider("fake", FakeProvider())
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                with get_connection() as connection:
                    connection.execute(
                        """
                        INSERT INTO review_weekly_reviews (
                            weekly_review_id,
                            season_id,
                            block_id,
                            week_id,
                            review_status,
                            adherence_rate,
                            traceability_rate,
                            actual_minutes,
                            planned_reference_minutes,
                            volume_delta_minutes,
                            risk_level,
                            recommendation_text,
                            summary_text
                        ) VALUES (501, 2026, 1, 11, 'closed', 0.9, 1.0, 85, 90, -5, 'low', 'Maintain the week intent.', 'Strong weekly traceability.')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_segments (
                            segment_id,
                            source_system,
                            external_segment_id,
                            segment_name,
                            discipline
                        ) VALUES (601, 'garmin', 'segment-601', 'Tempo climb', 'road_biking')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_segment_efforts (
                            segment_effort_id,
                            source_system,
                            external_segment_effort_id,
                            segment_id,
                            activity_id,
                            activity_date,
                            started_at,
                            elapsed_time_seconds,
                            avg_power,
                            avg_cadence,
                            avg_heart_rate,
                            max_heart_rate
                        ) VALUES (701, 'garmin', 'effort-701', 601, 201, '2026-05-28', '2026-05-28T07:30:00', 420, 255, 82, 152, 165)
                        """
                    )

                weekly_run = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.WEEKLY,
                        agent_profile_key="weekly_adherence_adequacy_v1",
                        season_id=2026,
                        week_id=11,
                        window_start_date="2026-05-26",
                        window_end_date="2026-06-01",
                    )
                )
                block_run = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.BLOCK,
                        agent_profile_key="block_performance_direction_v1",
                        season_id=2026,
                        block_id=1,
                        window_start_date="2026-05-26",
                        window_end_date="2026-06-22",
                    )
                )

                self.assertEqual(weekly_run["run_status"], "completed")
                self.assertEqual(weekly_run["result_summary"]["confidence_label"], "medium")
                self.assertEqual(block_run["run_status"], "completed")
                self.assertEqual(block_run["result_summary"]["confidence_label"], "medium")

                weekly_detail = get_assessment_run(weekly_run["assessment_run_id"])
                block_detail = get_assessment_run(block_run["assessment_run_id"])

                self.assertEqual(weekly_detail["assessment_type_results"][0]["assessment_type_key"], "weekly_adherence_adequacy")
                self.assertEqual(weekly_detail["assessment_type_results"][0]["result_label"], "weekly_on_plan")
                self.assertEqual(weekly_detail["findings"][0]["finding_kind"], "adherence_observation")
                self.assertIn("review_weekly_reviews available", weekly_detail["principal_evidence"])
                self.assertEqual(block_detail["assessment_type_results"][0]["assessment_type_key"], "block_performance_direction")
                self.assertEqual(block_detail["assessment_type_results"][0]["result_label"], "direction_established")
                self.assertEqual(block_detail["findings"][0]["finding_kind"], "performance_signal")

    def test_assessment_context_supports_season_scoped_windows_without_inferring_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                snapshot = build_assessment_context(
                    cadence=AssessmentCadence.SEASON,
                    season_id=2026,
                    window_start_date="2026-01-01",
                    window_end_date="2026-12-31",
                )

                self.assertEqual(snapshot.window.subject_scope_key, "season:2026")
                self.assertIsNone(snapshot.window.block_id)
                self.assertIsNone(snapshot.window.week_id)

    def test_runs_for_same_window_are_isolated_by_profile(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                return f"Assessment generated for {invocation.profile_key}."

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.dict("os.environ", {"AI_ASSESSMENT_PROVIDER": "fake", "AI_ASSESSMENT_MODEL": "fake-model"}):
                register_gateway_provider("fake", FakeProvider())
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                execution_run = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )
                readiness_run = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_recovery_readiness_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                self.assertEqual(execution_run["run_status"], "completed")
                self.assertEqual(readiness_run["run_status"], "completed")
                self.assertNotEqual(execution_run["assessment_run_id"], readiness_run["assessment_run_id"])
                self.assertEqual(execution_run["assessment_window_id"], readiness_run["assessment_window_id"])

                with get_connection() as connection:
                    run_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM agent_assessment_runs"
                    ).fetchone()["total"]

                self.assertEqual(run_count, 2)

    def test_weekly_run_can_persist_linked_proposals_from_structured_output(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                return (
                    '{'
                    '"summary_text":"The week stayed mostly on plan but the next block step should be held.",'
                    '"proposals":['
                    '{'
                    '"target_planning_level":"block",'
                    '"proposal_title":"Hold block progression for one extra week",'
                    '"proposal_summary":"Extend the current stabilization period before the next load increase.",'
                    '"change_kind":"extend_stabilization",'
                    '"proposed_change":{"target_entity":"plan_meso_blocks.block_id=1","changes":{"duration_weeks_min":4,"duration_weeks_max":5}},'
                    '"reasoning_summary":"Recovery quality drifted late in the week.",'
                    '"conflict_group_key":"block:B1:progression"'
                    '},'
                    '{'
                    '"target_planning_level":"block",'
                    '"proposal_title":"Reduce weekend density before the next load step",'
                    '"proposal_summary":"Protect recovery going into the next progression.",'
                    '"change_kind":"reduce_density",'
                    '"proposed_change":{"target_entity":"plan_meso_blocks.block_id=1","changes":{"weekend_sessions":1}},'
                    '"reasoning_summary":"Session clustering was high for the current week.",'
                    '"conflict_group_key":"block:B1:progression"'
                    '}'
                    ']'
                    '}'
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.dict("os.environ", {"AI_ASSESSMENT_PROVIDER": "fake", "AI_ASSESSMENT_MODEL": "fake-model"}):
                register_gateway_provider("fake", FakeProvider())
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                with get_connection() as connection:
                    connection.execute(
                        """
                        INSERT INTO review_weekly_reviews (
                            weekly_review_id,
                            season_id,
                            block_id,
                            week_id,
                            review_status,
                            adherence_rate,
                            traceability_rate,
                            actual_minutes,
                            planned_reference_minutes,
                            volume_delta_minutes,
                            risk_level,
                            recommendation_text,
                            summary_text
                        ) VALUES (502, 2026, 1, 11, 'closed', 0.88, 0.95, 82, 90, -8, 'watch', 'Hold the next progression step.', 'Weekly review indicates recovery cost.')
                        """
                    )

                created = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.WEEKLY,
                        agent_profile_key="weekly_adherence_adequacy_v1",
                        season_id=2026,
                        week_id=11,
                        window_start_date="2026-05-26",
                        window_end_date="2026-06-01",
                    )
                )

                self.assertEqual(created["run_status"], "completed")
                self.assertEqual(created["result_summary"]["proposal_count"], 2)
                self.assertEqual(created["result_summary"]["summary_text"], "The week stayed mostly on plan but the next block step should be held.")

                detail = get_assessment_run(created["assessment_run_id"])
                self.assertEqual(len(detail["proposals"]), 2)
                self.assertEqual(detail["proposals"][0]["proposal_status"], "pending")
                self.assertEqual(detail["proposals"][0]["source_cadence"], "weekly")
                self.assertEqual(detail["proposals"][0]["target_planning_level"], "block")

                with get_connection() as connection:
                    stored = connection.execute(
                        """
                        SELECT proposal_title, proposal_status, source_cadence, target_planning_level, conflict_group_key
                        FROM agent_adaptation_proposals
                        WHERE assessment_run_id = ?
                        ORDER BY proposal_id
                        """,
                        (created["assessment_run_id"],),
                    ).fetchall()

                self.assertEqual(len(stored), 2)
                self.assertEqual(stored[0]["proposal_title"], "Hold block progression for one extra week")
                self.assertEqual(stored[0]["proposal_status"], "pending")
                self.assertEqual(stored[0]["source_cadence"], "weekly")
                self.assertEqual(stored[0]["target_planning_level"], "block")
                self.assertEqual(stored[0]["conflict_group_key"], "block:B1:progression")


if __name__ == "__main__":
    unittest.main()
