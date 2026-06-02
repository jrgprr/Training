from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.activity_quality import RULE_SET_VERSION, get_activity_quality
from app.db import initialize_database
from app.imports.contracts import GarminImportBatch, GarminImportRequest, ImportFetchMetadata, NormalizedActivity, NormalizedMetricReading
from app.imports.garmin_connect import GarminConnectAdapter
from app.imports.storage import GarminImportStorage
from app.main import ActivityQualityReplayPayload, replay_activity_quality_endpoint


class ActivityQualityAdapterTests(unittest.TestCase):
    def test_fetch_activities_extracts_metric_readings_from_activity_detail_stream(self) -> None:
        adapter = GarminConnectAdapter()
        request = GarminImportRequest(
            season_id=2026,
            date_from="2026-05-05",
            date_to="2026-05-05",
            include_daily_metrics=False,
        )

        class FakeClient:
            def get_activities_by_date(self, date_from, date_to, sortorder="asc"):
                return [
                    {
                        "activityId": 123,
                        "startTimeLocal": "2026-05-05T08:00:00",
                        "activityName": "Salida larga",
                        "activityTypeDTO": {"typeKey": "road_biking"},
                        "summaryDTO": {"duration": 3600, "distance": 25000, "averageHR": 160, "maxHR": 242},
                    }
                ]

            def connectapi(self, path):
                if path == "/segment-service/segment/list/123":
                    return []
                if path == "/activity-service/activity/123/details":
                    return {
                        "metricDescriptors": [
                            {"metricsIndex": 0, "key": "directTimestamp"},
                            {"metricsIndex": 1, "key": "sumElapsedDuration"},
                            {"metricsIndex": 2, "key": "directHeartRate"},
                            {"metricsIndex": 3, "key": "directPower"},
                            {"metricsIndex": 4, "key": "directRespirationRate"},
                        ],
                        "activityDetailMetrics": [
                            {"metrics": [0, 0, 150, 210, 28.5]},
                            {"metrics": [1_000, 1, 242, 220, 31.0]},
                            {"metrics": [2_000, 2, 152, 215, 29.5]},
                        ],
                    }
                raise AssertionError(f"unexpected path: {path}")

            def get_activity_details(self, activity_id):
                return {}

            def download_activity(self, activity_id, _format):
                return b"fake-tcx"

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter.configuration.artifacts_path = temp_dir
            activities, artifact_paths, artifact_failures = adapter._fetch_activities(FakeClient(), request)

        self.assertEqual(len(activities), 1)
        self.assertEqual(len(artifact_paths), 1)
        self.assertEqual(artifact_failures, 0)

        heart_rate_readings = [reading for reading in activities[0].metric_readings if reading.metric_name == "heart_rate"]
        power_readings = [reading for reading in activities[0].metric_readings if reading.metric_name == "power"]
        respiration_readings = [reading for reading in activities[0].metric_readings if reading.metric_name == "respiration_rate"]
        self.assertEqual([reading.raw_value for reading in heart_rate_readings], [150.0, 242.0, 152.0])
        self.assertEqual([reading.sample_index for reading in power_readings], [0, 1, 2])
        self.assertEqual([reading.raw_value for reading in respiration_readings], [28.5, 31.0, 29.5])


class ActivityQualityStorageTests(unittest.TestCase):
    def test_persist_batch_filters_hr_spike_and_reuses_quality_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()

                batch = GarminImportBatch(
                    request=GarminImportRequest(
                        season_id=2026,
                        date_from="2026-05-05",
                        date_to="2026-05-05",
                        include_daily_metrics=False,
                    ),
                    metadata=ImportFetchMetadata(
                        source_system="garmin",
                        source_label="garminconnect",
                        date_from="2026-05-05",
                        date_to="2026-05-05",
                        notes=["quality batch"],
                    ),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="123",
                            activity_date="2026-05-05",
                            started_at="2026-05-05T08:00:00",
                            discipline="road_biking",
                            activity_type="Salida larga",
                            duration_seconds=3600,
                            distance_meters=25000,
                            ascent_meters=500,
                            calories=700,
                            avg_hr=181,
                            max_hr=242,
                            avg_power=250,
                            normalized_power=265,
                            training_load=90,
                            avg_pace_seconds_per_km=None,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=150),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=242),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=2, raw_value=152),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                first_summary = storage.persist_batch(batch)
                second_summary = storage.persist_batch(batch)

                self.assertEqual(first_summary.breakdown.quality_runs_created, 1)
                self.assertEqual(first_summary.breakdown.quality_decisions_recorded, 1)
                self.assertEqual(second_summary.breakdown.quality_runs_reused, 1)

                quality = get_activity_quality(1)
                assert quality is not None
                self.assertEqual(quality["activity"]["quality_status"], "filtered")
                self.assertEqual(quality["activity"]["quality_rule_version"], RULE_SET_VERSION)
                self.assertTrue(quality["activity"]["source_reading_fingerprint"])
                self.assertEqual(quality["metrics"][0]["excluded_reading_count"], 1)

                with storage_connection(database_path) as connection:
                    activity_row = connection.execute(
                        "SELECT avg_hr, max_hr, quality_status, quality_decision_count FROM exec_activities WHERE activity_id = 1"
                    ).fetchone()
                    run_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_quality_runs WHERE activity_id = 1"
                    ).fetchone()["total"]
                    decision_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_quality_decisions WHERE activity_id = 1"
                    ).fetchone()["total"]
                    reading_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_metric_readings WHERE activity_id = 1"
                    ).fetchone()["total"]

                self.assertEqual(activity_row["quality_status"], "filtered")
                self.assertEqual(activity_row["quality_decision_count"], 1)
                self.assertEqual(activity_row["avg_hr"], 151.0)
                self.assertEqual(activity_row["max_hr"], 152.0)
                self.assertEqual(run_count, 1)
                self.assertEqual(decision_count, 1)
                self.assertEqual(reading_count, 3)

    def test_replay_activity_quality_reuses_existing_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()

                batch = build_quality_batch()
                storage.persist_batch(batch)

                replay_result = storage.replay_activity_quality(1)

                self.assertIsNotNone(replay_result)
                assert replay_result is not None
                self.assertEqual(replay_result["result"], "reused_existing_run")
                self.assertEqual(replay_result["quality_status"], "filtered")

                with storage_connection(database_path) as connection:
                    run_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_quality_runs WHERE activity_id = 1"
                    ).fetchone()["total"]
                self.assertEqual(run_count, 1)

    def test_persist_batch_creates_passthrough_respiration_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()

                batch = build_quality_batch()
                batch.activities[0].metric_readings.extend(
                    [
                        NormalizedMetricReading(metric_name="respiration_rate", sample_index=0, raw_value=28.5),
                        NormalizedMetricReading(metric_name="respiration_rate", sample_index=1, raw_value=31.0),
                    ]
                )

                storage.persist_batch(batch)

                quality = get_activity_quality(1)
                assert quality is not None
                respiration_metric = next(metric for metric in quality["metrics"] if metric["metric_name"] == "respiration_rate")
                self.assertEqual(respiration_metric["metric_status"], "clean")
                self.assertEqual(respiration_metric["accepted_reading_count"], 2)
                self.assertEqual(
                    [impact["trusted_value"] for impact in respiration_metric["summary_impacts"]],
                    [29.75, 31.0],
                )

    def test_replay_endpoint_returns_conflict_when_canonical_readings_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                create_minimal_exec_tables(database_path)
                with storage_connection(database_path) as connection:
                    connection.execute(
                        """
                        INSERT INTO exec_activities (
                            season_id, source_system, external_activity_id, activity_date, started_at,
                            discipline, activity_type, duration_seconds, distance_meters, ascent_meters,
                            calories, avg_hr, max_hr, avg_power, normalized_power, training_load,
                            avg_pace_seconds_per_km, raw_payload_path, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            2026,
                            "garmin",
                            "123",
                            "2026-05-05",
                            "2026-05-05T08:00:00",
                            "road_biking",
                            "Salida larga",
                            3600,
                            25000,
                            500,
                            700,
                            180,
                            190,
                            250,
                            265,
                            90,
                            None,
                            None,
                            None,
                        ),
                    )
                    connection.commit()

                with self.assertRaises(Exception) as raised:
                    replay_activity_quality_endpoint(1, ActivityQualityReplayPayload())

                self.assertEqual(raised.exception.status_code, 409)

    def test_replay_activity_quality_backfills_from_tcx_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            artifact_path = Path(temp_dir) / "123.tcx"
            artifact_path.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2" xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
    <Activities>
        <Activity Sport="Biking">
            <Lap StartTime="2026-05-05T08:00:00Z">
                <Track>
                    <Trackpoint>
                        <Time>2026-05-05T08:00:00Z</Time>
                        <HeartRateBpm><Value>150</Value></HeartRateBpm>
                        <Cadence>82</Cadence>
                        <Extensions><ns3:TPX><ns3:Watts>210</ns3:Watts></ns3:TPX></Extensions>
                    </Trackpoint>
                    <Trackpoint>
                        <Time>2026-05-05T08:00:01Z</Time>
                        <HeartRateBpm><Value>242</Value></HeartRateBpm>
                        <Cadence>84</Cadence>
                        <Extensions><ns3:TPX><ns3:Watts>220</ns3:Watts></ns3:TPX></Extensions>
                    </Trackpoint>
                    <Trackpoint>
                        <Time>2026-05-05T08:00:02Z</Time>
                        <HeartRateBpm><Value>152</Value></HeartRateBpm>
                        <Cadence>83</Cadence>
                        <Extensions><ns3:TPX><ns3:Watts>215</ns3:Watts></ns3:TPX></Extensions>
                    </Trackpoint>
                </Track>
            </Lap>
        </Activity>
    </Activities>
</TrainingCenterDatabase>
""",
                encoding="utf-8",
            )
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                create_minimal_exec_tables(database_path)
                with storage_connection(database_path) as connection:
                    connection.execute(
                        """
                        INSERT INTO exec_activities (
                            season_id, source_system, external_activity_id, activity_date, started_at,
                            discipline, activity_type, duration_seconds, distance_meters, ascent_meters,
                            calories, avg_hr, max_hr, avg_power, normalized_power, training_load,
                            avg_pace_seconds_per_km, raw_payload_path, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            2026,
                            "garmin",
                            "123",
                            "2026-05-05",
                            "2026-05-05T08:00:00",
                            "road_biking",
                            "Salida larga",
                            3600,
                            25000,
                            500,
                            700,
                            181,
                            242,
                            250,
                            265,
                            90,
                            None,
                            str(artifact_path),
                            None,
                        ),
                    )
                    connection.commit()

                storage = GarminImportStorage()
                replay_result = storage.replay_activity_quality(1, source_mode="artifact")

                self.assertIsNotNone(replay_result)
                assert replay_result is not None
                self.assertEqual(replay_result["result"], "created_new_run")
                self.assertEqual(replay_result["quality_status"], "filtered")

                with storage_connection(database_path) as connection:
                    reading_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_metric_readings WHERE activity_id = 1"
                    ).fetchone()["total"]
                    activity_row = connection.execute(
                        "SELECT avg_hr, max_hr, quality_status FROM exec_activities WHERE activity_id = 1"
                    ).fetchone()

                self.assertEqual(reading_count, 9)
                self.assertEqual(activity_row["avg_hr"], 151.0)
                self.assertEqual(activity_row["max_hr"], 152.0)
                self.assertEqual(activity_row["quality_status"], "filtered")

    def test_persist_batch_marks_quality_limited_when_all_hr_samples_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()

                batch = GarminImportBatch(
                    request=GarminImportRequest(
                        season_id=2026,
                        date_from="2026-05-06",
                        date_to="2026-05-06",
                        include_daily_metrics=False,
                    ),
                    metadata=ImportFetchMetadata(
                        source_system="garmin",
                        source_label="garminconnect",
                        date_from="2026-05-06",
                        date_to="2026-05-06",
                        notes=["quality limited batch"],
                    ),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="456",
                            activity_date="2026-05-06",
                            started_at="2026-05-06T08:00:00",
                            discipline="road_biking",
                            activity_type="Salida corta",
                            duration_seconds=1800,
                            distance_meters=12000,
                            ascent_meters=200,
                            calories=350,
                            avg_hr=242,
                            max_hr=245,
                            avg_power=220,
                            normalized_power=230,
                            training_load=45,
                            avg_pace_seconds_per_km=None,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=242),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=245),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                summary = storage.persist_batch(batch)

                self.assertEqual(summary.breakdown.quality_limited_metrics, 1)
                quality = get_activity_quality(1)
                assert quality is not None
                self.assertEqual(quality["activity"]["quality_status"], "limited")
                self.assertEqual(quality["metrics"][0]["metric_status"], "quality_limited")
                self.assertEqual(quality["metrics"][0]["accepted_reading_count"], 0)
                self.assertEqual(quality["metrics"][0]["excluded_reading_count"], 2)
                self.assertEqual(quality["metrics"][0]["summary_impacts"][0]["trusted_value"], None)
                self.assertEqual(quality["metrics"][0]["summary_impacts"][1]["trusted_value"], None)

                with storage_connection(database_path) as connection:
                    activity_row = connection.execute(
                        """
                        SELECT avg_hr, max_hr, quality_status, quality_limited_metric_count
                        FROM exec_activities
                        WHERE activity_id = 1
                        """
                    ).fetchone()

                self.assertEqual(activity_row["avg_hr"], None)
                self.assertEqual(activity_row["max_hr"], None)
                self.assertEqual(activity_row["quality_status"], "limited")
                self.assertEqual(activity_row["quality_limited_metric_count"], 1)


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


def build_quality_batch() -> GarminImportBatch:
    return GarminImportBatch(
        request=GarminImportRequest(
            season_id=2026,
            date_from="2026-05-05",
            date_to="2026-05-05",
            include_daily_metrics=False,
        ),
        metadata=ImportFetchMetadata(
            source_system="garmin",
            source_label="garminconnect",
            date_from="2026-05-05",
            date_to="2026-05-05",
            notes=["quality batch"],
        ),
        activities=[
            NormalizedActivity(
                external_activity_id="123",
                activity_date="2026-05-05",
                started_at="2026-05-05T08:00:00",
                discipline="road_biking",
                activity_type="Salida larga",
                duration_seconds=3600,
                distance_meters=25000,
                ascent_meters=500,
                calories=700,
                avg_hr=181,
                max_hr=242,
                avg_power=250,
                normalized_power=265,
                training_load=90,
                avg_pace_seconds_per_km=None,
                metric_readings=[
                    NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=150),
                    NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=242),
                    NormalizedMetricReading(metric_name="heart_rate", sample_index=2, raw_value=152),
                ],
            )
        ],
        daily_metrics=[],
    )


def storage_connection(database_path: Path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return closing(connection)


if __name__ == "__main__":
    unittest.main()