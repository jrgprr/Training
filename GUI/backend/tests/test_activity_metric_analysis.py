from __future__ import annotations

import importlib.util
import sqlite3
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[3] / ".github" / "skills" / "activity-metric-analysis" / "scripts" / "compute_activity_metric_analysis.py"
SPEC = importlib.util.spec_from_file_location("compute_activity_metric_analysis", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
activity_metric_analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activity_metric_analysis)


class ActivityMetricAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE exec_activities (
                activity_id INTEGER PRIMARY KEY,
                season_id INTEGER,
                activity_date TEXT,
                started_at TEXT,
                discipline TEXT,
                activity_type TEXT,
                duration_seconds INTEGER,
                distance_meters REAL,
                ascent_meters REAL,
                calories REAL,
                avg_hr REAL,
                max_hr REAL,
                avg_power REAL,
                normalized_power REAL,
                avg_pace_seconds_per_km REAL,
                training_load REAL,
                quality_status TEXT,
                quality_decision_count INTEGER,
                quality_limited_metric_count INTEGER
            );
            CREATE TABLE link_plan_execution (
                link_id INTEGER PRIMARY KEY,
                planned_session_id INTEGER,
                activity_id INTEGER,
                compliance_status TEXT
            );
            CREATE TABLE plan_planned_sessions (
                planned_session_id INTEGER PRIMARY KEY,
                primary_session TEXT,
                objective TEXT,
                duration_min INTEGER,
                duration_max INTEGER,
                intensity_class TEXT
            );
            CREATE TABLE plan_session_zone_targets (
                planned_zone_target_id INTEGER PRIMARY KEY,
                planned_session_id INTEGER,
                target_basis TEXT,
                target_kind TEXT,
                source_text TEXT
            );
            CREATE TABLE exec_activity_metric_summaries (
                activity_id INTEGER,
                metric_name TEXT,
                summary_kind TEXT,
                trusted_value REAL,
                summary_status TEXT
            );
            CREATE TABLE exec_activity_metric_readings (
                activity_metric_reading_id INTEGER PRIMARY KEY,
                activity_id INTEGER,
                metric_name TEXT,
                sample_index INTEGER,
                raw_value REAL,
                recorded_at TEXT,
                elapsed_seconds REAL
            );
            CREATE TABLE exec_activity_zone_results (
                activity_zone_result_id INTEGER PRIMARY KEY,
                activity_id INTEGER,
                zone_profile_id INTEGER,
                metric_basis TEXT,
                calculation_status TEXT,
                quality_status_snapshot TEXT,
                supported_sample_count INTEGER,
                total_supported_seconds INTEGER,
                dominant_zone_code TEXT,
                dominant_zone_share REAL,
                calculation_notes TEXT
            );
            CREATE TABLE exec_activity_zone_buckets (
                activity_zone_bucket_id INTEGER PRIMARY KEY,
                activity_zone_result_id INTEGER,
                zone_index INTEGER,
                zone_code TEXT,
                seconds_in_zone INTEGER,
                share_in_zone REAL
            );
            CREATE TABLE exec_segments (
                segment_id INTEGER PRIMARY KEY,
                source_system TEXT,
                external_segment_id TEXT,
                segment_name TEXT,
                discipline TEXT,
                distance_meters REAL,
                ascent_meters REAL,
                average_grade_percent REAL
            );
            CREATE TABLE exec_segment_efforts (
                segment_effort_id INTEGER PRIMARY KEY,
                source_system TEXT,
                external_segment_effort_id TEXT,
                segment_id INTEGER,
                activity_id INTEGER,
                activity_date TEXT,
                started_at TEXT,
                elapsed_time_seconds INTEGER,
                avg_power REAL,
                avg_cadence REAL,
                avg_heart_rate REAL,
                max_heart_rate REAL,
                notes TEXT
            );
            """
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_compute_activity_metric_analysis_includes_segments_and_recent_comparison(self) -> None:
        self.connection.executemany(
            """
            INSERT INTO exec_activities (
                activity_id, season_id, activity_date, started_at, discipline, activity_type,
                duration_seconds, distance_meters, ascent_meters, calories, avg_hr, max_hr, avg_power, normalized_power,
                avg_pace_seconds_per_km, training_load, quality_status,
                quality_decision_count, quality_limited_metric_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 2026, "2026-06-15", "2026-06-15T08:00:00", "road_biking", "ride", 3600, 30000, 400, 900, 120, 140, 150, 160, None, 90, "clean", 0, 0),
                (2, 2026, "2026-06-13", "2026-06-13T08:00:00", "road_biking", "ride", 3300, 28000, 420, 950, 125, 145, 170, 180, None, 140, "clean", 0, 0),
                (3, 2026, "2026-06-10", "2026-06-10T08:00:00", "road_biking", "ride", 3900, 32000, 390, 920, 128, 150, 165, 175, None, 135, "clean", 0, 0),
                (4, 2026, "2026-06-08", "2026-06-08T08:00:00", "running", "run", 3600, 10000, 120, 700, 150, 165, None, None, 320, 120, "clean", 0, 0),
            ],
        )
        self.connection.execute(
            "INSERT INTO plan_planned_sessions (planned_session_id, primary_session, objective, duration_min, duration_max, intensity_class) VALUES (?, ?, ?, ?, ?, ?)",
            (101, "Bicicleta Z1 60-90 minutos.", "Recuperacion aerobica", 60, 90, "muy suave"),
        )
        self.connection.execute(
            "INSERT INTO plan_session_zone_targets (planned_zone_target_id, planned_session_id, target_basis, target_kind, source_text) VALUES (?, ?, ?, ?, ?)",
            (1, 101, "heart_rate", "single_zone", "Bicicleta Z1 60-90 minutos."),
        )
        self.connection.execute(
            "INSERT INTO link_plan_execution (link_id, planned_session_id, activity_id, compliance_status) VALUES (?, ?, ?, ?)",
            (1, 101, 1, "completed"),
        )

        self.connection.executemany(
            "INSERT INTO exec_activity_metric_summaries (activity_id, metric_name, summary_kind, trusted_value, summary_status) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "respiration_rate", "average", 22.0, "trusted"),
                (1, "performance_condition", "average", 1.1, "trusted"),
                (1, "performance_condition", "minimum", -3.0, "trusted"),
                (1, "performance_condition", "maximum", 3.0, "trusted"),
                (2, "respiration_rate", "average", 24.0, "trusted"),
                (3, "respiration_rate", "average", 23.0, "trusted"),
            ],
        )
        self.connection.executemany(
            "INSERT INTO exec_activity_zone_results (activity_zone_result_id, activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share, calculation_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 1, "heart_rate", "calculated", "clean", 3600, 3600, "Z1", 0.8, None),
                (2, 1, 1, "power", "calculated", "clean", 3600, 3600, "Z1", 0.75, None),
            ],
        )
        self.connection.executemany(
            "INSERT INTO exec_activity_zone_buckets (activity_zone_bucket_id, activity_zone_result_id, zone_index, zone_code, seconds_in_zone, share_in_zone) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 1, "Z1", 2880, 0.8),
                (2, 1, 2, "Z2", 720, 0.2),
                (3, 2, 1, "Z1", 2700, 0.75),
                (4, 2, 2, "Z2", 900, 0.25),
            ],
        )
        self.connection.executemany(
            "INSERT INTO exec_activity_metric_readings (activity_id, metric_name, sample_index, raw_value, recorded_at, elapsed_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "power", 0, 0, None, 0),
                (1, "power", 1, 120, None, 300),
                (1, "power", 2, 160, None, 600),
                (1, "power", 3, 0, None, 900),
                (1, "power", 4, 170, None, 1200),
                (1, "power", 5, 155, None, 1500),
                (1, "power", 6, 0, None, 1800),
                (1, "power", 7, 150, None, 2100),
                (1, "power", 8, 140, None, 2400),
                (1, "power", 9, 0, None, 2700),
                (1, "power", 10, 145, None, 3000),
                (1, "power", 11, 135, None, 3300),
                (1, "heart_rate", 0, 118, None, 0),
                (1, "heart_rate", 1, 119, None, 300),
                (1, "heart_rate", 2, 120, None, 600),
                (1, "heart_rate", 3, 121, None, 900),
                (1, "heart_rate", 4, 122, None, 1200),
                (1, "heart_rate", 5, 121, None, 1500),
                (1, "heart_rate", 6, 120, None, 1800),
                (1, "heart_rate", 7, 119, None, 2100),
                (1, "heart_rate", 8, 118, None, 2400),
                (1, "heart_rate", 9, 119, None, 2700),
                (1, "heart_rate", 10, 120, None, 3000),
                (1, "heart_rate", 11, 121, None, 3300),
                (1, "performance_condition", 0, -2, None, 0),
                (1, "performance_condition", 1, -1, None, 300),
                (1, "performance_condition", 2, 0, None, 600),
                (1, "performance_condition", 3, 3, None, 900),
                (1, "performance_condition", 4, 2, None, 1200),
                (1, "performance_condition", 5, 1, None, 1500),
            ],
        )

        self.connection.executemany(
            "INSERT INTO exec_segments (segment_id, source_system, external_segment_id, segment_name, discipline, distance_meters, ascent_meters, average_grade_percent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (11, "garmin", "seg-11", "Climb A", "road_biking", 1200, 80, 6.4),
                (12, "garmin", "seg-12", "Flat B", "road_biking", 900, 5, 0.4),
            ],
        )
        self.connection.executemany(
            """
            INSERT INTO exec_segment_efforts (
                segment_effort_id, source_system, external_segment_effort_id, segment_id, activity_id,
                activity_date, started_at, elapsed_time_seconds, avg_power, avg_cadence, avg_heart_rate, max_heart_rate, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (101, "garmin", "eff-101", 11, 1, "2026-06-15", "2026-06-15T08:15:00", 300, 205, 85, 142, 155, None),
                (102, "garmin", "eff-102", 12, 1, "2026-06-15", "2026-06-15T08:25:00", 180, 180, 90, 132, 140, None),
                (201, "garmin", "eff-201", 11, 2, "2026-06-13", "2026-06-13T08:15:00", 320, 215, 86, 148, 160, None),
                (301, "garmin", "eff-301", 11, 3, "2026-06-10", "2026-06-10T08:15:00", 290, 225, 88, 150, 162, None),
            ],
        )

        analysis = activity_metric_analysis.compute_activity_metric_analysis(self.connection, 1)

        self.assertIn("activity_efficiency", analysis)
        self.assertIn("segment_analysis", analysis)
        self.assertIn("recent_comparison", analysis)
        self.assertIsNotNone(analysis["segment_analysis"])
        self.assertIsNotNone(analysis["recent_comparison"])
        self.assertEqual(analysis["segment_analysis"]["segment_count"], 2)
        self.assertEqual(analysis["segment_analysis"]["comparable_segment_count"], 1)
        first_segment = analysis["segment_analysis"]["highlights"][0]
        self.assertEqual(first_segment["segment_name"], "Climb A")
        self.assertEqual(first_segment["delta_vs_previous_seconds"], -20)
        self.assertEqual(first_segment["delta_vs_best_seconds"], 10)
        self.assertEqual(first_segment["trend_status"], "improved_vs_previous")
        self.assertEqual(analysis["recent_comparison"]["sample_count"], 2)
        self.assertEqual(analysis["recent_comparison"]["similar_activities"][0]["activity_id"], 2)
        self.assertAlmostEqual(analysis["recent_comparison"]["current_vs_recent"]["avg_power"]["delta"], -17.5)
        efficiency = analysis["activity_efficiency"]
        assert efficiency is not None
        self.assertEqual(efficiency["efficiency_factor"]["basis"], "normalized_power_per_avg_hr")
        self.assertAlmostEqual(efficiency["efficiency_factor"]["current"], 1.333, places=3)
        self.assertAlmostEqual(efficiency["variability_index"]["current"], 1.067, places=3)
        self.assertEqual(efficiency["target_zone_compliance"]["status"], "acceptable")
        self.assertAlmostEqual(efficiency["target_zone_compliance"]["time_in_target_share"], 0.8, places=4)
        self.assertAlmostEqual(efficiency["load_density"]["current"], 90.0, places=1)
        self.assertAlmostEqual(efficiency["coasting_or_low_output_share"]["share"], 0.3333, places=4)
        self.assertAlmostEqual(efficiency["climbing_efficiency"]["vertical_rate_m_per_hour"]["current"], 400.0, places=1)
        self.assertAlmostEqual(efficiency["respiration_relationship"]["breaths_per_100w"]["current"], 14.67, places=2)
        performance_condition = analysis["performance_condition_signal"]
        assert performance_condition is not None
        self.assertEqual(performance_condition["status"], "mixed")
        self.assertAlmostEqual(performance_condition["average"], 1.1, places=2)
        self.assertAlmostEqual(performance_condition["minimum"], -3.0, places=2)
        self.assertAlmostEqual(performance_condition["maximum"], 3.0, places=2)
        self.assertIn("performance_condition", analysis["data_quality"]["metric_sources"])
        evolution = analysis["performance_condition_evolution"]
        assert evolution is not None
        self.assertIn("opened negative", evolution)
        self.assertIn("middle phase", evolution)
        self.assertIn("held a manageable internal cost", evolution)

    def test_walking_negative_hr_drift_is_not_flagged_as_poor(self) -> None:
        self.connection.execute(
            """
            INSERT INTO exec_activities (
                activity_id, season_id, activity_date, started_at, discipline, activity_type,
                duration_seconds, distance_meters, ascent_meters, calories, avg_hr, max_hr, avg_power, normalized_power,
                avg_pace_seconds_per_km, training_load, quality_status,
                quality_decision_count, quality_limited_metric_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (10, 2026, "2026-06-14", "2026-06-14T08:00:00", "walking", "walk", 7200, 15000, 700, 1100, 118, 136, None, None, 560, 80, "clean", 0, 0),
        )
        self.connection.executemany(
            "INSERT INTO exec_activity_metric_readings (activity_id, metric_name, sample_index, raw_value, recorded_at, elapsed_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (10, "heart_rate", 0, 124, None, 0),
                (10, "heart_rate", 1, 123, None, 600),
                (10, "heart_rate", 2, 121, None, 1200),
                (10, "heart_rate", 3, 120, None, 1800),
                (10, "heart_rate", 4, 118, None, 2400),
                (10, "heart_rate", 5, 117, None, 3000),
                (10, "heart_rate", 6, 115, None, 3600),
                (10, "heart_rate", 7, 114, None, 4200),
                (10, "heart_rate", 8, 113, None, 4800),
                (10, "heart_rate", 9, 112, None, 5400),
                (10, "heart_rate", 10, 111, None, 6000),
                (10, "heart_rate", 11, 110, None, 6600),
                (10, "speed", 0, 1.65, None, 0),
                (10, "speed", 1, 1.70, None, 600),
                (10, "speed", 2, 1.60, None, 1200),
                (10, "speed", 3, 1.68, None, 1800),
                (10, "speed", 4, 1.62, None, 2400),
                (10, "speed", 5, 1.58, None, 3000),
                (10, "speed", 6, 1.64, None, 3600),
                (10, "speed", 7, 1.61, None, 4200),
                (10, "speed", 8, 1.59, None, 4800),
                (10, "speed", 9, 1.63, None, 5400),
                (10, "speed", 10, 1.57, None, 6000),
                (10, "speed", 11, 1.60, None, 6600),
                (10, "vertical_speed", 0, 0.10, None, 0),
                (10, "vertical_speed", 1, 0.18, None, 600),
                (10, "vertical_speed", 2, 0.05, None, 1200),
                (10, "vertical_speed", 3, 0.20, None, 1800),
                (10, "vertical_speed", 4, -0.05, None, 2400),
                (10, "vertical_speed", 5, -0.08, None, 3000),
                (10, "vertical_speed", 6, 0.16, None, 3600),
                (10, "vertical_speed", 7, -0.02, None, 4200),
                (10, "vertical_speed", 8, -0.10, None, 4800),
                (10, "vertical_speed", 9, 0.04, None, 5400),
                (10, "vertical_speed", 10, -0.06, None, 6000),
                (10, "vertical_speed", 11, 0.02, None, 6600),
            ],
        )

        analysis = activity_metric_analysis.compute_activity_metric_analysis(self.connection, 10)

        self.assertEqual(analysis["analysis_scope"], "pace_plus_hr")
        self.assertEqual(analysis["aerobic_control_status"], "good")
        self.assertEqual(analysis["power_hr_relationship"], "aligned")
        self.assertIn("walking-like session", analysis["relationship_notes"])
        self.assertIn("pace", analysis["data_quality"]["metric_sources"])
        self.assertIsNotNone(analysis["grade_adjusted_pace"])
        efficiency = analysis["activity_efficiency"]
        assert efficiency is not None
        self.assertEqual(efficiency["efficiency_factor"]["basis"], "grade_adjusted_speed_per_avg_hr")
        self.assertIn("grade_adjusted_pace", efficiency)
        self.assertIn("climbing_efficiency", efficiency)

    def test_running_activity_efficiency_includes_grade_adjusted_pace(self) -> None:
        self.connection.executemany(
            """
            INSERT INTO exec_activities (
                activity_id, season_id, activity_date, started_at, discipline, activity_type,
                duration_seconds, distance_meters, ascent_meters, calories, avg_hr, max_hr, avg_power, normalized_power,
                avg_pace_seconds_per_km, training_load, quality_status,
                quality_decision_count, quality_limited_metric_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (20, 2026, "2026-05-30", "2026-05-30T07:00:00", "running", "run", 2400, 6000, 180, 480, 148, 166, None, None, 400, 95, "clean", 0, 0),
                (21, 2026, "2026-05-20", "2026-05-20T07:00:00", "running", "run", 2460, 6100, 160, 470, 150, 168, None, None, 403, 92, "clean", 0, 0),
            ],
        )
        self.connection.execute(
            "INSERT INTO exec_activity_metric_summaries (activity_id, metric_name, summary_kind, trusted_value, summary_status) VALUES (?, ?, ?, ?, ?)",
            (20, "respiration_rate", "average", 28.0, "trusted"),
        )
        self.connection.executemany(
            "INSERT INTO exec_activity_metric_readings (activity_id, metric_name, sample_index, raw_value, recorded_at, elapsed_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (20, "heart_rate", 0, 144, None, 0),
                (20, "heart_rate", 1, 145, None, 200),
                (20, "heart_rate", 2, 146, None, 400),
                (20, "heart_rate", 3, 147, None, 600),
                (20, "heart_rate", 4, 148, None, 800),
                (20, "heart_rate", 5, 149, None, 1000),
                (20, "heart_rate", 6, 150, None, 1200),
                (20, "heart_rate", 7, 151, None, 1400),
                (20, "heart_rate", 8, 152, None, 1600),
                (20, "heart_rate", 9, 153, None, 1800),
                (20, "heart_rate", 10, 154, None, 2000),
                (20, "heart_rate", 11, 155, None, 2200),
                (20, "speed", 0, 2.40, None, 0),
                (20, "speed", 1, 2.45, None, 200),
                (20, "speed", 2, 2.42, None, 400),
                (20, "speed", 3, 2.38, None, 600),
                (20, "speed", 4, 2.35, None, 800),
                (20, "speed", 5, 2.50, None, 1000),
                (20, "speed", 6, 2.55, None, 1200),
                (20, "speed", 7, 2.52, None, 1400),
                (20, "speed", 8, 2.48, None, 1600),
                (20, "speed", 9, 2.44, None, 1800),
                (20, "speed", 10, 2.46, None, 2000),
                (20, "speed", 11, 2.43, None, 2200),
                (20, "vertical_speed", 0, 0.05, None, 0),
                (20, "vertical_speed", 1, 0.12, None, 200),
                (20, "vertical_speed", 2, 0.20, None, 400),
                (20, "vertical_speed", 3, 0.18, None, 600),
                (20, "vertical_speed", 4, -0.05, None, 800),
                (20, "vertical_speed", 5, 0.30, None, 1000),
                (20, "vertical_speed", 6, 0.35, None, 1200),
                (20, "vertical_speed", 7, 0.16, None, 1400),
                (20, "vertical_speed", 8, -0.08, None, 1600),
                (20, "vertical_speed", 9, -0.12, None, 1800),
                (20, "vertical_speed", 10, 0.04, None, 2000),
                (20, "vertical_speed", 11, 0.00, None, 2200),
            ],
        )

        analysis = activity_metric_analysis.compute_activity_metric_analysis(self.connection, 20)

        self.assertEqual(analysis["analysis_scope"], "pace_plus_hr")
        self.assertIn(analysis["power_hr_relationship"], {"aligned", "hr_high_for_power"})
        self.assertIsNotNone(analysis["grade_adjusted_pace"])
        self.assertEqual(analysis["grade_adjusted_pace"]["model_key"], "running_grade_cost_model")
        efficiency = analysis["activity_efficiency"]
        assert efficiency is not None
        self.assertEqual(efficiency["efficiency_factor"]["basis"], "grade_adjusted_speed_per_avg_hr")
        self.assertIn("grade_adjusted_pace", efficiency)
        self.assertIn("breaths_per_km", efficiency["respiration_relationship"])


if __name__ == "__main__":
    unittest.main()
