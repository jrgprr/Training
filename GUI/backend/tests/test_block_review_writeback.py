from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[3] / ".github" / "skills" / "block-review-writeback" / "scripts" / "upsert_block_review.py"
SPEC = importlib.util.spec_from_file_location("upsert_block_review", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
upsert_block_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upsert_block_review)


class BlockReviewWritebackTests(unittest.TestCase):
    def test_build_row_upserts_review_and_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            connection.executescript(
                """
                CREATE TABLE review_block_reviews (
                    block_review_id INTEGER PRIMARY KEY,
                    season_id INTEGER NOT NULL,
                    block_id INTEGER NOT NULL UNIQUE,
                    review_status TEXT NOT NULL,
                    closed_at TEXT,
                    weeks_in_block INTEGER,
                    total_sessions INTEGER,
                    completed_sessions INTEGER,
                    partial_sessions INTEGER,
                    pending_sessions INTEGER,
                    skipped_sessions INTEGER,
                    replaced_sessions INTEGER,
                    adherence_rate REAL,
                    traceability_rate REAL,
                    planned_reference_minutes REAL,
                    actual_minutes REAL,
                    volume_delta_minutes REAL,
                    key_sessions_total INTEGER,
                    key_sessions_closed INTEGER,
                    aligned_zone_sessions INTEGER,
                    limited_zone_sessions INTEGER,
                    misaligned_zone_sessions INTEGER,
                    daily_training_load_total REAL,
                    daily_training_load_peak REAL,
                    starting_tsb REAL,
                    ending_tsb REAL,
                    lowest_tsb REAL,
                    starting_atl REAL,
                    ending_atl REAL,
                    starting_ctl REAL,
                    ending_ctl REAL,
                    avg_sleep_hours REAL,
                    avg_resting_hr REAL,
                    avg_stress REAL,
                    starting_weight_kg REAL,
                    ending_weight_kg REAL,
                    weight_delta_kg REAL,
                    risk_level TEXT,
                    recommendation_text TEXT,
                    summary_text TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            original_loader = upsert_block_review.load_block_context
            original_root = upsert_block_review.REPO_ROOT
            try:
                upsert_block_review.load_block_context = lambda block_id, season_id, db_path: {
                    "season": {"season_id": 2026},
                    "block_context": {"block_id": 1, "block_code": "B1"},
                    "block_summary": {
                        "weeks_in_block": 6,
                        "total_sessions": 42,
                        "completed_sessions": 26,
                        "partial_sessions": 5,
                        "pending_sessions": 11,
                        "skipped_sessions": 0,
                        "replaced_sessions": 0,
                        "adherence_rate": 73.81,
                        "traceability_rate": 73.81,
                        "planned_reference_minutes": 3158,
                        "actual_minutes": 2536,
                        "volume_delta_minutes": -622,
                        "key_sessions_total": 8,
                        "key_sessions_closed": 4,
                        "aligned_zone_sessions": 7,
                        "limited_zone_sessions": 11,
                        "misaligned_zone_sessions": 3,
                        "daily_training_load_total": 2764.02,
                        "daily_training_load_peak": 176.59,
                        "starting_tsb": -27.6,
                        "ending_tsb": -39.33,
                        "lowest_tsb": -42.85,
                        "starting_atl": 57.51,
                        "ending_atl": 95.91,
                        "starting_ctl": 29.9,
                        "ending_ctl": 56.58,
                        "avg_sleep_hours": 7.67,
                        "avg_resting_hr": 49.21,
                        "avg_stress": 35.38,
                        "starting_weight_kg": 93.21,
                        "ending_weight_kg": 87.94,
                        "weight_delta_kg": -5.27,
                    },
                }
                upsert_block_review.REPO_ROOT = Path(temp_dir)

                payload = {
                    "summary_text": "Bloque completado con fatiga creciente pero buena continuidad.",
                    "recommendation_text": "Abrir la descarga y consolidar tolerancia.",
                    "risk_level": "Riesgo medio",
                    "detailed_assessment_markdown": "# Assessment B1\n\nTexto de prueba.",
                }
                args = SimpleNamespace(block_id=1, season=2026, db=str(database_path))

                row, warnings = upsert_block_review.build_row(connection, payload, args)
                self.assertEqual(warnings, [])
                self.assertEqual(row["block_code"], "B1")
                self.assertEqual(row["summary_text"], payload["summary_text"])

                upsert_block_review.upsert_row(connection, row)
                stored = upsert_block_review.load_existing_row(connection, 1)
                self.assertIsNotNone(stored)
                assert stored is not None
                self.assertEqual(stored["season_id"], 2026)
                self.assertEqual(stored["block_id"], 1)
                self.assertEqual(stored["review_status"], "closed")
                self.assertEqual(stored["risk_level"], "Riesgo medio")
                self.assertEqual(stored["summary_text"], payload["summary_text"])

                markdown_path = upsert_block_review.write_assessment_markdown(row, payload)
                self.assertTrue(markdown_path.exists())
                markdown_text = markdown_path.read_text(encoding="utf-8")
                self.assertIn("# Assessment B1", markdown_text)
                self.assertIn("Structured Block Review Snapshot", markdown_text)
                self.assertIn(payload["summary_text"], markdown_text)
            finally:
                upsert_block_review.load_block_context = original_loader
                upsert_block_review.REPO_ROOT = original_root


if __name__ == "__main__":
    unittest.main()