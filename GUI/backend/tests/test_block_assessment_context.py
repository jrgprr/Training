from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[3] / ".github" / "skills" / "block-performance-assessment" / "scripts" / "build_block_context.py"
SPEC = importlib.util.spec_from_file_location("build_block_context", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
build_block_context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_block_context)


class BlockContextSummaryTests(unittest.TestCase):
    def test_compute_block_summary_aggregates_week_and_daily_signals(self) -> None:
        week_bundles = [
            {
                "review_metrics": {
                    "planned_reference_minutes": 300,
                    "actual_minutes": 360,
                },
                "plan_vs_real_rows": [
                    {"is_key_session": 1, "compliance_status": "completed"},
                    {"is_key_session": 0, "compliance_status": "partial"},
                    {"is_key_session": 0, "compliance_status": "pending"},
                ],
                "zone_comparison_summary": {
                    "items": [
                        {"aligned_count": 1, "limited_count": 1, "misaligned_count": 0},
                    ]
                },
            },
            {
                "review_metrics": {
                    "planned_reference_minutes": 280,
                    "actual_minutes": 250,
                },
                "plan_vs_real_rows": [
                    {"is_key_session": 1, "compliance_status": "completed_but_over_target"},
                    {"is_key_session": 0, "compliance_status": "skipped"},
                ],
                "zone_comparison_summary": {
                    "items": [
                        {"aligned_count": 2, "limited_count": 0, "misaligned_count": 1},
                    ]
                },
            },
        ]
        daily_trend = [
            {
                "sleep_hours": 7.0,
                "resting_hr": 50.0,
                "stress_avg": 30.0,
                "weight_kg": 90.0,
                "load_model": {"daily_training_load": 60.0, "tsb": -20.0, "atl": 70.0, "ctl": 40.0},
            },
            {
                "sleep_hours": 8.0,
                "resting_hr": 48.0,
                "stress_avg": 28.0,
                "weight_kg": 88.5,
                "load_model": {"daily_training_load": 90.0, "tsb": -35.0, "atl": 82.0, "ctl": 45.0},
            },
        ]

        summary = build_block_context.compute_block_summary(week_bundles, daily_trend)

        self.assertEqual(summary["weeks_in_block"], 2)
        self.assertEqual(summary["total_sessions"], 5)
        self.assertEqual(summary["completed_sessions"], 2)
        self.assertEqual(summary["partial_sessions"], 1)
        self.assertEqual(summary["pending_sessions"], 1)
        self.assertEqual(summary["skipped_sessions"], 1)
        self.assertEqual(summary["key_sessions_total"], 2)
        self.assertEqual(summary["key_sessions_closed"], 2)
        self.assertEqual(summary["planned_reference_minutes"], 580)
        self.assertEqual(summary["actual_minutes"], 610)
        self.assertEqual(summary["volume_delta_minutes"], 30)
        self.assertEqual(summary["aligned_zone_sessions"], 3)
        self.assertEqual(summary["limited_zone_sessions"], 1)
        self.assertEqual(summary["misaligned_zone_sessions"], 1)
        self.assertEqual(summary["daily_training_load_total"], 150.0)
        self.assertEqual(summary["starting_tsb"], -20.0)
        self.assertEqual(summary["ending_tsb"], -35.0)
        self.assertEqual(summary["weight_delta_kg"], -1.5)
        self.assertEqual(summary["avg_sleep_hours"], 7.5)


if __name__ == "__main__":
    unittest.main()
