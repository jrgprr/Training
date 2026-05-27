from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database
from app.imports.contracts import (
    GarminImportBatch,
    GarminImportRequest,
    ImportFetchMetadata,
    NormalizedActivity,
    NormalizedSegmentDefinition,
    NormalizedSegmentEffort,
)
from app.imports.garmin_connect import GarminConnectAdapter
from app.imports.storage import GarminImportStorage
from app.main import get_segment_history_endpoint, get_segments
from app.segments import get_segment_history, list_segments


class GarminSegmentStorageTests(unittest.TestCase):
    def test_persist_batch_stores_segments_and_updates_import_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()
                batch = build_batch()

                summary = storage.persist_batch(batch)

                self.assertEqual(summary.status, "completed")
                self.assertEqual(summary.breakdown.activity_rows_inserted, 1)
                self.assertEqual(summary.breakdown.segment_activities_checked, 1)
                self.assertEqual(summary.breakdown.segment_activities_with_data, 1)
                self.assertEqual(summary.breakdown.segment_efforts_detected, 2)
                self.assertEqual(summary.breakdown.segment_efforts_inserted, 2)
                self.assertEqual(summary.breakdown.segment_efforts_updated, 0)

                second_summary = storage.persist_batch(batch)
                self.assertEqual(second_summary.breakdown.activity_rows_updated, 1)
                self.assertEqual(second_summary.breakdown.segment_efforts_inserted, 0)
                self.assertEqual(second_summary.breakdown.segment_efforts_updated, 2)

                filtered_summary = storage.persist_batch(build_filtered_batch())
                self.assertEqual(filtered_summary.breakdown.activity_rows_updated, 1)
                self.assertEqual(filtered_summary.breakdown.segment_efforts_detected, 1)
                self.assertEqual(filtered_summary.breakdown.segment_efforts_inserted, 0)
                self.assertEqual(filtered_summary.breakdown.segment_efforts_updated, 1)

                with storage_module_connection(database_path) as connection:
                    activity = connection.execute(
                        "SELECT segment_data_status, segment_effort_count FROM exec_activities WHERE external_activity_id = '123'"
                    ).fetchone()
                    segment_total = connection.execute("SELECT COUNT(*) AS total FROM exec_segments").fetchone()["total"]
                    effort_total = connection.execute("SELECT COUNT(*) AS total FROM exec_segment_efforts").fetchone()["total"]

                self.assertEqual(activity["segment_data_status"], "available")
                self.assertEqual(activity["segment_effort_count"], 1)
                self.assertEqual(segment_total, 1)
                self.assertEqual(effort_total, 1)

    def test_segment_queries_return_history_and_missing_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()
                storage.persist_batch(build_batch())

                items = list_segments(season_id=2026)
                self.assertEqual(len(items), 1)
                item = items[0]
                self.assertEqual(item["effort_count"], 2)
                self.assertEqual(item["best_elapsed_time_seconds"], 412)
                self.assertEqual(item["missing_metric_counts"]["avg_heart_rate"], 1)

                history = get_segment_history(segment_id=item["segment_id"])
                assert history is not None
                self.assertEqual(history["summary"]["effort_count"], 2)
                self.assertEqual(history["summary"]["trend_status"], "declining")
                self.assertEqual(history["summary"]["comparable_effort_count"], 2)
                self.assertEqual(history["summary"]["membership_only_count"], 0)
                self.assertEqual(history["summary"]["best_effort_id"], history["efforts"][0]["segment_effort_id"])
                self.assertTrue(history["efforts"][1]["is_latest_effort"])
                self.assertIn("avg_heart_rate", history["efforts"][1]["missing_metrics"])
                self.assertEqual(history["efforts"][1]["delta_vs_best_seconds"], 14)

    def test_segment_queries_flag_membership_only_rows_when_elapsed_times_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()
                storage.persist_batch(build_membership_only_batch())

                items = list_segments(season_id=2026)
                self.assertEqual(len(items), 1)
                item = items[0]
                self.assertEqual(item["effort_count"], 2)
                self.assertEqual(item["comparable_effort_count"], 0)
                self.assertEqual(item["best_elapsed_time_seconds"], None)

                history = get_segment_history(segment_id=item["segment_id"])
                assert history is not None
                self.assertEqual(history["summary"]["effort_count"], 2)
                self.assertEqual(history["summary"]["comparable_effort_count"], 0)
                self.assertEqual(history["summary"]["membership_only_count"], 2)
                self.assertEqual(history["summary"]["trend_status"], "insufficient_data")
                self.assertEqual(history["summary"]["available_metric_names"], [])
                self.assertEqual(history["summary"]["best_effort_id"], None)
                self.assertEqual(history["efforts"][0]["delta_vs_best_seconds"], None)


class GarminSegmentAdapterTests(unittest.TestCase):
    def test_fetch_activities_uses_segment_list_when_activity_details_lack_efforts(self) -> None:
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
                        "summaryDTO": {
                            "duration": 3600,
                            "distance": 25000,
                            "elevationGain": 500,
                            "calories": 700,
                            "averageHR": 150,
                            "maxHR": 176,
                            "avgPower": 250,
                            "normPower": 265,
                        },
                    }
                ]

            def connectapi(self, path):
                if path == "/segment-service/segment/list/123":
                    return [
                        {
                            "segmentPk": 9001,
                            "segmentUuid": "segment-uuid-1",
                            "segmentName": "Subida del puerto",
                            "segmentDistance": 1450,
                            "favorite": True,
                            "classificationPk": 8,
                            "surfaceTypePk": 2,
                            "userMostRecentCrossingDate": "May 5, 2026 8:15:00 AM",
                        },
                        {
                            "segmentPk": 9002,
                            "segmentUuid": "segment-uuid-2",
                            "segmentName": "Rampas finales",
                            "segmentDistance": 620,
                            "favorite": False,
                            "classificationPk": 8,
                            "surfaceTypePk": 2,
                            "userMostRecentCrossingDate": "May 5, 2026 8:45:00 AM",
                        },
                    ]
                raise AssertionError(f"unexpected path: {path}")

            def get_activity_details(self, activity_id):
                return {}

            def download_activity(self, activity_id, _format):
                return b"fake-tcx"

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter.configuration.artifacts_path = temp_dir
            activities, artifact_paths, artifact_failures = adapter._fetch_activities(FakeClient(), request)

        self.assertEqual(len(activities), 1)
        activity = activities[0]
        self.assertEqual(activity.segment_data_status, "available")
        self.assertEqual(activity.segment_effort_count, 1)
        self.assertEqual(len(activity.segments), 1)
        self.assertEqual(activity.segments[0].definition.external_segment_id, "segment-uuid-1")
        self.assertEqual(activity.segments[0].definition.segment_name, "Subida del puerto")
        self.assertEqual(activity.segments[0].elapsed_time_seconds, None)
        self.assertEqual(activity.segments[0].external_segment_effort_id, "123:segment-uuid-1")
        self.assertEqual(len(artifact_paths), 1)
        self.assertEqual(artifact_failures, 0)

    def test_fetch_activities_prefers_detail_efforts_when_available(self) -> None:
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
                        "summaryDTO": {
                            "duration": 3600,
                            "distance": 25000,
                        },
                    }
                ]

            def connectapi(self, path):
                if path == "/segment-service/segment/list/123":
                    return [
                        {
                            "segmentPk": 9001,
                            "segmentUuid": "segment-uuid-1",
                            "segmentName": "Subida del puerto",
                            "segmentDistance": 1450,
                            "favorite": True,
                        }
                    ]
                raise AssertionError(f"unexpected path: {path}")

            def get_activity_details(self, activity_id):
                return {
                    "segmentEfforts": [
                        {
                            "segmentEffortId": 501,
                            "startTimeGMT": "2026-05-05T08:15:00",
                            "elapsedDuration": 412,
                            "averagePower": 320,
                            "averageCadence": 84,
                            "averageHR": 167,
                            "maxHR": 176,
                            "segment": {
                                "segmentId": 9001,
                                "name": "Subida del puerto",
                                "distance": 1450,
                                "elevationGain": 121,
                                "averageGrade": 8.3,
                            },
                        }
                    ]
                }

            def download_activity(self, activity_id, _format):
                return b"fake-tcx"

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter.configuration.artifacts_path = temp_dir
            activities, artifact_paths, artifact_failures = adapter._fetch_activities(FakeClient(), request)

        self.assertEqual(len(activities), 1)
        activity = activities[0]
        self.assertEqual(activity.segment_data_status, "available")
        self.assertEqual(activity.segment_effort_count, 1)
        self.assertEqual(activity.segments[0].definition.external_segment_id, "9001")
        self.assertEqual(activity.segments[0].elapsed_time_seconds, 412)
        self.assertEqual(activity.segments[0].avg_heart_rate, 167)
        self.assertEqual(len(artifact_paths), 1)
        self.assertEqual(artifact_failures, 0)

    def test_fetch_activities_reconstructs_metrics_from_activity_detail_stream(self) -> None:
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
                        "summaryDTO": {
                            "duration": 3600,
                            "distance": 25000,
                        },
                    }
                ]

            def connectapi(self, path):
                if path == "/segment-service/segment/list/123":
                    return [
                        {
                            "segmentUuid": "segment-uuid-1",
                            "segmentName": "Subida del puerto",
                            "segmentDistance": 1.0,
                            "favorite": True,
                            "timeEnteredSegment": 30_000,
                        },
                        {
                            "segmentUuid": "segment-uuid-2",
                            "segmentName": "Llano",
                            "segmentDistance": 0.4,
                            "favorite": False,
                            "timeEnteredSegment": 120_000,
                        }
                    ]
                if path == "/activity-service/activity/123/details":
                    return {
                        "metricDescriptors": [
                            {"metricsIndex": 0, "key": "directLatitude"},
                            {"metricsIndex": 1, "key": "directLongitude"},
                            {"metricsIndex": 2, "key": "directTimestamp"},
                            {"metricsIndex": 3, "key": "sumDistance"},
                            {"metricsIndex": 4, "key": "sumElapsedDuration"},
                            {"metricsIndex": 5, "key": "directPower"},
                            {"metricsIndex": 6, "key": "directBikeCadence"},
                            {"metricsIndex": 7, "key": "directHeartRate"},
                        ],
                        "activityDetailMetrics": [
                            {"metrics": [43.0000, -2.0000, 0, 0, 0, 100, 80, 120]},
                            {"metrics": [43.0000, -1.9999, 30_000, 200, 30, 200, 85, 140]},
                            {"metrics": [43.0000, -1.9940, 150_000, 700, 150, 220, 90, 150]},
                            {"metrics": [43.0000, -1.9880, 270_000, 1_200, 270, 240, 95, 160]},
                        ],
                    }
                if path == "/segment-service/segment/segment-uuid-1":
                    return {
                        "distance": 1.0,
                        "geoPoints": [
                            {"latitude": 43.0000, "longitude": -1.9999},
                            {"latitude": 43.0000, "longitude": -1.9880},
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
        activity = activities[0]
        self.assertEqual(activity.segment_data_status, "available")
        self.assertEqual(activity.segment_effort_count, 1)
        self.assertEqual(activity.segments[0].elapsed_time_seconds, 240)
        self.assertEqual(activity.segments[0].started_at, "1970-01-01T00:00:30+00:00")
        self.assertEqual(activity.segments[0].avg_power, 220)
        self.assertEqual(activity.segments[0].avg_cadence, 90)
        self.assertEqual(activity.segments[0].avg_heart_rate, 150)
        self.assertEqual(activity.segments[0].max_heart_rate, 160)
        self.assertEqual(activity.segments[0].notes, "reconstructed_from_activity_detail_stream")
        self.assertEqual(activity.segments[0].definition.distance_meters, 1000)
        self.assertEqual(len(artifact_paths), 1)
        self.assertEqual(artifact_failures, 0)

    def test_fetch_activities_reconstructs_multiple_occurrences_for_same_favorite_segment(self) -> None:
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
                        "summaryDTO": {
                            "duration": 7200,
                            "distance": 50000,
                        },
                    }
                ]

            def connectapi(self, path):
                if path == "/segment-service/segment/list/123":
                    return [
                        {
                            "segmentUuid": "segment-uuid-1",
                            "segmentName": "Subida del puerto",
                            "segmentDistance": 1.0,
                            "favorite": True,
                        }
                    ]
                if path == "/activity-service/activity/123/details":
                    return {
                        "metricDescriptors": [
                            {"metricsIndex": 0, "key": "directLatitude"},
                            {"metricsIndex": 1, "key": "directLongitude"},
                            {"metricsIndex": 2, "key": "directTimestamp"},
                            {"metricsIndex": 3, "key": "sumDistance"},
                            {"metricsIndex": 4, "key": "sumElapsedDuration"},
                            {"metricsIndex": 5, "key": "directPower"},
                            {"metricsIndex": 6, "key": "directBikeCadence"},
                            {"metricsIndex": 7, "key": "directHeartRate"},
                        ],
                        "activityDetailMetrics": [
                            {"metrics": [43.0000, -2.0002, 0, 0, 0, 100, 80, 120]},
                            {"metrics": [43.0000, -1.9999, 30_000, 200, 30, 200, 85, 140]},
                            {"metrics": [43.0000, -1.9940, 150_000, 700, 150, 220, 90, 150]},
                            {"metrics": [43.0000, -1.9880, 270_000, 1_200, 270, 240, 95, 160]},
                            {"metrics": [43.0000, -2.0020, 600_000, 2_000, 600, 130, 81, 121]},
                            {"metrics": [43.0000, -1.9999, 630_000, 2_200, 630, 210, 86, 141]},
                            {"metrics": [43.0000, -1.9940, 750_000, 2_700, 750, 230, 91, 151]},
                            {"metrics": [43.0000, -1.9880, 870_000, 3_200, 870, 250, 96, 161]},
                        ],
                    }
                if path == "/segment-service/segment/segment-uuid-1":
                    return {
                        "distance": 1.0,
                        "geoPoints": [
                            {"latitude": 43.0000, "longitude": -1.9999},
                            {"latitude": 43.0000, "longitude": -1.9880},
                        ],
                    }
                raise AssertionError(f"unexpected path: {path}")

            def get_activity_details(self, activity_id):
                return {}

            def download_activity(self, activity_id, _format):
                return b"fake-tcx"

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter.configuration.artifacts_path = temp_dir
            activities, _, _ = adapter._fetch_activities(FakeClient(), request)

        self.assertEqual(len(activities), 1)
        activity = activities[0]
        self.assertEqual(activity.segment_data_status, "available")
        self.assertEqual(activity.segment_effort_count, 2)
        self.assertEqual([segment.elapsed_time_seconds for segment in activity.segments], [240, 240])
        self.assertEqual(
            [segment.started_at for segment in activity.segments],
            ["1970-01-01T00:00:30+00:00", "1970-01-01T00:10:30+00:00"],
        )
        self.assertEqual(len({segment.external_segment_effort_id for segment in activity.segments}), 2)
        self.assertTrue(
            all(segment.notes == "reconstructed_from_activity_detail_stream" for segment in activity.segments)
        )

    def test_fetch_activities_discards_non_favorite_native_segment_efforts(self) -> None:
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
                        "summaryDTO": {"duration": 3600, "distance": 25000},
                    }
                ]

            def connectapi(self, path):
                if path == "/segment-service/segment/list/123":
                    return [
                        {
                            "segmentPk": 9001,
                            "segmentUuid": "segment-uuid-1",
                            "segmentName": "Subida del puerto",
                            "segmentDistance": 1450,
                            "favorite": True,
                        }
                    ]
                raise AssertionError(f"unexpected path: {path}")

            def get_activity_details(self, activity_id):
                return {
                    "segmentEfforts": [
                        {
                            "segmentEffortId": 501,
                            "startTimeGMT": "2026-05-05T08:15:00",
                            "elapsedDuration": 412,
                            "segment": {"segmentId": 9001, "name": "Subida del puerto", "distance": 1450},
                        },
                        {
                            "segmentEffortId": 502,
                            "startTimeGMT": "2026-05-05T08:25:00",
                            "elapsedDuration": 120,
                            "segment": {"segmentId": 9002, "name": "No favorita", "distance": 500},
                        },
                    ]
                }

            def download_activity(self, activity_id, _format):
                return b"fake-tcx"

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter.configuration.artifacts_path = temp_dir
            activities, _, _ = adapter._fetch_activities(FakeClient(), request)

        self.assertEqual(len(activities), 1)
        activity = activities[0]
        self.assertEqual(activity.segment_effort_count, 1)
        self.assertEqual(activity.segments[0].definition.external_segment_id, "9001")


class GarminSegmentApiTests(unittest.TestCase):
    def test_segment_endpoints_return_backend_contract_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                create_minimal_exec_tables(database_path)
                storage = GarminImportStorage()
                storage.persist_batch(build_batch())

                segment_payload = get_segments(season_id=2026, limit=20)
                self.assertEqual(len(segment_payload["items"]), 1)
                segment = segment_payload["items"][0]
                self.assertEqual(segment["external_segment_id"], "seg-1")
                self.assertEqual(segment["effort_count"], 2)
                self.assertIn("missing_metric_counts", segment)

                history_payload = get_segment_history_endpoint(segment_id=segment["segment_id"], limit=20)
                self.assertEqual(history_payload["segment"]["external_segment_id"], "seg-1")
                self.assertEqual(history_payload["summary"]["effort_count"], 2)
                self.assertEqual(len(history_payload["efforts"]), 2)



def build_batch() -> GarminImportBatch:
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
            notes=["batch ok"],
        ),
        activities=[
            NormalizedActivity(
                external_activity_id="123",
                activity_date="2026-05-05",
                started_at="2026-05-05T08:00:00",
                discipline="road_biking",
                activity_type="Bici",
                duration_seconds=3600,
                distance_meters=25000,
                ascent_meters=500,
                calories=700,
                avg_hr=150,
                max_hr=176,
                avg_power=250,
                normalized_power=265,
                training_load=80,
                avg_pace_seconds_per_km=None,
                segment_data_status="available",
                segment_effort_count=2,
                segment_checked_at="2026-05-05T09:00:00",
                segments=[
                    NormalizedSegmentEffort(
                        definition=NormalizedSegmentDefinition(
                            external_segment_id="seg-1",
                            segment_name="Subida del puerto",
                            discipline="cycling",
                            distance_meters=1450,
                            ascent_meters=121,
                            average_grade_percent=8.3,
                        ),
                        external_segment_effort_id="eff-1",
                        started_at="2026-05-05T08:15:00",
                        elapsed_time_seconds=412,
                        avg_power=320,
                        avg_cadence=84,
                        avg_heart_rate=167,
                        max_heart_rate=176,
                    ),
                    NormalizedSegmentEffort(
                        definition=NormalizedSegmentDefinition(
                            external_segment_id="seg-1",
                            segment_name="Subida del puerto",
                            discipline="cycling",
                            distance_meters=1450,
                            ascent_meters=121,
                            average_grade_percent=8.3,
                        ),
                        external_segment_effort_id="eff-2",
                        started_at="2026-05-05T08:45:00",
                        elapsed_time_seconds=426,
                        avg_power=311,
                        avg_cadence=82,
                        avg_heart_rate=None,
                        max_heart_rate=None,
                    ),
                ],
            )
        ],
        daily_metrics=[],
    )


def build_membership_only_batch() -> GarminImportBatch:
    return GarminImportBatch(
        request=GarminImportRequest(
            season_id=2026,
            date_from="2026-05-24",
            date_to="2026-05-25",
            include_daily_metrics=False,
        ),
        metadata=ImportFetchMetadata(
            source_system="garmin",
            source_label="garminconnect",
            date_from="2026-05-24",
            date_to="2026-05-25",
            notes=["membership only"],
        ),
        activities=[
            NormalizedActivity(
                external_activity_id="ride-1",
                activity_date="2026-05-24",
                started_at="2026-05-24T08:00:00",
                discipline="road_biking",
                activity_type="Bici",
                duration_seconds=3600,
                distance_meters=25000,
                ascent_meters=500,
                calories=700,
                avg_hr=150,
                max_hr=176,
                avg_power=250,
                normalized_power=265,
                training_load=80,
                avg_pace_seconds_per_km=None,
                segment_data_status="available",
                segment_effort_count=1,
                segment_checked_at="2026-05-24T09:00:00",
                segments=[
                    NormalizedSegmentEffort(
                        definition=NormalizedSegmentDefinition(
                            external_segment_id="seg-live-1",
                            segment_name="Miota",
                            discipline="cycling",
                            distance_meters=1450,
                            ascent_meters=121,
                            average_grade_percent=8.3,
                        ),
                        external_segment_effort_id="ride-1:seg-live-1",
                        started_at=None,
                        elapsed_time_seconds=None,
                    )
                ],
            ),
            NormalizedActivity(
                external_activity_id="ride-2",
                activity_date="2026-05-25",
                started_at="2026-05-25T08:00:00",
                discipline="road_biking",
                activity_type="Bici",
                duration_seconds=3500,
                distance_meters=24000,
                ascent_meters=480,
                calories=680,
                avg_hr=148,
                max_hr=172,
                avg_power=245,
                normalized_power=258,
                training_load=77,
                avg_pace_seconds_per_km=None,
                segment_data_status="available",
                segment_effort_count=1,
                segment_checked_at="2026-05-25T09:00:00",
                segments=[
                    NormalizedSegmentEffort(
                        definition=NormalizedSegmentDefinition(
                            external_segment_id="seg-live-1",
                            segment_name="Miota",
                            discipline="cycling",
                            distance_meters=1450,
                            ascent_meters=121,
                            average_grade_percent=8.3,
                        ),
                        external_segment_effort_id="ride-2:seg-live-1",
                        started_at=None,
                        elapsed_time_seconds=None,
                    )
                ],
            ),
        ],
        daily_metrics=[],
    )


def build_filtered_batch() -> GarminImportBatch:
    batch = build_batch()
    batch.activities[0].segment_effort_count = 1
    batch.activities[0].segments = [batch.activities[0].segments[0]]
    return batch


def storage_module_connection(database_path: Path):
    import sqlite3
    from contextlib import contextmanager

    @contextmanager
    def _connection_manager():
        connection = sqlite3.connect(database_path)
        try:
            connection.row_factory = sqlite3.Row
            yield connection
            connection.commit()
        finally:
            connection.close()

    return _connection_manager()


def create_minimal_exec_tables(database_path: Path) -> None:
    with storage_module_connection(database_path) as connection:
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
                segment_data_status TEXT NOT NULL DEFAULT 'not_checked',
                segment_effort_count INTEGER NOT NULL DEFAULT 0,
                segment_checked_at TEXT,
                raw_payload_path TEXT,
                notes TEXT,
                UNIQUE (source_system, external_activity_id)
            );

            CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                daily_metric_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                metric_date TEXT NOT NULL,
                source_system TEXT NOT NULL,
                weight_kg REAL,
                sleep_hours REAL,
                sleep_quality TEXT,
                resting_hr REAL,
                hrv REAL,
                body_battery REAL,
                subjective_energy INTEGER,
                subjective_fatigue INTEGER,
                notes TEXT,
                UNIQUE (season_id, metric_date, source_system)
            );

            CREATE TABLE IF NOT EXISTS exec_segments (
                segment_id INTEGER PRIMARY KEY,
                source_system TEXT NOT NULL,
                external_segment_id TEXT NOT NULL,
                segment_name TEXT,
                discipline TEXT,
                distance_meters REAL,
                ascent_meters REAL,
                average_grade_percent REAL,
                first_seen_activity_id INTEGER,
                last_seen_activity_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_system, external_segment_id)
            );

            CREATE TABLE IF NOT EXISTS exec_segment_efforts (
                segment_effort_id INTEGER PRIMARY KEY,
                source_system TEXT NOT NULL,
                external_segment_effort_id TEXT NOT NULL,
                segment_id INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                activity_date TEXT NOT NULL,
                started_at TEXT,
                elapsed_time_seconds INTEGER,
                avg_power REAL,
                avg_cadence REAL,
                avg_heart_rate REAL,
                max_heart_rate REAL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_system, external_segment_effort_id)
            );
            """
        )


if __name__ == "__main__":
    unittest.main()