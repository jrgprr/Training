from __future__ import annotations

import sqlite3
from pathlib import Path


WEEKLY_REVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_weekly_reviews (
    weekly_review_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    block_id INTEGER NOT NULL,
    week_id INTEGER NOT NULL UNIQUE,
    review_status TEXT NOT NULL DEFAULT 'open',
    closed_at TEXT,
    adherence_rate REAL,
    traceability_rate REAL,
    actual_minutes INTEGER,
    planned_reference_minutes INTEGER,
    volume_delta_minutes INTEGER,
    risk_level TEXT,
    recommendation_text TEXT,
    summary_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id),
    FOREIGN KEY (block_id) REFERENCES plan_meso_blocks (block_id),
    FOREIGN KEY (week_id) REFERENCES plan_micro_weeks (week_id)
);

CREATE INDEX IF NOT EXISTS idx_weekly_reviews_status ON review_weekly_reviews (season_id, review_status);
"""


IMPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta_import_jobs (
    import_job_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    source_system TEXT NOT NULL,
    import_type TEXT NOT NULL,
    source_path TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    request_date_from TEXT,
    request_date_to TEXT,
    include_daily_metrics INTEGER NOT NULL DEFAULT 1,
    rows_detected INTEGER,
    rows_loaded INTEGER,
    status TEXT NOT NULL,
    failure_stage TEXT,
    failure_class TEXT,
    retry_suitability TEXT,
    partial_completion INTEGER NOT NULL DEFAULT 0,
    operator_detail TEXT,
    activity_rows_detected INTEGER NOT NULL DEFAULT 0,
    activity_rows_inserted INTEGER NOT NULL DEFAULT 0,
    activity_rows_updated INTEGER NOT NULL DEFAULT 0,
    activity_rows_skipped INTEGER NOT NULL DEFAULT 0,
    daily_metric_rows_detected INTEGER NOT NULL DEFAULT 0,
    daily_metric_rows_inserted INTEGER NOT NULL DEFAULT 0,
    daily_metric_rows_updated INTEGER NOT NULL DEFAULT 0,
    daily_metric_rows_skipped INTEGER NOT NULL DEFAULT 0,
    segment_activities_checked INTEGER NOT NULL DEFAULT 0,
    segment_activities_with_data INTEGER NOT NULL DEFAULT 0,
    segment_efforts_detected INTEGER NOT NULL DEFAULT 0,
    segment_efforts_inserted INTEGER NOT NULL DEFAULT 0,
    segment_efforts_updated INTEGER NOT NULL DEFAULT 0,
    segment_efforts_skipped INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

CREATE TABLE IF NOT EXISTS staging_garmin_activities (
    staging_activity_id INTEGER PRIMARY KEY,
    import_job_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    source_system TEXT NOT NULL,
    external_activity_id TEXT,
    activity_date TEXT NOT NULL,
    started_at TEXT,
    discipline TEXT,
    activity_type TEXT,
    duration_seconds REAL,
    distance_meters REAL,
    ascent_meters REAL,
    calories REAL,
    avg_hr REAL,
    max_hr REAL,
    avg_power REAL,
    normalized_power REAL,
    training_load REAL,
    avg_pace_seconds_per_km REAL,
    raw_payload_path TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (import_job_id) REFERENCES meta_import_jobs (import_job_id)
);

CREATE TABLE IF NOT EXISTS staging_garmin_daily_metrics (
    staging_daily_metric_id INTEGER PRIMARY KEY,
    import_job_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    source_system TEXT NOT NULL,
    metric_date TEXT NOT NULL,
    weight_kg REAL,
    body_fat_pct REAL,
    body_water_pct REAL,
    bone_mass_kg REAL,
    muscle_mass_kg REAL,
    bmi REAL,
    visceral_fat REAL,
    metabolic_age REAL,
    physique_rating REAL,
    sleep_hours REAL,
    sleep_quality TEXT,
    resting_hr REAL,
    vo2max_cycling REAL,
    vo2max_running REAL,
    lactate_threshold_hr REAL,
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
    notes TEXT,
    raw_payload_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (import_job_id) REFERENCES meta_import_jobs (import_job_id)
);

CREATE INDEX IF NOT EXISTS idx_import_jobs_season_date ON meta_import_jobs (season_id, imported_at DESC);
CREATE INDEX IF NOT EXISTS idx_staging_garmin_activities_job ON staging_garmin_activities (import_job_id);
CREATE INDEX IF NOT EXISTS idx_staging_garmin_metrics_job ON staging_garmin_daily_metrics (import_job_id);

CREATE TABLE IF NOT EXISTS exec_segments (
    segment_id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    external_segment_id TEXT NOT NULL,
    segment_name TEXT,
    discipline TEXT,
    distance_meters REAL,
    ascent_meters REAL,
    average_grade_percent REAL,
    first_seen_activity_id INTEGER,
    last_seen_activity_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, external_segment_id),
    FOREIGN KEY (first_seen_activity_id) REFERENCES exec_activities (activity_id),
    FOREIGN KEY (last_seen_activity_id) REFERENCES exec_activities (activity_id)
);

CREATE TABLE IF NOT EXISTS exec_segment_efforts (
    segment_effort_id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    external_segment_effort_id TEXT NOT NULL,
    segment_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    activity_date TEXT NOT NULL,
    started_at TEXT,
    elapsed_time_seconds INTEGER,
    avg_power REAL,
    avg_cadence REAL,
    avg_heart_rate REAL,
    max_heart_rate REAL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, external_segment_effort_id),
    FOREIGN KEY (segment_id) REFERENCES exec_segments (segment_id),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id)
);

CREATE INDEX IF NOT EXISTS idx_exec_segments_name ON exec_segments (segment_name);
CREATE INDEX IF NOT EXISTS idx_exec_segment_efforts_segment_date ON exec_segment_efforts (segment_id, activity_date DESC);
CREATE INDEX IF NOT EXISTS idx_exec_segment_efforts_activity ON exec_segment_efforts (activity_id);

CREATE TABLE IF NOT EXISTS exec_activity_metric_readings (
    activity_metric_reading_id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    sample_index INTEGER NOT NULL,
    raw_value REAL NOT NULL,
    recorded_at TEXT,
    elapsed_seconds REAL,
    source_payload_kind TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_id, metric_name, sample_index),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id)
);

CREATE TABLE IF NOT EXISTS exec_activity_quality_runs (
    quality_run_id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL,
    rule_set_key TEXT NOT NULL,
    rule_set_version TEXT NOT NULL,
    source_reading_fingerprint TEXT NOT NULL,
    source_payload_path TEXT,
    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    evaluated_metric_names TEXT,
    skipped_metric_names TEXT,
    evaluated_reading_count INTEGER NOT NULL DEFAULT 0,
    excluded_reading_count INTEGER NOT NULL DEFAULT 0,
    limited_metric_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    UNIQUE (activity_id, rule_set_key, rule_set_version, source_reading_fingerprint),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id)
);

CREATE TABLE IF NOT EXISTS exec_activity_quality_decisions (
    quality_decision_id INTEGER PRIMARY KEY,
    quality_run_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    start_sample_index INTEGER NOT NULL,
    end_sample_index INTEGER NOT NULL,
    reason_code TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    threshold_low REAL,
    threshold_high REAL,
    evidence_json TEXT,
    impacted_summary_kinds TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (quality_run_id, metric_name, start_sample_index, end_sample_index, rule_key),
    FOREIGN KEY (quality_run_id) REFERENCES exec_activity_quality_runs (quality_run_id),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id)
);

CREATE TABLE IF NOT EXISTS exec_activity_metric_summaries (
    activity_metric_summary_id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL,
    quality_run_id INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    summary_kind TEXT NOT NULL,
    source_value REAL,
    trusted_value REAL,
    summary_status TEXT NOT NULL,
    evaluated_reading_count INTEGER NOT NULL DEFAULT 0,
    accepted_reading_count INTEGER NOT NULL DEFAULT 0,
    excluded_reading_count INTEGER NOT NULL DEFAULT 0,
    changed_by_filter INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_id, metric_name, summary_kind),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id),
    FOREIGN KEY (quality_run_id) REFERENCES exec_activity_quality_runs (quality_run_id)
);

CREATE INDEX IF NOT EXISTS idx_exec_activity_metric_readings_activity_metric ON exec_activity_metric_readings (activity_id, metric_name);
CREATE INDEX IF NOT EXISTS idx_exec_activity_quality_runs_activity ON exec_activity_quality_runs (activity_id, evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_exec_activity_quality_decisions_activity_metric ON exec_activity_quality_decisions (activity_id, metric_name, start_sample_index);
CREATE INDEX IF NOT EXISTS idx_exec_activity_metric_summaries_activity_metric ON exec_activity_metric_summaries (activity_id, metric_name, summary_kind);
"""


PRESCRIPTION_SCHEMA = """
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
    source_markdown_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planned_session_id) REFERENCES plan_planned_sessions (planned_session_id)
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
    notes TEXT,
    FOREIGN KEY (prescription_id) REFERENCES plan_session_prescriptions (prescription_id),
    UNIQUE (prescription_id, sequence_order)
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
    notes TEXT,
    FOREIGN KEY (prescription_block_id) REFERENCES plan_prescription_blocks (prescription_block_id),
    UNIQUE (prescription_block_id, sequence_order)
);

CREATE TABLE IF NOT EXISTS plan_prescription_exercise_options (
    exercise_option_id INTEGER PRIMARY KEY,
    prescription_exercise_id INTEGER NOT NULL,
    sequence_order INTEGER NOT NULL,
    option_name TEXT NOT NULL,
    equipment TEXT,
    condition_notes TEXT,
    FOREIGN KEY (prescription_exercise_id) REFERENCES plan_prescription_exercises (prescription_exercise_id),
    UNIQUE (prescription_exercise_id, sequence_order)
);

CREATE INDEX IF NOT EXISTS idx_plan_prescriptions_session ON plan_session_prescriptions (planned_session_id);
CREATE INDEX IF NOT EXISTS idx_plan_prescription_blocks_prescription ON plan_prescription_blocks (prescription_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_plan_prescription_exercises_block ON plan_prescription_exercises (prescription_block_id, sequence_order);
"""


ZONE_SCHEMA = """
CREATE TABLE IF NOT EXISTS zone_metric_profiles (
    zone_metric_profile_id INTEGER PRIMARY KEY,
    season_id INTEGER,
    discipline TEXT NOT NULL,
    metric_basis TEXT NOT NULL,
    profile_label TEXT,
    model_key TEXT NOT NULL,
    resting_hr REAL,
    max_hr REAL,
    ftp REAL,
    effective_start_date TEXT NOT NULL,
    effective_end_date TEXT,
    accepted_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (discipline, metric_basis, effective_start_date),
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

CREATE TABLE IF NOT EXISTS zone_profiles (
    zone_profile_id INTEGER PRIMARY KEY,
    season_id INTEGER,
    discipline TEXT NOT NULL,
    metric_basis TEXT NOT NULL,
    profile_label TEXT,
    governance_status TEXT NOT NULL DEFAULT 'pending',
    effective_start_date TEXT NOT NULL,
    effective_end_date TEXT,
    accepted_at TEXT,
    derived_from_proposal_id INTEGER,
    source_metric_profile_id INTEGER,
    calculation_model_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (discipline, metric_basis, effective_start_date, governance_status),
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id),
    FOREIGN KEY (derived_from_proposal_id) REFERENCES zone_refinement_proposals (proposal_id),
    FOREIGN KEY (source_metric_profile_id) REFERENCES zone_metric_profiles (zone_metric_profile_id)
);

CREATE TABLE IF NOT EXISTS zone_profile_boundaries (
    zone_profile_boundary_id INTEGER PRIMARY KEY,
    zone_profile_id INTEGER NOT NULL,
    zone_index INTEGER NOT NULL,
    zone_code TEXT NOT NULL,
    zone_name TEXT,
    lower_bound_value REAL,
    upper_bound_value REAL,
    bound_unit TEXT NOT NULL,
    target_kind TEXT NOT NULL DEFAULT 'closed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (zone_profile_id, zone_index),
    UNIQUE (zone_profile_id, zone_code),
    FOREIGN KEY (zone_profile_id) REFERENCES zone_profiles (zone_profile_id)
);

CREATE TABLE IF NOT EXISTS zone_refinement_proposals (
    proposal_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    discipline TEXT NOT NULL,
    metric_basis TEXT NOT NULL,
    source_zone_profile_id INTEGER,
    proposal_status TEXT NOT NULL DEFAULT 'pending',
    confidence_level TEXT NOT NULL DEFAULT 'medium',
    recommendation_kind TEXT NOT NULL DEFAULT 'rebalance',
    proposal_summary TEXT,
    limiting_factors TEXT,
    proposed_effective_start_date TEXT,
    decided_at TEXT,
    decision_notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id),
    FOREIGN KEY (source_zone_profile_id) REFERENCES zone_profiles (zone_profile_id)
);

CREATE TABLE IF NOT EXISTS zone_refinement_proposal_boundaries (
    proposal_boundary_id INTEGER PRIMARY KEY,
    proposal_id INTEGER NOT NULL,
    zone_index INTEGER NOT NULL,
    zone_code TEXT NOT NULL,
    proposed_lower_bound_value REAL,
    proposed_upper_bound_value REAL,
    bound_unit TEXT NOT NULL,
    delta_vs_current_lower REAL,
    delta_vs_current_upper REAL,
    UNIQUE (proposal_id, zone_index),
    FOREIGN KEY (proposal_id) REFERENCES zone_refinement_proposals (proposal_id)
);

CREATE TABLE IF NOT EXISTS zone_refinement_evidence (
    proposal_evidence_id INTEGER PRIMARY KEY,
    proposal_id INTEGER NOT NULL,
    evidence_type TEXT NOT NULL,
    activity_id INTEGER,
    daily_metric_id INTEGER,
    evidence_date TEXT,
    evidence_role TEXT NOT NULL,
    metric_basis TEXT,
    summary_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id) REFERENCES zone_refinement_proposals (proposal_id),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id),
    FOREIGN KEY (daily_metric_id) REFERENCES exec_daily_metrics (daily_metric_id)
);

CREATE TABLE IF NOT EXISTS exec_activity_zone_results (
    activity_zone_result_id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL,
    zone_profile_id INTEGER NOT NULL,
    metric_basis TEXT NOT NULL,
    calculation_status TEXT NOT NULL DEFAULT 'unavailable',
    quality_status_snapshot TEXT,
    supported_sample_count INTEGER NOT NULL DEFAULT 0,
    total_supported_seconds INTEGER NOT NULL DEFAULT 0,
    dominant_zone_code TEXT,
    dominant_zone_share REAL,
    calculation_notes TEXT,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_id, metric_basis, zone_profile_id),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id),
    FOREIGN KEY (zone_profile_id) REFERENCES zone_profiles (zone_profile_id)
);

CREATE TABLE IF NOT EXISTS exec_activity_zone_buckets (
    activity_zone_bucket_id INTEGER PRIMARY KEY,
    activity_zone_result_id INTEGER NOT NULL,
    zone_index INTEGER NOT NULL,
    zone_code TEXT NOT NULL,
    seconds_in_zone INTEGER NOT NULL DEFAULT 0,
    share_in_zone REAL,
    sample_count INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_zone_result_id, zone_index),
    FOREIGN KEY (activity_zone_result_id) REFERENCES exec_activity_zone_results (activity_zone_result_id)
);

CREATE TABLE IF NOT EXISTS plan_session_zone_targets (
    planned_zone_target_id INTEGER PRIMARY KEY,
    planned_session_id INTEGER NOT NULL UNIQUE,
    target_basis TEXT,
    target_kind TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'explicit',
    source_text TEXT,
    comparison_eligibility TEXT NOT NULL DEFAULT 'eligible',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planned_session_id) REFERENCES plan_planned_sessions (planned_session_id)
);

CREATE TABLE IF NOT EXISTS plan_session_zone_segments (
    planned_zone_segment_id INTEGER PRIMARY KEY,
    planned_zone_target_id INTEGER NOT NULL,
    sequence_order INTEGER NOT NULL,
    segment_label TEXT,
    target_zone_min_code TEXT,
    target_zone_max_code TEXT,
    target_duration_seconds_min INTEGER,
    target_duration_seconds_max INTEGER,
    notes TEXT,
    UNIQUE (planned_zone_target_id, sequence_order),
    FOREIGN KEY (planned_zone_target_id) REFERENCES plan_session_zone_targets (planned_zone_target_id)
);

CREATE INDEX IF NOT EXISTS idx_zone_profiles_lookup ON zone_profiles (discipline, metric_basis, governance_status, effective_start_date DESC);
CREATE INDEX IF NOT EXISTS idx_zone_metric_profiles_lookup ON zone_metric_profiles (discipline, metric_basis, effective_start_date DESC);
CREATE INDEX IF NOT EXISTS idx_zone_proposals_lookup ON zone_refinement_proposals (season_id, discipline, metric_basis, proposal_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exec_activity_zone_results_activity ON exec_activity_zone_results (activity_id, metric_basis);
CREATE INDEX IF NOT EXISTS idx_plan_session_zone_targets_session ON plan_session_zone_targets (planned_session_id);
"""


DISCIPLINE_ALIASES = {
    "bicicleta": "road_biking",
    "caminar": "walking",
    "fuerza": "strength_training",
    "marcha nordica": "nordic_walking",
    "paseo": "walking",
    "senderismo": "hiking",
}


def get_database_path() -> Path:
    return Path(__file__).resolve().parents[3] / "Sistema" / "training.sqlite"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    return connection


def normalize_activity_discipline(discipline: str | None) -> str | None:
    if discipline is None:
        return None
    normalized = discipline.strip().lower()
    if not normalized:
        return None
    return DISCIPLINE_ALIASES.get(normalized, normalized)


def normalize_existing_manual_activity_disciplines(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE exec_activities
        SET discipline = CASE lower(trim(discipline))
            WHEN 'bicicleta' THEN 'road_biking'
            WHEN 'caminar' THEN 'walking'
            WHEN 'fuerza' THEN 'strength_training'
                        WHEN 'marcha nordica' THEN 'nordic_walking'
            WHEN 'paseo' THEN 'walking'
            WHEN 'senderismo' THEN 'hiking'
            ELSE lower(trim(discipline))
        END
        WHERE source_system LIKE 'manual%'
          AND discipline IS NOT NULL
                    AND lower(trim(discipline)) IN ('bicicleta', 'caminar', 'fuerza', 'marcha nordica', 'paseo', 'senderismo')
        """
    )


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(WEEKLY_REVIEW_SCHEMA)
        connection.executescript(IMPORT_SCHEMA)
        connection.executescript(PRESCRIPTION_SCHEMA)
        connection.executescript(ZONE_SCHEMA)
        _ensure_zone_schema(connection)
        _ensure_import_job_columns(connection)
        _ensure_daily_metric_columns(connection)
        _ensure_exec_activity_quality_schema(connection)
        normalize_existing_manual_activity_disciplines(connection)


def _ensure_zone_schema(connection: sqlite3.Connection) -> None:
    zone_profiles_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'zone_profiles'"
    ).fetchone()
    if zone_profiles_exists is not None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(zone_profiles)").fetchall()
        }
        expected_columns = {
            "source_metric_profile_id": "ALTER TABLE zone_profiles ADD COLUMN source_metric_profile_id INTEGER",
            "calculation_model_key": "ALTER TABLE zone_profiles ADD COLUMN calculation_model_key TEXT",
        }
        for column_name, statement in expected_columns.items():
            if column_name not in existing_columns:
                connection.execute(statement)

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_zone_metric_profiles_lookup ON zone_metric_profiles (discipline, metric_basis, effective_start_date DESC)"
    )


def _ensure_daily_metric_columns(connection: sqlite3.Connection) -> None:
    expected_columns_by_table = {
        "staging_garmin_daily_metrics": {
            "body_fat_pct": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN body_fat_pct REAL",
            "body_water_pct": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN body_water_pct REAL",
            "bone_mass_kg": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN bone_mass_kg REAL",
            "muscle_mass_kg": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN muscle_mass_kg REAL",
            "bmi": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN bmi REAL",
            "visceral_fat": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN visceral_fat REAL",
            "metabolic_age": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN metabolic_age REAL",
            "physique_rating": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN physique_rating REAL",
            "stress_avg": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN stress_avg REAL",
            "stress_max": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN stress_max REAL",
            "spo2_avg": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN spo2_avg REAL",
            "spo2_sleep_avg": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN spo2_sleep_avg REAL",
            "spo2_7d_avg": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN spo2_7d_avg REAL",
            "spo2_lowest": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN spo2_lowest REAL",
            "vo2max_cycling": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN vo2max_cycling REAL",
            "vo2max_running": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN vo2max_running REAL",
            "lactate_threshold_hr": "ALTER TABLE staging_garmin_daily_metrics ADD COLUMN lactate_threshold_hr REAL",
        },
        "exec_daily_metrics": {
            "body_fat_pct": "ALTER TABLE exec_daily_metrics ADD COLUMN body_fat_pct REAL",
            "body_water_pct": "ALTER TABLE exec_daily_metrics ADD COLUMN body_water_pct REAL",
            "bone_mass_kg": "ALTER TABLE exec_daily_metrics ADD COLUMN bone_mass_kg REAL",
            "muscle_mass_kg": "ALTER TABLE exec_daily_metrics ADD COLUMN muscle_mass_kg REAL",
            "bmi": "ALTER TABLE exec_daily_metrics ADD COLUMN bmi REAL",
            "visceral_fat": "ALTER TABLE exec_daily_metrics ADD COLUMN visceral_fat REAL",
            "metabolic_age": "ALTER TABLE exec_daily_metrics ADD COLUMN metabolic_age REAL",
            "physique_rating": "ALTER TABLE exec_daily_metrics ADD COLUMN physique_rating REAL",
            "stress_avg": "ALTER TABLE exec_daily_metrics ADD COLUMN stress_avg REAL",
            "stress_max": "ALTER TABLE exec_daily_metrics ADD COLUMN stress_max REAL",
            "spo2_avg": "ALTER TABLE exec_daily_metrics ADD COLUMN spo2_avg REAL",
            "spo2_sleep_avg": "ALTER TABLE exec_daily_metrics ADD COLUMN spo2_sleep_avg REAL",
            "spo2_7d_avg": "ALTER TABLE exec_daily_metrics ADD COLUMN spo2_7d_avg REAL",
            "spo2_lowest": "ALTER TABLE exec_daily_metrics ADD COLUMN spo2_lowest REAL",
            "vo2max_cycling": "ALTER TABLE exec_daily_metrics ADD COLUMN vo2max_cycling REAL",
            "vo2max_running": "ALTER TABLE exec_daily_metrics ADD COLUMN vo2max_running REAL",
            "lactate_threshold_hr": "ALTER TABLE exec_daily_metrics ADD COLUMN lactate_threshold_hr REAL",
        },
    }
    for table_name, expected_columns in expected_columns_by_table.items():
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if table_exists is None:
            continue
        existing_columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, statement in expected_columns.items():
            if column_name not in existing_columns:
                connection.execute(statement)


def _ensure_import_job_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(meta_import_jobs)").fetchall()
    }
    expected_columns = {
        "finished_at": "ALTER TABLE meta_import_jobs ADD COLUMN finished_at TEXT",
        "request_date_from": "ALTER TABLE meta_import_jobs ADD COLUMN request_date_from TEXT",
        "request_date_to": "ALTER TABLE meta_import_jobs ADD COLUMN request_date_to TEXT",
        "include_daily_metrics": "ALTER TABLE meta_import_jobs ADD COLUMN include_daily_metrics INTEGER NOT NULL DEFAULT 1",
        "failure_stage": "ALTER TABLE meta_import_jobs ADD COLUMN failure_stage TEXT",
        "failure_class": "ALTER TABLE meta_import_jobs ADD COLUMN failure_class TEXT",
        "retry_suitability": "ALTER TABLE meta_import_jobs ADD COLUMN retry_suitability TEXT",
        "partial_completion": "ALTER TABLE meta_import_jobs ADD COLUMN partial_completion INTEGER NOT NULL DEFAULT 0",
        "operator_detail": "ALTER TABLE meta_import_jobs ADD COLUMN operator_detail TEXT",
        "activity_rows_detected": "ALTER TABLE meta_import_jobs ADD COLUMN activity_rows_detected INTEGER NOT NULL DEFAULT 0",
        "activity_rows_inserted": "ALTER TABLE meta_import_jobs ADD COLUMN activity_rows_inserted INTEGER NOT NULL DEFAULT 0",
        "activity_rows_updated": "ALTER TABLE meta_import_jobs ADD COLUMN activity_rows_updated INTEGER NOT NULL DEFAULT 0",
        "activity_rows_skipped": "ALTER TABLE meta_import_jobs ADD COLUMN activity_rows_skipped INTEGER NOT NULL DEFAULT 0",
        "daily_metric_rows_detected": "ALTER TABLE meta_import_jobs ADD COLUMN daily_metric_rows_detected INTEGER NOT NULL DEFAULT 0",
        "daily_metric_rows_inserted": "ALTER TABLE meta_import_jobs ADD COLUMN daily_metric_rows_inserted INTEGER NOT NULL DEFAULT 0",
        "daily_metric_rows_updated": "ALTER TABLE meta_import_jobs ADD COLUMN daily_metric_rows_updated INTEGER NOT NULL DEFAULT 0",
        "daily_metric_rows_skipped": "ALTER TABLE meta_import_jobs ADD COLUMN daily_metric_rows_skipped INTEGER NOT NULL DEFAULT 0",
        "segment_activities_checked": "ALTER TABLE meta_import_jobs ADD COLUMN segment_activities_checked INTEGER NOT NULL DEFAULT 0",
        "segment_activities_with_data": "ALTER TABLE meta_import_jobs ADD COLUMN segment_activities_with_data INTEGER NOT NULL DEFAULT 0",
        "segment_efforts_detected": "ALTER TABLE meta_import_jobs ADD COLUMN segment_efforts_detected INTEGER NOT NULL DEFAULT 0",
        "segment_efforts_inserted": "ALTER TABLE meta_import_jobs ADD COLUMN segment_efforts_inserted INTEGER NOT NULL DEFAULT 0",
        "segment_efforts_updated": "ALTER TABLE meta_import_jobs ADD COLUMN segment_efforts_updated INTEGER NOT NULL DEFAULT 0",
        "segment_efforts_skipped": "ALTER TABLE meta_import_jobs ADD COLUMN segment_efforts_skipped INTEGER NOT NULL DEFAULT 0",
        "quality_activities_checked": "ALTER TABLE meta_import_jobs ADD COLUMN quality_activities_checked INTEGER NOT NULL DEFAULT 0",
        "quality_activities_filtered": "ALTER TABLE meta_import_jobs ADD COLUMN quality_activities_filtered INTEGER NOT NULL DEFAULT 0",
        "quality_runs_created": "ALTER TABLE meta_import_jobs ADD COLUMN quality_runs_created INTEGER NOT NULL DEFAULT 0",
        "quality_runs_reused": "ALTER TABLE meta_import_jobs ADD COLUMN quality_runs_reused INTEGER NOT NULL DEFAULT 0",
        "quality_decisions_recorded": "ALTER TABLE meta_import_jobs ADD COLUMN quality_decisions_recorded INTEGER NOT NULL DEFAULT 0",
        "quality_limited_metrics": "ALTER TABLE meta_import_jobs ADD COLUMN quality_limited_metrics INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, statement in expected_columns.items():
        if column_name not in existing_columns:
            connection.execute(statement)

    _ensure_exec_activity_segment_columns(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS exec_segments (
            segment_id INTEGER PRIMARY KEY,
            source_system TEXT NOT NULL,
            external_segment_id TEXT NOT NULL,
            segment_name TEXT,
            discipline TEXT,
            distance_meters REAL,
            ascent_meters REAL,
            average_grade_percent REAL,
            first_seen_activity_id INTEGER,
            last_seen_activity_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_system, external_segment_id),
            FOREIGN KEY (first_seen_activity_id) REFERENCES exec_activities (activity_id),
            FOREIGN KEY (last_seen_activity_id) REFERENCES exec_activities (activity_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS exec_segment_efforts (
            segment_effort_id INTEGER PRIMARY KEY,
            source_system TEXT NOT NULL,
            external_segment_effort_id TEXT NOT NULL,
            segment_id INTEGER NOT NULL,
            activity_id INTEGER NOT NULL,
            activity_date TEXT NOT NULL,
            started_at TEXT,
            elapsed_time_seconds INTEGER,
            avg_power REAL,
            avg_cadence REAL,
            avg_heart_rate REAL,
            max_heart_rate REAL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_system, external_segment_effort_id),
            FOREIGN KEY (segment_id) REFERENCES exec_segments (segment_id),
            FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id)
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_exec_segments_name ON exec_segments (segment_name)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_exec_segment_efforts_segment_date ON exec_segment_efforts (segment_id, activity_date DESC)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_exec_segment_efforts_activity ON exec_segment_efforts (activity_id)")


def _ensure_exec_activity_segment_columns(connection: sqlite3.Connection) -> None:
    exec_activities_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'exec_activities'"
    ).fetchone()
    if exec_activities_exists is None:
        return
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(exec_activities)").fetchall()
    }
    expected_columns = {
        "segment_data_status": "ALTER TABLE exec_activities ADD COLUMN segment_data_status TEXT NOT NULL DEFAULT 'not_checked'",
        "segment_effort_count": "ALTER TABLE exec_activities ADD COLUMN segment_effort_count INTEGER NOT NULL DEFAULT 0",
        "segment_checked_at": "ALTER TABLE exec_activities ADD COLUMN segment_checked_at TEXT",
    }
    for column_name, statement in expected_columns.items():
        if column_name not in existing_columns:
            connection.execute(statement)


def _ensure_exec_activity_quality_schema(connection: sqlite3.Connection) -> None:
    exec_activities_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'exec_activities'"
    ).fetchone()
    if exec_activities_exists is None:
        return

    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(exec_activities)").fetchall()
    }
    expected_columns = {
        "quality_status": "ALTER TABLE exec_activities ADD COLUMN quality_status TEXT NOT NULL DEFAULT 'not_checked'",
        "quality_checked_at": "ALTER TABLE exec_activities ADD COLUMN quality_checked_at TEXT",
        "quality_rule_version": "ALTER TABLE exec_activities ADD COLUMN quality_rule_version TEXT",
        "quality_decision_count": "ALTER TABLE exec_activities ADD COLUMN quality_decision_count INTEGER NOT NULL DEFAULT 0",
        "quality_limited_metric_count": "ALTER TABLE exec_activities ADD COLUMN quality_limited_metric_count INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, statement in expected_columns.items():
        if column_name not in existing_columns:
            connection.execute(statement)

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS exec_activity_metric_readings (
            activity_metric_reading_id INTEGER PRIMARY KEY,
            activity_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            sample_index INTEGER NOT NULL,
            raw_value REAL NOT NULL,
            recorded_at TEXT,
            elapsed_seconds REAL,
            source_payload_kind TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (activity_id, metric_name, sample_index)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS exec_activity_quality_runs (
            quality_run_id INTEGER PRIMARY KEY,
            activity_id INTEGER NOT NULL,
            rule_set_key TEXT NOT NULL,
            rule_set_version TEXT NOT NULL,
            source_reading_fingerprint TEXT NOT NULL,
            source_payload_path TEXT,
            evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            evaluated_metric_names TEXT,
            skipped_metric_names TEXT,
            evaluated_reading_count INTEGER NOT NULL DEFAULT 0,
            excluded_reading_count INTEGER NOT NULL DEFAULT 0,
            limited_metric_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            UNIQUE (activity_id, rule_set_key, rule_set_version, source_reading_fingerprint)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS exec_activity_quality_decisions (
            quality_decision_id INTEGER PRIMARY KEY,
            quality_run_id INTEGER NOT NULL,
            activity_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            decision_status TEXT NOT NULL,
            start_sample_index INTEGER NOT NULL,
            end_sample_index INTEGER NOT NULL,
            reason_code TEXT NOT NULL,
            rule_key TEXT NOT NULL,
            threshold_low REAL,
            threshold_high REAL,
            evidence_json TEXT,
            impacted_summary_kinds TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (quality_run_id, metric_name, start_sample_index, end_sample_index, rule_key)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS exec_activity_metric_summaries (
            activity_metric_summary_id INTEGER PRIMARY KEY,
            activity_id INTEGER NOT NULL,
            quality_run_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            summary_kind TEXT NOT NULL,
            source_value REAL,
            trusted_value REAL,
            summary_status TEXT NOT NULL,
            evaluated_reading_count INTEGER NOT NULL DEFAULT 0,
            accepted_reading_count INTEGER NOT NULL DEFAULT 0,
            excluded_reading_count INTEGER NOT NULL DEFAULT 0,
            changed_by_filter INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (activity_id, metric_name, summary_kind)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_exec_activity_metric_readings_activity_metric ON exec_activity_metric_readings (activity_id, metric_name)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_exec_activity_quality_runs_activity ON exec_activity_quality_runs (activity_id, evaluated_at DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_exec_activity_quality_decisions_activity_metric ON exec_activity_quality_decisions (activity_id, metric_name, start_sample_index)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_exec_activity_metric_summaries_activity_metric ON exec_activity_metric_summaries (activity_id, metric_name, summary_kind)"
    )
