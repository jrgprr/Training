from __future__ import annotations

import sqlite3
from typing import Any

WALKING_DISCIPLINES = {"walking", "hiking", "trail_walking", "nordic_walking"}
CYCLING_DISCIPLINES = {"cycling", "road_biking", "indoor_cycling", "mountain_biking"}
RUNNING_DISCIPLINES = {"running", "trail_running", "treadmill_running", "track_running"}
STRENGTH_KEYWORDS = {
    "fuerza",
    "core",
    "pecho",
    "triceps",
    "hombro",
    "espalda",
    "biceps",
    "pierna",
    "piernas",
    "gluteo",
    "gluteos",
    "torso",
}
MOBILITY_KEYWORDS = {"yoga", "movilidad", "estiramientos", "flexibilidad", "elasticidad"}


def delete_planned_session_prescription(connection: sqlite3.Connection, planned_session_id: int) -> None:
    existing_row = connection.execute(
        "SELECT prescription_id FROM plan_session_prescriptions WHERE planned_session_id = ?",
        (planned_session_id,),
    ).fetchone()
    if existing_row is None:
        return

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


def replace_planned_session_prescription(connection: sqlite3.Connection, prescription: dict[str, Any]) -> None:
    planned_session_id = int(prescription["planned_session_id"])
    delete_planned_session_prescription(connection, planned_session_id)

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


def build_activity_groups_from_prescription(prescription: dict[str, Any] | None) -> list[dict[str, Any]]:
    if prescription is None:
        return []

    groups_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    groups: list[dict[str, Any]] = []
    for block in prescription.get("blocks", []):
        relation_group = int(block.get("relation_group") or 1)
        group_role = str(block.get("block_role") or "primary")
        group_key = (relation_group, group_role)
        group = groups_by_key.get(group_key)
        if group is None:
            group = {
                "activity_group_id": None,
                "planned_session_id": prescription.get("planned_session_id"),
                "group_role": group_role,
                "relation_group": relation_group,
                "relation_mode": block.get("relation_mode") or "all_of",
                "is_optional": int(block.get("is_optional") or 0),
                "summary_label": None,
                "notes": None,
                "items": [],
            }
            groups_by_key[group_key] = group
            groups.append(group)
        group["items"].append(
            {
                "activity_item_id": None,
                "sequence_order": int(block.get("sequence_order") or len(group["items"]) + 1),
                "item_type": block.get("block_type") or "other",
                "discipline_family": block.get("discipline_family"),
                "display_label": block.get("block_name"),
                "duration_min": block.get("duration_min"),
                "duration_max": block.get("duration_max"),
                "target_basis": block.get("target_basis"),
                "target_zone_min_code": block.get("target_zone_min_code"),
                "target_zone_max_code": block.get("target_zone_max_code"),
                "condition_key": block.get("condition_key"),
                "condition_value": block.get("condition_value"),
                "notes": block.get("notes"),
            }
        )
    return groups


def render_prescription_block(block: dict[str, Any]) -> str:
    label = str(block.get("block_name") or block.get("block_type") or "block").strip()
    zone_min = block.get("target_zone_min_code")
    zone_max = block.get("target_zone_max_code")
    duration_min = block.get("duration_min")
    duration_max = block.get("duration_max")

    parts = [label]
    if zone_min:
        if zone_min == zone_max or not zone_max:
            parts.append(str(zone_min))
        else:
            parts.append(f"{zone_min}-{zone_max}")
    if duration_min is not None and duration_max is not None:
        if duration_min == duration_max:
            parts.append(f"{duration_min} minutos")
        else:
            parts.append(f"{duration_min}-{duration_max} minutos")
    elif duration_min is not None:
        parts.append(f"{duration_min} minutos")
    return " ".join(str(part) for part in parts if part)


def render_prescription_summary(prescription: dict[str, Any] | None, *, group_role: str | None = None) -> str | None:
    if prescription is None:
        return None

    grouped_blocks: dict[int, list[dict[str, Any]]] = {}
    for block in prescription.get("blocks", []):
        if group_role is not None and str(block.get("block_role") or "primary") != group_role:
            continue
        grouped_blocks.setdefault(int(block.get("relation_group") or 1), []).append(block)

    rendered_groups: list[str] = []
    for relation_group in sorted(grouped_blocks):
        blocks = sorted(grouped_blocks[relation_group], key=lambda block: int(block.get("sequence_order") or 0))
        if not blocks:
            continue
        separator = " o " if str(blocks[0].get("relation_mode") or "all_of") == "one_of" else " + "
        rendered_groups.append(separator.join(render_prescription_block(block) for block in blocks))

    summary = " + ".join(part for part in rendered_groups if part)
    return summary or None


def derive_zone_target_from_prescription(prescription: dict[str, Any] | None) -> dict[str, Any] | None:
    if prescription is None:
        return None
    targeted_blocks = [
        block
        for block in prescription.get("blocks", [])
        if block.get("target_basis")
        and block.get("target_zone_min_code")
        and block.get("target_zone_max_code")
        and str(block.get("block_role") or "primary") == "primary"
    ]
    if not targeted_blocks:
        return None

    target_bases = list(dict.fromkeys(str(block["target_basis"]) for block in targeted_blocks))
    target_basis = target_bases[0] if len(target_bases) == 1 else "mixed"
    target_kind = "single_zone"
    if len(targeted_blocks) > 1:
        target_kind = "multi_segment"
    elif targeted_blocks[0].get("target_zone_min_code") != targeted_blocks[0].get("target_zone_max_code"):
        target_kind = "multi_segment"

    segments = []
    for index, block in enumerate(sorted(targeted_blocks, key=lambda item: int(item.get("sequence_order") or 0)), start=1):
        duration_min = block.get("duration_min")
        duration_max = block.get("duration_max")
        segments.append(
            {
                "sequence_order": index,
                "segment_label": block.get("block_name") or block.get("block_type") or f"Block {index}",
                "target_zone_min_code": block.get("target_zone_min_code"),
                "target_zone_max_code": block.get("target_zone_max_code"),
                "target_duration_seconds_min": int(duration_min) * 60 if duration_min is not None else None,
                "target_duration_seconds_max": int(duration_max) * 60 if duration_max is not None else None,
                "notes": block.get("notes"),
            }
        )

    return {
        "planned_session_id": prescription.get("planned_session_id"),
        "target_basis": target_basis,
        "target_kind": target_kind,
        "source_kind": "prescription",
        "comparison_eligibility": "eligible" if target_kind == "single_zone" and target_basis != "mixed" else "limited",
        "segments": segments,
    }


def derive_planned_role_from_prescription(session_row: dict[str, Any], prescription: dict[str, Any] | None) -> str:
    planned_type = str(session_row.get("planned_type") or "").strip().lower()
    is_key_session = int(session_row.get("is_key_session") or 0) == 1
    primary_blocks = [
        block
        for block in (prescription or {}).get("blocks", [])
        if str(block.get("block_role") or "primary") == "primary"
    ]
    zone_codes = {
        str(block.get("target_zone_min_code"))
        for block in primary_blocks
        if block.get("target_zone_min_code")
    }
    primary_families = {
        str(block.get("discipline_family"))
        for block in primary_blocks
        if block.get("discipline_family")
    }

    if planned_type == "descanso":
        return "descanso"
    if planned_type == "recuperacion":
        return "recuperacion"
    if planned_type == "activacion":
        return "activacion-neuromuscular"
    if planned_type == "fuerza":
        return "desarrollo-de-fuerza"
    if planned_type == "salida-larga":
        return "resistencia-aerobica-extensiva"
    if planned_type == "referencia-aerobica":
        return "resistencia-aerobica-principal"
    if planned_type == "intervals":
        return "potencia-aerobica"
    if planned_type == "bicicleta-aerobica":
        return "resistencia-aerobica-suave"
    if planned_type == "bicicleta-z2":
        return "resistencia-aerobica-principal" if is_key_session else "resistencia-aerobica-secundaria"
    if planned_type == "complementaria":
        if zone_codes & {"Z4", "Z5"}:
            return "potencia-aerobica"
        if "Z2" in zone_codes:
            return "resistencia-aerobica-secundaria"
        return "resistencia-aerobica-suave"

    if zone_codes & {"Z4", "Z5"}:
        return "potencia-aerobica"
    if "Z2" in zone_codes:
        return "resistencia-aerobica-principal" if is_key_session else "resistencia-aerobica-secundaria"
    if "Z1" in zone_codes:
        return "recuperacion"
    if "strength_training" in primary_families:
        return "desarrollo-de-fuerza"
    return "resistencia-aerobica-principal" if is_key_session else "resistencia-aerobica-suave"


def project_planned_session_row_from_prescription(session_row: dict[str, Any], prescription: dict[str, Any] | None) -> dict[str, Any]:
    projected = dict(session_row)
    if prescription is None:
        projected.setdefault("planned_prescription", None)
        projected.setdefault("planned_activity_groups", [])
        return projected

    projected["planned_prescription"] = prescription
    projected["planned_activity_groups"] = build_activity_groups_from_prescription(prescription)
    if projected.get("duration_min") is None and prescription.get("estimated_duration_min") is not None:
        projected["duration_min"] = prescription.get("estimated_duration_min")
    if projected.get("duration_max") is None and prescription.get("estimated_duration_max") is not None:
        projected["duration_max"] = prescription.get("estimated_duration_max")
    target = derive_zone_target_from_prescription(prescription)
    if target is not None:
        projected["target_basis"] = target.get("target_basis")
        projected["target_kind"] = target.get("target_kind")
        projected["comparison_eligibility"] = target.get("comparison_eligibility")
    return projected


def collect_matching_family_groups(connection: sqlite3.Connection, session_row: dict[str, Any]) -> list[set[str]]:
    planned_session_id = int(session_row["planned_session_id"])
    prescription = get_planned_session_prescription(connection, planned_session_id)
    if prescription is None:
        return []
    groups = build_activity_groups_from_prescription(prescription)
    matching_groups: list[set[str]] = []
    for group in groups:
        families = {
            str(item["discipline_family"])
            for item in group["items"]
            if item.get("discipline_family") in {"cycling", "walking", "running", "strength_training", "yoga"}
        }
        if families:
            matching_groups.append(families)
    return matching_groups


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