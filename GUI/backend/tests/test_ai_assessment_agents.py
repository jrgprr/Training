from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_assessment_models import AssessmentCadence, AssessmentRunTriggerRequest
from app.ai_assessments import register_gateway_provider
from app.db import get_connection, initialize_database
from app.main import create_assessment_run
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


if __name__ == "__main__":
    unittest.main()
