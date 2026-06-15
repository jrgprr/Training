from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database
from app.elevation_enrichment import apply_activity_elevation_enrichment, load_corrected_altitudes
from app.imports.storage import GarminImportStorage


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
            CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                daily_metric_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                metric_date TEXT NOT NULL,
                source_system TEXT NOT NULL,
                UNIQUE (season_id, metric_date, source_system)
            );
            """
        )


class ElevationEnrichmentTests(unittest.TestCase):
    def test_backfill_route_points_from_tcx_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            artifact_path = Path(temp_dir) / "123.tcx"
            artifact_path.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
    <Activities>
        <Activity Sport="Other">
            <Lap StartTime="2026-05-05T08:00:00Z">
                <Track>
                    <Trackpoint><Time>2026-05-05T08:00:00Z</Time><Position><LatitudeDegrees>43.12</LatitudeDegrees><LongitudeDegrees>-2.58</LongitudeDegrees></Position><AltitudeMeters>180.0</AltitudeMeters><DistanceMeters>0.0</DistanceMeters></Trackpoint>
                    <Trackpoint><Time>2026-05-05T08:00:02Z</Time><Position><LatitudeDegrees>43.121</LatitudeDegrees><LongitudeDegrees>-2.579</LongitudeDegrees></Position><AltitudeMeters>181.5</AltitudeMeters><DistanceMeters>10.0</DistanceMeters></Trackpoint>
                </Track>
            </Lap>
        </Activity>
    </Activities>
</TrainingCenterDatabase>
""",
                encoding="utf-8",
            )
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                create_minimal_exec_tables(database_path)
                with storage_connection(database_path) as connection:
                    connection.execute(
                        """
                        INSERT INTO exec_activities (season_id, source_system, external_activity_id, activity_date, raw_payload_path)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (2026, "garmin", "123", "2026-05-05", str(artifact_path)),
                    )
                    connection.commit()

                result = GarminImportStorage().backfill_route_points_batch(activity_id=1)

                self.assertEqual(result["backfilled_count"], 1)
                with storage_connection(database_path) as connection:
                    route_point_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_route_points WHERE activity_id = 1"
                    ).fetchone()["total"]
                self.assertEqual(route_point_count, 2)

    def test_apply_smoothed_elevation_enrichment_persists_corrected_points(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                create_minimal_exec_tables(database_path)
                with storage_connection(database_path) as connection:
                    connection.execute(
                        "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date) VALUES (?, ?, ?, ?, ?)",
                        (1, 2026, "garmin", "123", "2026-05-05"),
                    )
                    connection.executemany(
                        """
                        INSERT INTO exec_activity_route_points (
                            activity_id, point_index, latitude_degrees, longitude_degrees, altitude_meters, distance_meters, elapsed_seconds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (1, 0, 43.12, -2.58, 180.0, 0.0, 0.0),
                            (1, 1, 43.121, -2.579, 184.0, 10.0, 2.0),
                            (1, 2, 43.122, -2.578, 182.0, 20.0, 4.0),
                        ],
                    )
                    connection.commit()

                result = apply_activity_elevation_enrichment(1, provider_config={"window_size": 3})
                corrected = load_corrected_altitudes(1)

                self.assertEqual(result["status"], "created_new_run")
                self.assertEqual(result["provider_key"], "smoothed_altitude")
                self.assertEqual(len(corrected), 3)
                self.assertEqual(corrected[1]["correction_status"], "smoothed")
                self.assertAlmostEqual(corrected[1]["corrected_altitude_meters"], 182.0, places=1)


if __name__ == "__main__":
    unittest.main()
