from __future__ import annotations

import sqlite3
from typing import Any

from .planned_sessions import build_legacy_activity_groups


PRESCRIPTION_SOURCE_COLUMNS = (
    "planned_session_id",
    "planned_role",
    "planned_type",
    "objective",
    "primary_session",
    "complementary_session",
    "notes",
    "is_key_session",
    "intensity_class",
    "duration_min",
    "duration_max",
    "adjustment_rule",
    "markdown_path",
)


def sync_all_planned_session_prescriptions(connection: sqlite3.Connection) -> None:
    session_table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plan_planned_sessions'"
    ).fetchone()
    if session_table_exists is None:
        return

    rows = connection.execute(
        f"SELECT {', '.join(PRESCRIPTION_SOURCE_COLUMNS)} FROM plan_planned_sessions ORDER BY planned_session_id"
    ).fetchall()
    for row in rows:
        sync_planned_session_prescription(connection, dict(row))


def sync_planned_session_prescription(connection: sqlite3.Connection, session_row: dict[str, Any]) -> None:
    prescription = build_structured_prescription(session_row)
    current = get_planned_session_prescription(connection, int(session_row["planned_session_id"]))
    if _prescription_signature(current) == _prescription_signature(prescription):
        return
    replace_planned_session_prescription(connection, prescription)


def replace_planned_session_prescription(connection: sqlite3.Connection, prescription: dict[str, Any]) -> None:
    planned_session_id = int(prescription["planned_session_id"])
    existing_row = connection.execute(
        "SELECT prescription_id FROM plan_session_prescriptions WHERE planned_session_id = ?",
        (planned_session_id,),
    ).fetchone()
    if existing_row is not None:
        prescription_id = int(existing_row["prescription_id"])
        block_rows = connection.execute(
            "SELECT prescription_block_id FROM plan_prescription_blocks WHERE prescription_id = ?",
            (prescription_id,),
        ).fetchall()
        block_ids = [int(row["prescription_block_id"]) for row in block_rows]
        if block_ids:
            placeholders = ", ".join("?" for _ in block_ids)
            exercise_rows = connection.execute(
                f"SELECT prescription_exercise_id FROM plan_prescription_exercises WHERE prescription_block_id IN ({placeholders})",
                tuple(block_ids),
            ).fetchall()
            exercise_ids = [int(row["prescription_exercise_id"]) for row in exercise_rows]
            if exercise_ids:
                exercise_placeholders = ", ".join("?" for _ in exercise_ids)
                connection.execute(
                    f"DELETE FROM plan_prescription_exercise_options WHERE prescription_exercise_id IN ({exercise_placeholders})",
                    tuple(exercise_ids),
                )
                connection.execute(
                    f"DELETE FROM plan_prescription_exercises WHERE prescription_exercise_id IN ({exercise_placeholders})",
                    tuple(exercise_ids),
                )
            connection.execute(
                f"DELETE FROM plan_prescription_blocks WHERE prescription_block_id IN ({placeholders})",
                tuple(block_ids),
            )
        connection.execute("DELETE FROM plan_session_prescriptions WHERE prescription_id = ?", (prescription_id,))

    cursor = connection.execute(
        """
        INSERT INTO plan_session_prescriptions (
            planned_session_id, prescription_type, discipline_family, title,
            focus_primary, focus_secondary, estimated_duration_min, estimated_duration_max,
            target_rpe_min, target_rpe_max, warmup_notes, cooldown_notes,
            execution_notes, adaptation_notes, source_kind, structure_version, source_markdown_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            planned_session_id,
            prescription["prescription_type"],
            prescription.get("discipline_family"),
            prescription.get("title"),
            prescription.get("focus_primary"),
            prescription.get("focus_secondary"),
            prescription.get("estimated_duration_min"),
            prescription.get("estimated_duration_max"),
            prescription.get("target_rpe_min"),
            prescription.get("target_rpe_max"),
            prescription.get("warmup_notes"),
            prescription.get("cooldown_notes"),
            prescription.get("execution_notes"),
            prescription.get("adaptation_notes"),
            prescription.get("source_kind", "generated"),
            prescription.get("structure_version", "v1"),
            prescription.get("source_markdown_path"),
        ),
    )
    prescription_id = int(cursor.lastrowid)

    for block in prescription.get("blocks", []):
        block_cursor = connection.execute(
            """
            INSERT INTO plan_prescription_blocks (
                prescription_id, sequence_order, block_role, relation_group, relation_mode,
                is_optional, block_type, block_name, objective, rounds, rest_seconds,
                discipline_family, duration_min, duration_max, target_basis,
                target_zone_min_code, target_zone_max_code, condition_key,
                condition_value, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prescription_id,
                block["sequence_order"],
                block["block_role"],
                block["relation_group"],
                block["relation_mode"],
                block["is_optional"],
                block["block_type"],
                block.get("block_name"),
                block.get("objective"),
                block.get("rounds"),
                block.get("rest_seconds"),
                block.get("discipline_family"),
                block.get("duration_min"),
                block.get("duration_max"),
                block.get("target_basis"),
                block.get("target_zone_min_code"),
                block.get("target_zone_max_code"),
                block.get("condition_key"),
                block.get("condition_value"),
                block.get("notes"),
            ),
        )
        prescription_block_id = int(block_cursor.lastrowid)
        for exercise in block.get("exercises", []):
            exercise_cursor = connection.execute(
                """
                INSERT INTO plan_prescription_exercises (
                    prescription_block_id, sequence_order, exercise_name, movement_pattern,
                    equipment, unilateral_mode, sets_count, reps_min, reps_max,
                    hold_seconds_min, hold_seconds_max, distance_meters, target_rpe_min,
                    target_rpe_max, target_rir_min, target_rir_max, tempo, load_guidance,
                    optional_flag, substitution_group, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prescription_block_id,
                    exercise["sequence_order"],
                    exercise["exercise_name"],
                    exercise.get("movement_pattern"),
                    exercise.get("equipment"),
                    exercise.get("unilateral_mode", "none"),
                    exercise.get("sets_count"),
                    exercise.get("reps_min"),
                    exercise.get("reps_max"),
                    exercise.get("hold_seconds_min"),
                    exercise.get("hold_seconds_max"),
                    exercise.get("distance_meters"),
                    exercise.get("target_rpe_min"),
                    exercise.get("target_rpe_max"),
                    exercise.get("target_rir_min"),
                    exercise.get("target_rir_max"),
                    exercise.get("tempo"),
                    exercise.get("load_guidance"),
                    exercise.get("optional_flag", 0),
                    exercise.get("substitution_group"),
                    exercise.get("notes"),
                ),
            )
            prescription_exercise_id = int(exercise_cursor.lastrowid)
            for option in exercise.get("options", []):
                connection.execute(
                    """
                    INSERT INTO plan_prescription_exercise_options (
                        prescription_exercise_id, sequence_order, option_name, equipment, condition_notes
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        prescription_exercise_id,
                        option["sequence_order"],
                        option["option_name"],
                        option.get("equipment"),
                        option.get("condition_notes"),
                    ),
                )


def get_planned_session_prescription(connection: sqlite3.Connection, planned_session_id: int) -> dict[str, Any] | None:
    prescription_row = connection.execute(
        """
        SELECT prescription_id, planned_session_id, prescription_type, discipline_family, title,
               focus_primary, focus_secondary, estimated_duration_min, estimated_duration_max,
               target_rpe_min, target_rpe_max, warmup_notes, cooldown_notes,
               execution_notes, adaptation_notes, source_kind, structure_version, source_markdown_path
        FROM plan_session_prescriptions
        WHERE planned_session_id = ?
        """,
        (planned_session_id,),
    ).fetchone()
    if prescription_row is None:
        return None

    block_rows = connection.execute(
        """
        SELECT prescription_block_id, prescription_id, sequence_order, block_role, relation_group,
               relation_mode, is_optional, block_type, block_name, objective, rounds,
               rest_seconds, discipline_family, duration_min, duration_max, target_basis,
               target_zone_min_code, target_zone_max_code, condition_key, condition_value, notes
        FROM plan_prescription_blocks
        WHERE prescription_id = ?
        ORDER BY relation_group, sequence_order
        """,
        (int(prescription_row["prescription_id"]),),
    ).fetchall()

    blocks: list[dict[str, Any]] = []
    for block_row in block_rows:
        block_id = int(block_row["prescription_block_id"])
        exercise_rows = connection.execute(
            """
            SELECT prescription_exercise_id, sequence_order, exercise_name, movement_pattern,
                   equipment, unilateral_mode, sets_count, reps_min, reps_max,
                   hold_seconds_min, hold_seconds_max, distance_meters, target_rpe_min,
                   target_rpe_max, target_rir_min, target_rir_max, tempo, load_guidance,
                   optional_flag, substitution_group, notes
            FROM plan_prescription_exercises
            WHERE prescription_block_id = ?
            ORDER BY sequence_order
            """,
            (block_id,),
        ).fetchall()
        exercises: list[dict[str, Any]] = []
        for exercise_row in exercise_rows:
            exercise_id = int(exercise_row["prescription_exercise_id"])
            option_rows = connection.execute(
                """
                SELECT exercise_option_id, sequence_order, option_name, equipment, condition_notes
                FROM plan_prescription_exercise_options
                WHERE prescription_exercise_id = ?
                ORDER BY sequence_order
                """,
                (exercise_id,),
            ).fetchall()
            exercise = dict(exercise_row)
            exercise["prescription_exercise_id"] = exercise_id
            exercise["options"] = [dict(option_row) for option_row in option_rows]
            exercises.append(exercise)

        block = dict(block_row)
        block["prescription_block_id"] = block_id
        block["exercises"] = exercises
        blocks.append(block)

    payload = dict(prescription_row)
    payload["prescription_id"] = int(prescription_row["prescription_id"])
    payload["planned_session_id"] = int(prescription_row["planned_session_id"])
    payload["blocks"] = blocks
    return payload


def build_structured_prescription(session_row: dict[str, Any]) -> dict[str, Any]:
    groups = build_legacy_activity_groups(session_row)
    blocks: list[dict[str, Any]] = []
    top_level_discipline_family: str | None = None
    global_sequence_order = 1
    for relation_group, group in enumerate(groups, start=1):
        for sequence_order, item in enumerate(group.get("items", []), start=1):
            if top_level_discipline_family is None and item.get("discipline_family") is not None:
                top_level_discipline_family = str(item.get("discipline_family"))
            blocks.append(
                {
                    "sequence_order": global_sequence_order,
                    "block_role": group.get("group_role") or "primary",
                    "relation_group": relation_group,
                    "relation_mode": group.get("relation_mode") or "all_of",
                    "is_optional": int(group.get("is_optional") or 0),
                    "block_type": item.get("item_type") or "other",
                    "block_name": _build_block_name(item),
                    "objective": session_row.get("objective") if sequence_order == 1 and relation_group == 1 else None,
                    "rounds": None,
                    "rest_seconds": None,
                    "discipline_family": item.get("discipline_family"),
                    "duration_min": item.get("duration_min"),
                    "duration_max": item.get("duration_max"),
                    "target_basis": item.get("target_basis"),
                    "target_zone_min_code": item.get("target_zone_min_code"),
                    "target_zone_max_code": item.get("target_zone_max_code"),
                    "condition_key": item.get("condition_key"),
                    "condition_value": item.get("condition_value"),
                    "notes": item.get("notes") or group.get("notes"),
                    "exercises": _build_block_exercises(item),
                }
            )
            global_sequence_order += 1

    return {
        "planned_session_id": int(session_row["planned_session_id"]),
        "prescription_type": str(session_row.get("planned_type") or "other"),
        "discipline_family": top_level_discipline_family,
        "title": session_row.get("primary_session"),
        "focus_primary": session_row.get("planned_role") or session_row.get("objective"),
        "focus_secondary": session_row.get("complementary_session"),
        "estimated_duration_min": session_row.get("duration_min"),
        "estimated_duration_max": session_row.get("duration_max"),
        "target_rpe_min": None,
        "target_rpe_max": None,
        "warmup_notes": None,
        "cooldown_notes": None,
        "execution_notes": session_row.get("notes"),
        "adaptation_notes": session_row.get("adjustment_rule"),
        "source_kind": "generated",
        "structure_version": "v1",
        "source_markdown_path": session_row.get("markdown_path"),
        "blocks": blocks,
    }


def _build_block_name(item: dict[str, Any]) -> str:
    label = str(item.get("display_label") or "").strip()
    if label:
        return label
    discipline_family = item.get("discipline_family")
    if discipline_family == "cycling":
        return "bicicleta"
    if discipline_family == "walking":
        return "paseo"
    if discipline_family == "running":
        return "carrera"
    return str(item.get("item_type") or "bloque")


def _build_block_exercises(item: dict[str, Any]) -> list[dict[str, Any]]:
    if item.get("item_type") != "strength":
        return []
    label = _build_block_name(item)
    return [
        {
            "sequence_order": 1,
            "exercise_name": label,
            "movement_pattern": None,
            "equipment": None,
            "unilateral_mode": "none",
            "sets_count": None,
            "reps_min": None,
            "reps_max": None,
            "hold_seconds_min": None,
            "hold_seconds_max": None,
            "distance_meters": None,
            "target_rpe_min": None,
            "target_rpe_max": None,
            "target_rir_min": None,
            "target_rir_max": None,
            "tempo": None,
            "load_guidance": None,
            "optional_flag": 0,
            "substitution_group": None,
            "notes": None,
            "options": [],
        }
    ]


def _prescription_signature(prescription: dict[str, Any] | None) -> dict[str, Any] | None:
    if prescription is None:
        return None
    return {
        "planned_session_id": prescription.get("planned_session_id"),
        "prescription_type": prescription.get("prescription_type"),
        "discipline_family": prescription.get("discipline_family"),
        "title": prescription.get("title"),
        "focus_primary": prescription.get("focus_primary"),
        "focus_secondary": prescription.get("focus_secondary"),
        "estimated_duration_min": prescription.get("estimated_duration_min"),
        "estimated_duration_max": prescription.get("estimated_duration_max"),
        "target_rpe_min": prescription.get("target_rpe_min"),
        "target_rpe_max": prescription.get("target_rpe_max"),
        "warmup_notes": prescription.get("warmup_notes"),
        "cooldown_notes": prescription.get("cooldown_notes"),
        "execution_notes": prescription.get("execution_notes"),
        "adaptation_notes": prescription.get("adaptation_notes"),
        "source_kind": prescription.get("source_kind"),
        "structure_version": prescription.get("structure_version"),
        "source_markdown_path": prescription.get("source_markdown_path"),
        "blocks": [
            {
                "sequence_order": block.get("sequence_order"),
                "block_role": block.get("block_role"),
                "relation_group": block.get("relation_group"),
                "relation_mode": block.get("relation_mode"),
                "is_optional": block.get("is_optional"),
                "block_type": block.get("block_type"),
                "block_name": block.get("block_name"),
                "objective": block.get("objective"),
                "rounds": block.get("rounds"),
                "rest_seconds": block.get("rest_seconds"),
                "discipline_family": block.get("discipline_family"),
                "duration_min": block.get("duration_min"),
                "duration_max": block.get("duration_max"),
                "target_basis": block.get("target_basis"),
                "target_zone_min_code": block.get("target_zone_min_code"),
                "target_zone_max_code": block.get("target_zone_max_code"),
                "condition_key": block.get("condition_key"),
                "condition_value": block.get("condition_value"),
                "notes": block.get("notes"),
                "exercises": [
                    {
                        "sequence_order": exercise.get("sequence_order"),
                        "exercise_name": exercise.get("exercise_name"),
                        "movement_pattern": exercise.get("movement_pattern"),
                        "equipment": exercise.get("equipment"),
                        "unilateral_mode": exercise.get("unilateral_mode"),
                        "sets_count": exercise.get("sets_count"),
                        "reps_min": exercise.get("reps_min"),
                        "reps_max": exercise.get("reps_max"),
                        "hold_seconds_min": exercise.get("hold_seconds_min"),
                        "hold_seconds_max": exercise.get("hold_seconds_max"),
                        "distance_meters": exercise.get("distance_meters"),
                        "target_rpe_min": exercise.get("target_rpe_min"),
                        "target_rpe_max": exercise.get("target_rpe_max"),
                        "target_rir_min": exercise.get("target_rir_min"),
                        "target_rir_max": exercise.get("target_rir_max"),
                        "tempo": exercise.get("tempo"),
                        "load_guidance": exercise.get("load_guidance"),
                        "optional_flag": exercise.get("optional_flag"),
                        "substitution_group": exercise.get("substitution_group"),
                        "notes": exercise.get("notes"),
                    }
                    for exercise in block.get("exercises", [])
                ],
            }
            for block in prescription.get("blocks", [])
        ],
    }