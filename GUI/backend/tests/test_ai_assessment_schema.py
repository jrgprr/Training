from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_assessments import sync_assessment_profiles
from app.db import get_connection, initialize_database
from tests.test_ai_assessment_context import create_minimal_assessment_source_tables, seed_assessment_context_data


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

    def test_views_sql_exposes_assessment_read_models(self) -> None:
        views_path = Path(__file__).resolve().parents[3] / "Sistema" / "views.sql"
        required_views = {
            "vw_agent_latest_assessment_summaries",
            "vw_agent_assessment_detail",
            "vw_agent_proposal_review_queue",
            "vw_agent_proposal_decision_history",
            "vw_agent_accepted_plan_mutation_traceability",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"

            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                create_minimal_assessment_source_tables()
                seed_assessment_context_data()

                with get_connection() as connection:
                    connection.executescript(views_path.read_text(encoding="utf-8"))
                    sync_assessment_profiles(connection)

                    profile_row = connection.execute(
                        "SELECT agent_profile_id FROM agent_assessment_profiles WHERE profile_key = 'daily_execution_v1'"
                    ).fetchone()

                    connection.execute(
                        """
                        INSERT INTO agent_assessment_windows (
                            assessment_window_id,
                            cadence,
                            season_id,
                            block_id,
                            week_id,
                            window_start_date,
                            window_end_date,
                            subject_scope_key,
                            evidence_fingerprint,
                            latest_materialized_at
                        ) VALUES (601, 'daily', 2026, 1, 11, '2026-05-28', '2026-05-28', 'day:2026-05-28', 'fp-one', '2026-05-28T08:00:00')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_assessment_runs (
                            assessment_run_id,
                            agent_profile_id,
                            assessment_window_id,
                            trigger_mode,
                            run_status,
                            provider_key,
                            model_name,
                            instruction_version,
                            prompt_hash,
                            summary_text,
                            confidence_label,
                            principal_evidence_json,
                            created_at,
                            started_at,
                            completed_at
                        ) VALUES (?,  ?, 601, 'manual', 'completed', 'fake', 'fake-model', 'v1', 'prompt-1', 'Earlier summary', 'limited', '["seed"]', '2026-05-28T08:00:00', '2026-05-28T08:00:00', '2026-05-28T08:01:00')
                        """,
                        (701, profile_row["agent_profile_id"]),
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_assessment_runs (
                            assessment_run_id,
                            agent_profile_id,
                            assessment_window_id,
                            trigger_mode,
                            run_status,
                            provider_key,
                            model_name,
                            instruction_version,
                            prompt_hash,
                            summary_text,
                            confidence_label,
                            principal_evidence_json,
                            created_at,
                            started_at,
                            completed_at,
                            supersedes_run_id
                        ) VALUES (?, ?, 601, 'rerun', 'completed', 'fake', 'fake-model', 'v1', 'prompt-2', 'Latest summary', 'medium', '["seed","metrics"]', '2026-05-28T09:00:00', '2026-05-28T09:00:00', '2026-05-28T09:01:00', 701)
                        """,
                        (702, profile_row["agent_profile_id"]),
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_assessment_type_results (
                            assessment_type_result_id,
                            assessment_run_id,
                            assessment_type_key,
                            result_label,
                            confidence_label,
                            narrative_text,
                            evidence_summary_json
                        ) VALUES (801, 702, 'daily_execution', 'executed', 'medium', 'Narrative', '["seed","metrics"]')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_assessment_findings (
                            assessment_finding_id,
                            assessment_run_id,
                            assessment_type_result_id,
                            finding_kind,
                            severity,
                            title,
                            detail_text,
                            evidence_refs_json,
                            sort_order
                        ) VALUES (901, 702, 801, 'next_action', 'info', 'Daily Execution Agent', 'Keep the next ride aerobic.', '["seed"]', 0)
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_adaptation_proposals (
                            proposal_id,
                            assessment_run_id,
                            agent_profile_id,
                            source_cadence,
                            target_planning_level,
                            proposal_status,
                            proposal_title,
                            proposal_summary,
                            change_kind,
                            proposed_change_json,
                            reasoning_summary,
                            conflict_group_key,
                            created_at,
                            updated_at
                        ) VALUES (1001, 702, ?, 'daily', 'weekly', 'pending', 'Reduce next day load', 'Pending queue item', 'reduce_volume', '{}', 'Fatigue is drifting up.', 'week:11:load', '2026-05-28T09:02:00', '2026-05-28T09:02:00')
                        """,
                        (profile_row["agent_profile_id"],),
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_adaptation_proposals (
                            proposal_id,
                            assessment_run_id,
                            agent_profile_id,
                            source_cadence,
                            target_planning_level,
                            proposal_status,
                            proposal_title,
                            proposal_summary,
                            change_kind,
                            proposed_change_json,
                            reasoning_summary,
                            conflict_group_key,
                            created_at,
                            updated_at
                        ) VALUES (1002, 702, ?, 'daily', 'weekly', 'accepted', 'Keep tomorrow easy', 'Accepted queue item', 'preserve_intensity', '{}', 'Recovery context supports holding back.', 'week:11:intensity', '2026-05-28T09:03:00', '2026-05-28T09:04:00')
                        """,
                        (profile_row["agent_profile_id"],),
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_proposal_decisions (
                            proposal_decision_id,
                            proposal_id,
                            decision_status,
                            decision_note,
                            decided_by,
                            decided_at,
                            applied_change_ref
                        ) VALUES (1101, 1002, 'accepted', 'Approved for the next two days.', 'local-operator', '2026-05-28T10:00:00', 'mutation-1002')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_accepted_plan_mutations (
                            plan_mutation_id,
                            proposal_id,
                            target_planning_level,
                            target_entity_id,
                            mutation_summary,
                            before_snapshot_json,
                            after_snapshot_json,
                            applied_at,
                            applied_by
                        ) VALUES (1201, 1002, 'weekly', 'week:11', 'Reduced the next session load', '{"load":"planned"}', '{"load":"reduced"}', '2026-05-28T10:01:00', 'local-operator')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO agent_assessment_dialog_context (
                            dialog_context_id,
                            assessment_run_id,
                            entry_kind,
                            entry_scope,
                            entry_text,
                            created_at,
                            created_by
                        ) VALUES (1301, 702, 'user_clarification', 'assessment_summary', 'The ride was moved one day earlier.', '2026-05-28T10:02:00', 'athlete')
                        """
                    )

                    views = {
                        row["name"]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'view' AND name LIKE 'vw_agent_%'"
                        ).fetchall()
                    }
                    latest_summary = connection.execute(
                        "SELECT assessment_run_id, summary_text, proposal_count, pending_proposal_count FROM vw_agent_latest_assessment_summaries WHERE profile_key = 'daily_execution_v1'"
                    ).fetchone()
                    detail = connection.execute(
                        "SELECT assessment_run_id, finding_count, type_result_count, proposal_count, pending_proposal_count, dialog_entry_count FROM vw_agent_assessment_detail WHERE assessment_run_id = 702"
                    ).fetchone()
                    review_rows = connection.execute(
                        "SELECT proposal_id, proposal_status, latest_decision_status, latest_applied_change_ref FROM vw_agent_proposal_review_queue ORDER BY proposal_id"
                    ).fetchall()
                    decision = connection.execute(
                        "SELECT proposal_id, decision_status, decided_by, applied_change_ref FROM vw_agent_proposal_decision_history WHERE proposal_id = 1002"
                    ).fetchone()
                    mutation = connection.execute(
                        "SELECT proposal_id, profile_key, decision_status, target_entity_id, applied_by FROM vw_agent_accepted_plan_mutation_traceability WHERE proposal_id = 1002"
                    ).fetchone()

                self.assertEqual(required_views - views, set())
                self.assertEqual(latest_summary["assessment_run_id"], 702)
                self.assertEqual(latest_summary["summary_text"], 'Latest summary')
                self.assertEqual(latest_summary["proposal_count"], 2)
                self.assertEqual(latest_summary["pending_proposal_count"], 1)
                self.assertEqual(detail["assessment_run_id"], 702)
                self.assertEqual(detail["finding_count"], 1)
                self.assertEqual(detail["type_result_count"], 1)
                self.assertEqual(detail["proposal_count"], 2)
                self.assertEqual(detail["pending_proposal_count"], 1)
                self.assertEqual(detail["dialog_entry_count"], 1)
                self.assertEqual(len(review_rows), 2)
                self.assertEqual(review_rows[0]["proposal_id"], 1001)
                self.assertEqual(review_rows[0]["proposal_status"], 'pending')
                self.assertIsNone(review_rows[0]["latest_decision_status"])
                self.assertEqual(review_rows[1]["proposal_id"], 1002)
                self.assertEqual(review_rows[1]["latest_decision_status"], 'accepted')
                self.assertEqual(review_rows[1]["latest_applied_change_ref"], 'mutation-1002')
                self.assertEqual(decision["proposal_id"], 1002)
                self.assertEqual(decision["decision_status"], 'accepted')
                self.assertEqual(decision["decided_by"], 'local-operator')
                self.assertEqual(decision["applied_change_ref"], 'mutation-1002')
                self.assertEqual(mutation["proposal_id"], 1002)
                self.assertEqual(mutation["profile_key"], 'daily_execution_v1')
                self.assertEqual(mutation["decision_status"], 'accepted')
                self.assertEqual(mutation["target_entity_id"], 'week:11')
                self.assertEqual(mutation["applied_by"], 'local-operator')