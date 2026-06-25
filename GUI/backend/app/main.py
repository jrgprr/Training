from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .activity_quality import get_activity_quality
from .activity_weather import backfill_activity_weather_batch, backfill_activity_weather_for_external_ids, enrich_activity_weather, get_activity_weather
from .db import get_connection, get_database_path, initialize_database
from .imports import GarminConnectAdapter, GarminConnectImportError, GarminConnectNotConfiguredError, GarminImportPipeline, GarminImportRequest, GarminImportStorage, classify_garmin_failure
from .load_engine import compute_activity_load, get_load_model_snapshot
from .planned_prescriptions import get_planned_session_prescription, project_planned_session_row_from_prescription
from .segments import get_segment_history, list_segments
from .training_zones import accept_zone_metric_profile, accept_zone_refinement_proposal, get_activity_zone_detail, get_planned_session_zone_target, get_week_zone_comparison_summary, get_zone_proposal_detail, list_activity_zone_summaries, list_current_zone_metric_profiles, list_current_zone_profiles, list_session_zone_comparisons, list_zone_proposals

app = FastAPI(title="Training System GUI API", version="0.2.0")

REPO_ROOT = Path(__file__).resolve().parents[3]
DAILY_ASSESSMENT_ROOT_NAME = "Daily-Assessment-Logbook"
WEEKLY_ASSESSMENT_ROOT_NAME = "Weekly-Assessment-Logbook"
BLOCK_ASSESSMENT_ROOT_NAME = "Block-Assessment-Logbook"
WEIGHT_ASSESSMENT_ROOT_NAME = "Weight-Assessment-Logbook"
RUNNING_DISCIPLINES = {"running", "trail_running", "track_running", "treadmill_running"}
RUNNING_DYNAMICS_METRIC_NAMES = (
    "cadence_double",
    "run_cadence",
    "ground_contact_time",
    "ground_contact_balance_left",
    "vertical_oscillation",
    "vertical_ratio",
    "stride_length",
    "performance_condition",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def fetch_all(query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def fetch_one(query: str, parameters: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(query, parameters).fetchone()
    return dict(row) if row else None


def ensure_entity_exists(rows: list[dict[str, Any]], message: str) -> list[dict[str, Any]]:
    if not rows:
        raise HTTPException(status_code=404, detail=message)
    return rows


def attach_planned_activity_groups(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    for row in rows:
        row.setdefault("planned_activity_groups", [])


def attach_planned_prescriptions(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with get_connection() as connection:
        for row in rows:
            prescription = get_planned_session_prescription(connection, int(row["planned_session_id"]))
            row.update(project_planned_session_row_from_prescription(row, prescription))


def normalize_running_dynamics_metric_value(metric_name: str, value: float) -> float:
    if metric_name == "stride_length" and value > 10:
        return value / 100.0
    return value


def get_activity_running_dynamics_history(activity_id: int, limit: int = 5) -> dict[str, Any] | None:
    activity = fetch_one(
        """
        SELECT activity_id, season_id, activity_date, started_at, discipline
        FROM exec_activities
        WHERE activity_id = ?
        """,
        (activity_id,),
    )
    if activity is None:
        return None

    discipline = str(activity.get("discipline") or "").lower()
    if discipline not in RUNNING_DISCIPLINES:
        return {
            "activity_id": activity_id,
            "discipline": activity.get("discipline"),
            "compared_activity_count": 0,
            "baseline_metrics": {},
            "history": [],
        }

    discipline_placeholders = ",".join("?" for _ in RUNNING_DISCIPLINES)
    candidates = fetch_all(
        f"""
        SELECT ea.activity_id, ea.activity_date, ea.started_at, ea.discipline, ea.activity_type,
               ea.duration_seconds, ea.avg_pace_seconds_per_km, ea.avg_hr
        FROM exec_activities ea
        WHERE ea.season_id = ?
          AND ea.activity_id != ?
          AND ea.discipline IN ({discipline_placeholders})
          AND (
            ea.activity_date < ?
            OR (ea.activity_date = ? AND COALESCE(ea.started_at, '') < COALESCE(?, ''))
          )
        ORDER BY ea.activity_date DESC, COALESCE(ea.started_at, ea.activity_date) DESC, ea.activity_id DESC
        LIMIT ?
        """,
        (
            int(activity["season_id"]),
            activity_id,
            *sorted(RUNNING_DISCIPLINES),
            str(activity["activity_date"]),
            str(activity["activity_date"]),
            activity.get("started_at"),
            max(limit * 3, limit),
        ),
    )
    if not candidates:
        return {
            "activity_id": activity_id,
            "discipline": activity.get("discipline"),
            "compared_activity_count": 0,
            "baseline_metrics": {},
            "history": [],
        }

    candidate_ids = [int(row["activity_id"]) for row in candidates]
    metric_placeholders = ",".join("?" for _ in RUNNING_DYNAMICS_METRIC_NAMES)
    id_placeholders = ",".join("?" for _ in candidate_ids)
    summary_rows = fetch_all(
        f"""
        SELECT activity_id, metric_name, trusted_value
        FROM exec_activity_metric_summaries
        WHERE activity_id IN ({id_placeholders})
          AND summary_kind = 'average'
          AND metric_name IN ({metric_placeholders})
          AND trusted_value IS NOT NULL
        """,
        tuple(candidate_ids) + RUNNING_DYNAMICS_METRIC_NAMES,
    )

    summaries_by_activity: dict[int, dict[str, float]] = {}
    for row in summary_rows:
        activity_metrics = summaries_by_activity.setdefault(int(row["activity_id"]), {})
        activity_metrics[str(row["metric_name"])] = normalize_running_dynamics_metric_value(
            str(row["metric_name"]), float(row["trusted_value"])
        )

    history: list[dict[str, Any]] = []
    for row in candidates:
        metrics = summaries_by_activity.get(int(row["activity_id"]), {})
        if not metrics:
            continue
        history.append(
            {
                "activity_id": int(row["activity_id"]),
                "activity_date": row["activity_date"],
                "started_at": row["started_at"],
                "discipline": row["discipline"],
                "activity_type": row["activity_type"],
                "duration_seconds": row["duration_seconds"],
                "avg_pace_seconds_per_km": row["avg_pace_seconds_per_km"],
                "avg_hr": row["avg_hr"],
                "metrics": metrics,
            }
        )
        if len(history) >= limit:
            break

    baseline_metrics: dict[str, float] = {}
    for metric_name in RUNNING_DYNAMICS_METRIC_NAMES:
        values = [float(item["metrics"][metric_name]) for item in history if metric_name in item["metrics"]]
        if values:
            baseline_metrics[metric_name] = round(sum(values) / len(values), 4)

    return {
        "activity_id": activity_id,
        "discipline": activity.get("discipline"),
        "compared_activity_count": len(history),
        "baseline_metrics": baseline_metrics,
        "history": history,
    }


def get_activity_metric_analysis(activity_id: int) -> dict[str, Any] | None:
    scripts_path = str(REPO_ROOT / ".github" / "skills" / "activity-metric-analysis" / "scripts")
    try:
        sys.path.insert(0, scripts_path)
        from compute_activity_metric_analysis import compute_activity_metric_analysis  # type: ignore

        with get_connection() as connection:
            return compute_activity_metric_analysis(connection, activity_id)
    except Exception:
        return None
    finally:
        if scripts_path in sys.path:
            sys.path.remove(scripts_path)


def get_daily_assessment_markdown_path(season_id: int, review_date: str, planned_session_id: int | None) -> Path:
    suffix = f"ps-{planned_session_id}" if planned_session_id is not None else "general"
    return REPO_ROOT / str(season_id) / DAILY_ASSESSMENT_ROOT_NAME / f"{review_date}-{suffix}.md"


def get_weekly_assessment_markdown_path(season_id: int, week_code: str, week_id: int) -> Path:
    return REPO_ROOT / str(season_id) / WEEKLY_ASSESSMENT_ROOT_NAME / f"{week_code}-week-{week_id}.md"


def get_block_assessment_markdown_path(season_id: int, block_code: str, block_id: int) -> Path:
    return REPO_ROOT / str(season_id) / BLOCK_ASSESSMENT_ROOT_NAME / f"{block_code}-block-{block_id}.md"


def get_weight_assessment_markdown_path(season_id: int, review_date: str) -> Path:
    return REPO_ROOT / str(season_id) / WEIGHT_ASSESSMENT_ROOT_NAME / f"{review_date}.md"


class WeeklyReviewPayload(BaseModel):
    summary_text: str | None = None
    recommendation_text: str | None = None
    risk_level: str | None = None


class GarminConnectImportPayload(BaseModel):
    season_id: int
    date_from: str
    date_to: str
    include_daily_metrics: bool = True


class ActivityQualityReplayPayload(BaseModel):
    source_mode: str = "canonical"


class ActivityWeatherBackfillPayload(BaseModel):
    activity_id: int | None = None
    season_id: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int | None = None
    force: bool = False


class ActivityWeatherEnrichPayload(BaseModel):
    force: bool = False


class ZoneProposalAcceptancePayload(BaseModel):
    effective_start_date: str | None = None
    accepted_at: str | None = None
    decision_notes: str | None = None


class ZoneMetricProfileAcceptancePayload(BaseModel):
    discipline: str
    metric_basis: str
    model_key: str
    effective_start_date: str
    profile_label: str | None = None
    resting_hr: float | None = None
    max_hr: float | None = None
    ftp: float | None = None
    accepted_at: str | None = None
    notes: str | None = None


def get_daily_metric(season_id: int, metric_date: str) -> dict[str, Any]:
    metric = fetch_one(
        """
        SELECT daily_metric_id, season_id, metric_date, source_system,
                                                 weight_measured_at, weight_measurement_source,
                         weight_kg, body_fat_pct, body_water_pct, bone_mass_kg, muscle_mass_kg,
                         bmi, visceral_fat, metabolic_age, physique_rating,
                         sleep_hours, sleep_quality, resting_hr,
             vo2max_cycling, vo2max_running, lactate_threshold_hr,
             hrv, body_battery, total_steps, total_distance_m, step_goal,
               stress_avg, stress_max,
               spo2_avg, spo2_sleep_avg, spo2_7d_avg, spo2_lowest,
               subjective_energy, subjective_fatigue, soreness, notes
        FROM exec_daily_metrics
        WHERE season_id = ? AND metric_date = ?
        ORDER BY CASE WHEN source_system = 'garmin' THEN 0 ELSE 1 END, daily_metric_id DESC
        LIMIT 1
        """,
        (season_id, metric_date),
    )
    if metric is None:
        raise HTTPException(status_code=404, detail=f"No existen metricas diarias para {metric_date} en la temporada {season_id}.")
    metric["load_model"] = get_load_model_snapshot(season_id=season_id, metric_date=metric_date)
    metric["weight_trend"] = get_weight_trend_snapshot(season_id=season_id, metric_date=metric_date)
    metric["weight_measurements"] = get_weight_measurement_snapshot(season_id=season_id, metric_date=metric_date)
    return metric


def get_weight_trend_snapshot(season_id: int, metric_date: str, trailing_days: int = 14) -> list[dict[str, Any]]:
    return fetch_all(
        """
        WITH ranked_weights AS (
            SELECT
                daily_metric_id,
                metric_date,
                weight_kg,
                weight_measured_at,
                weight_measurement_source,
                ROW_NUMBER() OVER (
                    PARTITION BY metric_date
                    ORDER BY
                        CASE WHEN source_system = 'garmin' THEN 0 ELSE 1 END,
                        CASE WHEN weight_measured_at IS NULL THEN 1 ELSE 0 END,
                        COALESCE(weight_measured_at, metric_date) ASC,
                        daily_metric_id DESC
                ) AS row_rank
            FROM exec_daily_metrics
            WHERE season_id = ?
              AND metric_date <= ?
              AND weight_kg IS NOT NULL
        ),
        selected_weights AS (
            SELECT metric_date, weight_kg, weight_measured_at, weight_measurement_source
            FROM ranked_weights
            WHERE row_rank = 1
            ORDER BY metric_date DESC
            LIMIT ?
        )
        SELECT metric_date, weight_kg, weight_measured_at, weight_measurement_source
        FROM selected_weights
        ORDER BY metric_date ASC
        """,
        (season_id, metric_date, trailing_days),
    )


def get_weight_measurement_snapshot(season_id: int, metric_date: str, trailing_days: int = 14) -> list[dict[str, Any]]:
    return fetch_all(
        """
        WITH ranked_weights AS (
            SELECT
                daily_metric_id,
                metric_date,
                ROW_NUMBER() OVER (
                    PARTITION BY metric_date
                    ORDER BY
                        CASE WHEN source_system = 'garmin' THEN 0 ELSE 1 END,
                        CASE WHEN weight_measured_at IS NULL THEN 1 ELSE 0 END,
                        COALESCE(weight_measured_at, metric_date) ASC,
                        daily_metric_id DESC
                ) AS row_rank
            FROM exec_daily_metrics
            WHERE season_id = ?
              AND metric_date <= ?
              AND weight_kg IS NOT NULL
        ),
        selected_dates AS (
            SELECT metric_date
            FROM ranked_weights
            WHERE row_rank = 1
            ORDER BY metric_date DESC
            LIMIT ?
        )
        SELECT metric_date, measured_at, weight_kg, measurement_source
        FROM exec_weight_measurements
        WHERE season_id = ?
          AND metric_date IN (SELECT metric_date FROM selected_dates)
        ORDER BY metric_date ASC, COALESCE(measured_at, metric_date) ASC, weight_measurement_id ASC
        """,
        (season_id, metric_date, trailing_days, season_id),
    )


def get_week_context(week_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT w.week_id, w.week_code, w.week_role, w.objective_primary,
               b.block_id, b.block_code, b.season_id
        FROM plan_micro_weeks w
        JOIN plan_meso_blocks b ON b.block_id = w.block_id
        WHERE w.week_id = ?
        """,
        (week_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No existe la semana {week_id}.")
    return row


def get_block_context(block_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT block_id, season_id, block_code, block_name, phase_name, sequence_order,
               start_date, end_date, objective_primary, exit_criteria
        FROM plan_meso_blocks
        WHERE block_id = ?
        """,
        (block_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No existe el bloque {block_id}.")
    return row


def get_week_plan_vs_real_rows(week_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        WITH ranked_links AS (
            SELECT l.planned_session_id, l.activity_id, l.link_type, l.compliance_status, l.rationale,
                   ea.source_system, ea.activity_type, ea.duration_seconds, ea.perceived_exertion, ea.discipline,
                   ROW_NUMBER() OVER (
                       PARTITION BY l.planned_session_id
                       ORDER BY
                           CASE WHEN ea.source_system = 'garmin' THEN 0 ELSE 1 END,
                           CASE WHEN l.link_type = 'direct' THEN 0 ELSE 1 END,
                           l.link_id DESC
                   ) AS link_rank
            FROM link_plan_execution l
            JOIN exec_activities ea ON ea.activity_id = l.activity_id
        )
         SELECT ps.planned_session_id, ps.session_date, ps.day_name, ps.planned_role,
             ps.planned_type AS prescription_type, ps.planned_type,
               ps.objective AS planned_objective, ps.primary_session AS planned_session,
             ps.duration_min, ps.duration_max, ps.is_key_session,
             up.support_routine AS planned_support_routine,
             rr.daily_review_id, mb.season_id AS review_season_id,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN NULL
                   ELSE rl.activity_id
               END AS activity_id,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN NULL
                   ELSE rl.activity_type
               END AS actual_activity_type,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN NULL
                   ELSE rl.duration_seconds / 60.0
               END AS actual_duration_min,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN NULL
                   ELSE rl.perceived_exertion
               END AS perceived_exertion,
               COALESCE(rr.compliance_status, rl.compliance_status, 'pending') AS compliance_status,
               rr.actual_summary, rr.general_feeling, rr.next_day_decision,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN NULL
                   ELSE rl.link_type
               END AS actual_link_type,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN NULL
                   ELSE rl.source_system
               END AS actual_source_system,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN NULL
                   ELSE rl.discipline
               END AS actual_discipline,
               CASE
                   WHEN COALESCE(rr.compliance_status, rl.compliance_status, 'pending') = 'skipped' THEN 0
                   ELSE (
                       SELECT COUNT(*)
                       FROM exec_activities ea2
                       WHERE ea2.source_system = 'garmin'
                         AND ea2.activity_date = ps.session_date
                         AND (
                             CASE
                                 WHEN ea2.discipline IN ('road_biking', 'indoor_cycling', 'mountain_biking') THEN 'cycling'
                                 WHEN ea2.discipline IN ('walking', 'hiking') THEN 'walking'
                                 WHEN ea2.discipline IN ('running', 'trail_running') THEN 'running'
                                 ELSE ea2.discipline
                             END
                         ) = (
                             CASE
                                 WHEN rl.discipline IN ('road_biking', 'indoor_cycling', 'mountain_biking') THEN 'cycling'
                                 WHEN rl.discipline IN ('walking', 'hiking') THEN 'walking'
                                 WHEN rl.discipline IN ('running', 'trail_running') THEN 'running'
                                 ELSE rl.discipline
                             END
                         )
                   )
               END AS compatible_garmin_count
        FROM plan_planned_sessions ps
        JOIN plan_micro_weeks mw ON mw.week_id = ps.week_id
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        LEFT JOIN plan_user_profiles up ON up.season_id = mb.season_id
        LEFT JOIN ranked_links rl ON rl.planned_session_id = ps.planned_session_id AND rl.link_rank = 1
        LEFT JOIN review_daily_reviews rr ON rr.planned_session_id = ps.planned_session_id
        WHERE ps.week_id = ?
        ORDER BY ps.sequence_in_week
        """,
        (week_id,),
    )
    attach_planned_activity_groups(rows)
    attach_planned_prescriptions(rows)

    for row in rows:
        row["planned_session"] = row.get("primary_session")
        daily_review_id = row.get("daily_review_id")
        review_season_id = row.get("review_season_id")
        markdown_available = False
        if daily_review_id is not None and review_season_id is not None:
            markdown_path = get_daily_assessment_markdown_path(int(review_season_id), str(row["session_date"]), row["planned_session_id"])
            markdown_available = markdown_path.exists()
        row["daily_assessment_available"] = markdown_available
        row["daily_assessment_url"] = f"/api/daily-reviews/{daily_review_id}/markdown" if markdown_available else None

    linked_rows = fetch_all(
        """
        WITH ranked_links AS (
            SELECT l.planned_session_id, l.activity_id, l.link_type, l.compliance_status,
                   ea.source_system, ea.activity_type, ea.duration_seconds, ea.perceived_exertion, ea.discipline,
                   ROW_NUMBER() OVER (
                       PARTITION BY l.planned_session_id
                       ORDER BY
                           CASE WHEN ea.source_system = 'garmin' THEN 0 ELSE 1 END,
                           CASE WHEN l.link_type = 'direct' THEN 0 ELSE 1 END,
                           l.link_id DESC
                   ) AS link_rank
            FROM link_plan_execution l
            JOIN exec_activities ea ON ea.activity_id = l.activity_id
        )
        SELECT ps.planned_session_id,
               rl.activity_id,
               rl.activity_type,
               rl.duration_seconds / 60.0 AS actual_duration_min,
               rl.perceived_exertion,
               rl.link_type AS actual_link_type,
               rl.source_system AS actual_source_system,
               rl.discipline AS actual_discipline,
               (
                   SELECT COUNT(*)
                   FROM exec_activities ea2
                   WHERE ea2.source_system = 'garmin'
                     AND ea2.activity_date = ps.session_date
                     AND (
                         CASE
                             WHEN ea2.discipline IN ('road_biking', 'indoor_cycling', 'mountain_biking') THEN 'cycling'
                             WHEN ea2.discipline IN ('walking', 'hiking') THEN 'walking'
                             WHEN ea2.discipline IN ('running', 'trail_running') THEN 'running'
                             ELSE ea2.discipline
                         END
                     ) = (
                         CASE
                             WHEN rl.discipline IN ('road_biking', 'indoor_cycling', 'mountain_biking') THEN 'cycling'
                             WHEN rl.discipline IN ('walking', 'hiking') THEN 'walking'
                             WHEN rl.discipline IN ('running', 'trail_running') THEN 'running'
                             ELSE rl.discipline
                         END
                     )
               ) AS compatible_garmin_count
        FROM plan_planned_sessions ps
        JOIN ranked_links rl ON rl.planned_session_id = ps.planned_session_id
        WHERE ps.week_id = ?
        ORDER BY ps.sequence_in_week, rl.link_rank
        """,
        (week_id,),
    )

    optional_rows = fetch_all(
        """
        SELECT ps.session_date,
               ea.activity_id,
               ea.activity_type,
               ea.duration_seconds / 60.0 AS actual_duration_min,
               ea.perceived_exertion,
               ea.source_system AS actual_source_system,
               ea.discipline AS actual_discipline,
               ea.started_at
        FROM plan_planned_sessions ps
        JOIN exec_activities ea ON ea.activity_date = ps.session_date
        WHERE ps.week_id = ?
          AND ea.source_system = 'garmin'
          AND ea.discipline IN ('strength_training', 'yoga')
          AND NOT EXISTS (
              SELECT 1
              FROM link_plan_execution l
              WHERE l.activity_id = ea.activity_id
          )
        ORDER BY ps.sequence_in_week, COALESCE(ea.started_at, ea.activity_date), ea.activity_id
        """,
        (week_id,),
    )

    other_rows = fetch_all(
        """
        SELECT ps.session_date,
               ea.activity_id,
               ea.activity_type,
               ea.duration_seconds / 60.0 AS actual_duration_min,
               ea.perceived_exertion,
               ea.source_system AS actual_source_system,
               ea.discipline AS actual_discipline,
               ea.started_at
        FROM plan_planned_sessions ps
        JOIN exec_activities ea ON ea.activity_date = ps.session_date
        WHERE ps.week_id = ?
          AND ea.source_system = 'garmin'
          AND ea.discipline NOT IN ('strength_training', 'yoga')
          AND NOT EXISTS (
              SELECT 1
              FROM link_plan_execution l
              WHERE l.activity_id = ea.activity_id
          )
        ORDER BY ps.sequence_in_week, COALESCE(ea.started_at, ea.activity_date), ea.activity_id
        """,
        (week_id,),
    )

    activities_by_session: dict[int, list[dict[str, Any]]] = {}
    for linked_row in linked_rows:
        activities_by_session.setdefault(linked_row["planned_session_id"], []).append(
            {
                "activity_id": linked_row["activity_id"],
                "actual_activity_type": linked_row["activity_type"],
                "actual_duration_min": linked_row["actual_duration_min"],
                "perceived_exertion": linked_row["perceived_exertion"],
                "actual_link_type": linked_row["actual_link_type"],
                "actual_source_system": linked_row["actual_source_system"],
                "actual_discipline": linked_row["actual_discipline"],
                "compatible_garmin_count": linked_row["compatible_garmin_count"],
            }
        )

    optional_activities_by_date: dict[str, list[dict[str, Any]]] = {}
    for optional_row in optional_rows:
        optional_activities_by_date.setdefault(optional_row["session_date"], []).append(
            {
                "activity_id": optional_row["activity_id"],
                "actual_activity_type": optional_row["activity_type"],
                "actual_duration_min": optional_row["actual_duration_min"],
                "perceived_exertion": optional_row["perceived_exertion"],
                "actual_link_type": None,
                "actual_source_system": optional_row["actual_source_system"],
                "actual_discipline": optional_row["actual_discipline"],
                "compatible_garmin_count": 0,
                "started_at": optional_row["started_at"],
            }
        )

    other_activities_by_date: dict[str, list[dict[str, Any]]] = {}
    for other_row in other_rows:
        other_activities_by_date.setdefault(other_row["session_date"], []).append(
            {
                "activity_id": other_row["activity_id"],
                "actual_activity_type": other_row["activity_type"],
                "actual_duration_min": other_row["actual_duration_min"],
                "perceived_exertion": other_row["perceived_exertion"],
                "actual_link_type": None,
                "actual_source_system": other_row["actual_source_system"],
                "actual_discipline": other_row["actual_discipline"],
                "compatible_garmin_count": 0,
                "started_at": other_row["started_at"],
            }
        )

    zone_comparison_by_session = list_session_zone_comparisons(week_id)

    for row in rows:
        activities = [] if row["compliance_status"] == "skipped" else activities_by_session.get(row["planned_session_id"], [])
        row["activities"] = activities
        row["optional_daily_activities"] = optional_activities_by_date.get(row["session_date"], [])
        row["other_daily_activities"] = other_activities_by_date.get(row["session_date"], [])
        row["zone_comparison"] = zone_comparison_by_session.get(row["planned_session_id"], [])

        if not activities:
            continue

        total_minutes = sum(activity["actual_duration_min"] for activity in activities if activity["actual_duration_min"] is not None)
        row["actual_duration_min"] = total_minutes if total_minutes > 0 else row["actual_duration_min"]

    return rows


def calculate_weekly_review_metrics(week_id: int) -> dict[str, Any]:
    week = get_week_context(week_id)
    session_rows = fetch_all(
        """
        SELECT duration_min, duration_max, is_key_session
        FROM plan_planned_sessions
        WHERE week_id = ?
        ORDER BY sequence_in_week
        """,
        (week_id,),
    )
    rows = get_week_plan_vs_real_rows(week_id)

    total = len(rows)
    completed = sum(1 for row in rows if row["compliance_status"] == "completed")
    partial = sum(1 for row in rows if row["compliance_status"] == "partial")
    pending = sum(1 for row in rows if row["compliance_status"] == "pending")
    skipped = sum(1 for row in rows if row["compliance_status"] == "skipped")
    replaced = sum(1 for row in rows if row["compliance_status"] == "replaced")
    tracked = total - pending
    actual_minutes = round(sum((row["actual_duration_min"] or 0) for row in rows))
    planned_reference_minutes = round(
        sum((((session["duration_min"] or session["duration_max"] or 0) + (session["duration_max"] or session["duration_min"] or 0)) / 2) for session in session_rows)
    )
    planned_lower_minutes = sum((session["duration_min"] or 0) for session in session_rows)
    planned_upper_minutes = sum((session["duration_max"] or session["duration_min"] or 0) for session in session_rows)
    adherence_rate = 0 if total == 0 else round(((completed + partial) / total) * 100, 2)
    traceability_rate = 0 if total == 0 else round((tracked / total) * 100, 2)
    volume_delta_minutes = actual_minutes - planned_reference_minutes
    volume_status = (
        "sin carga real"
        if actual_minutes == 0
        else "por debajo de la banda"
        if actual_minutes < planned_lower_minutes
        else "por encima de la banda"
        if actual_minutes > planned_upper_minutes
        else "dentro de la banda"
    )

    risk_level = (
        "Riesgo alto"
        if pending >= 2 or skipped >= 2 or volume_status == "por debajo de la banda"
        else "Riesgo medio"
        if pending == 1 or skipped == 1 or replaced > 0 or volume_status == "por encima de la banda"
        else "Riesgo bajo"
    )

    recommendation_text = (
        "Cerrar primero los registros pendientes antes de interpretar la semana."
        if pending > 0
        else "Revisar si las sesiones omitidas exigen recorte o rediseno de la siguiente microsemana."
        if skipped > 0
        else "Verificar que las sustituciones mantengan el objetivo funcional original de la semana."
        if replaced > 0
        else "Semana util pero corta; conviene confirmar si la reduccion fue deliberada o defensiva."
        if volume_status == "por debajo de la banda"
        else "Semana mas cargada de lo previsto; vigilar absorcion y fatiga antes de empujar mas."
        if volume_status == "por encima de la banda"
        else "Mantener la estructura actual; la semana cierra dentro de rango y sin incidencias operativas."
    )

    summary_text = (
        f"{week['week_code']}: {completed} completadas, {partial} parciales, {pending} pendientes, "
        f"{skipped} skipped, {replaced} replaced. {actual_minutes} minutos reales y riesgo {risk_level.lower()}."
    )

    return {
        "season_id": week["season_id"],
        "block_id": week["block_id"],
        "week_id": week["week_id"],
        "week_code": week["week_code"],
        "week_role": week["week_role"],
        "objective_primary": week["objective_primary"],
        "review_status": "closed",
        "adherence_rate": adherence_rate,
        "traceability_rate": traceability_rate,
        "actual_minutes": actual_minutes,
        "planned_reference_minutes": planned_reference_minutes,
        "volume_delta_minutes": volume_delta_minutes,
        "risk_level": risk_level,
        "recommendation_text": recommendation_text,
        "summary_text": summary_text,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": str(get_database_path())}


@app.get("/api/imports/garmin-connect/status")
def get_garmin_connect_status() -> dict[str, Any]:
    adapter = GarminConnectAdapter()
    return adapter.configuration_status()


@app.post("/api/imports/garmin-connect/preview")
def preview_garmin_connect_import(payload: GarminConnectImportPayload) -> dict[str, Any]:
    pipeline = GarminImportPipeline()
    request = GarminImportRequest(
        season_id=payload.season_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        include_daily_metrics=payload.include_daily_metrics,
    )
    try:
        return pipeline.preview(request).to_dict()
    except GarminConnectNotConfiguredError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GarminConnectImportError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/imports/garmin-connect/run")
def run_garmin_connect_import(payload: GarminConnectImportPayload) -> dict[str, Any]:
    pipeline = GarminImportPipeline()
    storage = GarminImportStorage()
    request = GarminImportRequest(
        season_id=payload.season_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        include_daily_metrics=payload.include_daily_metrics,
    )
    import_job_id = storage.start_import_job(
        season_id=request.season_id,
        source_system="garmin",
        import_type="garminconnect",
        source_path=f"{request.date_from}:{request.date_to}",
        request_date_from=request.date_from,
        request_date_to=request.date_to,
        include_daily_metrics=request.include_daily_metrics,
        notes=["Importacion Garmin iniciada.", "Pendiente de fetch desde Garmin Connect."],
    )
    try:
        batch = pipeline.run(request)
    except GarminConnectNotConfiguredError as error:
        failure = classify_garmin_failure(error)
        storage.fail_import_job(
            import_job_id,
            notes=["Importacion Garmin fallida.", str(error)],
            failure_stage=failure["failure_stage"],
            failure_class=failure["failure_class"],
            operator_detail=failure["operator_detail"],
        )
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GarminConnectImportError as error:
        failure = classify_garmin_failure(error)
        storage.fail_import_job(
            import_job_id,
            notes=["Importacion Garmin fallida durante fetch.", str(error)],
            failure_stage=failure["failure_stage"],
            failure_class=failure["failure_class"],
            operator_detail=failure["operator_detail"],
        )
        raise HTTPException(status_code=502, detail=str(error)) from error
    except NotImplementedError as error:
        failure = classify_garmin_failure(error)
        storage.fail_import_job(
            import_job_id,
            notes=["Importacion Garmin no implementada para esta operacion.", str(error)],
            failure_stage=failure["failure_stage"],
            failure_class=failure["failure_class"],
            operator_detail=failure["operator_detail"],
        )
        raise HTTPException(status_code=501, detail=str(error)) from error
    try:
        summary = storage.persist_batch(batch, import_job_id=import_job_id)
    except Exception as error:
        counts = batch.counts()
        rows_detected = counts["activities_detected"] + counts["daily_metrics_detected"]
        failure = classify_garmin_failure(error)
        storage.fail_import_job(
            import_job_id,
            notes=["Importacion Garmin fallida durante persistencia.", str(error)],
            rows_detected=rows_detected,
            status="failed",
            failure_stage=failure["failure_stage"],
            failure_class=failure["failure_class"],
            operator_detail=failure["operator_detail"],
        )
        raise

    counts = dict(batch.counts())
    counts["segment_efforts_loaded"] = (
        summary.breakdown.segment_efforts_inserted + summary.breakdown.segment_efforts_updated
    )
    counts["segment_activities_with_data"] = summary.breakdown.segment_activities_with_data
    counts["quality_runs_created"] = summary.breakdown.quality_runs_created
    counts["quality_runs_reused"] = summary.breakdown.quality_runs_reused

    weather_summary: dict[str, Any] | None = None
    weather_external_ids = [activity.external_activity_id for activity in batch.activities if activity.external_activity_id]
    if weather_external_ids:
        try:
            weather_summary = backfill_activity_weather_for_external_ids(
                season_id=request.season_id,
                source_system="garmin",
                external_activity_ids=weather_external_ids,
            )
            counts["weather_activities_processed"] = weather_summary["processed_count"]
            counts["weather_activities_completed"] = weather_summary["completed_count"]
        except Exception as error:
            weather_summary = {
                "activity_count": 0,
                "processed_count": 0,
                "completed_count": 0,
                "results": [],
                "status": "failed",
                "detail": str(error),
            }

    return {
        "status": "ok",
        "counts": counts,
        "metadata": {
            **batch.metadata.to_dict(),
            "segment_summary": {
                "activities_with_segment_data": summary.breakdown.segment_activities_with_data,
                "activities_without_segment_data": max(
                    summary.breakdown.segment_activities_checked - summary.breakdown.segment_activities_with_data,
                    0,
                ),
            },
            "quality_summary": {
                "clean_activities": max(
                    summary.breakdown.quality_activities_checked
                    - summary.breakdown.quality_activities_filtered
                    - summary.breakdown.quality_limited_metrics,
                    0,
                ),
                "filtered_activities": summary.breakdown.quality_activities_filtered,
                "limited_activities": summary.breakdown.quality_limited_metrics,
                "rule_version": batch.activities[0].quality_rule_version if batch.activities else None,
            },
            "weather_summary": weather_summary,
        },
        "import_job": summary.to_dict(),
    }


@app.get("/api/import-jobs")
def get_import_jobs() -> list[dict[str, Any]]:
    storage = GarminImportStorage()
    return storage.list_import_jobs()


@app.get("/api/import-jobs/{import_job_id}")
def get_import_job(import_job_id: int) -> dict[str, Any]:
    storage = GarminImportStorage()
    job = storage.get_import_job(import_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No existe el import job {import_job_id}.")
    return job


@app.get("/api/segments")
def get_segments(season_id: int, query: str | None = None, limit: int = 50) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit debe ser mayor que 0.")
    if limit > 200:
        raise HTTPException(status_code=400, detail="limit no puede ser mayor que 200.")
    return {"items": list_segments(season_id=season_id, query=query, limit=limit)}


@app.get("/api/segments/{segment_id}/history")
def get_segment_history_endpoint(segment_id: int, limit: int = 20) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit debe ser mayor que 0.")
    if limit > 200:
        raise HTTPException(status_code=400, detail="limit no puede ser mayor que 200.")
    history = get_segment_history(segment_id=segment_id, limit=limit)
    if history is None:
        raise HTTPException(status_code=404, detail=f"No existe el segmento {segment_id}.")
    return history


@app.get("/api/activities/{activity_id}")
def get_activity(activity_id: int) -> dict[str, Any]:
    activity = fetch_one(
        """
        SELECT ea.activity_id, ea.season_id, ea.source_system, ea.external_activity_id,
               ea.activity_date, ea.started_at, ea.discipline, ea.activity_type,
               ea.duration_seconds, ea.distance_meters, ea.ascent_meters, ea.calories,
               ea.avg_hr, ea.max_hr, ea.avg_power, ea.normalized_power, ea.training_load,
                             ea.avg_pace_seconds_per_km, ea.perceived_exertion, ea.subjective_feeling,
                             (
                                     SELECT trusted_value
                                     FROM exec_activity_metric_summaries summary
                                     WHERE summary.activity_id = ea.activity_id
                                         AND summary.metric_name = 'respiration_rate'
                                         AND summary.summary_kind = 'average'
                                     LIMIT 1
                             ) AS avg_respiration_rate,
                             (
                                     SELECT trusted_value
                                     FROM exec_activity_metric_summaries summary
                                     WHERE summary.activity_id = ea.activity_id
                                         AND summary.metric_name = 'respiration_rate'
                                         AND summary.summary_kind = 'maximum'
                                     LIMIT 1
                             ) AS max_respiration_rate,
             dm.stress_avg, dm.stress_max,
             dm.spo2_sleep_avg, dm.spo2_avg, dm.spo2_7d_avg, dm.spo2_lowest,
             ea.source_file, ea.raw_payload_path, ea.notes,
             ea.quality_status, ea.quality_checked_at, ea.quality_rule_version,
             ea.quality_decision_count, ea.quality_limited_metric_count,
               l.planned_session_id, l.compliance_status, l.rationale,
               rr.actual_summary, rr.general_feeling, rr.next_day_decision
        FROM exec_activities ea
         LEFT JOIN exec_daily_metrics dm
             ON dm.season_id = ea.season_id
            AND dm.metric_date = ea.activity_date
            AND dm.source_system = ea.source_system
        LEFT JOIN link_plan_execution l ON l.activity_id = ea.activity_id
        LEFT JOIN review_daily_reviews rr
               ON rr.planned_session_id = l.planned_session_id
              AND rr.review_date = ea.activity_date
        WHERE ea.activity_id = ?
        """,
        (activity_id,),
    )
    if activity is None:
        raise HTTPException(status_code=404, detail=f"No existe la actividad {activity_id}.")
    calculated_load = compute_activity_load(activity, season_id=int(activity["season_id"]))
    activity["calculated_training_load"] = round(float(calculated_load["load_value"]), 2)
    activity["calculated_training_load_source"] = calculated_load["load_source"]
    activity["activity_metric_analysis"] = get_activity_metric_analysis(activity_id)
    activity["weather"] = get_activity_weather(activity_id)
    return activity


@app.get("/api/seasons/{season_id}/activities")
def get_season_activities(season_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT ea.activity_id, ea.season_id, ea.source_system, ea.external_activity_id,
               ea.activity_date, ea.started_at, ea.discipline, ea.activity_type,
               ea.duration_seconds, ea.distance_meters, ea.ascent_meters, ea.calories,
               ea.avg_hr, ea.max_hr, ea.avg_power, ea.normalized_power, ea.training_load,
               ea.avg_pace_seconds_per_km, ea.perceived_exertion, ea.subjective_feeling,
             ea.raw_payload_path, ea.notes,
             ea.quality_status, ea.quality_checked_at, ea.quality_rule_version,
             ea.quality_decision_count, ea.quality_limited_metric_count,
               l.planned_session_id, l.compliance_status, l.rationale,
               rr.actual_summary, rr.general_feeling, rr.next_day_decision
        FROM exec_activities ea
        LEFT JOIN link_plan_execution l ON l.activity_id = ea.activity_id
        LEFT JOIN review_daily_reviews rr
               ON rr.planned_session_id = l.planned_session_id
              AND rr.review_date = ea.activity_date
        WHERE ea.season_id = ?
        ORDER BY ea.activity_date DESC, COALESCE(ea.started_at, ea.activity_date) DESC, ea.activity_id DESC
        LIMIT 120
        """,
        (season_id,),
    )
    rows = ensure_entity_exists(rows, f"No se encontraron actividades para la temporada {season_id}.")
    zone_summaries = list_activity_zone_summaries([int(row["activity_id"]) for row in rows])
    for row in rows:
        calculated_load = compute_activity_load(row, season_id=int(row["season_id"]))
        row["calculated_training_load"] = round(float(calculated_load["load_value"]), 2)
        row["calculated_training_load_source"] = calculated_load["load_source"]
        row["zone_summary"] = zone_summaries.get(int(row["activity_id"]), {})
    return rows

@app.get("/api/seasons/{season_id}/daily-metrics/{metric_date}")
def get_season_daily_metric(season_id: int, metric_date: str) -> dict[str, Any]:
    return get_daily_metric(season_id, metric_date)


@app.get("/api/seasons/{season_id}/zone-profiles/current")
def get_current_zone_profiles_endpoint(season_id: int, discipline: str) -> dict[str, Any]:
    season = fetch_one(
        """
        SELECT season_id, season_code, season_name
        FROM plan_seasons
        WHERE season_id = ?
        """,
        (season_id,),
    )
    if season is None:
        raise HTTPException(status_code=404, detail=f"No existe la temporada {season_id}.")

    payload = list_current_zone_profiles(season_id=season_id, discipline=discipline)
    if not payload["profiles"]:
        raise HTTPException(
            status_code=404,
            detail=f"No existen perfiles de zonas vigentes para {discipline} en la temporada {season_id}.",
        )
    return payload


@app.get("/api/seasons/{season_id}/zone-metric-profiles/current")
def get_current_zone_metric_profiles_endpoint(season_id: int, discipline: str) -> dict[str, Any]:
    season = fetch_one(
        """
        SELECT season_id
        FROM plan_seasons
        WHERE season_id = ?
        """,
        (season_id,),
    )
    if season is None:
        raise HTTPException(status_code=404, detail=f"No existe la temporada {season_id}.")

    payload = list_current_zone_metric_profiles(season_id=season_id, discipline=discipline)
    if not payload["profiles"]:
        raise HTTPException(
            status_code=404,
            detail=f"No existen perfiles metricos vigentes para {discipline} en la temporada {season_id}.",
        )
    return payload


@app.post("/api/seasons/{season_id}/zone-metric-profiles/accept")
def accept_zone_metric_profile_endpoint(season_id: int, payload: ZoneMetricProfileAcceptancePayload) -> dict[str, Any]:
    try:
        return accept_zone_metric_profile(
            season_id=season_id,
            discipline=payload.discipline,
            metric_basis=payload.metric_basis,
            model_key=payload.model_key,
            effective_start_date=payload.effective_start_date,
            profile_label=payload.profile_label,
            resting_hr=payload.resting_hr,
            max_hr=payload.max_hr,
            ftp=payload.ftp,
            accepted_at=payload.accepted_at,
            notes=payload.notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/seasons/{season_id}/zone-proposals")
def get_zone_proposals_endpoint(season_id: int, discipline: str) -> dict[str, Any]:
    season = fetch_one(
        """
        SELECT season_id
        FROM plan_seasons
        WHERE season_id = ?
        """,
        (season_id,),
    )
    if season is None:
        raise HTTPException(status_code=404, detail=f"No existe la temporada {season_id}.")
    return list_zone_proposals(season_id, discipline)


@app.get("/api/zone-proposals/{proposal_id}")
def get_zone_proposal_detail_endpoint(proposal_id: int) -> dict[str, Any]:
    payload = get_zone_proposal_detail(proposal_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No existe la propuesta {proposal_id}.")
    return payload


@app.post("/api/zone-proposals/{proposal_id}/accept")
def accept_zone_proposal_endpoint(proposal_id: int, payload: ZoneProposalAcceptancePayload) -> dict[str, Any]:
    try:
        return accept_zone_refinement_proposal(
            proposal_id,
            effective_start_date=payload.effective_start_date,
            accepted_at=payload.accepted_at,
            decision_notes=payload.decision_notes,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/activities/{activity_id}/quality")
def get_activity_quality_endpoint(activity_id: int) -> dict[str, Any]:
    quality = get_activity_quality(activity_id)
    if quality is None:
        raise HTTPException(status_code=404, detail=f"No existe la actividad {activity_id}.")
    return quality


@app.get("/api/activities/{activity_id}/running-dynamics-history")
def get_activity_running_dynamics_history_endpoint(activity_id: int, limit: int = 5) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit debe ser mayor que 0.")
    if limit > 20:
        raise HTTPException(status_code=400, detail="limit no puede ser mayor que 20.")
    history = get_activity_running_dynamics_history(activity_id, limit=limit)
    if history is None:
        raise HTTPException(status_code=404, detail=f"No existe la actividad {activity_id}.")
    return history


@app.post("/api/activities/{activity_id}/quality/replay")
def replay_activity_quality_endpoint(activity_id: int, payload: ActivityQualityReplayPayload) -> dict[str, Any]:
    storage = GarminImportStorage()
    try:
        result = storage.replay_activity_quality(activity_id, source_mode=payload.source_mode)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail=f"No existe la actividad {activity_id}.")
    return result


@app.get("/api/activities/{activity_id}/weather")
def get_activity_weather_endpoint(activity_id: int) -> dict[str, Any]:
    payload = get_activity_weather(activity_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No existe enriquecimiento meteorologico para la actividad {activity_id}.")
    return payload


@app.post("/api/activities/{activity_id}/weather/enrich")
def enrich_activity_weather_endpoint(activity_id: int, payload: ActivityWeatherEnrichPayload) -> dict[str, Any]:
    try:
        return enrich_activity_weather(activity_id, force=payload.force)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/activities/weather/backfill")
def backfill_activity_weather_endpoint(payload: ActivityWeatherBackfillPayload) -> dict[str, Any]:
    if payload.activity_id is None and payload.season_id is None and payload.date_from is None and payload.date_to is None:
        raise HTTPException(status_code=400, detail="Debes indicar activity_id o un rango/temporada para backfill meteorologico.")
    return backfill_activity_weather_batch(
        activity_id=payload.activity_id,
        season_id=payload.season_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        limit=payload.limit,
        force=payload.force,
    )


@app.get("/api/activities/{activity_id}/zones")
def get_activity_zones_endpoint(activity_id: int) -> dict[str, Any]:
    payload = get_activity_zone_detail(activity_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No existe la actividad {activity_id}.")
    if not payload["results"]:
        raise HTTPException(status_code=404, detail=f"No existen zonas calculadas para la actividad {activity_id}.")
    return payload


@app.get("/api/seasons")
def get_seasons() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT season_id, season_code, season_name, start_date, end_date, status
        FROM plan_seasons
        ORDER BY season_code
        """
    )


@app.get("/api/seasons/{season_id}/blocks")
def get_blocks(season_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT block_id, block_code, block_name, phase_name, sequence_order,
               start_date, end_date, objective_primary
        FROM plan_meso_blocks
        WHERE season_id = ?
        ORDER BY sequence_order
        """,
        (season_id,),
    )
    return ensure_entity_exists(rows, f"No se encontraron bloques para la temporada {season_id}.")


@app.get("/api/blocks/{block_id}/weeks")
def get_weeks(block_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT week_id, week_code, sequence_in_block, start_date, end_date,
               week_role, objective_primary, target_volume_hours_min,
               target_volume_hours_max
        FROM plan_micro_weeks
        WHERE block_id = ?
        ORDER BY sequence_in_block
        """,
        (block_id,),
    )
    return ensure_entity_exists(rows, f"No se encontraron semanas para el bloque {block_id}.")


@app.get("/api/blocks/{block_id}/review")
def get_block_review(block_id: int) -> dict[str, Any]:
    block = get_block_context(block_id)
    row = fetch_one(
        """
        SELECT block_review_id, season_id, block_id, review_status, closed_at,
               weeks_in_block, total_sessions, completed_sessions, partial_sessions,
               pending_sessions, skipped_sessions, replaced_sessions,
               adherence_rate, traceability_rate, planned_reference_minutes,
               actual_minutes, volume_delta_minutes, key_sessions_total,
               key_sessions_closed, aligned_zone_sessions, limited_zone_sessions,
               misaligned_zone_sessions, daily_training_load_total,
               daily_training_load_peak, starting_tsb, ending_tsb, lowest_tsb,
               starting_atl, ending_atl, starting_ctl, ending_ctl,
               avg_sleep_hours, avg_resting_hr, avg_stress,
               starting_weight_kg, ending_weight_kg, weight_delta_kg,
               risk_level, recommendation_text, summary_text,
               created_at, updated_at
        FROM review_block_reviews
        WHERE block_id = ?
        """,
        (block_id,),
    )
    if row is None:
        return {
            "block_id": block["block_id"],
            "season_id": block["season_id"],
            "block_code": block["block_code"],
            "block_name": block["block_name"],
            "review_status": "open",
            "closed_at": None,
            "risk_level": None,
            "recommendation_text": None,
            "summary_text": None,
            "block_assessment_available": False,
            "block_assessment_url": None,
        }

    markdown_path = get_block_assessment_markdown_path(int(row["season_id"]), str(block["block_code"]), int(block_id))
    row["block_code"] = block["block_code"]
    row["block_name"] = block["block_name"]
    row["block_assessment_available"] = markdown_path.exists()
    row["block_assessment_url"] = f"/api/blocks/{block_id}/assessment-markdown" if markdown_path.exists() else None
    return row


@app.get("/api/blocks/{block_id}/assessment-markdown")
def get_block_assessment_markdown(block_id: int) -> FileResponse:
    block = get_block_context(block_id)
    row = fetch_one(
        """
        SELECT block_review_id, season_id, block_id
        FROM review_block_reviews
        WHERE block_id = ?
        """,
        (block_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No se encontro la revision de bloque {block_id}.")

    markdown_path = get_block_assessment_markdown_path(int(row["season_id"]), str(block["block_code"]), int(block_id))
    if not markdown_path.exists():
        raise HTTPException(status_code=404, detail="No existe markdown para esta revision de bloque.")
    return FileResponse(markdown_path, media_type="text/markdown")


@app.get("/api/weeks/{week_id}/sessions")
def get_sessions(week_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
             SELECT ps.planned_session_id, ps.session_date, ps.day_name, ps.planned_role,
                     ps.planned_type AS prescription_type, ps.planned_type, ps.objective,
           ps.primary_session, ps.complementary_session, ps.intensity_class,
             up.support_routine AS planned_support_routine,
           ps.duration_min, ps.duration_max, ps.is_key_session
        FROM plan_planned_sessions
        AS ps
        JOIN plan_micro_weeks mw ON mw.week_id = ps.week_id
        JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
        LEFT JOIN plan_user_profiles up ON up.season_id = mb.season_id
       WHERE ps.week_id = ?
       ORDER BY ps.sequence_in_week
        """,
        (week_id,),
    )
    attach_planned_activity_groups(rows)
    attach_planned_prescriptions(rows)
    for row in rows:
        row["planned_zone_target"] = get_planned_session_zone_target(row["planned_session_id"])
    return ensure_entity_exists(rows, f"No se encontraron sesiones para la semana {week_id}.")


@app.get("/api/planned-sessions/{planned_session_id}/prescription")
def get_session_prescription(planned_session_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        payload = get_planned_session_prescription(connection, planned_session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No existe prescripcion estructurada para la sesion {planned_session_id}.")
    return payload


@app.get("/api/weeks/{week_id}/plan-vs-real")
def get_week_plan_vs_real(week_id: int) -> list[dict[str, Any]]:
    rows = get_week_plan_vs_real_rows(week_id)
    return ensure_entity_exists(rows, f"No se encontro comparativa plan vs realidad para la semana {week_id}.")


@app.get("/api/daily-reviews/{daily_review_id}/markdown")
def get_daily_review_markdown(daily_review_id: int) -> FileResponse:
    row = fetch_one(
        """
        SELECT daily_review_id, season_id, review_date, planned_session_id
        FROM review_daily_reviews
        WHERE daily_review_id = ?
        """,
        (daily_review_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No se encontro la revision diaria {daily_review_id}.")

    markdown_path = get_daily_assessment_markdown_path(int(row["season_id"]), str(row["review_date"]), row["planned_session_id"])
    if not markdown_path.exists():
        raise HTTPException(status_code=404, detail="No existe markdown para esta revision diaria.")
    return FileResponse(markdown_path, media_type="text/markdown")


@app.get("/api/weeks/{week_id}/review")
def get_weekly_review(week_id: int) -> dict[str, Any]:
    week = get_week_context(week_id)
    row = fetch_one(
        """
        SELECT weekly_review_id, season_id, block_id, week_id, review_status, closed_at,
               adherence_rate, traceability_rate, actual_minutes, planned_reference_minutes,
               volume_delta_minutes, risk_level, recommendation_text, summary_text,
               created_at, updated_at
        FROM review_weekly_reviews
        WHERE week_id = ?
        """,
        (week_id,),
    )
    if row is None:
        return {
            "week_id": week["week_id"],
            "week_code": week["week_code"],
            "review_status": "open",
            "closed_at": None,
            "risk_level": None,
            "recommendation_text": None,
            "summary_text": None,
            "weekly_assessment_available": False,
            "weekly_assessment_url": None,
            "zone_comparison_summary": get_week_zone_comparison_summary(week_id),
        }
    markdown_path = get_weekly_assessment_markdown_path(int(row["season_id"]), str(week["week_code"]), int(week["week_id"]))
    row["week_code"] = week["week_code"]
    row["weekly_assessment_available"] = markdown_path.exists()
    row["weekly_assessment_url"] = f"/api/weeks/{week_id}/assessment-markdown" if markdown_path.exists() else None
    row["zone_comparison_summary"] = get_week_zone_comparison_summary(week_id)
    return row


@app.get("/api/weeks/{week_id}/assessment-markdown")
def get_weekly_assessment_markdown(week_id: int) -> FileResponse:
    week = get_week_context(week_id)
    row = fetch_one(
        """
        SELECT weekly_review_id, season_id, week_id
        FROM review_weekly_reviews
        WHERE week_id = ?
        """,
        (week_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No se encontro la revision semanal {week_id}.")

    markdown_path = get_weekly_assessment_markdown_path(int(row["season_id"]), str(week["week_code"]), int(week_id))
    if not markdown_path.exists():
        raise HTTPException(status_code=404, detail="No existe markdown para esta revision semanal.")
    return FileResponse(markdown_path, media_type="text/markdown")


@app.get("/api/seasons/{season_id}/weight-review/latest")
def get_latest_weight_review(season_id: int) -> dict[str, Any]:
    season = fetch_one(
        """
        SELECT season_id
        FROM plan_seasons
        WHERE season_id = ?
        """,
        (season_id,),
    )
    if season is None:
        raise HTTPException(status_code=404, detail=f"No se encontro la temporada {season_id}.")

    row = fetch_one(
        """
        SELECT weight_review_id, season_id, review_date, block_id, week_id,
               reference_weight_kg, target_weight_kg,
               latest_weight_kg, latest_7d_avg_kg, delta_7d_avg_kg,
               latest_14d_avg_kg, delta_14d_avg_kg, volatility_7d_kg,
               gap_to_target_kg, classification, recommendation_text, summary_text,
               created_at, updated_at
        FROM review_weight_reviews
        WHERE season_id = ?
        ORDER BY review_date DESC, weight_review_id DESC
        LIMIT 1
        """,
        (season_id,),
    )
    if row is None:
        return {
            "season_id": season_id,
            "weight_review_id": None,
            "review_date": None,
            "classification": None,
            "recommendation_text": None,
            "summary_text": None,
            "latest_weight_kg": None,
            "latest_7d_avg_kg": None,
            "delta_7d_avg_kg": None,
            "latest_14d_avg_kg": None,
            "delta_14d_avg_kg": None,
            "volatility_7d_kg": None,
            "gap_to_target_kg": None,
            "weight_assessment_available": False,
            "weight_assessment_url": None,
        }

    markdown_path = get_weight_assessment_markdown_path(int(row["season_id"]), str(row["review_date"]))
    row["weight_assessment_available"] = markdown_path.exists()
    row["weight_assessment_url"] = (
        f"/api/weight-reviews/{row['weight_review_id']}/assessment-markdown" if markdown_path.exists() else None
    )
    return row


@app.get("/api/weight-reviews/{weight_review_id}/assessment-markdown")
def get_weight_assessment_markdown(weight_review_id: int) -> FileResponse:
    row = fetch_one(
        """
        SELECT weight_review_id, season_id, review_date
        FROM review_weight_reviews
        WHERE weight_review_id = ?
        """,
        (weight_review_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No se encontro la revision de peso {weight_review_id}.")

    markdown_path = get_weight_assessment_markdown_path(int(row["season_id"]), str(row["review_date"]))
    if not markdown_path.exists():
        raise HTTPException(status_code=404, detail="No existe markdown para esta revision de peso.")
    return FileResponse(markdown_path, media_type="text/markdown")


@app.put("/api/weeks/{week_id}/review")
def upsert_weekly_review(week_id: int, payload: WeeklyReviewPayload) -> dict[str, Any]:
    metrics = calculate_weekly_review_metrics(week_id)
    summary_text = payload.summary_text or metrics["summary_text"]
    recommendation_text = payload.recommendation_text or metrics["recommendation_text"]
    risk_level = payload.risk_level or metrics["risk_level"]

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO review_weekly_reviews (
                season_id, block_id, week_id, review_status, closed_at, adherence_rate,
                traceability_rate, actual_minutes, planned_reference_minutes,
                volume_delta_minutes, risk_level, recommendation_text, summary_text,
                updated_at
            ) VALUES (?, ?, ?, 'closed', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(week_id) DO UPDATE SET
                review_status = 'closed',
                closed_at = CURRENT_TIMESTAMP,
                adherence_rate = excluded.adherence_rate,
                traceability_rate = excluded.traceability_rate,
                actual_minutes = excluded.actual_minutes,
                planned_reference_minutes = excluded.planned_reference_minutes,
                volume_delta_minutes = excluded.volume_delta_minutes,
                risk_level = excluded.risk_level,
                recommendation_text = excluded.recommendation_text,
                summary_text = excluded.summary_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                metrics["season_id"],
                metrics["block_id"],
                metrics["week_id"],
                metrics["adherence_rate"],
                metrics["traceability_rate"],
                metrics["actual_minutes"],
                metrics["planned_reference_minutes"],
                metrics["volume_delta_minutes"],
                risk_level,
                recommendation_text,
                summary_text,
            ),
        )

    review = get_weekly_review(week_id)
    review["recommendation_text"] = recommendation_text
    review["risk_level"] = risk_level
    review["summary_text"] = summary_text
    review["adherence_rate"] = metrics["adherence_rate"]
    review["traceability_rate"] = metrics["traceability_rate"]
    review["actual_minutes"] = metrics["actual_minutes"]
    review["planned_reference_minutes"] = metrics["planned_reference_minutes"]
    review["volume_delta_minutes"] = metrics["volume_delta_minutes"]
    return review


@app.delete("/api/weeks/{week_id}/review")
def reopen_weekly_review(week_id: int) -> dict[str, Any]:
    get_week_context(week_id)
    with get_connection() as connection:
        connection.execute("DELETE FROM review_weekly_reviews WHERE week_id = ?", (week_id,))
    return {"status": "ok", "week_id": week_id, "review_status": "open"}
