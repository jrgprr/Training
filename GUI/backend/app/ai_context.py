from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .ai_assessment_models import AssessmentCadence
from .db import get_connection


@dataclass(frozen=True)
class AssessmentContextWindow:
    cadence: AssessmentCadence
    season_id: int
    block_id: int | None
    week_id: int | None
    window_start_date: str
    window_end_date: str
    subject_scope_key: str


@dataclass(frozen=True)
class AssessmentContextSnapshot:
    window: AssessmentContextWindow
    evidence_fingerprint: str
    context: dict[str, Any]


def _fetch_one(connection, query: str, parameters: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = connection.execute(query, parameters).fetchone()
    return dict(row) if row else None


def _fetch_all(connection, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def _infer_week_row(connection, season_id: int, window_start_date: str, window_end_date: str) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT w.week_id,
               w.week_code,
               w.block_id,
               w.start_date,
               w.end_date,
               w.week_role,
               w.objective_primary,
               b.block_code,
               b.block_name
        FROM plan_micro_weeks w
        JOIN plan_meso_blocks b ON b.block_id = w.block_id
        WHERE b.season_id = ?
          AND w.start_date <= ?
          AND w.end_date >= ?
        ORDER BY w.start_date
        LIMIT 1
        """,
        (season_id, window_start_date, window_end_date),
    )


def _resolve_block_row(connection, season_id: int, block_id: int | None, window_start_date: str, window_end_date: str) -> dict[str, Any] | None:
    if block_id is not None:
        return _fetch_one(
            connection,
            """
            SELECT block_id, block_code, block_name, phase_name, start_date, end_date, objective_primary
            FROM plan_meso_blocks
            WHERE season_id = ? AND block_id = ?
            """,
            (season_id, block_id),
        )
    return _fetch_one(
        connection,
        """
        SELECT block_id, block_code, block_name, phase_name, start_date, end_date, objective_primary
        FROM plan_meso_blocks
        WHERE season_id = ?
          AND COALESCE(start_date, ?) <= ?
          AND COALESCE(end_date, ?) >= ?
        ORDER BY sequence_order
        LIMIT 1
        """,
        (season_id, window_start_date, window_end_date, window_end_date, window_start_date),
    )


def _resolve_week_row(
    connection,
    season_id: int,
    week_id: int | None,
    window_start_date: str,
    window_end_date: str,
) -> dict[str, Any] | None:
    if week_id is not None:
        return _fetch_one(
            connection,
            """
            SELECT w.week_id,
                   w.week_code,
                   w.block_id,
                   w.start_date,
                   w.end_date,
                   w.week_role,
                   w.objective_primary,
                   b.block_code,
                   b.block_name
            FROM plan_micro_weeks w
            JOIN plan_meso_blocks b ON b.block_id = w.block_id
            WHERE b.season_id = ? AND w.week_id = ?
            """,
            (season_id, week_id),
        )
    return _infer_week_row(connection, season_id, window_start_date, window_end_date)


def _build_subject_scope_key(
    cadence: AssessmentCadence,
    season: dict[str, Any] | None,
    block_row: dict[str, Any] | None,
    week_row: dict[str, Any] | None,
    window_start_date: str,
    window_end_date: str,
) -> str:
    if cadence is AssessmentCadence.DAILY:
        return f"day:{window_start_date}"
    if cadence is AssessmentCadence.WEEKLY:
        if week_row is not None:
            return f"week:{week_row['week_code']}"
        return f"week:{window_start_date}:{window_end_date}"
    if cadence is AssessmentCadence.BLOCK:
        if block_row is not None:
            return f"block:{block_row['block_code']}"
        return f"block:{window_start_date}:{window_end_date}"
    if season is not None:
        return f"season:{season['season_code']}"
    return f"season:{window_start_date}:{window_end_date}"


def _get_season_row(connection, season_id: int) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT season_id, season_code, season_name, start_date, end_date, status
        FROM plan_seasons
        WHERE season_id = ?
        """,
        (season_id,),
    )


def _get_planned_sessions(connection, week_id: int | None, window_start_date: str, window_end_date: str) -> list[dict[str, Any]]:
    if week_id is not None:
        return _fetch_all(
            connection,
            """
            SELECT planned_session_id, week_id, session_date, day_name, sequence_in_week,
                   planned_type, objective, primary_session, complementary_session,
                   notes, is_key_session, intensity_class, duration_min, duration_max
            FROM plan_planned_sessions
            WHERE week_id = ?
            ORDER BY session_date, sequence_in_week
            """,
            (week_id,),
        )
    return _fetch_all(
        connection,
        """
        SELECT planned_session_id, week_id, session_date, day_name, sequence_in_week,
               planned_type, objective, primary_session, complementary_session,
               notes, is_key_session, intensity_class, duration_min, duration_max
        FROM plan_planned_sessions
        WHERE session_date BETWEEN ? AND ?
        ORDER BY session_date, sequence_in_week
        """,
        (window_start_date, window_end_date),
    )


def _get_activities(connection, season_id: int, window_start_date: str, window_end_date: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT ea.activity_id,
               ea.season_id,
               ea.source_system,
               ea.external_activity_id,
               ea.activity_date,
               ea.started_at,
               ea.discipline,
               ea.activity_type,
               ea.duration_seconds,
               ea.distance_meters,
               ea.ascent_meters,
               ea.calories,
               ea.avg_hr,
               ea.max_hr,
               ea.avg_power,
               ea.normalized_power,
               ea.training_load,
               ea.avg_pace_seconds_per_km,
               ea.segment_data_status,
               ea.segment_effort_count,
               ea.segment_checked_at,
               ea.quality_status,
               ea.quality_checked_at,
               ea.quality_rule_version,
               ea.quality_decision_count,
               ea.quality_limited_metric_count,
               ea.perceived_exertion,
               ea.subjective_feeling,
               ea.notes,
               l.planned_session_id,
               l.link_type,
               l.compliance_status,
               l.rationale,
               rr.actual_summary,
               rr.general_feeling,
               rr.next_day_decision
        FROM exec_activities ea
        LEFT JOIN link_plan_execution l ON l.activity_id = ea.activity_id
        LEFT JOIN review_daily_reviews rr
               ON rr.planned_session_id = l.planned_session_id
              AND rr.review_date = ea.activity_date
        WHERE ea.season_id = ?
          AND ea.activity_date BETWEEN ? AND ?
        ORDER BY ea.activity_date, COALESCE(ea.started_at, ea.activity_date), ea.activity_id
        """,
        (season_id, window_start_date, window_end_date),
    )


def _get_daily_metrics(connection, season_id: int, window_start_date: str, window_end_date: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT daily_metric_id,
               season_id,
               metric_date,
               source_system,
               weight_kg,
               sleep_hours,
               sleep_quality,
               resting_hr,
               hrv,
               body_battery,
               subjective_energy,
               subjective_fatigue,
               soreness,
               notes
        FROM exec_daily_metrics
        WHERE season_id = ?
          AND metric_date BETWEEN ? AND ?
        ORDER BY metric_date, source_system
        """,
        (season_id, window_start_date, window_end_date),
    )


def _get_daily_reviews(connection, season_id: int, window_start_date: str, window_end_date: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT daily_review_id,
               season_id,
               review_date,
               block_id,
               week_id,
               planned_session_id,
               planned_summary,
               actual_summary,
               compliance_status,
               general_feeling,
               perceived_recovery,
               motivation,
               observations,
               next_day_decision
        FROM review_daily_reviews
        WHERE season_id = ?
          AND review_date BETWEEN ? AND ?
        ORDER BY review_date, daily_review_id
        """,
        (season_id, window_start_date, window_end_date),
    )


def _get_weekly_review(connection, week_id: int | None) -> dict[str, Any] | None:
    if week_id is None:
        return None
    return _fetch_one(
        connection,
        """
        SELECT weekly_review_id,
               season_id,
               block_id,
               week_id,
               review_status,
               closed_at,
               adherence_rate,
               traceability_rate,
               actual_minutes,
               planned_reference_minutes,
               volume_delta_minutes,
               risk_level,
               recommendation_text,
               summary_text,
               created_at,
               updated_at
        FROM review_weekly_reviews
        WHERE week_id = ?
        """,
        (week_id,),
    )


def _get_segment_summary(connection, season_id: int, window_start_date: str, window_end_date: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT s.segment_id,
               s.segment_name,
               s.discipline,
               COUNT(se.segment_effort_id) AS effort_count,
               MIN(se.elapsed_time_seconds) AS best_elapsed_time_seconds,
               MAX(se.activity_date) AS latest_activity_date
        FROM exec_segments s
        JOIN exec_segment_efforts se ON se.segment_id = s.segment_id
        JOIN exec_activities ea ON ea.activity_id = se.activity_id
        WHERE ea.season_id = ?
          AND se.activity_date BETWEEN ? AND ?
        GROUP BY s.segment_id, s.segment_name, s.discipline
        ORDER BY latest_activity_date DESC, effort_count DESC, s.segment_id DESC
        LIMIT 12
        """,
        (season_id, window_start_date, window_end_date),
    )


def _build_context_payload(
    connection,
    cadence: AssessmentCadence,
    season_id: int,
    block_id: int | None,
    week_id: int | None,
    window_start_date: str,
    window_end_date: str,
) -> AssessmentContextSnapshot:
    season = _get_season_row(connection, season_id)
    if cadence is AssessmentCadence.SEASON:
        week_row = None
        block_row = _resolve_block_row(connection, season_id, block_id, window_start_date, window_end_date) if block_id is not None else None
        resolved_week_id = week_id
    else:
        week_row = _resolve_week_row(connection, season_id, week_id, window_start_date, window_end_date)
        resolved_block_id = block_id or (week_row["block_id"] if week_row is not None else None)
        block_row = _resolve_block_row(connection, season_id, resolved_block_id, window_start_date, window_end_date)
        resolved_week_id = week_row["week_id"] if week_row is not None else week_id
    subject_scope_key = _build_subject_scope_key(cadence, season, block_row, week_row, window_start_date, window_end_date)

    context = {
        "season": season,
        "block": block_row,
        "week": week_row,
        "planned_sessions": _get_planned_sessions(connection, resolved_week_id if cadence is AssessmentCadence.WEEKLY else None, window_start_date, window_end_date),
        "activities": _get_activities(connection, season_id, window_start_date, window_end_date),
        "daily_metrics": _get_daily_metrics(connection, season_id, window_start_date, window_end_date),
        "daily_reviews": _get_daily_reviews(connection, season_id, window_start_date, window_end_date),
        "weekly_review": _get_weekly_review(connection, resolved_week_id),
        "segment_summary": _get_segment_summary(connection, season_id, window_start_date, window_end_date),
    }

    evidence_fingerprint = hashlib.sha1(
        json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    return AssessmentContextSnapshot(
        window=AssessmentContextWindow(
            cadence=cadence,
            season_id=season_id,
            block_id=block_row["block_id"] if block_row is not None else None,
            week_id=resolved_week_id,
            window_start_date=window_start_date,
            window_end_date=window_end_date,
            subject_scope_key=subject_scope_key,
        ),
        evidence_fingerprint=evidence_fingerprint,
        context=context,
    )


def build_assessment_context(
    cadence: AssessmentCadence,
    season_id: int,
    window_start_date: str,
    window_end_date: str,
    block_id: int | None = None,
    week_id: int | None = None,
) -> AssessmentContextSnapshot:
    with get_connection() as connection:
        return _build_context_payload(connection, cadence, season_id, block_id, week_id, window_start_date, window_end_date)


def build_assessment_context_with_connection(
    connection,
    cadence: AssessmentCadence,
    season_id: int,
    window_start_date: str,
    window_end_date: str,
    block_id: int | None = None,
    week_id: int | None = None,
) -> AssessmentContextSnapshot:
    return _build_context_payload(connection, cadence, season_id, block_id, week_id, window_start_date, window_end_date)