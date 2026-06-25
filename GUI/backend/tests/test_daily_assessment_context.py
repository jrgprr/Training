from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


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


class DayContextWeatherTests(unittest.TestCase):
    def test_summarize_weather_impact_flags_hot_low_cooling_conditions(self) -> None:
        summary = build_day_context.summarize_weather_impact(
            {
                "summary": {
                    "temperature_mean": 31.6,
                    "temperature_max": 35.5,
                    "apparent_temperature_mean": 36.5,
                    "cloud_cover_mean": 8.0,
                    "wind_speed_mean": 7.5,
                    "shortwave_radiation_mean": 410.0,
                    "rain_sum_est": 0.0,
                }
            }
        )

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["heat_level"], "high")
        self.assertEqual(summary["cooling_level"], "limited")
        self.assertEqual(summary["moisture_context"], "dry")
        self.assertTrue(any("hydration demand" in note for note in summary["analysis_notes"]))

    def test_enrich_activities_with_weather_attaches_weather_and_analysis(self) -> None:
        activities = [{"activity_id": 7, "discipline": "road_biking"}]
        fake_weather = {
            "summary": {
                "temperature_mean": 27.0,
                "temperature_max": 31.0,
                "apparent_temperature_mean": 29.0,
                "cloud_cover_mean": 55.0,
                "wind_speed_mean": 12.0,
                "shortwave_radiation_mean": 180.0,
                "rain_sum_est": 0.0,
            }
        }

        with patch.object(build_day_context, "load_activity_weather", return_value=fake_weather):
            build_day_context.enrich_activities_with_weather(activities)

        self.assertEqual(activities[0]["weather"], fake_weather)
        self.assertIsNotNone(activities[0]["weather_analysis"])
        self.assertEqual(activities[0]["weather_analysis"]["heat_level"], "moderate")


if __name__ == "__main__":
    unittest.main()