from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[3] / ".github" / "skills" / "daily-review-writeback" / "scripts" / "upsert_daily_review.py"
SPEC = importlib.util.spec_from_file_location("upsert_daily_review", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
upsert_daily_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upsert_daily_review)


class DailyReviewWritebackLinkingTests(unittest.TestCase):
    def test_build_row_infers_unique_compatible_activity_and_inserts_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            connection.executescript(
                """
                CREATE TABLE plan_seasons (
                    season_id INTEGER PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL
                );
                CREATE TABLE plan_meso_blocks (
                    block_id INTEGER PRIMARY KEY,
                    season_id INTEGER NOT NULL,
                    block_code TEXT
                );
                CREATE TABLE plan_micro_weeks (
                    week_id INTEGER PRIMARY KEY,
                    block_id INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    week_code TEXT,
                    block_code TEXT
                );
                CREATE TABLE plan_planned_sessions (
                    planned_session_id INTEGER PRIMARY KEY,
                    week_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
                    planned_type TEXT,
                    primary_session TEXT,
                    objective TEXT
                );
                CREATE TABLE exec_activities (
                    activity_id INTEGER PRIMARY KEY,
                    activity_date TEXT NOT NULL,
                    started_at TEXT,
                    discipline TEXT
                );
                CREATE TABLE link_plan_execution (
                    link_id INTEGER PRIMARY KEY,
                    planned_session_id INTEGER NOT NULL,
                    activity_id INTEGER NOT NULL,
                    link_type TEXT NOT NULL,
                    compliance_status TEXT NOT NULL,
                    rationale TEXT
                );
                """
            )
            connection.execute("INSERT INTO plan_seasons (season_id, start_date, end_date) VALUES (2026, '2026-01-01', '2026-12-31')")
            connection.execute("INSERT INTO plan_meso_blocks (block_id, season_id, block_code) VALUES (1, 2026, 'B1')")
            connection.execute("INSERT INTO plan_micro_weeks (week_id, block_id, start_date, end_date, week_code, block_code) VALUES (106, 1, '2026-06-08', '2026-06-14', 'Semana-06', 'B1')")
            connection.execute(
                "INSERT INTO plan_planned_sessions (planned_session_id, week_id, session_date, planned_type, primary_session, objective) VALUES (10607, 106, '2026-06-14', 'complementaria', 'Monte suave controlado 60-90 minutos.', 'Usar el monte como soporte aerobico controlado sin competir con el sabado.')"
            )
            connection.execute(
                "INSERT INTO exec_activities (activity_id, activity_date, started_at, discipline) VALUES (900276, '2026-06-14', '2026-06-14 18:29:50', 'walking')"
            )
            connection.commit()

            payload = {
                "actual_summary": "Caminata de monte larga.",
                "compliance_status": "completed_but_over_target",
            }
            args = SimpleNamespace(date="2026-06-14", season=2026)

            row, warnings = upsert_daily_review.build_row(connection, payload, args)
            self.assertEqual(row["planned_session_id"], 10607)
            self.assertEqual(row["activity_id"], 900276)
            self.assertIn("activity_id inferred from unique compatible day activity", warnings)

            link_action = upsert_daily_review.ensure_activity_link(connection, row, row["activity_id"], payload)
            connection.commit()
            link_row = connection.execute(
                "SELECT planned_session_id, activity_id, link_type, compliance_status FROM link_plan_execution"
            ).fetchone()

            self.assertEqual(link_action, "link_plan_execution inserted")
            self.assertIsNotNone(link_row)
            assert link_row is not None
            self.assertEqual(link_row["planned_session_id"], 10607)
            self.assertEqual(link_row["activity_id"], 900276)
            self.assertEqual(link_row["link_type"], "garmin_auto")
            self.assertEqual(link_row["compliance_status"], "completed_but_over_target")


if __name__ == "__main__":
    unittest.main()
