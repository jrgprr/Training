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
    sleep_hours REAL,
    sleep_quality TEXT,
    resting_hr REAL,
    hrv REAL,
    body_battery REAL,
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


ASSESSMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_assessment_profiles (
    agent_profile_id INTEGER PRIMARY KEY,
    profile_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    cadence TEXT NOT NULL CHECK (cadence IN ('daily', 'weekly', 'block', 'season')),
    assessment_scope TEXT NOT NULL,
    target_planning_level TEXT CHECK (target_planning_level IS NULL OR target_planning_level IN ('weekly', 'block', 'season', 'macro')),
    instruction_version TEXT NOT NULL,
    provider_key TEXT,
    model_name TEXT,
    execution_policy TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'experimental')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_assessment_windows (
    assessment_window_id INTEGER PRIMARY KEY,
    cadence TEXT NOT NULL CHECK (cadence IN ('daily', 'weekly', 'block', 'season')),
    season_id INTEGER NOT NULL,
    block_id INTEGER,
    week_id INTEGER,
    window_start_date TEXT NOT NULL,
    window_end_date TEXT NOT NULL,
    subject_scope_key TEXT NOT NULL,
    evidence_fingerprint TEXT NOT NULL,
    latest_materialized_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cadence, subject_scope_key, evidence_fingerprint),
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id),
    FOREIGN KEY (block_id) REFERENCES plan_meso_blocks (block_id),
    FOREIGN KEY (week_id) REFERENCES plan_micro_weeks (week_id)
);

CREATE TABLE IF NOT EXISTS agent_assessment_runs (
    assessment_run_id INTEGER PRIMARY KEY,
    agent_profile_id INTEGER NOT NULL,
    assessment_window_id INTEGER NOT NULL,
    trigger_mode TEXT NOT NULL CHECK (trigger_mode IN ('manual', 'rerun', 'scheduled')),
    run_status TEXT NOT NULL CHECK (run_status IN ('queued', 'running', 'completed', 'no_new_data', 'partial_context', 'failed', 'cancelled')),
    provider_key TEXT,
    model_name TEXT,
    instruction_version TEXT NOT NULL,
    prompt_hash TEXT,
    summary_text TEXT,
    confidence_label TEXT CHECK (confidence_label IS NULL OR confidence_label IN ('high', 'medium', 'limited')),
    principal_evidence_json TEXT,
    failure_code TEXT,
    failure_detail TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    supersedes_run_id INTEGER,
    FOREIGN KEY (agent_profile_id) REFERENCES agent_assessment_profiles (agent_profile_id),
    FOREIGN KEY (assessment_window_id) REFERENCES agent_assessment_windows (assessment_window_id),
    FOREIGN KEY (supersedes_run_id) REFERENCES agent_assessment_runs (assessment_run_id)
);

CREATE TABLE IF NOT EXISTS agent_assessment_type_results (
    assessment_type_result_id INTEGER PRIMARY KEY,
    assessment_run_id INTEGER NOT NULL,
    assessment_type_key TEXT NOT NULL,
    result_label TEXT NOT NULL,
    confidence_label TEXT CHECK (confidence_label IS NULL OR confidence_label IN ('high', 'medium', 'limited')),
    narrative_text TEXT,
    evidence_summary_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (assessment_run_id, assessment_type_key),
    FOREIGN KEY (assessment_run_id) REFERENCES agent_assessment_runs (assessment_run_id)
);

CREATE TABLE IF NOT EXISTS agent_assessment_findings (
    assessment_finding_id INTEGER PRIMARY KEY,
    assessment_run_id INTEGER NOT NULL,
    assessment_type_result_id INTEGER,
    finding_kind TEXT NOT NULL CHECK (finding_kind IN ('positive_signal', 'risk_signal', 'adherence_observation', 'recovery_observation', 'performance_signal', 'next_action', 'data_confidence')),
    severity TEXT CHECK (severity IS NULL OR severity IN ('info', 'watch', 'warning', 'critical')),
    title TEXT NOT NULL,
    detail_text TEXT,
    evidence_refs_json TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_run_id) REFERENCES agent_assessment_runs (assessment_run_id),
    FOREIGN KEY (assessment_type_result_id) REFERENCES agent_assessment_type_results (assessment_type_result_id)
);

CREATE TABLE IF NOT EXISTS agent_adaptation_proposals (
    proposal_id INTEGER PRIMARY KEY,
    assessment_run_id INTEGER NOT NULL,
    agent_profile_id INTEGER NOT NULL,
    source_cadence TEXT NOT NULL CHECK (source_cadence IN ('daily', 'weekly', 'block', 'season')),
    target_planning_level TEXT NOT NULL CHECK (target_planning_level IN ('weekly', 'block', 'season', 'macro')),
    proposal_status TEXT NOT NULL DEFAULT 'pending' CHECK (proposal_status IN ('pending', 'accepted', 'rejected', 'superseded')),
    proposal_title TEXT NOT NULL,
    proposal_summary TEXT,
    change_kind TEXT NOT NULL,
    proposed_change_json TEXT NOT NULL,
    reasoning_summary TEXT,
    conflict_group_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (source_cadence = 'daily' AND target_planning_level = 'weekly') OR
        (source_cadence = 'weekly' AND target_planning_level = 'block') OR
        (source_cadence = 'block' AND target_planning_level = 'season') OR
        (source_cadence = 'season' AND target_planning_level = 'macro')
    ),
    FOREIGN KEY (assessment_run_id) REFERENCES agent_assessment_runs (assessment_run_id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_assessment_profiles (agent_profile_id)
);

CREATE TABLE IF NOT EXISTS agent_proposal_decisions (
    proposal_decision_id INTEGER PRIMARY KEY,
    proposal_id INTEGER NOT NULL,
    decision_status TEXT NOT NULL CHECK (decision_status IN ('accepted', 'rejected', 'superseded')),
    decision_note TEXT,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    superseding_proposal_id INTEGER,
    applied_change_ref TEXT,
    FOREIGN KEY (proposal_id) REFERENCES agent_adaptation_proposals (proposal_id),
    FOREIGN KEY (superseding_proposal_id) REFERENCES agent_adaptation_proposals (proposal_id)
);

CREATE TABLE IF NOT EXISTS agent_accepted_plan_mutations (
    plan_mutation_id INTEGER PRIMARY KEY,
    proposal_id INTEGER NOT NULL UNIQUE,
    target_planning_level TEXT NOT NULL CHECK (target_planning_level IN ('weekly', 'block', 'season', 'macro')),
    target_entity_id TEXT NOT NULL,
    mutation_summary TEXT NOT NULL,
    before_snapshot_json TEXT,
    after_snapshot_json TEXT,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES agent_adaptation_proposals (proposal_id)
);

CREATE TABLE IF NOT EXISTS agent_assessment_dialog_context (
    dialog_context_id INTEGER PRIMARY KEY,
    assessment_run_id INTEGER,
    proposal_id INTEGER,
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('user_question', 'user_clarification', 'assistant_response', 'system_note')),
    entry_scope TEXT NOT NULL CHECK (entry_scope IN ('assessment_summary', 'finding', 'proposal', 'reassessment_request')),
    clarification_kind TEXT CHECK (clarification_kind IS NULL OR clarification_kind IN ('schedule_shift', 'session_swap', 'missing_context', 'device_issue', 'execution_intent')),
    entry_text TEXT NOT NULL,
    linked_evidence_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    CHECK (assessment_run_id IS NOT NULL OR proposal_id IS NOT NULL),
    FOREIGN KEY (assessment_run_id) REFERENCES agent_assessment_runs (assessment_run_id),
    FOREIGN KEY (proposal_id) REFERENCES agent_adaptation_proposals (proposal_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_assessment_profiles_cadence_status ON agent_assessment_profiles (cadence, status);
CREATE INDEX IF NOT EXISTS idx_agent_assessment_windows_scope ON agent_assessment_windows (season_id, cadence, subject_scope_key, window_end_date DESC);
CREATE INDEX IF NOT EXISTS idx_agent_assessment_runs_window_profile ON agent_assessment_runs (assessment_window_id, agent_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_assessment_type_results_run ON agent_assessment_type_results (assessment_run_id);
CREATE INDEX IF NOT EXISTS idx_agent_assessment_findings_run_sort ON agent_assessment_findings (assessment_run_id, sort_order, assessment_finding_id);
CREATE INDEX IF NOT EXISTS idx_agent_adaptation_proposals_status ON agent_adaptation_proposals (proposal_status, target_planning_level, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_proposal_decisions_proposal ON agent_proposal_decisions (proposal_id, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_assessment_dialog_context_run ON agent_assessment_dialog_context (assessment_run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_assessment_dialog_context_proposal ON agent_assessment_dialog_context (proposal_id, created_at DESC);
"""


DISCIPLINE_ALIASES = {
    "bicicleta": "road_biking",
    "caminar": "walking",
    "fuerza": "strength_training",
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
            WHEN 'paseo' THEN 'walking'
            WHEN 'senderismo' THEN 'hiking'
            ELSE lower(trim(discipline))
        END
        WHERE source_system LIKE 'manual%'
          AND discipline IS NOT NULL
          AND lower(trim(discipline)) IN ('bicicleta', 'caminar', 'fuerza', 'paseo', 'senderismo')
        """
    )


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(WEEKLY_REVIEW_SCHEMA)
        connection.executescript(IMPORT_SCHEMA)
        connection.executescript(PRESCRIPTION_SCHEMA)
        connection.executescript(ASSESSMENT_SCHEMA)
        _ensure_import_job_columns(connection)
        _ensure_exec_activity_quality_schema(connection)
        normalize_existing_manual_activity_disciplines(connection)


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
