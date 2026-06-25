from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.activity_quality import (
    RULE_SET_VERSION,
    get_activity_quality,
    normalize_metric_readings_from_activity_detail,
    normalize_route_points_from_activity_detail,
)
from app.db import initialize_database
from app.imports.contracts import GarminImportBatch, GarminImportRequest, ImportFetchMetadata, NormalizedActivity, NormalizedMetricReading, NormalizedRoutePoint
from app.imports.garmin_connect import GarminConnectAdapter
from app.imports.storage import GarminImportStorage
from app.main import ActivityQualityReplayPayload, get_activity_running_dynamics_history_endpoint, replay_activity_quality_endpoint


class ActivityQualityAdapterTests(unittest.TestCase):
    def test_normalize_activity_detail_extracts_route_points(self) -> None:
        route_points = normalize_route_points_from_activity_detail(
            {
                "metricDescriptors": [
                    {"metricsIndex": 0, "key": "directTimestamp"},
                    {"metricsIndex": 1, "key": "sumElapsedDuration"},
                    {"metricsIndex": 2, "key": "directLatitude"},
                    {"metricsIndex": 3, "key": "directLongitude"},
                    {"metricsIndex": 4, "key": "directElevation"},
                    {"metricsIndex": 5, "key": "sumDistance"},
                ],
                "activityDetailMetrics": [
                    {"metrics": [0, 0, 43.12, -2.58, 180.2, 0.0]},
                    {"metrics": [1_000, 1, 43.13, -2.57, 181.4, 12.5]},
                ],
            }
        )

        self.assertEqual(len(route_points), 2)
        self.assertEqual(route_points[0].point_index, 0)
        self.assertAlmostEqual(route_points[1].latitude_degrees, 43.13, places=2)
        self.assertAlmostEqual(route_points[1].distance_meters or 0.0, 12.5, places=2)

    def test_normalize_activity_detail_converts_stride_length_to_meters(self) -> None:
        readings = normalize_metric_readings_from_activity_detail(
            {
                "metricDescriptors": [
                    {"metricsIndex": 0, "key": "directTimestamp"},
                    {"metricsIndex": 1, "key": "sumElapsedDuration"},
                    {"metricsIndex": 2, "key": "directStrideLength"},
                ],
                "activityDetailMetrics": [
                    {"metrics": [0, 0, 112]},
                ],
            }
        )

        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].metric_name, "stride_length")
        self.assertAlmostEqual(readings[0].raw_value, 1.12, places=2)

    def test_fetch_activities_extracts_running_dynamics_metric_readings(self) -> None:
        adapter = GarminConnectAdapter()
        request = GarminImportRequest(
            season_id=2026,
            date_from="2026-05-30",
            date_to="2026-05-30",
            include_daily_metrics=False,
        )

        class FakeClient:
            def get_activities_by_date(self, date_from, date_to, sortorder="asc"):
                return [
                    {
                        "activityId": 23065909925,
                        "startTimeLocal": "2026-05-30T08:00:00",
                        "activityName": "Elorrio Carrera",
                        "activityTypeDTO": {"typeKey": "running"},
                        "summaryDTO": {"duration": 3600, "distance": 10000, "averageHR": 150, "maxHR": 165},
                    }
                ]

            def connectapi(self, path):
                if path == "/segment-service/segment/list/23065909925":
                    return []
                if path == "/activity-service/activity/23065909925/details":
                    return {
                        "metricDescriptors": [
                            {"metricsIndex": 0, "key": "directTimestamp"},
                            {"metricsIndex": 1, "key": "sumElapsedDuration"},
                            {"metricsIndex": 2, "key": "directHeartRate"},
                            {"metricsIndex": 3, "key": "directRunCadence"},
                            {"metricsIndex": 4, "key": "directDoubleCadence"},
                            {"metricsIndex": 5, "key": "directFractionalCadence"},
                            {"metricsIndex": 6, "key": "directVerticalRatio"},
                            {"metricsIndex": 7, "key": "directGroundContactTime"},
                            {"metricsIndex": 8, "key": "directGroundContactBalanceLeft"},
                            {"metricsIndex": 9, "key": "directVerticalOscillation"},
                            {"metricsIndex": 10, "key": "directStrideLength"},
                            {"metricsIndex": 11, "key": "directPerformanceCondition"},
                            {"metricsIndex": 12, "key": "directLatitude"},
                            {"metricsIndex": 13, "key": "directLongitude"},
                            {"metricsIndex": 14, "key": "directElevation"},
                            {"metricsIndex": 15, "key": "sumDistance"},
                        ],
                        "activityDetailMetrics": [
                            {"metrics": [0, 0, 145, 86, 172, 0.3, 6.8, 248, 49.7, 8.7, 1.12, -2, 43.12, -2.58, 180.0, 0.0]},
                            {"metrics": [1_000, 1, 147, 87, 174, 0.5, 6.9, 246, 50.1, 8.8, 1.14, -1, 43.13, -2.57, 181.0, 12.5]},
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

        metric_names = {reading.metric_name for reading in activities[0].metric_readings}
        self.assertTrue(
            {
                "heart_rate",
                "run_cadence",
                "cadence_double",
                "cadence_fractional",
                "vertical_ratio",
                "ground_contact_time",
                "ground_contact_balance_left",
                "vertical_oscillation",
                "stride_length",
                "performance_condition",
            }.issubset(metric_names)
        )
        self.assertEqual(len(activities[0].route_points), 2)
        self.assertAlmostEqual(activities[0].route_points[0].latitude_degrees, 43.12, places=2)

    def test_normalize_activity_derives_pace_for_trail_walking(self) -> None:
        adapter = GarminConnectAdapter()

        activity = adapter._normalize_activity(
            {
                "activityId": 456,
                "startTimeLocal": "2026-05-06T08:00:00",
                "activityName": "Trail Walking",
                "activityTypeDTO": {"typeKey": "trail_walking"},
                "summaryDTO": {
                    "duration": 3600,
                    "distance": 6500,
                    "averageSpeed": 1.8,
                    "averageHR": 118,
                    "maxHR": 132,
                },
            }
        )

        self.assertEqual(activity.discipline, "trail_walking")
        self.assertAlmostEqual(activity.avg_pace_seconds_per_km, 555.56, places=2)

    def test_fetch_daily_metrics_includes_step_aggregates(self) -> None:
        adapter = GarminConnectAdapter()
        request = GarminImportRequest(
            season_id=2026,
            date_from="2026-05-30",
            date_to="2026-05-30",
            include_daily_metrics=True,
        )

        class FakeClient:
            def get_user_profile(self):
                return {"userData": {"vo2MaxCycling": 52}}

            def get_daily_steps(self, date_from, date_to):
                return [{
                    "calendarDate": "2026-05-30",
                    "totalSteps": 14321,
                    "totalDistance": 11234,
                    "stepGoal": 10000,
                }]

            def get_stats(self, cdate):
                return {"calendarDate": cdate}

            def get_sleep_data(self, cdate):
                return {"dailySleepDTO": {"sleepTimeSeconds": 28800}}

            def get_heart_rates(self, cdate):
                return {"restingHeartRate": 48}

            def get_hrv_data(self, cdate):
                return None

            def get_body_battery(self, startdate, enddate):
                return []

            def get_all_day_stress(self, cdate):
                return {}

            def get_spo2_data(self, cdate):
                return {}

            def get_body_composition(self, startdate, enddate=None):
                return {}

        metrics = adapter._fetch_daily_metrics(FakeClient(), request)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].total_steps, 14321)
        self.assertEqual(metrics[0].total_distance_m, 11234.0)
        self.assertEqual(metrics[0].step_goal, 10000)
        self.assertEqual(metrics[0].resting_hr, 48.0)

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

            def get_activity(self, activity_id):
                return {
                    "activityId": int(activity_id),
                    "metadataDTO": {
                        "sensors": [
                            {
                                "manufacturer": "GARMIN",
                                "sku": "006-B2787-00",
                                "serialNumber": 3996467079,
                                "fitProductNumber": 2787,
                                "sourceType": "ANTPLUS",
                                "antplusDeviceType": "BIKE_POWER",
                            }
                        ]
                    },
                    "summaryDTO": {
                        "leftPowerPhaseStart": 14.0,
                    },
                }

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
        self.assertEqual(activities[0].power_sensor_profile, "pedal_power_meter")
        self.assertEqual(activities[0].power_sensor_manufacturer, "GARMIN")
        self.assertIn("006-B2787-00", activities[0].power_sensor_label or "")
        self.assertIn('"fitProductNumber": 2787', activities[0].power_sensor_metadata_json or "")

        heart_rate_readings = [reading for reading in activities[0].metric_readings if reading.metric_name == "heart_rate"]
        power_readings = [reading for reading in activities[0].metric_readings if reading.metric_name == "power"]
        respiration_readings = [reading for reading in activities[0].metric_readings if reading.metric_name == "respiration_rate"]
        self.assertEqual([reading.raw_value for reading in heart_rate_readings], [150.0, 242.0, 152.0])
        self.assertEqual([reading.sample_index for reading in power_readings], [0, 1, 2])
        self.assertEqual([reading.raw_value for reading in respiration_readings], [28.5, 31.0, 29.5])


class ActivityQualityStorageTests(unittest.TestCase):
    def test_running_dynamics_history_endpoint_returns_normalized_baseline(self) -> None:
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
                            activity_id, season_id, source_system, external_activity_id, activity_date, started_at,
                            discipline, activity_type, duration_seconds, avg_hr, avg_pace_seconds_per_km
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (1, 2026, "garmin", "a1", "2026-05-30", "2026-05-30T08:00:00", "running", "Run A", 3600, 145, 360),
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_activities (
                            activity_id, season_id, source_system, external_activity_id, activity_date, started_at,
                            discipline, activity_type, duration_seconds, avg_hr, avg_pace_seconds_per_km
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (2, 2026, "garmin", "a2", "2026-05-29", "2026-05-29T08:00:00", "running", "Run B", 3500, 142, 370),
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_activity_quality_runs (
                            quality_run_id, activity_id, rule_set_key, rule_set_version, source_reading_fingerprint,
                            evaluated_metric_names, skipped_metric_names, evaluated_reading_count, excluded_reading_count,
                            limited_metric_count, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (1, 2, "bad_reading_filter", RULE_SET_VERSION, "fingerprint-2", "[]", "[]", 10, 0, 0, "clean"),
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_activity_metric_summaries (
                            activity_id, quality_run_id, metric_name, summary_kind, source_value, trusted_value, summary_status,
                            evaluated_reading_count, accepted_reading_count, excluded_reading_count, changed_by_filter
                        ) VALUES (?, ?, ?, 'average', ?, ?, 'clean', 10, 10, 0, 0)
                        """,
                        (2, 1, "stride_length", 104.0, 104.0),
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_activity_metric_summaries (
                            activity_id, quality_run_id, metric_name, summary_kind, source_value, trusted_value, summary_status,
                            evaluated_reading_count, accepted_reading_count, excluded_reading_count, changed_by_filter
                        ) VALUES (?, ?, ?, 'average', ?, ?, 'clean', 10, 10, 0, 0)
                        """,
                        (2, 1, "ground_contact_time", 278.0, 278.0),
                    )
                    connection.commit()

                payload = get_activity_running_dynamics_history_endpoint(1, limit=5)

                self.assertEqual(payload["compared_activity_count"], 1)
                self.assertAlmostEqual(payload["baseline_metrics"]["stride_length"], 1.04, places=2)
                self.assertAlmostEqual(payload["history"][0]["metrics"]["stride_length"], 1.04, places=2)

    def test_persist_batch_stores_running_dynamics_metric_names(self) -> None:
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
                        date_from="2026-05-30",
                        date_to="2026-05-30",
                        include_daily_metrics=False,
                    ),
                    metadata=ImportFetchMetadata(
                        source_system="garmin",
                        source_label="garminconnect",
                        date_from="2026-05-30",
                        date_to="2026-05-30",
                        notes=["running dynamics batch"],
                    ),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="23065909925",
                            activity_date="2026-05-30",
                            started_at="2026-05-30T08:00:00",
                            discipline="running",
                            activity_type="Elorrio Carrera",
                            duration_seconds=3600,
                            distance_meters=10000,
                            ascent_meters=120,
                            calories=650,
                            avg_hr=150,
                            max_hr=165,
                            avg_power=None,
                            normalized_power=None,
                            training_load=60,
                            avg_pace_seconds_per_km=330,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="run_cadence", sample_index=0, raw_value=86),
                                NormalizedMetricReading(metric_name="cadence_double", sample_index=0, raw_value=172),
                                NormalizedMetricReading(metric_name="cadence_fractional", sample_index=0, raw_value=0.3),
                                NormalizedMetricReading(metric_name="vertical_ratio", sample_index=0, raw_value=6.8),
                                NormalizedMetricReading(metric_name="ground_contact_time", sample_index=0, raw_value=248),
                                NormalizedMetricReading(metric_name="ground_contact_balance_left", sample_index=0, raw_value=49.7),
                                NormalizedMetricReading(metric_name="vertical_oscillation", sample_index=0, raw_value=8.7),
                                NormalizedMetricReading(metric_name="stride_length", sample_index=0, raw_value=1.12),
                                NormalizedMetricReading(metric_name="performance_condition", sample_index=0, raw_value=-2),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                storage.persist_batch(batch)

                with storage_connection(database_path) as connection:
                    metric_names = {
                        row["metric_name"]
                        for row in connection.execute(
                            "SELECT DISTINCT metric_name FROM exec_activity_metric_readings WHERE activity_id = 1"
                        ).fetchall()
                    }

                self.assertTrue(
                    {
                        "run_cadence",
                        "cadence_double",
                        "cadence_fractional",
                        "vertical_ratio",
                        "ground_contact_time",
                        "ground_contact_balance_left",
                        "vertical_oscillation",
                        "stride_length",
                        "performance_condition",
                    }.issubset(metric_names)
                )

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
                        <Position><LatitudeDegrees>43.12</LatitudeDegrees><LongitudeDegrees>-2.58</LongitudeDegrees></Position>
                        <AltitudeMeters>180.0</AltitudeMeters>
                        <DistanceMeters>0.0</DistanceMeters>
                        <HeartRateBpm><Value>150</Value></HeartRateBpm>
                        <Cadence>82</Cadence>
                        <Extensions><ns3:TPX><ns3:Watts>210</ns3:Watts></ns3:TPX></Extensions>
                    </Trackpoint>
                    <Trackpoint>
                        <Time>2026-05-05T08:00:01Z</Time>
                        <Position><LatitudeDegrees>43.1205</LatitudeDegrees><LongitudeDegrees>-2.5795</LongitudeDegrees></Position>
                        <AltitudeMeters>181.0</AltitudeMeters>
                        <DistanceMeters>5.0</DistanceMeters>
                        <HeartRateBpm><Value>242</Value></HeartRateBpm>
                        <Cadence>84</Cadence>
                        <Extensions><ns3:TPX><ns3:Watts>220</ns3:Watts></ns3:TPX></Extensions>
                    </Trackpoint>
                    <Trackpoint>
                        <Time>2026-05-05T08:00:02Z</Time>
                        <Position><LatitudeDegrees>43.121</LatitudeDegrees><LongitudeDegrees>-2.579</LongitudeDegrees></Position>
                        <AltitudeMeters>182.0</AltitudeMeters>
                        <DistanceMeters>10.0</DistanceMeters>
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
                    route_point_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_route_points WHERE activity_id = 1"
                    ).fetchone()["total"]
                    first_route_point = connection.execute(
                        "SELECT latitude_degrees, longitude_degrees, altitude_meters, distance_meters FROM exec_activity_route_points WHERE activity_id = 1 ORDER BY point_index LIMIT 1"
                    ).fetchone()
                    activity_row = connection.execute(
                        "SELECT avg_hr, max_hr, quality_status FROM exec_activities WHERE activity_id = 1"
                    ).fetchone()

                self.assertEqual(reading_count, 9)
                self.assertEqual(route_point_count, 3)
                self.assertAlmostEqual(first_route_point["latitude_degrees"], 43.12, places=2)
                self.assertEqual(activity_row["avg_hr"], 151.0)
                self.assertEqual(activity_row["max_hr"], 152.0)
                self.assertEqual(activity_row["quality_status"], "filtered")

    def test_persist_batch_stores_route_points(self) -> None:
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
                    ),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="route-1",
                            activity_date="2026-05-06",
                            started_at="2026-05-06T08:00:00",
                            discipline="walking",
                            activity_type="Walk",
                            duration_seconds=1200,
                            distance_meters=1500,
                            ascent_meters=40,
                            calories=100,
                            avg_hr=110,
                            max_hr=120,
                            avg_power=None,
                            normalized_power=None,
                            training_load=10,
                            avg_pace_seconds_per_km=700,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=108),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=112),
                            ],
                            route_points=[
                                NormalizedRoutePoint(point_index=0, latitude_degrees=43.12, longitude_degrees=-2.58, altitude_meters=180.0, distance_meters=0.0),
                                NormalizedRoutePoint(point_index=1, latitude_degrees=43.121, longitude_degrees=-2.579, altitude_meters=181.0, distance_meters=12.0),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                storage.persist_batch(batch)

                with storage_connection(database_path) as connection:
                    route_point_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_route_points WHERE activity_id = 1"
                    ).fetchone()["total"]

                self.assertEqual(route_point_count, 2)

    def test_persist_batch_stores_power_sensor_metadata(self) -> None:
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
                        date_from="2026-06-25",
                        date_to="2026-06-25",
                        include_daily_metrics=False,
                    ),
                    metadata=ImportFetchMetadata(
                        source_system="garmin",
                        source_label="garminconnect",
                        date_from="2026-06-25",
                        date_to="2026-06-25",
                    ),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="sensor-1",
                            activity_date="2026-06-25",
                            started_at="2026-06-25T08:00:00",
                            discipline="road_biking",
                            activity_type="Recovery ride",
                            duration_seconds=1800,
                            distance_meters=12000,
                            ascent_meters=180,
                            calories=320,
                            avg_hr=120,
                            max_hr=140,
                            avg_power=132,
                            normalized_power=145,
                            training_load=32,
                            avg_pace_seconds_per_km=None,
                            power_sensor_profile="pedal_power_meter",
                            power_sensor_manufacturer="GARMIN",
                            power_sensor_label="GARMIN 006-B2787-00 fit:2787 serial:3996467079",
                            power_sensor_metadata_json='{"antplusDeviceType":"BIKE_POWER","fitProductNumber":2787,"manufacturer":"GARMIN"}',
                        )
                    ],
                    daily_metrics=[],
                )

                storage.persist_batch(batch)

                with storage_connection(database_path) as connection:
                    activity_row = connection.execute(
                        "SELECT power_sensor_profile, power_sensor_manufacturer, power_sensor_label, power_sensor_metadata_json FROM exec_activities WHERE activity_id = 1"
                    ).fetchone()

                self.assertEqual(activity_row["power_sensor_profile"], "pedal_power_meter")
                self.assertEqual(activity_row["power_sensor_manufacturer"], "GARMIN")
                self.assertIn("006-B2787-00", activity_row["power_sensor_label"])
                self.assertIn('"fitProductNumber":2787', activity_row["power_sensor_metadata_json"])

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