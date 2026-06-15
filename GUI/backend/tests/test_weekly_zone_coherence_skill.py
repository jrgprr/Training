from __future__ import annotations

import argparse
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database
from tests.test_training_zones import TrainingZoneComparisonTests


MODULE_PATH = Path(__file__).resolve().parents[3] / ".github" / "skills" / "weekly-zone-coherence-assessment" / "scripts" / "analyze_week_zone_coherence.py"
SPEC = importlib.util.spec_from_file_location("analyze_week_zone_coherence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
analyze_week_zone_coherence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyze_week_zone_coherence)


class WeeklyZoneCoherenceSkillScriptTests(unittest.TestCase):
    def test_build_zone_coherence_payload_returns_week_and_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    TrainingZoneComparisonTests._create_week_zone_context(connection)

                args = argparse.Namespace(week_id=20, date=None, season=None, db=str(database_path))
                payload = analyze_week_zone_coherence.build_zone_coherence_payload(args)

        self.assertEqual(payload["metadata"]["week_id"], 20)
        self.assertEqual(payload["week_context"]["week_code"], "W20")
        self.assertEqual(payload["zone_coherence_assessment"]["overall_status"], "update_candidate")


if __name__ == "__main__":
    unittest.main()