from __future__ import annotations

import json
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database
from app.planned_sessions import get_planned_session_activity_groups, sync_planned_session_structure


class PlanningSeedApplyTests(unittest.TestCase):
    def test_apply_planning_seed_replaces_structure_for_changed_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            database_path = temp_root / "training.sqlite"
            first_seed_path = temp_root / "seed-1.sql"
            second_seed_path = temp_root / "seed-2.sql"

            first_seed_path.write_text(
                """
                INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date, status)
                VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31', 'active');

                INSERT INTO plan_meso_blocks (
                    block_id, season_id, block_code, block_name, phase_name, sequence_order,
                    start_date, end_date, objective_primary
                ) VALUES (
                    2, 2026, 'B2', 'Bloque 2', 'base', 2,
                    '2026-06-15', '2026-07-26', 'Construccion aerobica'
                );

                INSERT INTO plan_micro_weeks (
                    week_id, block_id, week_code, sequence_in_block, start_date, end_date,
                    week_role, objective_primary
                ) VALUES (
                    201, 2, '201', 1, '2026-06-15', '2026-06-21', 'build', 'Semana base'
                );

                INSERT INTO plan_planned_sessions (
                    planned_session_id, week_id, session_date, day_name, sequence_in_week,
                    planned_type, objective, primary_session, complementary_session, notes,
                    is_key_session, intensity_class, duration_min, duration_max, adjustment_rule, markdown_path
                ) VALUES (
                    20101, 201, '2026-06-15', 'Lunes', 1,
                    'recuperacion', 'Soltar carga residual.',
                    'Paseo 40-55 minutos o bicicleta Z1 60-90 minutos o descanso activo.',
                    'Pecho, triceps y hombro 25-30 minutos.',
                    'Dia regenerativo.',
                    0, 'muy suave', 40, 90, 'Mantener muy facil.', 'week-201.md'
                );
                """,
                encoding="utf-8",
            )
            second_seed_path.write_text(
                """
                UPDATE plan_planned_sessions
                SET primary_session = 'Paseo 45-60 minutos o descanso activo.',
                    complementary_session = 'Movilidad 10-15 minutos.',
                    duration_min = 45,
                    duration_max = 60
                WHERE planned_session_id = 20101;
                """,
                encoding="utf-8",
            )

            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()

            script_path = Path(__file__).resolve().parents[3] / "Sistema" / "Seeds" / "apply_planning_seed.py"
            spec = importlib.util.spec_from_file_location("apply_planning_seed", script_path)
            self.assertIsNotNone(spec)
            module = importlib.util.module_from_spec(spec)
            assert spec is not None and spec.loader is not None
            spec.loader.exec_module(module)
            main = module.main

            with patch("sys.argv", [str(script_path), str(first_seed_path), str(second_seed_path), "--db", str(database_path)]):
                with patch("builtins.print") as print_mock:
                    exit_code = main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["results"][0]["upserted_planned_session_ids"], [20101])
            self.assertEqual(payload["results"][1]["upserted_planned_session_ids"], [20101])

            import sqlite3

            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            groups = get_planned_session_activity_groups(connection, 20101)

            self.assertEqual(len(groups), 2)
            self.assertEqual([item["discipline_family"] for item in groups[0]["items"]], ["walking", None])
            self.assertEqual(groups[1]["items"][0]["discipline_family"], "yoga")
            self.assertEqual(groups[1]["items"][0]["duration_min"], 10)
            self.assertEqual(groups[1]["items"][0]["duration_max"], 15)

    def test_sync_planned_session_structure_replaces_stale_derived_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            database_path = temp_root / "training.sqlite"

            with patch("app.db.get_database_path", return_value=database_path), patch(
                "app.db.normalize_existing_manual_activity_disciplines"
            ):
                initialize_database()

            import sqlite3

            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            connection.executescript(
                """
                CREATE TABLE plan_seasons (
                    season_id INTEGER PRIMARY KEY,
                    season_code TEXT,
                    season_name TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT
                );
                CREATE TABLE plan_meso_blocks (
                    block_id INTEGER PRIMARY KEY,
                    season_id INTEGER NOT NULL,
                    block_code TEXT,
                    block_name TEXT,
                    phase_name TEXT,
                    sequence_order INTEGER,
                    start_date TEXT,
                    end_date TEXT,
                    objective_primary TEXT
                );
                CREATE TABLE plan_micro_weeks (
                    week_id INTEGER PRIMARY KEY,
                    block_id INTEGER NOT NULL,
                    week_code TEXT,
                    sequence_in_block INTEGER,
                    start_date TEXT,
                    end_date TEXT,
                    week_role TEXT,
                    objective_primary TEXT
                );
                CREATE TABLE plan_planned_sessions (
                    planned_session_id INTEGER PRIMARY KEY,
                    week_id INTEGER NOT NULL,
                    session_date TEXT,
                    day_name TEXT,
                    sequence_in_week INTEGER,
                    planned_type TEXT,
                    objective TEXT,
                    primary_session TEXT,
                    complementary_session TEXT,
                    notes TEXT,
                    is_key_session INTEGER,
                    intensity_class TEXT,
                    duration_min INTEGER,
                    duration_max INTEGER,
                    adjustment_rule TEXT,
                    markdown_path TEXT
                );
                """
            )
            connection.execute(
                "INSERT INTO plan_seasons (season_id, season_code, season_name, start_date, end_date, status) VALUES (2026, '2026', 'Season 2026', '2026-01-01', '2026-12-31', 'active')"
            )
            connection.execute(
                "INSERT INTO plan_meso_blocks (block_id, season_id, block_code, block_name, phase_name, sequence_order, start_date, end_date, objective_primary) VALUES (2, 2026, 'B2', 'Bloque 2', 'base', 2, '2026-06-15', '2026-07-26', 'Construccion aerobica')"
            )
            connection.execute(
                "INSERT INTO plan_micro_weeks (week_id, block_id, week_code, sequence_in_block, start_date, end_date, week_role, objective_primary) VALUES (202, 2, '202', 2, '2026-06-22', '2026-06-28', 'build', 'Semana ajustada')"
            )
            connection.execute(
                """
                INSERT INTO plan_planned_sessions (
                    planned_session_id, week_id, session_date, day_name, sequence_in_week,
                    planned_type, objective, primary_session, complementary_session, notes,
                    is_key_session, intensity_class, duration_min, duration_max, adjustment_rule, markdown_path
                ) VALUES (
                    20203, 202, '2026-06-24', 'Miercoles', 3,
                    'recuperacion', 'Soltar sin dejar residuo.',
                    'Bicicleta Z1 75-105 minutos o descanso activo si las piernas no estan normales.',
                    'Core 25-30 minutos.',
                    'Dia facil.',
                    0, 'suave', 75, 105, 'Mantener facil.', 'week-202.md'
                )
                """
            )

            stale_row = connection.execute(
                "SELECT * FROM plan_planned_sessions WHERE planned_session_id = 20203"
            ).fetchone()
            assert stale_row is not None
            sync_planned_session_structure(connection, dict(stale_row))

            connection.execute(
                """
                UPDATE plan_planned_sessions
                SET planned_type = 'bicicleta-z2',
                    objective = 'Adelantar el dia aerobico util.',
                    primary_session = 'Bicicleta Z2 120-130 minutos.',
                    complementary_session = 'Pecho, triceps y hombro 25-30 minutos.',
                    is_key_session = 1,
                    duration_min = 120,
                    duration_max = 130
                WHERE planned_session_id = 20203
                """
            )
            updated_row = connection.execute(
                "SELECT * FROM plan_planned_sessions WHERE planned_session_id = 20203"
            ).fetchone()
            assert updated_row is not None

            sync_planned_session_structure(connection, dict(updated_row))
            groups = get_planned_session_activity_groups(connection, 20203)

            self.assertEqual(len(groups), 2)
            self.assertEqual(groups[0]["items"][0]["display_label"], "bicicleta")
            self.assertEqual(groups[0]["items"][0]["target_zone_min_code"], "Z2")
            self.assertEqual(groups[0]["items"][0]["target_zone_max_code"], "Z2")
            self.assertEqual(groups[0]["items"][0]["duration_min"], 120)
            self.assertEqual(groups[0]["items"][0]["duration_max"], 130)
            self.assertEqual(groups[1]["items"][0]["display_label"], "Pecho, triceps y hombro 25-30 minutos.")
            connection.close()


if __name__ == "__main__":
    unittest.main()