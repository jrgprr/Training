from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.activity_weather import enrich_activity_weather, get_activity_weather, select_weather_sample_points
from app.db import initialize_database
from app.imports.contracts import NormalizedRoutePoint


def storage_connection(database_path: Path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return closing(connection)


def create_minimal_exec_tables(database_path: Path) -> None:
    with storage_connection(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS exec_activities (
                activity_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                source_system TEXT NOT NULL,
                external_activity_id TEXT,
                activity_date TEXT NOT NULL,
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
                training_load REAL,
                avg_pace_seconds_per_km REAL,
                raw_payload_path TEXT,
                notes TEXT,
                UNIQUE (source_system, external_activity_id)
            );
            """
        )


class ActivityWeatherTests(unittest.TestCase):
    def test_select_weather_sample_points_uses_15min_or_5km(self) -> None:
        points = [
            NormalizedRoutePoint(point_index=0, latitude_degrees=43.1, longitude_degrees=-2.5, distance_meters=0.0, elapsed_seconds=0.0),
            NormalizedRoutePoint(point_index=1, latitude_degrees=43.1, longitude_degrees=-2.5, distance_meters=2000.0, elapsed_seconds=600.0),
            NormalizedRoutePoint(point_index=2, latitude_degrees=43.1, longitude_degrees=-2.5, distance_meters=5200.0, elapsed_seconds=840.0),
            NormalizedRoutePoint(point_index=3, latitude_degrees=43.1, longitude_degrees=-2.5, distance_meters=7000.0, elapsed_seconds=1800.0),
        ]

        selected = select_weather_sample_points(points)

        self.assertEqual([point.point_index for point in selected], [0, 2, 3])

    def test_enrich_activity_weather_persists_summary_and_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            fake_payload = {
                "timezone": "Europe/Madrid",
                "elevation": 123.0,
                "hourly": {
                    "time": ["2026-06-14T10:00", "2026-06-14T11:00", "2026-06-14T12:00"],
                    "temperature_2m": [16.0, 18.0, 21.0],
                    "apparent_temperature": [15.0, 17.0, 20.0],
                    "precipitation": [0.0, 0.2, 0.0],
                    "rain": [0.0, 0.2, 0.0],
                    "snowfall": [0.0, 0.0, 0.0],
                    "weather_code": [1, 3, 3],
                    "cloud_cover": [10.0, 40.0, 55.0],
                    "wind_speed_10m": [5.0, 10.0, 14.0],
                    "wind_gusts_10m": [7.0, 14.0, 20.0],
                    "wind_direction_10m": [80.0, 100.0, 120.0],
                    "shortwave_radiation": [100.0, 250.0, 400.0],
                },
            }

            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                create_minimal_exec_tables(database_path)
                with storage_connection(database_path) as connection:
                    connection.execute(
                        "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (1, 2026, "garmin", "123", "2026-06-14", "2026-06-14 10:05:00"),
                    )
                    connection.executemany(
                        """
                        INSERT INTO exec_activity_route_points (
                            activity_id, point_index, latitude_degrees, longitude_degrees, distance_meters, elapsed_seconds, recorded_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (1, 0, 43.1, -2.5, 0.0, 0.0, "2026-06-14T10:05:00"),
                            (1, 1, 43.2, -2.4, 5100.0, 840.0, "2026-06-14T10:19:00"),
                            (1, 2, 43.3, -2.3, 9000.0, 1900.0, "2026-06-14T10:36:40"),
                        ],
                    )
                    connection.commit()

                with patch("app.activity_weather._fetch_open_meteo_hourly", return_value=fake_payload):
                    result = enrich_activity_weather(1)
                    weather = get_activity_weather(1)

                self.assertEqual(result["status"], "created_new_run")
                self.assertIsNotNone(weather)
                assert weather is not None
                self.assertEqual(weather["summary"]["sample_count"], 3)
                self.assertAlmostEqual(weather["summary"]["temperature_mean"], 16.6666666667, places=2)
                self.assertEqual(len(weather["samples"]), 3)
                self.assertEqual(weather["samples"][0]["weather_code"], 1)

    def test_enrich_activity_weather_matches_utc_route_points_with_utc_weather_hours(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            fake_payload = {
                "timezone": "GMT",
                "elevation": 123.0,
                "hourly": {
                    "time": ["2026-06-22T18:00", "2026-06-22T19:00", "2026-06-22T20:00"],
                    "temperature_2m": [24.0, 21.0, 19.0],
                    "apparent_temperature": [25.0, 22.0, 20.0],
                    "precipitation": [0.0, 0.0, 0.0],
                    "rain": [0.0, 0.0, 0.0],
                    "snowfall": [0.0, 0.0, 0.0],
                    "weather_code": [1, 2, 3],
                    "cloud_cover": [10.0, 20.0, 30.0],
                    "wind_speed_10m": [5.0, 6.0, 7.0],
                    "wind_gusts_10m": [8.0, 9.0, 10.0],
                    "wind_direction_10m": [80.0, 90.0, 100.0],
                    "shortwave_radiation": [500.0, 300.0, 100.0],
                },
            }

            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                create_minimal_exec_tables(database_path)
                with storage_connection(database_path) as connection:
                    connection.execute(
                        "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (1, 2026, "garmin", "123", "2026-06-22", "2026-06-22 20:06:29"),
                    )
                    connection.executemany(
                        """
                        INSERT INTO exec_activity_route_points (
                            activity_id, point_index, latitude_degrees, longitude_degrees, distance_meters, elapsed_seconds, recorded_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (1, 0, 43.1, -2.5, 0.0, 0.0, "2026-06-22T18:06:29+00:00"),
                            (1, 1, 43.2, -2.4, 5100.0, 840.0, "2026-06-22T18:20:01+00:00"),
                            (1, 2, 43.3, -2.3, 9000.0, 1900.0, "2026-06-22T18:36:40+00:00"),
                        ],
                    )
                    connection.commit()

                with patch("app.activity_weather._fetch_open_meteo_hourly", return_value=fake_payload):
                    weather = get_activity_weather(1)
                    self.assertIsNone(weather)
                    enrich_activity_weather(1)
                    weather = get_activity_weather(1)

                assert weather is not None
                self.assertEqual(weather["samples"][0]["sampled_at"], "2026-06-22T18:06:29+00:00")
                self.assertEqual(weather["samples"][0]["weather_hour"], "2026-06-22T18:00")
                self.assertEqual(weather["samples"][0]["weather_code"], 1)
                self.assertEqual(weather["samples"][1]["weather_hour"], "2026-06-22T18:00")
                self.assertEqual(weather["samples"][2]["weather_hour"], "2026-06-22T19:00")


if __name__ == "__main__":
    unittest.main()