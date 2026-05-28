from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_assessment_models import AssessmentCadence, AssessmentRunTriggerRequest, ProposalStatus, RunTriggerMode
from app.ai_assessments import register_gateway_provider
from app.db import get_connection, initialize_database
from app.main import create_assessment_run, get_assessment_run, get_latest_assessments, get_proposal, get_proposals
from tests.test_ai_assessment_context import create_minimal_assessment_source_tables, seed_assessment_context_data


class AssessmentApiTests(unittest.TestCase):
    def test_create_and_fetch_assessment_run_use_shared_services(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                return "The day matched the planned endurance intent with stable load and acceptable recovery context."

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                register_gateway_provider("fake", FakeProvider())
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
                        trigger_mode=RunTriggerMode.MANUAL,
                    )
                )

                self.assertEqual(created["run_status"], "failed")
                self.assertNotIn("summary_text", created["result_summary"])
                self.assertEqual(created["agent_profile"]["profile_key"], "daily_execution_v1")
                self.assertEqual(created["window"]["subject_scope_key"], "day:2026-05-28")

                with patch.dict("os.environ", {"AI_ASSESSMENT_PROVIDER": "fake", "AI_ASSESSMENT_MODEL": "fake-model"}):
                    created = create_assessment_run(
                        AssessmentRunTriggerRequest(
                            cadence=AssessmentCadence.DAILY,
                            agent_profile_key="daily_execution_v1",
                            season_id=2026,
                            window_start_date="2026-05-28",
                            window_end_date="2026-05-28",
                            trigger_mode=RunTriggerMode.RERUN,
                        )
                    )

                self.assertEqual(created["run_status"], "completed")
                self.assertEqual(created["result_summary"]["confidence_label"], "medium")
                self.assertEqual(created["agent_profile"]["profile_key"], "daily_execution_v1")
                self.assertEqual(created["window"]["subject_scope_key"], "day:2026-05-28")

                duplicated = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )
                self.assertEqual(duplicated["run_status"], "no_new_data")
                self.assertEqual(duplicated["assessment_run_id"], created["assessment_run_id"])

                detail = get_assessment_run(created["assessment_run_id"])
                self.assertEqual(detail["assessment_run_id"], created["assessment_run_id"])
                self.assertEqual(detail["run_status"], "completed")
                self.assertEqual(detail["agent_profile"]["profile_key"], "daily_execution_v1")
                self.assertIn("plan_planned_sessions count=1", detail["principal_evidence"])
                self.assertIn("exec_activities dates=2026-05-28", detail["principal_evidence"])
                self.assertEqual(detail["confidence_label"], "medium")
                self.assertEqual(len(detail["assessment_type_results"]), 1)
                self.assertEqual(detail["assessment_type_results"][0]["assessment_type_key"], "daily_execution")
                self.assertEqual(len(detail["findings"]), 1)
                self.assertEqual(detail["proposals"], [])
                self.assertEqual(detail["dialog_context"], [])

                with get_connection() as connection:
                    stored_run = connection.execute(
                        "SELECT trigger_mode, run_status FROM agent_assessment_runs WHERE assessment_run_id = ?",
                        (created["assessment_run_id"],),
                    ).fetchone()

                self.assertEqual(stored_run["trigger_mode"], "rerun")
                self.assertEqual(stored_run["run_status"], "completed")

    def test_daily_execution_without_activity_returns_partial_context(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                return "The planned session is missing execution evidence, so this assessment is bounded by sparse execution context."

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
                    connection.execute("DELETE FROM review_daily_reviews")
                    connection.execute("DELETE FROM link_plan_execution")
                    connection.execute("DELETE FROM exec_activities")

                created = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_execution_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                self.assertEqual(created["run_status"], "partial_context")
                self.assertEqual(created["result_summary"]["confidence_label"], "limited")

                detail = get_assessment_run(created["assessment_run_id"])
                self.assertEqual(detail["run_status"], "partial_context")
                self.assertEqual(detail["confidence_label"], "limited")
                self.assertEqual(detail["assessment_type_results"][0]["result_label"], "no_activity_recorded")
                self.assertEqual(detail["findings"][0]["finding_kind"], "data_confidence")

                with get_connection() as connection:
                    stored_run = connection.execute(
                        "SELECT run_status, confidence_label FROM agent_assessment_runs WHERE assessment_run_id = ?",
                        (created["assessment_run_id"],),
                    ).fetchone()

                self.assertEqual(stored_run["run_status"], "partial_context")
                self.assertEqual(stored_run["confidence_label"], "limited")

    def test_daily_recovery_readiness_without_activity_uses_recovery_context(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                return "Recovery markers are present and support a bounded readiness check for the next session."

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
                    connection.execute("DELETE FROM link_plan_execution")
                    connection.execute("DELETE FROM exec_activities")

                created = create_assessment_run(
                    AssessmentRunTriggerRequest(
                        cadence=AssessmentCadence.DAILY,
                        agent_profile_key="daily_recovery_readiness_v1",
                        season_id=2026,
                        window_start_date="2026-05-28",
                        window_end_date="2026-05-28",
                    )
                )

                self.assertEqual(created["run_status"], "completed")
                self.assertEqual(created["result_summary"]["confidence_label"], "medium")
                self.assertEqual(created["agent_profile"]["profile_key"], "daily_recovery_readiness_v1")

                detail = get_assessment_run(created["assessment_run_id"])
                self.assertEqual(detail["run_status"], "completed")
                self.assertEqual(detail["confidence_label"], "medium")
                self.assertEqual(detail["assessment_type_results"][0]["assessment_type_key"], "daily_recovery_readiness")
                self.assertEqual(detail["assessment_type_results"][0]["result_label"], "ready_check")
                self.assertEqual(detail["findings"][0]["finding_kind"], "recovery_observation")
                self.assertIn("exec_daily_metrics dates=2026-05-28", detail["principal_evidence"])
                self.assertIn("review_daily_reviews dates=2026-05-28", detail["principal_evidence"])

                with get_connection() as connection:
                    stored_run = connection.execute(
                        "SELECT run_status, confidence_label FROM agent_assessment_runs WHERE assessment_run_id = ?",
                        (created["assessment_run_id"],),
                    ).fetchone()

                self.assertEqual(stored_run["run_status"], "completed")
                self.assertEqual(stored_run["confidence_label"], "medium")

    def test_latest_assessments_and_proposal_reads_use_persisted_review_data(self) -> None:
        class FakeProvider:
            def invoke(self, invocation) -> str:
                if invocation.profile_key == "weekly_adherence_adequacy_v1":
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
                        '"reasoning_summary":"The athlete kept frequency but showed rising recovery cost.",'
                        '"conflict_group_key":"block:B1:progression"'
                        '}'
                        ']'
                        '}'
                    )
                return "The day matched the planned endurance intent with stable load and acceptable recovery context."

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
                        ) VALUES (503, 2026, 1, 11, 'closed', 0.88, 0.95, 82, 90, -8, 'watch', 'Hold the next progression step.', 'Weekly review indicates recovery cost.')
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

                with get_connection() as connection:
                    proposal_id = connection.execute(
                        "SELECT proposal_id FROM agent_adaptation_proposals WHERE assessment_run_id = ?",
                        (weekly_run["assessment_run_id"],),
                    ).fetchone()["proposal_id"]
                    connection.execute(
                        """
                        INSERT INTO agent_assessment_dialog_context (
                            proposal_id,
                            entry_kind,
                            entry_scope,
                            entry_text,
                            created_by
                        ) VALUES (?, 'user_question', 'proposal', 'Why hold progression instead of reducing intensity?', 'local-operator')
                        """,
                        (proposal_id,),
                    )

                latest = get_latest_assessments(season_id=2026, cadence=AssessmentCadence.WEEKLY)
                self.assertEqual(len(latest["items"]), 1)
                self.assertEqual(latest["items"][0]["assessment_run_id"], weekly_run["assessment_run_id"])
                self.assertEqual(latest["items"][0]["proposal_count"], 1)
                self.assertEqual(latest["items"][0]["pending_proposal_count"], 1)

                proposals = get_proposals(season_id=2026, status=ProposalStatus.PENDING)
                self.assertEqual(len(proposals["items"]), 1)
                self.assertEqual(proposals["items"][0]["proposal_id"], proposal_id)
                self.assertEqual(proposals["items"][0]["agent_profile_key"], "weekly_adherence_adequacy_v1")
                self.assertEqual(proposals["items"][0]["conflict_group_key"], "block:B1:progression")

                proposal_detail = get_proposal(proposal_id)
                self.assertEqual(proposal_detail["proposal_id"], proposal_id)
                self.assertEqual(proposal_detail["proposal_status"], "pending")
                self.assertEqual(proposal_detail["source_assessment"]["assessment_run_id"], weekly_run["assessment_run_id"])
                self.assertEqual(proposal_detail["source_assessment"]["agent_profile_key"], "weekly_adherence_adequacy_v1")
                self.assertEqual(proposal_detail["proposed_change"]["change_kind"], "extend_stabilization")
                self.assertEqual(len(proposal_detail["dialog_context"]), 1)
                self.assertEqual(proposal_detail["dialog_context"][0]["entry_scope"], "proposal")
                self.assertEqual(proposal_detail["decision_history"], [])


if __name__ == "__main__":
    unittest.main()