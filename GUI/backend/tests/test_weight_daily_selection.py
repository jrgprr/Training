from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.imports.garmin_connect import GarminConnectAdapter


WEIGHT_CONTEXT_PATH = (
    Path(__file__).resolve().parents[3]
    / ".github"
    / "skills"
    / "weight-control-assessment"
    / "scripts"
    / "build_weight_context.py"
)
SPEC = importlib.util.spec_from_file_location("build_weight_context", WEIGHT_CONTEXT_PATH)
assert SPEC is not None and SPEC.loader is not None
build_weight_context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_weight_context)


class GarminMorningWeightPreferenceTests(unittest.TestCase):
    def test_normalize_daily_metric_prefers_first_timestamped_weight_entry(self) -> None:
        metric = GarminConnectAdapter._normalize_daily_metric(
            metric_date="2026-06-14",
            stats_payload={},
            sleep_payload={},
            heart_rates_payload={},
            user_profile_payload=None,
            hrv_payload=None,
            body_battery_payload=None,
            stress_payload=None,
            spo2_payload=None,
            body_payload={
                "dateWeightList": [
                    {
                        "weight": 90100,
                        "measurementTimeLocal": "2026-06-14T18:45:00+02:00",
                        "bodyFat": 21.8,
                    },
                    {
                        "weight": 91300,
                        "measurementTimeLocal": "2026-06-14T07:12:00+02:00",
                        "bodyFat": 22.4,
                    },
                ]
            },
            steps_payload=None,
        )

        self.assertEqual(metric.weight_kg, 91.3)
        self.assertEqual(metric.weight_measured_at, "2026-06-14T07:12:00+02:00")
        self.assertEqual(metric.weight_measurement_source, "first_daily_measurement")
        self.assertEqual(metric.body_fat_pct, 22.4)

    def test_fetch_body_composition_payload_prefers_dayview_when_available(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.connectapi_calls: list[str] = []
                self.body_composition_calls: list[tuple[str, str]] = []

            def connectapi(self, path: str):
                self.connectapi_calls.append(path)
                return {
                    "dateWeightList": [
                        {"weight": 87940, "timestampGMT": 1781465654000},
                        {"weight": 89300, "timestampGMT": 1781430403000},
                    ]
                }

            def get_body_composition(self, start_date: str, end_date: str):
                self.body_composition_calls.append((start_date, end_date))
                return {"dateWeightList": [{"weight": 87940, "timestampGMT": 1781465654000}]}

        client = FakeClient()

        payload = GarminConnectAdapter._fetch_body_composition_payload(client, "2026-06-14")
        metric = GarminConnectAdapter._normalize_daily_metric(
            metric_date="2026-06-14",
            stats_payload={},
            sleep_payload={},
            heart_rates_payload={},
            user_profile_payload=None,
            hrv_payload=None,
            body_battery_payload=None,
            stress_payload=None,
            spo2_payload=None,
            body_payload=payload,
            steps_payload=None,
        )

        self.assertEqual(client.connectapi_calls, ["/weight-service/weight/dayview/2026-06-14"])
        self.assertEqual(client.body_composition_calls, [])
        self.assertEqual(metric.weight_kg, 89.3)
        self.assertEqual(metric.weight_measured_at, "2026-06-14T09:46:43+00:00")
        self.assertEqual(metric.weight_measurement_source, "first_daily_measurement")


class WeightTrendSelectionTests(unittest.TestCase):
    def test_select_weight_rows_for_trend_prefers_earliest_timestamped_rows_per_day(self) -> None:
        rows = [
            {
                "daily_metric_id": 1,
                "metric_date": "2026-06-10",
                "source_system": "garmin",
                "weight_kg": 90.8,
                "weight_measured_at": "2026-06-10T18:30:00+02:00",
                "weight_measurement_source": "first_daily_measurement",
            },
            {
                "daily_metric_id": 2,
                "metric_date": "2026-06-10",
                "source_system": "manual",
                "weight_kg": 91.1,
                "weight_measured_at": None,
                "weight_measurement_source": None,
            },
            {
                "daily_metric_id": 3,
                "metric_date": "2026-06-10",
                "source_system": "garmin",
                "weight_kg": 91.4,
                "weight_measured_at": "2026-06-10T07:05:00+02:00",
                "weight_measurement_source": "first_daily_measurement",
            },
            {
                "daily_metric_id": 4,
                "metric_date": "2026-06-11",
                "source_system": "garmin",
                "weight_kg": 90.9,
                "weight_measured_at": "2026-06-11T19:00:00+02:00",
                "weight_measurement_source": "first_daily_measurement",
            },
        ]

        selected = build_weight_context.select_weight_rows_for_trend(rows)

        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["metric_date"], "2026-06-10")
        self.assertEqual(selected[0]["weight_kg"], 91.4)
        self.assertEqual(selected[0]["weight_measurement_source"], "first_daily_measurement")
        self.assertEqual(selected[1]["metric_date"], "2026-06-11")
        self.assertEqual(selected[1]["weight_kg"], 90.9)

        summary = build_weight_context.summarize_weight_history(selected, target_weight=80.0, reference_weight=92.0)
        self.assertEqual(summary["timestamped_sample_days"], 2)
        self.assertEqual(summary["aggregate_sample_days"], 0)
        self.assertEqual(summary["latest_weight_measurement_source"], "first_daily_measurement")
        self.assertEqual(summary["selection_policy"], "earliest_timestamp_then_aggregate")


if __name__ == "__main__":
    unittest.main()