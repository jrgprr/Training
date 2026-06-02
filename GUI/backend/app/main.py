from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .activity_quality import get_activity_quality
from .db import get_connection, get_database_path, initialize_database
from .imports import GarminConnectAdapter, GarminConnectImportError, GarminConnectNotConfiguredError, GarminImportPipeline, GarminImportRequest, GarminImportStorage, classify_garmin_failure
from .load_engine import get_load_model_snapshot
from .segments import get_segment_history, list_segments
from .training_zones import accept_zone_metric_profile, accept_zone_refinement_proposal, get_activity_zone_detail, get_planned_session_zone_target, get_week_zone_comparison_summary, get_zone_proposal_detail, list_activity_zone_summaries, list_current_zone_metric_profiles, list_current_zone_profiles, list_session_zone_comparisons, list_zone_proposals

app = FastAPI(title="Training System GUI API", version="0.2.0")

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


class WeeklyReviewPayload(BaseModel):
    summary_text: str | None = None


class GarminConnectImportPayload(BaseModel):
    season_id: int
    date_from: str
    date_to: str
    include_daily_metrics: bool = True


class ActivityQualityReplayPayload(BaseModel):
    source_mode: str = "canonical"


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


class SegmentListQuery(BaseModel):
    season_id: int
    query: str | None = None
    limit: int = 50


def get_daily_metric(season_id: int, metric_date: str) -> dict[str, Any]:
    metric = fetch_one(
        """
        SELECT daily_metric_id, season_id, metric_date, source_system,
               weight_kg, sleep_hours, sleep_quality, resting_hr, hrv, body_battery,
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
    return metric


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
        SELECT ps.planned_session_id, ps.session_date, ps.day_name, ps.planned_type,
               ps.objective AS planned_objective, ps.primary_session AS planned_session,
               ps.duration_min, ps.duration_max, ps.is_key_session,
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
        LEFT JOIN ranked_links rl ON rl.planned_session_id = ps.planned_session_id AND rl.link_rank = 1
        LEFT JOIN review_daily_reviews rr ON rr.planned_session_id = ps.planned_session_id
        WHERE ps.week_id = ?
        ORDER BY ps.sequence_in_week
        """,
        (week_id,),
    )

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


def get_planned_session_context(planned_session_id: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT ps.planned_session_id, ps.session_date, ps.objective, ps.primary_session,
               w.week_id, b.block_id, b.season_id
        FROM plan_planned_sessions ps
        JOIN plan_micro_weeks w ON w.week_id = ps.week_id
        JOIN plan_meso_blocks b ON b.block_id = w.block_id
        WHERE ps.planned_session_id = ?
        """,
        (planned_session_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No existe la sesion planificada {planned_session_id}.")
    return row


def get_planned_session_prescription(planned_session_id: int) -> dict[str, Any]:
    session = fetch_one(
        """
        SELECT ps.planned_session_id, ps.session_date, ps.day_name, ps.planned_type,
               ps.objective, ps.primary_session, ps.complementary_session,
               p.prescription_id, p.prescription_type, p.title, p.focus_primary,
               p.focus_secondary, p.estimated_duration_min, p.estimated_duration_max,
               p.target_rpe_min, p.target_rpe_max, p.warmup_notes, p.cooldown_notes,
               p.execution_notes, p.adaptation_notes, p.source_markdown_path
        FROM plan_planned_sessions ps
        JOIN plan_session_prescriptions p ON p.planned_session_id = ps.planned_session_id
        WHERE ps.planned_session_id = ?
        """,
        (planned_session_id,),
    )
    if session is None:
        raise HTTPException(status_code=404, detail=f"No existe prescripcion estructurada para la sesion {planned_session_id}.")

    blocks = fetch_all(
        """
        SELECT prescription_block_id, sequence_order, block_type, block_name,
               objective, rounds, rest_seconds, notes
        FROM plan_prescription_blocks
        WHERE prescription_id = ?
        ORDER BY sequence_order
        """,
        (session["prescription_id"],),
    )

    exercises = fetch_all(
        """
        SELECT prescription_exercise_id, prescription_block_id, sequence_order,
               exercise_name, movement_pattern, equipment, unilateral_mode,
               sets_count, reps_min, reps_max, hold_seconds_min, hold_seconds_max,
               distance_meters, target_rpe_min, target_rpe_max, target_rir_min,
               target_rir_max, tempo, load_guidance, optional_flag,
               substitution_group, notes
        FROM plan_prescription_exercises
        WHERE prescription_block_id IN (
            SELECT prescription_block_id
            FROM plan_prescription_blocks
            WHERE prescription_id = ?
        )
        ORDER BY prescription_block_id, sequence_order
        """,
        (session["prescription_id"],),
    )

    options = fetch_all(
        """
        SELECT exercise_option_id, prescription_exercise_id, sequence_order,
               option_name, equipment, condition_notes
        FROM plan_prescription_exercise_options
        WHERE prescription_exercise_id IN (
            SELECT prescription_exercise_id
            FROM plan_prescription_exercises
            WHERE prescription_block_id IN (
                SELECT prescription_block_id
                FROM plan_prescription_blocks
                WHERE prescription_id = ?
            )
        )
        ORDER BY prescription_exercise_id, sequence_order
        """,
        (session["prescription_id"],),
    )

    options_by_exercise: dict[int, list[dict[str, Any]]] = {}
    for option in options:
        options_by_exercise.setdefault(option["prescription_exercise_id"], []).append(option)

    exercises_by_block: dict[int, list[dict[str, Any]]] = {}
    for exercise in exercises:
        exercise["options"] = options_by_exercise.get(exercise["prescription_exercise_id"], [])
        exercises_by_block.setdefault(exercise["prescription_block_id"], []).append(exercise)

    for block in blocks:
        block["exercises"] = exercises_by_block.get(block["prescription_block_id"], [])

    session["blocks"] = blocks
    return session


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


@app.get("/api/weeks/{week_id}/sessions")
def get_sessions(week_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT planned_session_id, session_date, day_name, planned_type, objective,
               primary_session, complementary_session, intensity_class,
               duration_min, duration_max, is_key_session,
               EXISTS (
                   SELECT 1
                   FROM plan_session_prescriptions p
                   WHERE p.planned_session_id = ps.planned_session_id
               ) AS has_structured_prescription
        FROM plan_planned_sessions
        AS ps
        WHERE week_id = ?
        ORDER BY sequence_in_week
        """,
        (week_id,),
    )
    for row in rows:
        row["planned_zone_target"] = get_planned_session_zone_target(row["planned_session_id"])
    return ensure_entity_exists(rows, f"No se encontraron sesiones para la semana {week_id}.")


@app.get("/api/planned-sessions/{planned_session_id}/prescription")
def get_session_prescription(planned_session_id: int) -> dict[str, Any]:
    payload = get_planned_session_prescription(planned_session_id)
    payload["planned_zone_target"] = get_planned_session_zone_target(planned_session_id)
    return payload


@app.get("/api/weeks/{week_id}/plan-vs-real")
def get_week_plan_vs_real(week_id: int) -> list[dict[str, Any]]:
    rows = get_week_plan_vs_real_rows(week_id)
    return ensure_entity_exists(rows, f"No se encontro comparativa plan vs realidad para la semana {week_id}.")


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
            "zone_comparison_summary": get_week_zone_comparison_summary(week_id),
        }
    row["week_code"] = week["week_code"]
    row["zone_comparison_summary"] = get_week_zone_comparison_summary(week_id)
    return row


@app.put("/api/weeks/{week_id}/review")
def upsert_weekly_review(week_id: int, payload: WeeklyReviewPayload) -> dict[str, Any]:
    metrics = calculate_weekly_review_metrics(week_id)
    summary_text = payload.summary_text or metrics["summary_text"]

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
                metrics["risk_level"],
                metrics["recommendation_text"],
                summary_text,
            ),
        )

    review = get_weekly_review(week_id)
    review["recommendation_text"] = metrics["recommendation_text"]
    review["risk_level"] = metrics["risk_level"]
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


@app.post("/api/manual/session-executions")
def create_manual_session_execution() -> dict[str, Any]:
    raise HTTPException(
        status_code=410,
        detail="El entorno actual esta en modo Garmin-only. El registro manual esta deshabilitado.",
    )
