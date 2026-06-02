from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.db import initialize_database
from app.imports.contracts import GarminImportBatch, GarminImportRequest, ImportFetchMetadata, NormalizedActivity, NormalizedMetricReading
from app.imports.storage import GarminImportStorage
from app.main import ZoneMetricProfileAcceptancePayload, ZoneProposalAcceptancePayload, accept_zone_metric_profile_endpoint, accept_zone_proposal_endpoint, get_activity_zones_endpoint, get_current_zone_metric_profiles_endpoint, get_current_zone_profiles_endpoint, get_season_activities, get_session_prescription, get_sessions, get_week_plan_vs_real, get_weekly_review, get_zone_proposal_detail_endpoint, get_zone_proposals_endpoint
from app.training_zones import accept_zone_metric_profile, derive_zone_boundaries_from_metrics, generate_zone_refinement_proposals, get_active_zone_profile_for_date, get_activity_zone_detail, get_planned_session_zone_target, get_week_zone_comparison_summary, get_zone_proposal_detail, is_zone_supported_discipline, list_current_zone_metric_profiles, list_current_zone_profiles, list_session_zone_comparisons, list_zone_proposals, normalize_zone_basis, persist_accepted_zone_profile


class TrainingZoneSchemaTests(unittest.TestCase):
    def test_initialize_database_creates_zone_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    table_names = {
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        ).fetchall()
                    }

        self.assertTrue({
            "zone_metric_profiles",
            "zone_profiles",
            "zone_profile_boundaries",
            "zone_refinement_proposals",
            "zone_refinement_proposal_boundaries",
            "zone_refinement_evidence",
            "exec_activity_zone_results",
            "exec_activity_zone_buckets",
            "plan_session_zone_targets",
            "plan_session_zone_segments",
        }.issubset(table_names))

    def test_list_current_zone_profiles_groups_boundaries_by_basis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (2, 2026, 'cycling', 'power', 'cycling power v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 1, 'Z1', 0, 118, 'bpm')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 2, 'Z2', 119, 146, 'bpm')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (2, 1, 'Z1', 0, 145, 'watts')"
                    )
                    connection.commit()

                payload = list_current_zone_profiles(season_id=2026, discipline="cycling")

        self.assertEqual(payload["discipline"], "cycling")
        self.assertIn("heart_rate", payload["profiles"])
        self.assertIn("power", payload["profiles"])
        self.assertEqual(len(payload["profiles"]["heart_rate"]["boundaries"]), 2)
        self.assertEqual(payload["profiles"]["power"]["boundaries"][0]["bound_unit"], "watts")

    def test_current_zone_profiles_endpoint_returns_active_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 1, 'Z1', 0, 118, 'bpm')"
                    )
                    connection.commit()

                payload = get_current_zone_profiles_endpoint(season_id=2026, discipline="cycling")

        self.assertEqual(payload["season_id"], 2026)
        self.assertIn("heart_rate", payload["profiles"])

    def test_current_zone_profiles_endpoint_raises_when_no_profiles_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.commit()

                with self.assertRaises(HTTPException) as context:
                    get_current_zone_profiles_endpoint(season_id=2026, discipline="cycling")

        self.assertEqual(context.exception.status_code, 404)

    def test_derive_zone_boundaries_from_metrics_supports_heart_rate_reserve(self) -> None:
        boundaries = derive_zone_boundaries_from_metrics(
            metric_basis="heart_rate",
            model_key="heart_rate_reserve_5_zone",
            resting_hr=48,
            max_hr=183,
        )

        self.assertEqual([boundary["zone_code"] for boundary in boundaries], ["Z1", "Z2", "Z3", "Z4", "Z5"])
        self.assertEqual(boundaries[0]["zone_name"], "Recuperacion")
        self.assertEqual(boundaries[0]["lower_bound_value"], 48)
        self.assertEqual(boundaries[1]["lower_bound_value"], boundaries[0]["upper_bound_value"] + 1)
        self.assertIsNone(boundaries[-1]["upper_bound_value"])

    def test_accept_zone_metric_profile_creates_source_profile_and_derived_zone_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS plan_seasons (season_id INTEGER PRIMARY KEY, season_code TEXT NOT NULL, season_name TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL)"
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.commit()

                accepted = accept_zone_metric_profile(
                    season_id=2026,
                    discipline="cycling",
                    metric_basis="heart_rate",
                    model_key="heart_rate_reserve_5_zone",
                    effective_start_date="2026-06-02",
                    profile_label="cycling hr reserve v1",
                    resting_hr=48,
                    max_hr=183,
                    accepted_at="2026-06-02T08:00:00Z",
                )
                current_profiles = list_current_zone_profiles(season_id=2026, discipline="cycling")
                current_metric_profiles = list_current_zone_metric_profiles(season_id=2026, discipline="cycling")

        self.assertEqual(accepted["metric_basis"], "heart_rate")
        self.assertEqual(len(accepted["boundaries"]), 5)
        self.assertEqual(current_profiles["profiles"]["heart_rate"]["calculation_model_key"], "heart_rate_reserve_5_zone")
        self.assertEqual(current_profiles["profiles"]["heart_rate"]["metric_profile"]["parameters"]["resting_hr"], 48)
        self.assertEqual(current_metric_profiles["profiles"]["heart_rate"]["parameters"]["max_hr"], 183)

    def test_accept_zone_metric_profile_endpoint_exposes_current_power_metric_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS plan_seasons (season_id INTEGER PRIMARY KEY, season_code TEXT NOT NULL, season_name TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL)"
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.commit()

                accepted = accept_zone_metric_profile_endpoint(
                    2026,
                    ZoneMetricProfileAcceptancePayload(
                        discipline="cycling",
                        metric_basis="power",
                        model_key="ftp_coggan_7_zone",
                        effective_start_date="2026-06-02",
                        profile_label="cycling ftp v1",
                        ftp=264,
                    ),
                )
                current = get_current_zone_metric_profiles_endpoint(season_id=2026, discipline="cycling")

        self.assertEqual(accepted["metric_basis"], "power")
        self.assertEqual(current["profiles"]["power"]["model_key"], "ftp_coggan_7_zone")
        self.assertEqual(current["profiles"]["power"]["parameters"]["ftp"], 264)

    def test_persist_accepted_zone_profile_closes_previous_profile_and_supports_date_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    first_profile_id = persist_accepted_zone_profile(
                        connection,
                        season_id=2026,
                        discipline="road_biking",
                        metric_basis="heart_rate",
                        profile_label="cycling hr v1",
                        effective_start_date="2026-05-01",
                        accepted_at="2026-05-01T09:00:00Z",
                        boundaries=[
                            {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 118},
                            {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 119, "upper_bound_value": 146},
                        ],
                    )
                    second_profile_id = persist_accepted_zone_profile(
                        connection,
                        season_id=2026,
                        discipline="cycling",
                        metric_basis="heart_rate",
                        profile_label="cycling hr v2",
                        effective_start_date="2026-06-15",
                        accepted_at="2026-06-15T09:00:00Z",
                        boundaries=[
                            {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 120},
                            {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 121, "upper_bound_value": 148},
                        ],
                    )
                    connection.commit()
                    first_row = connection.execute(
                        "SELECT effective_end_date FROM zone_profiles WHERE zone_profile_id = ?",
                        (first_profile_id,),
                    ).fetchone()

                earlier_profile = get_active_zone_profile_for_date(
                    2026,
                    discipline="road_biking",
                    metric_basis="heart_rate",
                    activity_date="2026-05-20",
                )
                later_profile = get_active_zone_profile_for_date(
                    2026,
                    discipline="road_biking",
                    metric_basis="heart_rate",
                    activity_date="2026-06-20",
                )

        self.assertEqual(first_row["effective_end_date"], "2026-06-14")
        assert earlier_profile is not None
        assert later_profile is not None
        self.assertEqual(earlier_profile["zone_profile_id"], first_profile_id)
        self.assertEqual(later_profile["zone_profile_id"], second_profile_id)
        self.assertEqual(later_profile["discipline"], "cycling")
        self.assertEqual(len(later_profile["boundaries"]), 2)

    def test_storage_persist_accepted_zone_profile_updates_current_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                storage = GarminImportStorage()

                profile_id = storage.persist_accepted_zone_profile(
                    season_id=2026,
                    discipline="road_biking",
                    metric_basis="power",
                    profile_label="cycling power v1",
                    effective_start_date="2026-05-01",
                    accepted_at="2026-05-01T09:00:00Z",
                    boundaries=[
                        {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 145},
                        {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 146, "upper_bound_value": 220},
                    ],
                )

                payload = list_current_zone_profiles(season_id=2026, discipline="road_biking")

        self.assertEqual(payload["discipline"], "cycling")
        self.assertEqual(payload["profiles"]["power"]["zone_profile_id"], profile_id)
        self.assertEqual(payload["profiles"]["power"]["boundaries"][0]["bound_unit"], "watts")

    def test_get_activity_zone_detail_returns_basis_specific_results_and_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, discipline, quality_status) VALUES (440, 2026, 'garmin', '123', '2026-05-19', 'cycling', 'filtered')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO exec_activity_zone_results (activity_zone_result_id, activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (10, 440, 1, 'heart_rate', 'calculated', 'filtered', 458, 4620, 'Z2', 0.61)"
                    )
                    connection.execute(
                        "INSERT INTO exec_activity_zone_buckets (activity_zone_result_id, zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count) VALUES (10, 1, 'Z1', 820, 0.18, 80)"
                    )
                    connection.execute(
                        "INSERT INTO exec_activity_zone_buckets (activity_zone_result_id, zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count) VALUES (10, 2, 'Z2', 2818, 0.61, 280)"
                    )
                    connection.commit()

                payload = get_activity_zone_detail(440)

        assert payload is not None
        self.assertEqual(payload["activity"]["quality_status"], "filtered")
        self.assertIn("heart_rate", payload["results"])
        self.assertEqual(payload["results"]["heart_rate"]["profile_label"], "cycling hr v1")
        self.assertEqual(len(payload["results"]["heart_rate"]["buckets"]), 2)

    def test_get_activity_zones_endpoint_raises_when_no_zone_results_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, discipline, quality_status) VALUES (440, 2026, 'garmin', '123', '2026-05-19', 'cycling', 'filtered')"
                    )
                    connection.commit()

                with self.assertRaises(HTTPException) as context:
                    get_activity_zones_endpoint(440)

        self.assertEqual(context.exception.status_code, 404)

    def test_get_season_activities_includes_compact_zone_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
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
                            perceived_exertion INTEGER,
                            subjective_feeling TEXT,
                            raw_payload_path TEXT,
                            notes TEXT,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked',
                            quality_checked_at TEXT,
                            quality_rule_version TEXT,
                            quality_decision_count INTEGER NOT NULL DEFAULT 0,
                            quality_limited_metric_count INTEGER NOT NULL DEFAULT 0
                        );

                        CREATE TABLE IF NOT EXISTS link_plan_execution (
                            link_id INTEGER PRIMARY KEY,
                            planned_session_id INTEGER,
                            activity_id INTEGER,
                            compliance_status TEXT,
                            rationale TEXT
                        );

                        CREATE TABLE IF NOT EXISTS review_daily_reviews (
                            daily_review_id INTEGER PRIMARY KEY,
                            planned_session_id INTEGER,
                            review_date TEXT,
                            actual_summary TEXT,
                            general_feeling TEXT,
                            next_day_decision TEXT
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, started_at, discipline, activity_type, duration_seconds, avg_hr, avg_power, quality_status) VALUES (440, 2026, 'garmin', '123', '2026-05-19', '2026-05-19T08:00:00Z', 'cycling', 'Ride', 3600, 149, 286, 'filtered')"
                    )
                    connection.execute(
                        "INSERT INTO exec_activity_zone_results (activity_zone_result_id, activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share, calculation_notes) VALUES (10, 440, 12, 'heart_rate', 'calculated', 'filtered', 458, 4620, 'Z2', 0.61, NULL)"
                    )
                    connection.execute(
                        "INSERT INTO exec_activity_zone_results (activity_zone_result_id, activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share, calculation_notes) VALUES (11, 440, 8, 'power', 'limited', 'filtered', 120, 0, NULL, NULL, '[\"insufficient_power_samples\"]')"
                    )
                    connection.commit()

                payload = get_season_activities(2026)

        self.assertEqual(len(payload), 1)
        self.assertIn("zone_summary", payload[0])
        self.assertEqual(payload[0]["zone_summary"]["heart_rate"]["dominant_zone_code"], "Z2")
        self.assertEqual(payload[0]["zone_summary"]["heart_rate"]["zone_profile_id"], 12)
        self.assertEqual(payload[0]["zone_summary"]["power"]["calculation_status"], "limited")
        self.assertEqual(payload[0]["zone_summary"]["power"]["limiting_reasons"], ["insufficient_power_samples"])

    def test_list_zone_proposals_returns_pending_items_for_discipline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.execute(
                        "INSERT INTO zone_refinement_proposals (proposal_id, season_id, discipline, metric_basis, proposal_status, confidence_level, recommendation_kind, proposal_summary, limiting_factors, source_zone_profile_id, proposed_effective_start_date, created_at) VALUES (31, 2026, 'cycling', 'heart_rate', 'pending', 'medium', 'rebalance', 'Recent aerobic rides suggest Z2 upper bound is slightly low.', '[\"elevated_stress_window\"]', 12, '2026-06-08', '2026-06-01T09:20:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_refinement_proposals (proposal_id, season_id, discipline, metric_basis, proposal_status, confidence_level, recommendation_kind, proposal_summary, limiting_factors, source_zone_profile_id, proposed_effective_start_date, created_at) VALUES (32, 2026, 'running', 'heart_rate', 'pending', 'low', 'rebalance', 'Should not appear.', '[]', 18, '2026-06-09', '2026-06-01T09:30:00Z')"
                    )
                    connection.commit()

                payload = list_zone_proposals(2026, "road_biking")

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["proposal_id"], 31)
        self.assertEqual(payload["items"][0]["discipline"], "cycling")
        self.assertEqual(payload["items"][0]["limiting_factors"], ["elevated_stress_window"])
        self.assertEqual(payload["review_state"], "heart_rate_only")
        self.assertEqual(payload["basis_summary"]["heart_rate"]["pending_count"], 1)

    def test_list_zone_proposals_exposes_mixed_basis_review_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.execute(
                        "INSERT INTO zone_refinement_proposals (proposal_id, season_id, discipline, metric_basis, proposal_status, confidence_level, recommendation_kind, proposal_summary, limiting_factors, source_zone_profile_id, proposed_effective_start_date, created_at) VALUES (31, 2026, 'cycling', 'heart_rate', 'pending', 'medium', 'rebalance', 'HR proposal.', '[]', 12, '2026-06-08', '2026-06-01T09:20:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_refinement_proposals (proposal_id, season_id, discipline, metric_basis, proposal_status, confidence_level, recommendation_kind, proposal_summary, limiting_factors, source_zone_profile_id, proposed_effective_start_date, created_at) VALUES (32, 2026, 'cycling', 'power', 'deferred', 'limited', 'rebalance', 'Power proposal.', '[\"recovery_watch\"]', 18, '2026-06-09', '2026-06-01T09:10:00Z')"
                    )
                    connection.commit()

                payload = list_zone_proposals(2026, "cycling")

        self.assertEqual(payload["review_state"], "mixed_basis")
        self.assertEqual(payload["basis_summary"]["heart_rate"]["pending_count"], 1)
        self.assertEqual(payload["basis_summary"]["heart_rate"]["actionable_count"], 1)
        self.assertEqual(payload["basis_summary"]["power"]["deferred_count"], 1)
        self.assertEqual(payload["basis_summary"]["power"]["actionable_count"], 1)
        self.assertEqual(payload["basis_summary"]["heart_rate"]["latest_proposal_id"], 31)
        self.assertEqual(payload["basis_summary"]["power"]["latest_proposal_id"], 32)

    def test_get_zone_proposal_detail_returns_boundaries_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.execute(
                        "INSERT INTO zone_refinement_proposals (proposal_id, season_id, discipline, metric_basis, proposal_status, confidence_level, recommendation_kind, proposal_summary, limiting_factors, source_zone_profile_id, proposed_effective_start_date, created_at) VALUES (31, 2026, 'cycling', 'heart_rate', 'pending', 'medium', 'rebalance', 'Recent aerobic rides suggest Z2 upper bound is slightly low.', '[\"elevated_stress_window\"]', 12, '2026-06-08', '2026-06-01T09:20:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_refinement_proposal_boundaries (proposal_id, zone_index, zone_code, proposed_lower_bound_value, proposed_upper_bound_value, bound_unit, delta_vs_current_lower, delta_vs_current_upper) VALUES (31, 2, 'Z2', 119, 149, 'bpm', 0, 3)"
                    )
                    connection.execute(
                        "INSERT INTO zone_refinement_evidence (proposal_id, evidence_type, activity_id, evidence_date, evidence_role, metric_basis, summary_json) VALUES (31, 'activity', 440, '2026-05-19', 'supporting', 'heart_rate', '{\"dominant_zone_code\": \"Z2\", \"aerobic_decoupling_hint\": \"stable\"}')"
                    )
                    connection.execute(
                        "INSERT INTO zone_refinement_evidence (proposal_id, evidence_type, daily_metric_id, evidence_date, evidence_role, metric_basis, summary_json) VALUES (31, 'daily_metric', 77, '2026-05-28', 'limiting', 'heart_rate', '{\"stress_avg\": 46, \"sleep_hours\": 5.2, \"note\": \"reduced confidence\"}')"
                    )
                    connection.commit()

                payload = get_zone_proposal_detail(31)

        assert payload is not None
        self.assertEqual(payload["proposal"]["proposal_id"], 31)
        self.assertEqual(payload["proposal"]["limiting_factors"], ["elevated_stress_window"])
        self.assertEqual(payload["boundaries"][0]["zone_code"], "Z2")
        self.assertEqual(payload["boundaries"][0]["delta_vs_current_upper"], 3)
        self.assertEqual(payload["evidence"][0]["summary"]["dominant_zone_code"], "Z2")
        self.assertEqual(payload["evidence"][1]["summary"]["stress_avg"], 46)

    def test_get_zone_proposals_endpoint_returns_pending_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_refinement_proposals (proposal_id, season_id, discipline, metric_basis, proposal_status, confidence_level, recommendation_kind, proposal_summary, limiting_factors, source_zone_profile_id, proposed_effective_start_date, created_at) VALUES (31, 2026, 'cycling', 'heart_rate', 'pending', 'medium', 'rebalance', 'Recent aerobic rides suggest Z2 upper bound is slightly low.', '[\"elevated_stress_window\"]', 12, '2026-06-08', '2026-06-01T09:20:00Z')"
                    )
                    connection.commit()

                payload = get_zone_proposals_endpoint(2026, "road_biking")

        self.assertEqual(payload["items"][0]["proposal_id"], 31)

    def test_get_zone_proposal_detail_endpoint_raises_when_proposal_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()

                with self.assertRaises(HTTPException) as context:
                    get_zone_proposal_detail_endpoint(999)

        self.assertEqual(context.exception.status_code, 404)


class TrainingZoneHelperTests(unittest.TestCase):
    def test_normalize_zone_basis_accepts_aliases(self) -> None:
        self.assertEqual(normalize_zone_basis("HR"), "heart_rate")
        self.assertEqual(normalize_zone_basis("watts"), "power")
        self.assertIsNone(normalize_zone_basis("pace"))

    def test_is_zone_supported_discipline_is_cycling_first(self) -> None:
        self.assertTrue(is_zone_supported_discipline("road_biking"))
        self.assertTrue(is_zone_supported_discipline("cycling"))
        self.assertFalse(is_zone_supported_discipline("running"))


class TrainingZoneRefinementTests(unittest.TestCase):
    def test_generate_zone_refinement_proposals_creates_heart_rate_pending_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    persist_accepted_zone_profile(
                        connection,
                        season_id=2026,
                        discipline="cycling",
                        metric_basis="heart_rate",
                        profile_label="cycling hr v1",
                        effective_start_date="2026-05-01",
                        accepted_at="2026-05-01T09:00:00Z",
                        boundaries=[
                            {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 120},
                            {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 121, "upper_bound_value": 150},
                            {"zone_code": "Z3", "zone_index": 3, "lower_bound_value": 151, "upper_bound_value": 170},
                        ],
                    )
                    for activity_id, activity_date, avg_hr in ((440, "2026-05-20", 153), (441, "2026-05-22", 154), (442, "2026-05-25", 156)):
                        connection.execute(
                            "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, discipline, avg_hr, quality_status) VALUES (?, 2026, 'garmin', ?, ?, 'road_biking', ?, 'filtered')",
                            (activity_id, str(activity_id), activity_date, avg_hr),
                        )
                        connection.execute(
                            "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (?, 1, 'heart_rate', 'calculated', 'filtered', 300, 3600, 'Z2', 0.74)",
                            (activity_id,),
                        )
                    connection.commit()

                payload = generate_zone_refinement_proposals(2026, discipline="road_biking")
                detail = get_zone_proposal_detail(payload["items"][0]["proposal_id"])

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["metric_basis"], "heart_rate")
        self.assertEqual(payload["items"][0]["proposal_status"], "pending")
        self.assertEqual(payload["items"][0]["confidence_level"], "high")
        assert detail is not None
        self.assertEqual(detail["boundaries"][0]["zone_code"], "Z2")
        self.assertEqual(detail["boundaries"][0]["delta_vs_current_upper"], 4)
        self.assertEqual(detail["boundaries"][1]["zone_code"], "Z3")
        self.assertEqual(detail["boundaries"][1]["delta_vs_current_lower"], 4)
        self.assertEqual(len(detail["evidence"]), 3)

    def test_generate_zone_refinement_proposals_creates_power_pending_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    persist_accepted_zone_profile(
                        connection,
                        season_id=2026,
                        discipline="cycling",
                        metric_basis="power",
                        profile_label="cycling power v1",
                        effective_start_date="2026-05-01",
                        accepted_at="2026-05-01T09:00:00Z",
                        boundaries=[
                            {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 145},
                            {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 146, "upper_bound_value": 220},
                            {"zone_code": "Z3", "zone_index": 3, "lower_bound_value": 221, "upper_bound_value": 300},
                        ],
                    )
                    for activity_id, activity_date, avg_power in ((540, "2026-05-20", 228), (541, "2026-05-21", 230), (542, "2026-05-24", 232)):
                        connection.execute(
                            "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, discipline, avg_power, quality_status) VALUES (?, 2026, 'garmin', ?, ?, 'road_biking', ?, 'filtered')",
                            (activity_id, str(activity_id), activity_date, avg_power),
                        )
                        connection.execute(
                            "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (?, 1, 'power', 'calculated', 'filtered', 300, 3600, 'Z2', 0.68)",
                            (activity_id,),
                        )
                    connection.commit()

                payload = generate_zone_refinement_proposals(2026, discipline="cycling")
                detail = get_zone_proposal_detail(payload["items"][0]["proposal_id"])

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["metric_basis"], "power")
        assert detail is not None
        self.assertEqual(detail["boundaries"][0]["delta_vs_current_upper"], 10)
        self.assertEqual(detail["boundaries"][1]["delta_vs_current_lower"], 10)

    def test_generate_zone_refinement_proposals_defers_when_recovery_context_is_poor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    persist_accepted_zone_profile(
                        connection,
                        season_id=2026,
                        discipline="cycling",
                        metric_basis="heart_rate",
                        profile_label="cycling hr v1",
                        effective_start_date="2026-05-01",
                        accepted_at="2026-05-01T09:00:00Z",
                        boundaries=[
                            {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 120},
                            {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 121, "upper_bound_value": 150},
                            {"zone_code": "Z3", "zone_index": 3, "lower_bound_value": 151, "upper_bound_value": 170},
                        ],
                    )
                    for activity_id, activity_date, avg_hr in ((640, "2026-05-20", 153), (641, "2026-05-22", 154)):
                        connection.execute(
                            "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, discipline, avg_hr, quality_status) VALUES (?, 2026, 'garmin', ?, ?, 'road_biking', ?, 'filtered')",
                            (activity_id, str(activity_id), activity_date, avg_hr),
                        )
                        connection.execute(
                            "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (?, 1, 'heart_rate', 'calculated', 'filtered', 300, 3600, 'Z2', 0.72)",
                            (activity_id,),
                        )
                    connection.execute(
                        "INSERT INTO exec_daily_metrics (daily_metric_id, season_id, metric_date, source_system, sleep_hours, stress_avg, body_battery) VALUES (77, 2026, '2026-05-22', 'garmin', 5.1, 52, 28)"
                    )
                    connection.commit()

                payload = generate_zone_refinement_proposals(2026, discipline="cycling", as_of_date="2026-05-22")
                detail = get_zone_proposal_detail(payload["items"][0]["proposal_id"])

        self.assertEqual(payload["items"][0]["proposal_status"], "deferred")
        self.assertEqual(payload["items"][0]["confidence_level"], "low")
        self.assertEqual(
            payload["items"][0]["limiting_factors"],
            ["elevated_stress_window", "low_body_battery_window", "low_sleep_window"],
        )
        assert detail is not None
        self.assertEqual(detail["evidence"][-1]["evidence_type"], "daily_metric")
        self.assertEqual(detail["evidence"][-1]["summary"]["stress_avg"], 52)

    def test_generate_zone_refinement_proposals_returns_noop_when_evidence_is_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    persist_accepted_zone_profile(
                        connection,
                        season_id=2026,
                        discipline="cycling",
                        metric_basis="heart_rate",
                        profile_label="cycling hr v1",
                        effective_start_date="2026-05-01",
                        accepted_at="2026-05-01T09:00:00Z",
                        boundaries=[
                            {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 120},
                            {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 121, "upper_bound_value": 150},
                            {"zone_code": "Z3", "zone_index": 3, "lower_bound_value": 151, "upper_bound_value": 170},
                        ],
                    )
                    connection.execute(
                        "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, discipline, avg_hr, quality_status) VALUES (740, 2026, 'garmin', '740', '2026-05-20', 'road_biking', 149, 'filtered')"
                    )
                    connection.execute(
                        "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (740, 1, 'heart_rate', 'calculated', 'filtered', 300, 3600, 'Z2', 0.72)"
                    )
                    connection.commit()

                payload = generate_zone_refinement_proposals(2026, discipline="cycling")
                with sqlite3.connect(database_path) as connection:
                    proposal_count = connection.execute("SELECT COUNT(*) FROM zone_refinement_proposals").fetchone()[0]

        self.assertEqual(payload, {"items": []})
        self.assertEqual(proposal_count, 0)

    def test_accept_zone_proposal_endpoint_creates_new_profile_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS exec_activities (
                            activity_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            source_system TEXT NOT NULL,
                            external_activity_id TEXT,
                            activity_date TEXT NOT NULL,
                            discipline TEXT,
                            avg_hr REAL,
                            avg_power REAL,
                            normalized_power REAL,
                            quality_status TEXT NOT NULL DEFAULT 'not_checked'
                        );
                        CREATE TABLE IF NOT EXISTS exec_daily_metrics (
                            daily_metric_id INTEGER PRIMARY KEY,
                            season_id INTEGER NOT NULL,
                            metric_date TEXT NOT NULL,
                            source_system TEXT NOT NULL,
                            sleep_hours REAL,
                            hrv REAL,
                            body_battery REAL,
                            stress_avg REAL
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    persist_accepted_zone_profile(
                        connection,
                        season_id=2026,
                        discipline="cycling",
                        metric_basis="heart_rate",
                        profile_label="cycling hr v1",
                        effective_start_date="2026-05-01",
                        accepted_at="2026-05-01T09:00:00Z",
                        boundaries=[
                            {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 120},
                            {"zone_code": "Z2", "zone_index": 2, "lower_bound_value": 121, "upper_bound_value": 150},
                            {"zone_code": "Z3", "zone_index": 3, "lower_bound_value": 151, "upper_bound_value": 170},
                        ],
                    )
                    for activity_id, activity_date, avg_hr in ((840, "2026-05-20", 153), (841, "2026-05-22", 154), (842, "2026-05-25", 156)):
                        connection.execute(
                            "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, discipline, avg_hr, quality_status) VALUES (?, 2026, 'garmin', ?, ?, 'road_biking', ?, 'filtered')",
                            (activity_id, str(activity_id), activity_date, avg_hr),
                        )
                        connection.execute(
                            "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (?, 1, 'heart_rate', 'calculated', 'filtered', 300, 3600, 'Z2', 0.74)",
                            (activity_id,),
                        )
                    connection.commit()

                generated_payload = generate_zone_refinement_proposals(2026, discipline="cycling")
                proposal_id = generated_payload["items"][0]["proposal_id"]
                accepted_payload = accept_zone_proposal_endpoint(
                    proposal_id,
                    ZoneProposalAcceptancePayload(
                        effective_start_date="2026-05-26",
                        accepted_at="2026-05-26T09:00:00Z",
                        decision_notes="Apply updated aerobic ceiling.",
                    ),
                )
                current_profile = get_active_zone_profile_for_date(
                    2026,
                    discipline="cycling",
                    metric_basis="heart_rate",
                    activity_date="2026-05-26",
                )
                proposal_detail = get_zone_proposal_detail(proposal_id)
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    first_profile = connection.execute(
                        "SELECT effective_end_date FROM zone_profiles WHERE zone_profile_id = 1"
                    ).fetchone()
                    accepted_profile_row = connection.execute(
                        "SELECT derived_from_proposal_id FROM zone_profiles WHERE zone_profile_id = ?",
                        (accepted_payload["zone_profile_id"],),
                    ).fetchone()

        self.assertEqual(accepted_payload["proposal_status"], "accepted")
        assert proposal_detail is not None
        self.assertEqual(proposal_detail["proposal"]["proposal_status"], "accepted")
        assert current_profile is not None
        self.assertEqual(current_profile["zone_profile_id"], accepted_payload["zone_profile_id"])
        self.assertEqual(current_profile["boundaries"][1]["upper_bound_value"], 154)
        self.assertEqual(first_profile["effective_end_date"], "2026-05-25")
        self.assertEqual(accepted_profile_row["derived_from_proposal_id"], proposal_id)


class TrainingZoneComparisonTests(unittest.TestCase):
    @staticmethod
    def _create_week_zone_context(connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS plan_seasons (
                season_id INTEGER PRIMARY KEY,
                season_code TEXT NOT NULL,
                season_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plan_meso_blocks (
                block_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                block_code TEXT NOT NULL,
                block_name TEXT NOT NULL,
                sequence_order INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plan_micro_weeks (
                week_id INTEGER PRIMARY KEY,
                block_id INTEGER NOT NULL,
                week_code TEXT NOT NULL,
                sequence_in_block INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                week_role TEXT,
                objective_primary TEXT
            );
            CREATE TABLE IF NOT EXISTS plan_planned_sessions (
                planned_session_id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                day_name TEXT NOT NULL,
                sequence_in_week INTEGER NOT NULL,
                planned_type TEXT,
                objective TEXT,
                primary_session TEXT,
                duration_min INTEGER,
                duration_max INTEGER,
                is_key_session INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS link_plan_execution (
                link_id INTEGER PRIMARY KEY,
                planned_session_id INTEGER,
                activity_id INTEGER,
                link_type TEXT,
                compliance_status TEXT,
                rationale TEXT
            );
            CREATE TABLE IF NOT EXISTS review_daily_reviews (
                daily_review_id INTEGER PRIMARY KEY,
                planned_session_id INTEGER,
                review_date TEXT,
                compliance_status TEXT,
                actual_summary TEXT,
                general_feeling TEXT,
                next_day_decision TEXT
            );
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
                avg_hr REAL,
                avg_power REAL,
                normalized_power REAL,
                perceived_exertion INTEGER,
                quality_status TEXT NOT NULL DEFAULT 'not_checked'
            );
            """
        )
        connection.execute(
            "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
        )
        connection.execute(
            "INSERT INTO plan_meso_blocks (block_id, season_id, block_code, block_name, sequence_order) VALUES (10, 2026, 'B2', 'Aerobic', 2)"
        )
        connection.execute(
            "INSERT INTO plan_micro_weeks (week_id, block_id, week_code, sequence_in_block, start_date, end_date, week_role, objective_primary) VALUES (20, 10, 'W20', 3, '2026-05-19', '2026-05-25', 'build', 'Aerobic consistency')"
        )
        connection.execute(
            "INSERT INTO plan_planned_sessions (planned_session_id, week_id, session_date, day_name, sequence_in_week, planned_type, objective, primary_session, duration_min, duration_max, is_key_session) VALUES (100, 20, '2026-05-20', 'Tue', 1, 'bicicleta-z2', 'Stay in Z2', 'Bike Z2', 90, 90, 1)"
        )
        connection.execute(
            "INSERT INTO plan_planned_sessions (planned_session_id, week_id, session_date, day_name, sequence_in_week, planned_type, objective, primary_session, duration_min, duration_max, is_key_session) VALUES (101, 20, '2026-05-22', 'Thu', 2, 'bicicleta-z2', 'Power Z2', 'Bike Z2 power', 75, 75, 0)"
        )
        connection.execute(
            "INSERT INTO plan_session_zone_targets (planned_zone_target_id, planned_session_id, target_basis, target_kind, source_kind, source_text, comparison_eligibility) VALUES (1, 100, 'heart_rate', 'single_zone', 'explicit', 'Z2', 'eligible')"
        )
        connection.execute(
            "INSERT INTO plan_session_zone_segments (planned_zone_target_id, sequence_order, segment_label, target_zone_min_code, target_zone_max_code) VALUES (1, 1, 'Main block', 'Z2', 'Z2')"
        )
        connection.execute(
            "INSERT INTO plan_session_zone_targets (planned_zone_target_id, planned_session_id, target_basis, target_kind, source_kind, source_text, comparison_eligibility) VALUES (2, 101, 'power', 'single_zone', 'explicit', 'Z2', 'eligible')"
        )
        connection.execute(
            "INSERT INTO plan_session_zone_segments (planned_zone_target_id, sequence_order, segment_label, target_zone_min_code, target_zone_max_code) VALUES (2, 1, 'Main block', 'Z2', 'Z2')"
        )
        connection.execute(
            "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, started_at, discipline, activity_type, duration_seconds, avg_hr, avg_power, normalized_power, perceived_exertion, quality_status) VALUES (500, 2026, 'garmin', '500', '2026-05-20', '2026-05-20T08:00:00Z', 'road_biking', 'Ride', 5400, 148, 210, 212, 4, 'filtered')"
        )
        connection.execute(
            "INSERT INTO exec_activities (activity_id, season_id, source_system, external_activity_id, activity_date, started_at, discipline, activity_type, duration_seconds, avg_hr, avg_power, normalized_power, perceived_exertion, quality_status) VALUES (501, 2026, 'garmin', '501', '2026-05-22', '2026-05-22T08:00:00Z', 'road_biking', 'Ride', 4500, 150, NULL, NULL, 5, 'filtered')"
        )
        connection.execute(
            "INSERT INTO link_plan_execution (link_id, planned_session_id, activity_id, link_type, compliance_status, rationale) VALUES (1, 100, 500, 'direct', 'completed', 'Direct match')"
        )
        connection.execute(
            "INSERT INTO link_plan_execution (link_id, planned_session_id, activity_id, link_type, compliance_status, rationale) VALUES (2, 101, 501, 'direct', 'completed', 'Direct match')"
        )
        connection.execute(
            "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-05-01T09:00:00Z')"
        )
        connection.execute(
            "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (2, 2026, 'cycling', 'power', 'cycling power v1', 'accepted', '2026-05-01', '2026-05-01T09:00:00Z')"
        )
        connection.execute(
            "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (500, 1, 'heart_rate', 'calculated', 'filtered', 300, 5400, 'Z2', 0.71)"
        )
        connection.execute(
            "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (500, 2, 'power', 'calculated', 'filtered', 300, 5400, 'Z3', 0.55)"
        )
        connection.execute(
            "INSERT INTO exec_activity_zone_results (activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot, supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share) VALUES (501, 1, 'heart_rate', 'calculated', 'filtered', 280, 4500, 'Z2', 0.63)"
        )
        connection.commit()

    def test_list_session_zone_comparisons_includes_aligned_and_limited_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    self._create_week_zone_context(connection)

                payload = list_session_zone_comparisons(20)

        self.assertEqual(payload[100][0]["comparison_status"], "aligned")
        self.assertEqual(payload[100][0]["metric_basis"], "heart_rate")
        self.assertEqual(payload[100][0]["target_zone_min_code"], "Z2")
        self.assertEqual(payload[101][0]["comparison_status"], "limited")
        self.assertEqual(payload[101][0]["metric_basis"], "power")
        self.assertEqual(payload[101][0]["dominant_zone_code"], None)

    def test_get_week_zone_comparison_summary_distinguishes_bases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    self._create_week_zone_context(connection)

                payload = get_week_zone_comparison_summary(20)

        self.assertEqual(len(payload["items"]), 2)
        heart_rate_summary = next(item for item in payload["items"] if item["metric_basis"] == "heart_rate")
        power_summary = next(item for item in payload["items"] if item["metric_basis"] == "power")
        self.assertEqual(heart_rate_summary["aligned_count"], 1)
        self.assertEqual(heart_rate_summary["limited_count"], 0)
        self.assertEqual(power_summary["aligned_count"], 0)
        self.assertEqual(power_summary["limited_count"], 1)

    def test_week_endpoints_expose_zone_comparison_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    self._create_week_zone_context(connection)

                rows = get_week_plan_vs_real(20)
                review = get_weekly_review(20)

        session_row = next(row for row in rows if row["planned_session_id"] == 100)
        limited_row = next(row for row in rows if row["planned_session_id"] == 101)
        self.assertEqual(session_row["zone_comparison"][0]["comparison_status"], "aligned")
        self.assertEqual(limited_row["zone_comparison"][0]["comparison_status"], "limited")
        self.assertEqual(review["zone_comparison_summary"]["items"][0]["planned_session_count"], 1)


class PlannedZoneTargetTests(unittest.TestCase):
    @staticmethod
    def _create_planned_zone_context(connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS plan_seasons (
                season_id INTEGER PRIMARY KEY,
                season_code TEXT NOT NULL,
                season_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plan_meso_blocks (
                block_id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                block_code TEXT NOT NULL,
                block_name TEXT NOT NULL,
                sequence_order INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plan_micro_weeks (
                week_id INTEGER PRIMARY KEY,
                block_id INTEGER NOT NULL,
                week_code TEXT NOT NULL,
                sequence_in_block INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                week_role TEXT,
                objective_primary TEXT
            );
            CREATE TABLE IF NOT EXISTS plan_planned_sessions (
                planned_session_id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                day_name TEXT NOT NULL,
                sequence_in_week INTEGER NOT NULL,
                planned_type TEXT,
                objective TEXT,
                primary_session TEXT,
                complementary_session TEXT,
                intensity_class TEXT,
                duration_min INTEGER,
                duration_max INTEGER,
                is_key_session INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS plan_session_prescriptions (
                prescription_id INTEGER PRIMARY KEY,
                planned_session_id INTEGER NOT NULL UNIQUE,
                prescription_type TEXT NOT NULL DEFAULT 'other',
                title TEXT,
                focus_primary TEXT,
                focus_secondary TEXT,
                estimated_duration_min INTEGER,
                estimated_duration_max INTEGER,
                target_rpe_min REAL,
                target_rpe_max REAL,
                warmup_notes TEXT,
                cooldown_notes TEXT,
                execution_notes TEXT,
                adaptation_notes TEXT,
                source_markdown_path TEXT
            );
            CREATE TABLE IF NOT EXISTS plan_prescription_blocks (
                prescription_block_id INTEGER PRIMARY KEY,
                prescription_id INTEGER NOT NULL,
                sequence_order INTEGER NOT NULL,
                block_type TEXT NOT NULL,
                block_name TEXT,
                objective TEXT,
                rounds INTEGER,
                rest_seconds INTEGER,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS plan_prescription_exercises (
                prescription_exercise_id INTEGER PRIMARY KEY,
                prescription_block_id INTEGER NOT NULL,
                sequence_order INTEGER NOT NULL,
                exercise_name TEXT NOT NULL,
                movement_pattern TEXT,
                equipment TEXT,
                unilateral_mode TEXT NOT NULL DEFAULT 'none',
                sets_count INTEGER,
                reps_min INTEGER,
                reps_max INTEGER,
                hold_seconds_min INTEGER,
                hold_seconds_max INTEGER,
                distance_meters REAL,
                target_rpe_min REAL,
                target_rpe_max REAL,
                target_rir_min REAL,
                target_rir_max REAL,
                tempo TEXT,
                load_guidance TEXT,
                optional_flag INTEGER NOT NULL DEFAULT 0,
                substitution_group TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS plan_prescription_exercise_options (
                exercise_option_id INTEGER PRIMARY KEY,
                prescription_exercise_id INTEGER NOT NULL,
                sequence_order INTEGER NOT NULL,
                option_name TEXT NOT NULL,
                equipment TEXT,
                condition_notes TEXT
            );
            """
        )
        connection.execute(
            "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
        )
        connection.execute(
            "INSERT INTO plan_meso_blocks (block_id, season_id, block_code, block_name, sequence_order) VALUES (10, 2026, 'B2', 'Aerobic', 2)"
        )
        connection.execute(
            "INSERT INTO plan_micro_weeks (week_id, block_id, week_code, sequence_in_block, start_date, end_date, week_role, objective_primary) VALUES (20, 10, 'W20', 3, '2026-05-19', '2026-05-25', 'build', 'Aerobic consistency')"
        )
        connection.execute(
            "INSERT INTO plan_planned_sessions (planned_session_id, week_id, session_date, day_name, sequence_in_week, planned_type, objective, primary_session, duration_min, duration_max, is_key_session) VALUES (200, 20, '2026-05-20', 'Tue', 1, 'bicicleta-z2', 'Stay aerobic in Z2', 'Bike Z2', 90, 90, 1)"
        )
        connection.execute(
            "INSERT INTO plan_planned_sessions (planned_session_id, week_id, session_date, day_name, sequence_in_week, planned_type, objective, primary_session, duration_min, duration_max, is_key_session) VALUES (201, 20, '2026-05-22', 'Thu', 2, 'intervals', 'Structured intervals', '3x5 Z4 after Z2 warmup', 75, 75, 0)"
        )
        connection.execute(
            "INSERT INTO plan_planned_sessions (planned_session_id, week_id, session_date, day_name, sequence_in_week, planned_type, objective, primary_session, duration_min, duration_max, is_key_session) VALUES (202, 20, '2026-05-24', 'Sat', 3, 'bicicleta-aerobica', 'Comfortable aerobic ride', 'Bike easy', 120, 120, 0)"
        )
        connection.execute(
            "INSERT INTO plan_session_prescriptions (prescription_id, planned_session_id, prescription_type, title, execution_notes) VALUES (1, 201, 'endurance', 'Threshold build', '15min Z2 + 3x5min Z4 + 10min Z2')"
        )
        connection.commit()

    def test_get_planned_session_zone_target_returns_explicit_single_zone_and_persists_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    self._create_planned_zone_context(connection)

                payload = get_planned_session_zone_target(200)
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    stored_target = connection.execute(
                        "SELECT target_basis, target_kind, source_kind, source_text FROM plan_session_zone_targets WHERE planned_session_id = 200"
                    ).fetchone()
                    stored_segments = connection.execute(
                        "SELECT sequence_order, target_zone_min_code, target_zone_max_code FROM plan_session_zone_segments WHERE planned_zone_target_id = (SELECT planned_zone_target_id FROM plan_session_zone_targets WHERE planned_session_id = 200) ORDER BY sequence_order"
                    ).fetchall()

        assert payload is not None
        self.assertEqual(payload["target_kind"], "single_zone")
        self.assertEqual(payload["target_basis"], "heart_rate")
        self.assertEqual(payload["segments"][0]["target_zone_min_code"], "Z2")
        self.assertEqual(stored_target["source_kind"], "derived")
        self.assertEqual(stored_segments[0]["target_zone_max_code"], "Z2")

    def test_get_planned_session_zone_target_returns_multi_segment_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    self._create_planned_zone_context(connection)

                payload = get_planned_session_zone_target(201)

        assert payload is not None
        self.assertEqual(payload["target_kind"], "multi_segment")
        self.assertEqual(payload["segments"][0]["target_zone_min_code"], "Z2")
        self.assertEqual(payload["segments"][1]["target_zone_min_code"], "Z4")
        self.assertEqual(len(payload["segments"]), 3)

    def test_get_planned_session_zone_target_returns_none_when_no_explicit_zone_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    self._create_planned_zone_context(connection)

                payload = get_planned_session_zone_target(202)
                with sqlite3.connect(database_path) as connection:
                    target_count = connection.execute(
                        "SELECT COUNT(*) FROM plan_session_zone_targets WHERE planned_session_id = 202"
                    ).fetchone()[0]

        self.assertIsNone(payload)
        self.assertEqual(target_count, 0)

    def test_session_endpoints_expose_planned_zone_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch("app.db.normalize_existing_manual_activity_disciplines"):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    self._create_planned_zone_context(connection)

                sessions = get_sessions(20)
                prescription = get_session_prescription(201)

        single_zone_row = next(row for row in sessions if row["planned_session_id"] == 200)
        no_zone_row = next(row for row in sessions if row["planned_session_id"] == 202)
        self.assertEqual(single_zone_row["planned_zone_target"]["target_kind"], "single_zone")
        self.assertIsNone(no_zone_row["planned_zone_target"])
        self.assertEqual(prescription["planned_zone_target"]["target_kind"], "multi_segment")


class TrainingZonePersistenceTests(unittest.TestCase):
    def test_persist_batch_stores_calculated_heart_rate_and_unavailable_power_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'active',
                            notes TEXT
                        );

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
                            quality_status TEXT NOT NULL DEFAULT 'not_checked',
                            quality_checked_at TEXT,
                            quality_rule_version TEXT,
                            quality_decision_count INTEGER NOT NULL DEFAULT 0,
                            quality_limited_metric_count INTEGER NOT NULL DEFAULT 0,
                            perceived_exertion INTEGER,
                            subjective_feeling TEXT,
                            source_file TEXT,
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
                            stress_avg REAL,
                            stress_max REAL,
                            spo2_avg REAL,
                            spo2_sleep_avg REAL,
                            spo2_7d_avg REAL,
                            spo2_lowest REAL,
                            subjective_energy INTEGER,
                            subjective_fatigue INTEGER,
                            soreness TEXT,
                            notes TEXT,
                            UNIQUE (season_id, metric_date, source_system)
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (2, 2026, 'cycling', 'power', 'cycling power v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 1, 'Z1', 0, 120, 'bpm')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 2, 'Z2', 121, 150, 'bpm')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (2, 1, 'Z1', 0, 145, 'watts')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (2, 2, 'Z2', 146, 220, 'watts')"
                    )
                    connection.commit()

                storage = GarminImportStorage()
                batch = GarminImportBatch(
                    request=GarminImportRequest(
                        season_id=2026,
                        date_from="2026-05-19",
                        date_to="2026-05-19",
                        include_daily_metrics=False,
                    ),
                    metadata=ImportFetchMetadata(
                        source_system="garmin",
                        source_label="garminconnect",
                        date_from="2026-05-19",
                        date_to="2026-05-19",
                    ),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="123",
                            activity_date="2026-05-19",
                            started_at="2026-05-19T08:00:00Z",
                            discipline="road_biking",
                            activity_type="Ride",
                            duration_seconds=180,
                            distance_meters=1000,
                            ascent_meters=10,
                            calories=100,
                            avg_hr=126,
                            max_hr=140,
                            avg_power=None,
                            normalized_power=None,
                            training_load=None,
                            avg_pace_seconds_per_km=None,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=110, elapsed_seconds=0),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=130, elapsed_seconds=60),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=2, raw_value=140, elapsed_seconds=120),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                storage.persist_batch(batch)

                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    rows = connection.execute(
                        "SELECT metric_basis, calculation_status, dominant_zone_code, total_supported_seconds FROM exec_activity_zone_results ORDER BY metric_basis"
                    ).fetchall()
                    hr_buckets = connection.execute(
                        "SELECT zone_code, seconds_in_zone FROM exec_activity_zone_buckets ORDER BY zone_index"
                    ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["metric_basis"], "heart_rate")
        self.assertEqual(rows[0]["calculation_status"], "calculated")
        self.assertEqual(rows[0]["dominant_zone_code"], "Z2")
        self.assertEqual(rows[1]["metric_basis"], "power")
        self.assertEqual(rows[1]["calculation_status"], "unavailable")
        self.assertEqual([(row["zone_code"], row["seconds_in_zone"]) for row in hr_buckets], [("Z1", 60), ("Z2", 120)])

    def test_persist_batch_stores_calculated_power_distribution_with_profile_traceability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'active',
                            notes TEXT
                        );

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
                            quality_status TEXT NOT NULL DEFAULT 'not_checked',
                            quality_checked_at TEXT,
                            quality_rule_version TEXT,
                            quality_decision_count INTEGER NOT NULL DEFAULT 0,
                            quality_limited_metric_count INTEGER NOT NULL DEFAULT 0,
                            perceived_exertion INTEGER,
                            subjective_feeling TEXT,
                            source_file TEXT,
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
                            stress_avg REAL,
                            stress_max REAL,
                            spo2_avg REAL,
                            spo2_sleep_avg REAL,
                            spo2_7d_avg REAL,
                            spo2_lowest REAL,
                            subjective_energy INTEGER,
                            subjective_fatigue INTEGER,
                            soreness TEXT,
                            notes TEXT,
                            UNIQUE (season_id, metric_date, source_system)
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (2, 2026, 'cycling', 'power', 'cycling power v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 1, 'Z1', 0, 120, 'bpm')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 2, 'Z2', 121, 150, 'bpm')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (2, 1, 'Z1', 0, 145, 'watts')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (2, 2, 'Z2', 146, 220, 'watts')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (2, 3, 'Z3', 221, 320, 'watts')"
                    )
                    connection.commit()

                storage = GarminImportStorage()
                batch = GarminImportBatch(
                    request=GarminImportRequest(
                        season_id=2026,
                        date_from="2026-05-21",
                        date_to="2026-05-21",
                        include_daily_metrics=False,
                    ),
                    metadata=ImportFetchMetadata(
                        source_system="garmin",
                        source_label="garminconnect",
                        date_from="2026-05-21",
                        date_to="2026-05-21",
                    ),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="125",
                            activity_date="2026-05-21",
                            started_at="2026-05-21T08:00:00Z",
                            discipline="road_biking",
                            activity_type="Ride",
                            duration_seconds=180,
                            distance_meters=1200,
                            ascent_meters=20,
                            calories=120,
                            avg_hr=130,
                            max_hr=142,
                            avg_power=210,
                            normalized_power=225,
                            training_load=68,
                            avg_pace_seconds_per_km=None,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=110, elapsed_seconds=0),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=130, elapsed_seconds=60),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=2, raw_value=140, elapsed_seconds=120),
                                NormalizedMetricReading(metric_name="power", sample_index=0, raw_value=140, elapsed_seconds=0),
                                NormalizedMetricReading(metric_name="power", sample_index=1, raw_value=180, elapsed_seconds=60),
                                NormalizedMetricReading(metric_name="power", sample_index=2, raw_value=260, elapsed_seconds=120),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                storage.persist_batch(batch)

                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    rows = connection.execute(
                        "SELECT metric_basis, zone_profile_id, calculation_status, dominant_zone_code FROM exec_activity_zone_results ORDER BY metric_basis"
                    ).fetchall()
                    power_buckets = connection.execute(
                        "SELECT zone_code, seconds_in_zone, sample_count FROM exec_activity_zone_buckets WHERE activity_zone_result_id = (SELECT activity_zone_result_id FROM exec_activity_zone_results WHERE activity_id = 1 AND metric_basis = 'power') ORDER BY zone_index"
                    ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["metric_basis"], "heart_rate")
        self.assertEqual(rows[0]["zone_profile_id"], 1)
        self.assertEqual(rows[1]["metric_basis"], "power")
        self.assertEqual(rows[1]["zone_profile_id"], 2)
        self.assertEqual(rows[1]["calculation_status"], "calculated")
        self.assertEqual(rows[1]["dominant_zone_code"], "Z1")
        self.assertEqual(
            [(row["zone_code"], row["seconds_in_zone"], row["sample_count"]) for row in power_buckets],
            [("Z1", 60, 1), ("Z2", 60, 1), ("Z3", 60, 1)],
        )

    def test_persist_batch_marks_basis_limited_when_samples_exist_but_no_bucket_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'active',
                            notes TEXT
                        );

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
                            quality_status TEXT NOT NULL DEFAULT 'not_checked',
                            quality_checked_at TEXT,
                            quality_rule_version TEXT,
                            quality_decision_count INTEGER NOT NULL DEFAULT 0,
                            quality_limited_metric_count INTEGER NOT NULL DEFAULT 0,
                            perceived_exertion INTEGER,
                            subjective_feeling TEXT,
                            source_file TEXT,
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
                            stress_avg REAL,
                            stress_max REAL,
                            spo2_avg REAL,
                            spo2_sleep_avg REAL,
                            spo2_7d_avg REAL,
                            spo2_lowest REAL,
                            subjective_energy INTEGER,
                            subjective_fatigue INTEGER,
                            soreness TEXT,
                            notes TEXT,
                            UNIQUE (season_id, metric_date, source_system)
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 1, 'Z1', 0, 120, 'bpm')"
                    )
                    connection.commit()

                storage = GarminImportStorage()
                batch = GarminImportBatch(
                    request=GarminImportRequest(season_id=2026, date_from="2026-05-20", date_to="2026-05-20", include_daily_metrics=False),
                    metadata=ImportFetchMetadata(source_system="garmin", source_label="garminconnect", date_from="2026-05-20", date_to="2026-05-20"),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="124",
                            activity_date="2026-05-20",
                            started_at="2026-05-20T08:00:00Z",
                            discipline="road_biking",
                            activity_type="Ride",
                            duration_seconds=120,
                            distance_meters=500,
                            ascent_meters=0,
                            calories=50,
                            avg_hr=170,
                            max_hr=172,
                            avg_power=None,
                            normalized_power=None,
                            training_load=None,
                            avg_pace_seconds_per_km=None,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=170, elapsed_seconds=0),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=172, elapsed_seconds=60),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                storage.persist_batch(batch)

                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    row = connection.execute(
                        "SELECT metric_basis, calculation_status, dominant_zone_code, calculation_notes FROM exec_activity_zone_results WHERE metric_basis = 'heart_rate'"
                    ).fetchone()
                    bucket_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_zone_buckets"
                    ).fetchone()["total"]

        self.assertEqual(row["calculation_status"], "limited")
        self.assertIsNone(row["dominant_zone_code"])
        self.assertIn("no_bucketed_samples", row["calculation_notes"])
        self.assertEqual(bucket_count, 0)

    def test_persist_batch_marks_power_as_limited_when_samples_are_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'active',
                            notes TEXT
                        );

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
                            quality_status TEXT NOT NULL DEFAULT 'not_checked',
                            quality_checked_at TEXT,
                            quality_rule_version TEXT,
                            quality_decision_count INTEGER NOT NULL DEFAULT 0,
                            quality_limited_metric_count INTEGER NOT NULL DEFAULT 0,
                            perceived_exertion INTEGER,
                            subjective_feeling TEXT,
                            source_file TEXT,
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
                            stress_avg REAL,
                            stress_max REAL,
                            spo2_avg REAL,
                            spo2_sleep_avg REAL,
                            spo2_7d_avg REAL,
                            spo2_lowest REAL,
                            subjective_energy INTEGER,
                            subjective_fatigue INTEGER,
                            soreness TEXT,
                            notes TEXT,
                            UNIQUE (season_id, metric_date, source_system)
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'power', 'cycling power v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 1, 'Z1', 0, 145, 'watts')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 2, 'Z2', 146, 220, 'watts')"
                    )
                    connection.commit()

                storage = GarminImportStorage()
                batch = GarminImportBatch(
                    request=GarminImportRequest(season_id=2026, date_from="2026-05-22", date_to="2026-05-22", include_daily_metrics=False),
                    metadata=ImportFetchMetadata(source_system="garmin", source_label="garminconnect", date_from="2026-05-22", date_to="2026-05-22"),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="126",
                            activity_date="2026-05-22",
                            started_at="2026-05-22T08:00:00Z",
                            discipline="road_biking",
                            activity_type="Ride",
                            duration_seconds=60,
                            distance_meters=300,
                            ascent_meters=0,
                            calories=30,
                            avg_hr=None,
                            max_hr=None,
                            avg_power=180,
                            normalized_power=180,
                            training_load=None,
                            avg_pace_seconds_per_km=None,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="power", sample_index=0, raw_value=180, elapsed_seconds=0),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )

                storage.persist_batch(batch)

                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    row = connection.execute(
                        "SELECT calculation_status, supported_sample_count, total_supported_seconds, calculation_notes FROM exec_activity_zone_results WHERE metric_basis = 'power'"
                    ).fetchone()
                    bucket_count = connection.execute(
                        "SELECT COUNT(*) AS total FROM exec_activity_zone_buckets"
                    ).fetchone()["total"]

        self.assertEqual(row["calculation_status"], "limited")
        self.assertEqual(row["supported_sample_count"], 1)
        self.assertEqual(row["total_supported_seconds"], 0)
        self.assertIn("insufficient_power_samples", row["calculation_notes"])
        self.assertEqual(bucket_count, 0)

    def test_replay_activity_quality_refreshes_zone_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "training.sqlite"
            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ), patch.object(GarminImportStorage, "_auto_link_garmin_activities", return_value=(0, 0)):
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS plan_seasons (
                            season_id INTEGER PRIMARY KEY,
                            season_code TEXT NOT NULL,
                            season_name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'active',
                            notes TEXT
                        );

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
                            quality_status TEXT NOT NULL DEFAULT 'not_checked',
                            quality_checked_at TEXT,
                            quality_rule_version TEXT,
                            quality_decision_count INTEGER NOT NULL DEFAULT 0,
                            quality_limited_metric_count INTEGER NOT NULL DEFAULT 0,
                            perceived_exertion INTEGER,
                            subjective_feeling TEXT,
                            source_file TEXT,
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
                            stress_avg REAL,
                            stress_max REAL,
                            spo2_avg REAL,
                            spo2_sleep_avg REAL,
                            spo2_7d_avg REAL,
                            spo2_lowest REAL,
                            subjective_energy INTEGER,
                            subjective_fatigue INTEGER,
                            soreness TEXT,
                            notes TEXT,
                            UNIQUE (season_id, metric_date, source_system)
                        );
                        """
                    )
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profiles (zone_profile_id, season_id, discipline, metric_basis, profile_label, governance_status, effective_start_date, accepted_at) VALUES (1, 2026, 'cycling', 'heart_rate', 'cycling hr v1', 'accepted', '2026-05-01', '2026-06-01T08:00:00Z')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 1, 'Z1', 0, 120, 'bpm')"
                    )
                    connection.execute(
                        "INSERT INTO zone_profile_boundaries (zone_profile_id, zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit) VALUES (1, 2, 'Z2', 121, 150, 'bpm')"
                    )
                    connection.commit()

                storage = GarminImportStorage()
                batch = GarminImportBatch(
                    request=GarminImportRequest(season_id=2026, date_from="2026-05-19", date_to="2026-05-19", include_daily_metrics=False),
                    metadata=ImportFetchMetadata(source_system="garmin", source_label="garminconnect", date_from="2026-05-19", date_to="2026-05-19"),
                    activities=[
                        NormalizedActivity(
                            external_activity_id="123",
                            activity_date="2026-05-19",
                            started_at="2026-05-19T08:00:00Z",
                            discipline="road_biking",
                            activity_type="Ride",
                            duration_seconds=180,
                            distance_meters=1000,
                            ascent_meters=10,
                            calories=100,
                            avg_hr=126,
                            max_hr=140,
                            avg_power=None,
                            normalized_power=None,
                            training_load=None,
                            avg_pace_seconds_per_km=None,
                            metric_readings=[
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=0, raw_value=110, elapsed_seconds=0),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=1, raw_value=130, elapsed_seconds=60),
                                NormalizedMetricReading(metric_name="heart_rate", sample_index=2, raw_value=140, elapsed_seconds=120),
                            ],
                        )
                    ],
                    daily_metrics=[],
                )
                storage.persist_batch(batch)

                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    connection.execute(
                        "UPDATE exec_activity_metric_readings SET raw_value = 118 WHERE activity_id = 1 AND metric_name = 'heart_rate' AND sample_index = 1"
                    )
                    connection.commit()

                result = storage.replay_activity_quality(1, source_mode="canonical")

                with sqlite3.connect(database_path) as connection:
                    connection.row_factory = sqlite3.Row
                    row = connection.execute(
                        "SELECT calculation_status, dominant_zone_code FROM exec_activity_zone_results WHERE activity_id = 1 AND metric_basis = 'heart_rate'"
                    ).fetchone()
                    buckets = connection.execute(
                        "SELECT zone_code, seconds_in_zone FROM exec_activity_zone_buckets WHERE activity_zone_result_id = (SELECT activity_zone_result_id FROM exec_activity_zone_results WHERE activity_id = 1 AND metric_basis = 'heart_rate') ORDER BY zone_index"
                    ).fetchall()

        assert result is not None
        self.assertIn(result["result"], {"reused_existing_run", "created_new_run"})
        self.assertEqual(row["calculation_status"], "calculated")
        self.assertEqual(row["dominant_zone_code"], "Z1")
        self.assertEqual([(bucket["zone_code"], bucket["seconds_in_zone"]) for bucket in buckets], [("Z1", 120), ("Z2", 60)])


if __name__ == "__main__":
    unittest.main()