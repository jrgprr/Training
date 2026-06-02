from __future__ import annotations

from typing import Any

from .db import get_connection


TREND_READY_EFFORT_COUNT = 2


def _missing_metrics(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for metric_name in ("avg_power", "avg_cadence", "avg_heart_rate", "max_heart_rate"):
        if row.get(metric_name) is None:
            missing.append(metric_name)
    return missing


def list_segments(season_id: int, query: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    search = f"%{(query or '').strip().lower()}%"
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT s.segment_id,
                   s.source_system,
                   s.external_segment_id,
                   s.segment_name,
                   s.discipline,
                   COUNT(se.segment_effort_id) AS effort_count,
                     SUM(CASE WHEN se.elapsed_time_seconds IS NOT NULL THEN 1 ELSE 0 END) AS comparable_effort_count,
                   MIN(se.activity_date) AS first_activity_date,
                   MAX(se.activity_date) AS last_activity_date,
                   MIN(se.elapsed_time_seconds) AS best_elapsed_time_seconds,
                   (
                       SELECT se_latest.elapsed_time_seconds
                       FROM exec_segment_efforts se_latest
                       WHERE se_latest.segment_id = s.segment_id
                       ORDER BY se_latest.activity_date DESC, se_latest.segment_effort_id DESC
                       LIMIT 1
                   ) AS latest_elapsed_time_seconds,
                   SUM(CASE WHEN se.avg_power IS NULL THEN 1 ELSE 0 END) AS missing_avg_power_count,
                   SUM(CASE WHEN se.avg_cadence IS NULL THEN 1 ELSE 0 END) AS missing_avg_cadence_count,
                   SUM(CASE WHEN se.avg_heart_rate IS NULL THEN 1 ELSE 0 END) AS missing_avg_heart_rate_count
            FROM exec_segments s
            JOIN exec_segment_efforts se ON se.segment_id = s.segment_id
            JOIN exec_activities ea ON ea.activity_id = se.activity_id
            WHERE ea.season_id = ?
              AND (? = '%%' OR lower(COALESCE(s.segment_name, '')) LIKE ?)
            GROUP BY s.segment_id, s.source_system, s.external_segment_id, s.segment_name, s.discipline
            ORDER BY last_activity_date DESC, effort_count DESC, s.segment_id DESC
            LIMIT ?
            """,
            (season_id, search, search, limit),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["missing_metric_counts"] = {
            "avg_power": item.pop("missing_avg_power_count"),
            "avg_cadence": item.pop("missing_avg_cadence_count"),
            "avg_heart_rate": item.pop("missing_avg_heart_rate_count"),
        }
        items.append(item)
    return items


def get_segment_history(segment_id: int, limit: int = 20) -> dict[str, Any] | None:
    with get_connection() as connection:
        segment_row = connection.execute(
            """
            SELECT segment_id, source_system, external_segment_id, segment_name, discipline,
                   distance_meters, ascent_meters, average_grade_percent
            FROM exec_segments
            WHERE segment_id = ?
            """,
            (segment_id,),
        ).fetchone()
        if segment_row is None:
            return None

        effort_rows = connection.execute(
            """
            SELECT *
            FROM (
                SELECT se.segment_effort_id,
                       se.activity_id,
                       ea.external_activity_id,
                       se.activity_date,
                       se.started_at,
                       se.elapsed_time_seconds,
                       se.avg_power,
                       se.avg_cadence,
                       se.avg_heart_rate,
                       se.max_heart_rate,
                       se.notes
                FROM exec_segment_efforts se
                JOIN exec_activities ea ON ea.activity_id = se.activity_id
                WHERE se.segment_id = ?
                ORDER BY se.activity_date DESC, se.segment_effort_id DESC
                LIMIT ?
            ) recent_efforts
            ORDER BY activity_date ASC, segment_effort_id ASC
            """,
            (segment_id, limit),
        ).fetchall()

    efforts = [dict(row) for row in effort_rows]
    if not efforts:
        return {
            "segment": dict(segment_row),
            "summary": {
                "effort_count": 0,
                "comparable_effort_count": 0,
                "membership_only_count": 0,
                "best_effort_id": None,
                "latest_effort_id": None,
                "trend_status": "insufficient_data",
                "recent_window_size": 0,
                "available_metric_names": [],
                "missing_metric_names": [],
            },
            "efforts": [],
        }

    best_effort = min(
        (effort for effort in efforts if effort.get("elapsed_time_seconds") is not None),
        key=lambda effort: effort["elapsed_time_seconds"],
        default=None,
    )
    latest_effort = efforts[-1]
    comparable_efforts = [effort for effort in efforts if effort.get("elapsed_time_seconds") is not None]
    available_metric_names: list[str] = []
    if comparable_efforts:
        available_metric_names.append("elapsed_time_seconds")
    for metric_name in ("avg_power", "avg_cadence", "avg_heart_rate", "max_heart_rate"):
        if any(effort.get(metric_name) is not None for effort in efforts):
            available_metric_names.append(metric_name)

    missing_metric_names = sorted({metric for effort in efforts for metric in _missing_metrics(effort)})
    previous_effort: dict[str, Any] | None = None
    for effort in efforts:
        effort["missing_metrics"] = _missing_metrics(effort)
        effort["is_best_effort"] = bool(best_effort and effort["segment_effort_id"] == best_effort["segment_effort_id"])
        effort["is_latest_effort"] = effort["segment_effort_id"] == latest_effort["segment_effort_id"]
        if best_effort and effort.get("elapsed_time_seconds") is not None and best_effort.get("elapsed_time_seconds") is not None:
            effort["delta_vs_best_seconds"] = effort["elapsed_time_seconds"] - best_effort["elapsed_time_seconds"]
        else:
            effort["delta_vs_best_seconds"] = None
        if (
            previous_effort is not None
            and effort.get("elapsed_time_seconds") is not None
            and previous_effort.get("elapsed_time_seconds") is not None
        ):
            effort["delta_vs_previous_seconds"] = effort["elapsed_time_seconds"] - previous_effort["elapsed_time_seconds"]
        else:
            effort["delta_vs_previous_seconds"] = None
        previous_effort = effort

    trend_status = "insufficient_data"
    if len(efforts) >= TREND_READY_EFFORT_COUNT:
        if len(comparable_efforts) >= TREND_READY_EFFORT_COUNT:
            latest_time = comparable_efforts[-1]["elapsed_time_seconds"]
            previous_time = comparable_efforts[-2]["elapsed_time_seconds"]
            if latest_time < previous_time:
                trend_status = "improving"
            elif latest_time > previous_time:
                trend_status = "declining"
            else:
                trend_status = "stable"

    return {
        "segment": dict(segment_row),
        "summary": {
            "effort_count": len(efforts),
            "comparable_effort_count": len(comparable_efforts),
            "membership_only_count": len(efforts) - len(comparable_efforts),
            "best_effort_id": best_effort["segment_effort_id"] if best_effort else None,
            "latest_effort_id": latest_effort["segment_effort_id"],
            "trend_status": trend_status,
            "recent_window_size": min(3, len(efforts)),
            "available_metric_names": available_metric_names,
            "missing_metric_names": missing_metric_names,
        },
        "efforts": efforts,
    }