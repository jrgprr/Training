from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.main import calculate_weekly_review_metrics, get_week_plan_vs_real_rows


class WeeklyReviewMetricsTests(unittest.TestCase):
    def _seed_context(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
        )
        connection.execute(
            "INSERT INTO plan_meso_blocks (block_id, season_id, block_code, block_name, sequence_order) VALUES (2, 2026, 'B2', 'Aerobic Build', 2)"
        )
        connection.execute(
            "INSERT INTO plan_micro_weeks (week_id, block_id, week_code, sequence_in_block, start_date, end_date, week_role, objective_primary) VALUES (204, 2, 'Semana-04', 4, '2026-07-06', '2026-07-12', 'Construccion principal', 'Expand useful aerobic time')"
        )
        connection.executemany(
            """
            INSERT INTO plan_planned_sessions (
                planned_session_id, week_id, session_date, day_name, sequence_in_week,
                planned_role, planned_type, objective, duration_min, duration_max, is_key_session
            ) VALUES (?, 204, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (20402, '2026-07-07', 'Tuesday', 1, 'resistencia-aerobica-principal', 'bike-z2', 'Primary aerobic session', 120, 140, 1),
                (20403, '2026-07-08', 'Wednesday', 2, 'resistencia-aerobica-suave', 'active-rest', 'Absorb fatigue', 25, 45, 0),
                (20404, '2026-07-09', 'Thursday', 3, 'resistencia-aerobica-principal', 'bike-z2', 'Continue aerobic work', 120, 135, 1),
            ],
        )
        connection.executemany(
            """
            INSERT INTO exec_activities (
                activity_id, season_id, source_system, external_activity_id, activity_date, started_at,
                discipline, activity_type, duration_seconds, quality_status
            ) VALUES (?, 2026, 'garmin', ?, '2026-07-07', ?, ?, ?, ?, 'clean')
            """,
            [
                (900298, '900298', '2026-07-07 15:39:01', 'walking', 'Madrid Caminar', 1895),
                (900299, '900299', '2026-07-07 20:13:37', 'running', 'Carrera', 3214),
            ],
        )
        connection.executemany(
            """
            INSERT INTO review_daily_reviews (
                season_id, review_date, block_id, week_id, planned_session_id, compliance_status, actual_summary
            ) VALUES (2026, ?, 2, 204, ?, ?, ?)
            """,
            [
                (
                    '2026-07-07',
                    20402,
                    'Replaced key ride with shorter mixed aerobic work.',
                    'The planned ride was not done. Instead, the day included a 31.6-minute walk and a 53.6-minute run.',
                ),
                (
                    '2026-07-08',
                    20403,
                    'Completed as full rest rather than active recovery.',
                    'No activity was recorded, which functioned as a full rest day rather than active recovery.',
                ),
                (
                    '2026-07-09',
                    20404,
                    'Key endurance session missed under clear recovery strain.',
                    'No activity was recorded, so the main Z2 cycling session was missed.',
                ),
            ],
        )
        connection.commit()

    def test_weekly_metrics_count_unlinked_replacement_minutes_and_normalize_review_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / 'training.sqlite'
            with patch('app.db.get_database_path', return_value=database_path), patch('app.db.normalize_existing_manual_activity_disciplines'):
                schema_path = Path(__file__).resolve().parents[3] / 'Sistema' / 'schema.sql'
                with sqlite3.connect(database_path) as connection:
                    connection.executescript(schema_path.read_text())
                    self._seed_context(connection)

                rows = get_week_plan_vs_real_rows(204)
                metrics = calculate_weekly_review_metrics(204)

        replaced_row = next(row for row in rows if row['planned_session_id'] == 20402)
        completed_rest_row = next(row for row in rows if row['planned_session_id'] == 20403)
        skipped_row = next(row for row in rows if row['planned_session_id'] == 20404)

        self.assertEqual(replaced_row['normalized_compliance_status'], 'replaced')
        self.assertAlmostEqual(replaced_row['actual_duration_min'], 85.15, places=2)
        self.assertEqual(completed_rest_row['normalized_compliance_status'], 'completed')
        self.assertEqual(skipped_row['normalized_compliance_status'], 'skipped')

        self.assertEqual(metrics['actual_minutes'], 85)
        self.assertEqual(metrics['planned_reference_minutes'], 292)
        self.assertEqual(metrics['volume_delta_minutes'], -207)
        self.assertEqual(metrics['adherence_rate'], 33.33)
        self.assertEqual(metrics['traceability_rate'], 100.0)
        self.assertEqual(metrics['risk_level'], 'Riesgo alto')
        self.assertIn('1 replaced', metrics['summary_text'])
        self.assertIn('1 completadas', metrics['summary_text'])
        self.assertIn('1 skipped', metrics['summary_text'])

    def test_weekly_metrics_exclude_unlinked_yoga_from_load_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / 'training.sqlite'
            with patch('app.db.get_database_path', return_value=database_path), patch('app.db.normalize_existing_manual_activity_disciplines'):
                schema_path = Path(__file__).resolve().parents[3] / 'Sistema' / 'schema.sql'
                with sqlite3.connect(database_path) as connection:
                    connection.executescript(schema_path.read_text())
                    connection.execute(
                        "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31')"
                    )
                    connection.execute(
                        "INSERT INTO plan_meso_blocks (block_id, season_id, block_code, block_name, sequence_order) VALUES (3, 2026, 'B3', 'Absorption', 3)"
                    )
                    connection.execute(
                        "INSERT INTO plan_micro_weeks (week_id, block_id, week_code, sequence_in_block, start_date, end_date, week_role, objective_primary) VALUES (301, 3, 'Semana-01', 1, '2026-07-20', '2026-07-26', 'absorcion', 'Absorb without extra cost')"
                    )
                    connection.execute(
                        """
                        INSERT INTO plan_planned_sessions (
                            planned_session_id, week_id, session_date, day_name, sequence_in_week,
                            planned_role, planned_type, objective, duration_min, duration_max, is_key_session
                        ) VALUES (30101, 301, '2026-07-20', 'Monday', 1, 'recuperacion', 'recuperacion', 'Easy day', 60, 90, 0)
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_activities (
                            activity_id, season_id, source_system, external_activity_id, activity_date, started_at,
                            discipline, activity_type, duration_seconds, quality_status
                        ) VALUES (910001, 2026, 'garmin', 'bike-1', '2026-07-20', '2026-07-20 18:00:00', 'road_biking', 'Ride', 3600, 'clean')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO exec_activities (
                            activity_id, season_id, source_system, external_activity_id, activity_date, started_at,
                            discipline, activity_type, duration_seconds, quality_status
                        ) VALUES (910002, 2026, 'garmin', 'yoga-1', '2026-07-20', '2026-07-20 21:00:00', 'yoga', 'Yoga', 1800, 'clean')
                        """
                    )
                    connection.execute(
                        "INSERT INTO link_plan_execution (planned_session_id, activity_id, link_type, compliance_status, rationale) VALUES (30101, 910001, 'garmin_auto', 'completed', 'Auto-link')"
                    )
                    connection.commit()

                rows = get_week_plan_vs_real_rows(301)
                metrics = calculate_weekly_review_metrics(301)

        row = rows[0]
        self.assertEqual(len(row['optional_daily_activities']), 1)
        self.assertEqual(row['optional_daily_activities'][0]['actual_discipline'], 'yoga')
        self.assertAlmostEqual(row['actual_duration_min'], 60.0, places=2)
        self.assertAlmostEqual(row['actual_minutes_total'], 60.0, places=2)
        self.assertEqual(metrics['actual_minutes'], 60)


if __name__ == '__main__':
    unittest.main()
