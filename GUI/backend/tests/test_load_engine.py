import sqlite3
import unittest
from unittest.mock import patch

from app import load_engine
from app.main import get_activity


class LoadEngineTests(unittest.TestCase):
    def test_compute_power_tss_uses_ftp_and_normalized_power(self) -> None:
        value = load_engine._compute_power_tss(
            duration_seconds=3600,
            normalized_power=250,
            average_power=230,
            ftp=250,
        )

        self.assertEqual(value, 100.0)

    def test_compute_hr_trimp_uses_heart_rate_reserve(self) -> None:
        value = load_engine._compute_hr_trimp(
            duration_seconds=3600,
            average_hr=150,
            resting_hr=50,
            max_hr=174,
        )

        self.assertAlmostEqual(value, 145.67, places=2)

    def test_compute_activity_load_prefers_hr_trimp_for_strength(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            def fake_fetch(*, metric_basis: str, **_: object):
                if metric_basis == "heart_rate":
                    return {"resting_hr": 50.0, "max_hr": 174.0}
                return None

            load_engine._fetch_anchor_profile = fake_fetch
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "strength_training",
                    "duration_seconds": 3600,
                    "avg_hr": 150,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 0.9,
                    "perceived_exertion": 6,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "hr_trimp")
        self.assertAlmostEqual(result["load_value"], 145.67, places=2)

    def test_compute_activity_load_uses_garmin_for_strength_when_hr_trimp_unavailable(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            load_engine._fetch_anchor_profile = lambda **_: None
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "strength_training",
                    "duration_seconds": 3600,
                    "avg_hr": None,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 0.9,
                    "perceived_exertion": 6,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "garmin_training_load")
        self.assertEqual(result["load_value"], 0.9)

    def test_activity_detail_exposes_computed_load_used_by_load_model(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            def fake_fetch(*, metric_basis: str, **_: object):
                if metric_basis == "heart_rate":
                    return {"resting_hr": 50.0, "max_hr": 174.0}
                return None

            load_engine._fetch_anchor_profile = fake_fetch
            with patch("app.main.fetch_one") as fetch_one_mock:
                fetch_one_mock.return_value = {
                    "activity_id": 900243,
                    "season_id": 2026,
                    "source_system": "garmin",
                    "external_activity_id": "abc",
                    "activity_date": "2026-06-03",
                    "started_at": "2026-06-03 23:18:44",
                    "discipline": "strength_training",
                    "activity_type": "Fuerza",
                    "duration_seconds": 2035,
                    "distance_meters": 0.0,
                    "ascent_meters": None,
                    "calories": 194.0,
                    "avg_hr": 92.61,
                    "max_hr": 114.0,
                    "avg_respiration_rate": None,
                    "max_respiration_rate": None,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 1.3,
                    "avg_pace_seconds_per_km": None,
                    "perceived_exertion": None,
                    "subjective_feeling": None,
                    "stress_avg": 37.0,
                    "stress_max": 99.0,
                    "spo2_sleep_avg": 93.0,
                    "spo2_avg": 93.0,
                    "spo2_7d_avg": 90.8,
                    "spo2_lowest": 85.0,
                    "source_file": None,
                    "raw_payload_path": None,
                    "notes": None,
                    "quality_status": "clean",
                    "quality_checked_at": None,
                    "quality_rule_version": None,
                    "quality_decision_count": 0,
                    "quality_limited_metric_count": 0,
                    "planned_session_id": 10503,
                    "compliance_status": "completed",
                    "rationale": None,
                    "actual_summary": None,
                    "general_feeling": None,
                    "next_day_decision": None,
                }

                activity = get_activity(900243)
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(activity["training_load"], 1.3)
        self.assertEqual(activity["calculated_training_load_source"], "hr_trimp")
        self.assertGreater(activity["calculated_training_load"], activity["training_load"])

    def test_compute_activity_load_prefers_hr_trimp_for_yoga(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            def fake_fetch(*, metric_basis: str, **_: object):
                if metric_basis == "heart_rate":
                    return {"resting_hr": 50.0, "max_hr": 174.0}
                return None

            load_engine._fetch_anchor_profile = fake_fetch
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "yoga",
                    "duration_seconds": 1800,
                    "avg_hr": 110,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 0.3,
                    "perceived_exertion": None,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "hr_trimp")
        self.assertGreater(result["load_value"], 0.3)

    def test_compute_activity_load_uses_hr_trimp_for_running_before_vendor_load(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            def fake_fetch(*, metric_basis: str, **_: object):
                if metric_basis == "heart_rate":
                    return {"resting_hr": 50.0, "max_hr": 174.0}
                return None

            load_engine._fetch_anchor_profile = fake_fetch
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "running",
                    "duration_seconds": 3600,
                    "avg_hr": 150,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 2.8,
                    "perceived_exertion": None,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "hr_trimp")
        self.assertAlmostEqual(result["load_value"], 145.67, places=2)

    def test_fetch_anchor_profile_falls_back_to_nearest_profile_for_older_dates(self) -> None:
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        database.executescript(
            """
            CREATE TABLE zone_metric_profiles (
                zone_metric_profile_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                discipline TEXT NOT NULL,
                metric_basis TEXT NOT NULL,
                model_key TEXT,
                resting_hr REAL,
                max_hr REAL,
                ftp REAL,
                effective_start_date TEXT NOT NULL,
                effective_end_date TEXT
            );
            """
        )
        database.executemany(
            """
            INSERT INTO zone_metric_profiles (
                zone_metric_profile_id, season_id, discipline, metric_basis, model_key,
                resting_hr, max_hr, ftp, effective_start_date, effective_end_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 2026, "cycling", "heart_rate", "heart_rate_reserve_5_zone", 50, 183, None, "2026-06-01", "2026-06-01"),
                (2, 2026, "cycling", "heart_rate", "heart_rate_reserve_5_zone", 50, 174, None, "2026-06-02", None),
            ],
        )
        database.commit()

        class _ContextManager:
            def __enter__(self):
                return database

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("app.load_engine.get_connection", return_value=_ContextManager()):
            profile = load_engine._fetch_anchor_profile(
                season_id=2026,
                metric_basis="heart_rate",
                activity_date="2026-05-30",
            )

        self.assertIsNotNone(profile)
        self.assertEqual(profile["effective_start_date"], "2026-06-01")
        self.assertEqual(profile["max_hr"], 183)

    def test_compute_activity_load_uses_hr_trimp_for_hiking_before_vendor_load_when_profile_is_future_dated(self) -> None:
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        database.executescript(
            """
            CREATE TABLE zone_metric_profiles (
                zone_metric_profile_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                discipline TEXT NOT NULL,
                metric_basis TEXT NOT NULL,
                model_key TEXT,
                resting_hr REAL,
                max_hr REAL,
                ftp REAL,
                effective_start_date TEXT NOT NULL,
                effective_end_date TEXT
            );
            """
        )
        database.execute(
            """
            INSERT INTO zone_metric_profiles (
                zone_metric_profile_id, season_id, discipline, metric_basis, model_key,
                resting_hr, max_hr, ftp, effective_start_date, effective_end_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 2026, "cycling", "heart_rate", "heart_rate_reserve_5_zone", 50, 183, None, "2026-06-01", None),
        )
        database.commit()

        class _ContextManager:
            def __enter__(self):
                return database

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("app.load_engine.get_connection", return_value=_ContextManager()):
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-05-30",
                    "started_at": None,
                    "discipline": "hiking",
                    "duration_seconds": 4734,
                    "avg_hr": 119.1,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 2.7,
                    "perceived_exertion": None,
                },
                season_id=2026,
            )

        self.assertEqual(result["load_source"], "hr_trimp")
        self.assertAlmostEqual(result["load_value"], 71.14, places=2)

    def test_compute_activity_load_uses_hr_trimp_for_new_locomotion_discipline_labels(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            def fake_fetch(*, metric_basis: str, **_: object):
                if metric_basis == "heart_rate":
                    return {"resting_hr": 50.0, "max_hr": 174.0}
                return None

            load_engine._fetch_anchor_profile = fake_fetch
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "trail_running",
                    "activity_type": "Monte Trail Run",
                    "duration_seconds": 3600,
                    "avg_hr": 150,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 2.8,
                    "perceived_exertion": None,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "hr_trimp")
        self.assertAlmostEqual(result["load_value"], 145.67, places=2)

    def test_compute_activity_load_uses_hr_trimp_for_trail_walking(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            def fake_fetch(*, metric_basis: str, **_: object):
                if metric_basis == "heart_rate":
                    return {"resting_hr": 50.0, "max_hr": 174.0}
                return None

            load_engine._fetch_anchor_profile = fake_fetch
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "trail_walking",
                    "activity_type": "Trail Walking",
                    "duration_seconds": 3600,
                    "avg_hr": 135,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 1.5,
                    "perceived_exertion": None,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "hr_trimp")
        self.assertGreater(result["load_value"], 0)

    def test_load_model_snapshot_reports_tsb_from_same_day_atl_ctl(self) -> None:
        snapshot = load_engine.get_load_model_snapshot(2026, "2026-06-03")

        self.assertAlmostEqual(snapshot["tsb"], round(snapshot["ctl"] - snapshot["atl"], 2), places=2)
        self.assertTrue(snapshot["trend"])
        for entry in snapshot["trend"]:
            self.assertLess(abs(entry["tsb"] - round(entry["ctl"] - entry["atl"], 2)), 0.011)

    def test_compute_activity_load_uses_hr_trimp_when_activity_type_marks_new_walking_like_activity(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            def fake_fetch(*, metric_basis: str, **_: object):
                if metric_basis == "heart_rate":
                    return {"resting_hr": 50.0, "max_hr": 174.0}
                return None

            load_engine._fetch_anchor_profile = fake_fetch
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "outdoor_fitness",
                    "activity_type": "Nordic Walking",
                    "duration_seconds": 3600,
                    "avg_hr": 135,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 1.5,
                    "perceived_exertion": None,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "hr_trimp")
        self.assertGreater(result["load_value"], 0)

    def test_compute_activity_load_uses_respiration_rate_heuristic_when_hr_is_unavailable(self) -> None:
        original_fetch = load_engine._fetch_anchor_profile
        try:
            load_engine._fetch_anchor_profile = lambda **_: None
            result = load_engine.compute_activity_load(
                {
                    "activity_date": "2026-06-02",
                    "started_at": None,
                    "discipline": "road_biking",
                    "duration_seconds": 3600,
                    "avg_hr": None,
                    "avg_respiration_rate": 30.0,
                    "avg_power": None,
                    "normalized_power": None,
                    "training_load": 0,
                    "perceived_exertion": None,
                },
                season_id=2026,
            )
        finally:
            load_engine._fetch_anchor_profile = original_fetch

        self.assertEqual(result["load_source"], "respiration_rate_heuristic")
        self.assertGreater(result["load_value"], 0)

    def test_get_load_model_snapshot_combines_multiple_sport_rules(self) -> None:
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        database.executescript(
            """
            CREATE TABLE exec_activities (
                activity_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                activity_date TEXT NOT NULL,
                started_at TEXT,
                discipline TEXT,
                duration_seconds INTEGER,
                avg_hr REAL,
                avg_power REAL,
                normalized_power REAL,
                training_load REAL,
                perceived_exertion REAL
            );
            CREATE TABLE zone_metric_profiles (
                zone_metric_profile_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                discipline TEXT NOT NULL,
                metric_basis TEXT NOT NULL,
                model_key TEXT,
                resting_hr REAL,
                max_hr REAL,
                ftp REAL,
                effective_start_date TEXT NOT NULL,
                effective_end_date TEXT
            );
            """
        )
        database.executemany(
            """
            INSERT INTO zone_metric_profiles (
                zone_metric_profile_id, season_id, discipline, metric_basis, model_key,
                resting_hr, max_hr, ftp, effective_start_date, effective_end_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 2026, "cycling", "heart_rate", "heart_rate_reserve_5_zone", 50, 174, None, "2026-06-01", None),
                (2, 2026, "cycling", "power", "ftp_coggan_7_zone", None, None, 250, "2026-06-01", None),
            ],
        )
        database.executemany(
            """
            INSERT INTO exec_activities (
                activity_id, season_id, activity_date, started_at, discipline, duration_seconds,
                avg_hr, avg_power, normalized_power, training_load, perceived_exertion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 2026, "2026-06-01", None, "road_biking", 3600, 150, 190, 200, 50, None),
                (2, 2026, "2026-06-02", None, "running", 3600, 150, None, None, 2, None),
                (3, 2026, "2026-06-02", None, "strength_training", 3600, None, None, None, 1, 6),
            ],
        )
        database.commit()

        class _ContextManager:
            def __enter__(self):
                return database

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("app.load_engine.get_connection", return_value=_ContextManager()):
            snapshot = load_engine.get_load_model_snapshot(2026, "2026-06-02")

        self.assertAlmostEqual(snapshot["daily_training_load"], 146.67, places=2)
        self.assertAlmostEqual(snapshot["source_totals"]["power_tss"], 64.0, places=2)
        self.assertAlmostEqual(snapshot["source_totals"]["hr_trimp"], 145.67, places=2)
        self.assertAlmostEqual(snapshot["source_totals"]["garmin_training_load"], 1.0, places=2)
        self.assertEqual(len(snapshot["trend"]), 2)


if __name__ == "__main__":
    unittest.main()