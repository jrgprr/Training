from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[3] / ".github" / "skills" / "daily-performance-assessment" / "scripts" / "build_day_context.py"
SPEC = importlib.util.spec_from_file_location("build_day_context", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
build_day_context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_day_context)


class DayContextMetricSelectorTests(unittest.TestCase):
    def test_walking_like_session_below_threshold_is_not_selected(self) -> None:
        selected, reasons = build_day_context.select_metric_analysis_activity(
            [
                {
                    "activity_id": 1,
                    "discipline": "trail_walking",
                    "duration_seconds": 44 * 60,
                    "modeled_load_value": 49.0,
                    "training_load": 1.3,
                }
            ],
            [],
        )

        self.assertIsNone(selected)
        self.assertEqual(reasons, [])

    def test_walking_like_session_is_selected_when_modeled_load_crosses_threshold(self) -> None:
        selected, reasons = build_day_context.select_metric_analysis_activity(
            [
                {
                    "activity_id": 1,
                    "discipline": "trail_walking",
                    "duration_seconds": 30 * 60,
                    "modeled_load_value": 53.7,
                    "training_load": 1.3,
                }
            ],
            [],
        )

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["activity_id"], 1)
        self.assertEqual(reasons, ["dominant_endurance_session", "meaningful_modeled_load"])


if __name__ == "__main__":
    unittest.main()