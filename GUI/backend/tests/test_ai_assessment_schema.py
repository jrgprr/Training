from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import get_connection, initialize_database


class AssessmentSchemaTests(unittest.TestCase):
    def test_initialize_database_creates_assessment_tables_and_enforces_proposal_boundaries(self) -> None:
        required_tables = {
            "agent_assessment_profiles",
            "agent_assessment_windows",
            "agent_assessment_runs",
            "agent_assessment_type_results",
            "agent_assessment_findings",
            "agent_adaptation_proposals",
            "agent_proposal_decisions",
            "agent_accepted_plan_mutations",
            "agent_assessment_dialog_context",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"

            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()

                with get_connection() as connection:
                    tables = {
                        row["name"]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'agent_%'"
                        ).fetchall()
                    }

                    self.assertEqual(required_tables - tables, set())

                    connection.execute(
                        """
                        INSERT INTO agent_adaptation_proposals (
                            assessment_run_id,
                            agent_profile_id,
                            source_cadence,
                            target_planning_level,
                            proposal_title,
                            change_kind,
                            proposed_change_json
                        ) VALUES (1, 1, 'daily', 'weekly', 'ok', 'reduce_volume', '{}')
                        """
                    )

                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(
                            """
                            INSERT INTO agent_adaptation_proposals (
                                assessment_run_id,
                                agent_profile_id,
                                source_cadence,
                                target_planning_level,
                                proposal_title,
                                change_kind,
                                proposed_change_json
                            ) VALUES (1, 1, 'daily', 'block', 'bad', 'reduce_volume', '{}')
                            """
                        )