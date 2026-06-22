from __future__ import annotations

import re
import sqlite3
from typing import Any


PLANNED_SESSION_STRUCTURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS plan_session_activity_groups (
    activity_group_id INTEGER PRIMARY KEY,
    planned_session_id INTEGER NOT NULL,
    group_role TEXT NOT NULL,
    relation_group INTEGER NOT NULL,
    relation_mode TEXT NOT NULL DEFAULT 'one_of',
    is_optional INTEGER NOT NULL DEFAULT 0,
    summary_label TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (planned_session_id, relation_group),
    FOREIGN KEY (planned_session_id) REFERENCES plan_planned_sessions (planned_session_id)
);

CREATE TABLE IF NOT EXISTS plan_session_activity_items (
    activity_item_id INTEGER PRIMARY KEY,
    activity_group_id INTEGER NOT NULL,
    sequence_order INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    discipline_family TEXT,
    display_label TEXT,
    duration_min INTEGER,
    duration_max INTEGER,
    target_basis TEXT,
    target_zone_min_code TEXT,
    target_zone_max_code TEXT,
    condition_key TEXT,
    condition_value TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_group_id, sequence_order),
    FOREIGN KEY (activity_group_id) REFERENCES plan_session_activity_groups (activity_group_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_session_activity_groups_session ON plan_session_activity_groups (planned_session_id, relation_group);
CREATE INDEX IF NOT EXISTS idx_plan_session_activity_items_group ON plan_session_activity_items (activity_group_id, sequence_order);
"""

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
REST_KEYWORDS = {"descanso", "descanso activo"}


def normalize_discipline_family(discipline: str | None) -> str | None:
    normalized = (discipline or "").strip().lower()
    if normalized in CYCLING_DISCIPLINES:
        return "cycling"
    if normalized in WALKING_DISCIPLINES:
        return "walking"
    if normalized in RUNNING_DISCIPLINES:
        return "running"
    if normalized == "strength_training":
        return "strength_training"
    if normalized == "yoga":
        return "yoga"
    return normalized or None


def ensure_planned_session_structure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(PLANNED_SESSION_STRUCTURE_SCHEMA)


def sync_all_planned_session_structures(connection: sqlite3.Connection) -> None:
    session_table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plan_planned_sessions'"
    ).fetchone()
    if session_table_exists is None:
        return

    rows = connection.execute(
        """
        SELECT planned_session_id, planned_type, primary_session, complementary_session,
               objective, duration_min, duration_max, intensity_class
        FROM plan_planned_sessions
        ORDER BY planned_session_id
        """
    ).fetchall()
    for row in rows:
        ensure_planned_session_structure(connection, dict(row))


def delete_planned_session_structure(connection: sqlite3.Connection, planned_session_id: int) -> None:
    connection.execute(
        "DELETE FROM plan_session_activity_items WHERE activity_group_id IN (SELECT activity_group_id FROM plan_session_activity_groups WHERE planned_session_id = ?)",
        (planned_session_id,),
    )
    connection.execute(
        "DELETE FROM plan_session_activity_groups WHERE planned_session_id = ?",
        (planned_session_id,),
    )


def replace_planned_session_structure(connection: sqlite3.Connection, session_row: dict[str, Any]) -> None:
    delete_planned_session_structure(connection, int(session_row["planned_session_id"]))
    _insert_planned_session_structure(connection, session_row)


def sync_planned_session_structure(connection: sqlite3.Connection, session_row: dict[str, Any]) -> None:
    planned_session_id = int(session_row["planned_session_id"])
    existing = get_planned_session_activity_groups(connection, planned_session_id)
    expected = build_legacy_activity_groups(session_row)
    if _planned_session_groups_signature(existing) == _planned_session_groups_signature(expected):
        return
    replace_planned_session_structure(connection, session_row)


def ensure_planned_session_structure(connection: sqlite3.Connection, session_row: dict[str, Any]) -> None:
    existing = connection.execute(
        "SELECT 1 FROM plan_session_activity_groups WHERE planned_session_id = ? LIMIT 1",
        (session_row["planned_session_id"],),
    ).fetchone()
    if existing is not None:
        return

    _insert_planned_session_structure(connection, session_row)


def _insert_planned_session_structure(connection: sqlite3.Connection, session_row: dict[str, Any]) -> None:

    groups = build_legacy_activity_groups(session_row)
    for group_index, group in enumerate(groups, start=1):
        cursor = connection.execute(
            """
            INSERT INTO plan_session_activity_groups (
                planned_session_id, group_role, relation_group, relation_mode,
                is_optional, summary_label, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_row["planned_session_id"],
                group["group_role"],
                group_index,
                group["relation_mode"],
                group["is_optional"],
                group.get("summary_label"),
                group.get("notes"),
            ),
        )
        activity_group_id = int(cursor.lastrowid)
        for sequence_order, item in enumerate(group["items"], start=1):
            connection.execute(
                """
                INSERT INTO plan_session_activity_items (
                    activity_group_id, sequence_order, item_type, discipline_family,
                    display_label, duration_min, duration_max, target_basis,
                    target_zone_min_code, target_zone_max_code, condition_key,
                    condition_value, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity_group_id,
                    sequence_order,
                    item["item_type"],
                    item.get("discipline_family"),
                    item.get("display_label"),
                    item.get("duration_min"),
                    item.get("duration_max"),
                    item.get("target_basis"),
                    item.get("target_zone_min_code"),
                    item.get("target_zone_max_code"),
                    item.get("condition_key"),
                    item.get("condition_value"),
                    item.get("notes"),
                ),
            )


def get_planned_session_activity_groups(connection: sqlite3.Connection, planned_session_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT psag.activity_group_id, psag.planned_session_id, psag.group_role,
               psag.relation_group, psag.relation_mode, psag.is_optional,
               psag.summary_label, psag.notes,
               psai.activity_item_id, psai.sequence_order, psai.item_type,
               psai.discipline_family, psai.display_label, psai.duration_min,
               psai.duration_max, psai.target_basis, psai.target_zone_min_code,
               psai.target_zone_max_code, psai.condition_key, psai.condition_value,
               psai.notes AS item_notes
        FROM plan_session_activity_groups psag
        JOIN plan_session_activity_items psai ON psai.activity_group_id = psag.activity_group_id
        WHERE psag.planned_session_id = ?
        ORDER BY psag.relation_group, psai.sequence_order
        """,
        (planned_session_id,),
    ).fetchall()
    groups: list[dict[str, Any]] = []
    groups_by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        activity_group_id = int(row["activity_group_id"])
        group = groups_by_id.get(activity_group_id)
        if group is None:
            group = {
                "activity_group_id": activity_group_id,
                "planned_session_id": int(row["planned_session_id"]),
                "group_role": row["group_role"],
                "relation_group": int(row["relation_group"]),
                "relation_mode": row["relation_mode"],
                "is_optional": int(row["is_optional"]),
                "summary_label": row["summary_label"],
                "notes": row["notes"],
                "items": [],
            }
            groups_by_id[activity_group_id] = group
            groups.append(group)
        group["items"].append(
            {
                "activity_item_id": int(row["activity_item_id"]),
                "sequence_order": int(row["sequence_order"]),
                "item_type": row["item_type"],
                "discipline_family": row["discipline_family"],
                "display_label": row["display_label"],
                "duration_min": row["duration_min"],
                "duration_max": row["duration_max"],
                "target_basis": row["target_basis"],
                "target_zone_min_code": row["target_zone_min_code"],
                "target_zone_max_code": row["target_zone_max_code"],
                "condition_key": row["condition_key"],
                "condition_value": row["condition_value"],
                "notes": row["item_notes"],
            }
        )
    return groups


def _planned_session_groups_signature(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signature: list[dict[str, Any]] = []
    for group in groups:
        signature.append(
            {
                "group_role": group.get("group_role"),
                "relation_mode": group.get("relation_mode"),
                "is_optional": int(group.get("is_optional") or 0),
                "summary_label": group.get("summary_label"),
                "notes": group.get("notes"),
                "items": [
                    {
                        "item_type": item.get("item_type"),
                        "discipline_family": item.get("discipline_family"),
                        "display_label": item.get("display_label"),
                        "duration_min": item.get("duration_min"),
                        "duration_max": item.get("duration_max"),
                        "target_basis": item.get("target_basis"),
                        "target_zone_min_code": item.get("target_zone_min_code"),
                        "target_zone_max_code": item.get("target_zone_max_code"),
                        "condition_key": item.get("condition_key"),
                        "condition_value": item.get("condition_value"),
                        "notes": item.get("notes"),
                    }
                    for item in group.get("items", [])
                ],
            }
        )
    return signature


def build_legacy_activity_groups(session_row: dict[str, Any]) -> list[dict[str, Any]]:
    planned_type = str(session_row.get("planned_type") or "").strip().lower()
    primary_session = str(session_row.get("primary_session") or "").strip()
    complementary_session = str(session_row.get("complementary_session") or "").strip()
    objective = str(session_row.get("objective") or "").strip()
    duration_min = _as_int(session_row.get("duration_min"))
    duration_max = _as_int(session_row.get("duration_max"))

    groups: list[dict[str, Any]] = []
    primary_items = _build_primary_items(
        planned_type=planned_type,
        primary_session=primary_session,
        duration_min=duration_min,
        duration_max=duration_max,
    )
    if primary_items:
        groups.append(
            {
                "group_role": "primary",
                "relation_mode": "one_of",
                "is_optional": 0,
                "summary_label": None,
                "notes": None,
                "items": primary_items,
            }
        )

    support_items = _build_support_items(
        planned_type=planned_type,
        complementary_session=complementary_session,
        objective=objective,
    )
    if support_items:
        groups.append(
            {
                "group_role": "support",
                "relation_mode": "one_of" if len(support_items) > 1 else "all_of",
                "is_optional": 1,
                "summary_label": None,
                "notes": None,
                "items": support_items,
            }
        )
    return groups


def collect_matching_family_groups(connection: sqlite3.Connection, session_row: dict[str, Any]) -> list[set[str]]:
    ensure_planned_session_structure(connection, session_row)
    groups = get_planned_session_activity_groups(connection, int(session_row["planned_session_id"]))
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


def _build_primary_items(
    *,
    planned_type: str,
    primary_session: str,
    duration_min: int | None,
    duration_max: int | None,
) -> list[dict[str, Any]]:
    if planned_type == "fuerza":
        return [_activity_item("strength", "strength_training", primary_session or "fuerza", duration_min, duration_max)]

    if planned_type in {"bicicleta-z2", "salida-larga", "referencia-aerobica"}:
        target_zone = "Z2" if planned_type in {"bicicleta-z2", "referencia-aerobica"} else None
        return [_activity_item("endurance", "cycling", "bicicleta", duration_min, duration_max, target_zone=target_zone)]

    inferred = _ordered_primary_families(primary_session)
    if not inferred:
        inferred = _fallback_primary_families(planned_type)

    items: list[dict[str, Any]] = []
    for family in inferred:
        if family == "walking":
            items.append(_activity_item("endurance", family, "paseo", duration_min, duration_max))
        elif family == "cycling":
            target_zone = "Z1" if planned_type in {"recuperacion", "activacion"} else None
            items.append(_activity_item("endurance", family, "bicicleta", duration_min, duration_max, target_zone=target_zone))
        elif family == "running":
            items.append(_activity_item("endurance", family, "carrera", duration_min, duration_max))
        elif family == "rest":
            items.append(_activity_item("rest", None, "descanso activo", None, None))
    return items


def _build_support_items(*, planned_type: str, complementary_session: str, objective: str) -> list[dict[str, Any]]:
    if planned_type == "fuerza":
        return []

    support_text = " ".join(part for part in [complementary_session, objective] if part).strip().lower()
    if not support_text:
        return []

    duration_min, duration_max = _extract_duration_range(complementary_session)
    items: list[dict[str, Any]] = []
    if any(keyword in support_text for keyword in STRENGTH_KEYWORDS):
        items.append(_activity_item("strength", "strength_training", complementary_session or "fuerza", duration_min, duration_max))
    if any(keyword in support_text for keyword in MOBILITY_KEYWORDS):
        mobility_label = complementary_session or "movilidad"
        if not items or normalize_discipline_family(items[0].get("discipline_family")) != "yoga":
            items.append(_activity_item("mobility", "yoga", mobility_label, duration_min, duration_max))
    return items


def _activity_item(
    item_type: str,
    discipline_family: str | None,
    display_label: str,
    duration_min: int | None,
    duration_max: int | None,
    *,
    target_zone: str | None = None,
) -> dict[str, Any]:
    return {
        "item_type": item_type,
        "discipline_family": discipline_family,
        "display_label": display_label,
        "duration_min": duration_min,
        "duration_max": duration_max,
        "target_basis": "heart_rate" if target_zone is not None else None,
        "target_zone_min_code": target_zone,
        "target_zone_max_code": target_zone,
        "condition_key": None,
        "condition_value": None,
        "notes": None,
    }


def _ordered_primary_families(primary_session: str) -> list[str]:
    normalized = primary_session.lower()
    families: list[str] = []
    candidates = [
        (normalized.find("paseo"), "walking"),
        (normalized.find("caminar"), "walking"),
        (normalized.find("monte"), "walking"),
        (normalized.find("sender"), "walking"),
        (normalized.find("bicicleta"), "cycling"),
        (normalized.find("bici"), "cycling"),
        (normalized.find("correr"), "running"),
        (normalized.find("running"), "running"),
        (normalized.find("descanso"), "rest"),
    ]
    for _, family in sorted((match for match in candidates if match[0] >= 0), key=lambda item: item[0]):
        if family not in families:
            families.append(family)
    return families


def _fallback_primary_families(planned_type: str) -> list[str]:
    if planned_type in {"activacion", "recuperacion"}:
        return ["walking", "cycling", "rest"]
    if planned_type == "complementaria":
        return ["walking", "cycling"]
    return []


def _extract_duration_range(text: str) -> tuple[int | None, int | None]:
    if not text:
        return (None, None)
    range_match = re.search(r"(\d{1,3})\s*-\s*(\d{1,3})\s*min", text.lower())
    if range_match is not None:
        return (int(range_match.group(1)), int(range_match.group(2)))
    single_match = re.search(r"(\d{1,3})\s*min", text.lower())
    if single_match is not None:
        value = int(single_match.group(1))
        return (value, value)
    return (None, None)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)