from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_assessment_models import AssessmentCadence, AssessmentRunTriggerRequest, RunTriggerMode
from app.db import get_connection, initialize_database
from app.main import create_assessment_run, get_assessment_run
from tests.test_ai_assessment_context import create_minimal_assessment_source_tables, seed_assessment_context_data


class AssessmentApiTests(unittest.TestCase):
    def test_create_and_fetch_assessment_run_use_shared_services(self) -> None:
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
                        trigger_mode=RunTriggerMode.MANUAL,
                    )
                )

                self.assertEqual(created["run_status"], "queued")
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
                self.assertEqual(detail["run_status"], "queued")
                self.assertEqual(detail["agent_profile"]["profile_key"], "daily_execution_v1")
                self.assertIn("plan_planned_sessions count=1", detail["principal_evidence"])
                self.assertIn("exec_activities dates=2026-05-28", detail["principal_evidence"])
                self.assertEqual(detail["assessment_type_results"], [])
                self.assertEqual(detail["findings"], [])
                self.assertEqual(detail["proposals"], [])
                self.assertEqual(detail["dialog_context"], [])

                with get_connection() as connection:
                    stored_run = connection.execute(
                        "SELECT trigger_mode, run_status FROM agent_assessment_runs WHERE assessment_run_id = ?",
                        (created["assessment_run_id"],),
                    ).fetchone()

                self.assertEqual(stored_run["trigger_mode"], "manual")
                self.assertEqual(stored_run["run_status"], "queued")


if __name__ == "__main__":
    unittest.main()