PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta_schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_seasons (
    season_id INTEGER PRIMARY KEY,
    season_code TEXT NOT NULL UNIQUE,
    season_name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS plan_user_profiles (
    profile_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL UNIQUE,
    alias TEXT,
    age_years INTEGER,
    height_cm REAL,
    reference_weight_kg REAL,
    target_weight_kg REAL,
    current_form TEXT,
    baseline_fatigue TEXT,
    current_strength TEXT,
    recovery_profile TEXT,
    primary_sport TEXT,
    secondary_sports TEXT,
    best_tolerated_training TEXT,
    worst_tolerated_training TEXT,
    availability_notes TEXT,
    support_routine TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

CREATE TABLE IF NOT EXISTS plan_macro_cycles (
    macro_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    objective_statement TEXT NOT NULL,
    context_summary TEXT,
    priorities TEXT,
    progression_rules TEXT,
    weight_rules TEXT,
    success_criteria TEXT,
    prudence_criteria TEXT,
    closing_rule TEXT,
    markdown_path TEXT,
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

CREATE TABLE IF NOT EXISTS plan_meso_blocks (
    block_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    block_code TEXT NOT NULL UNIQUE,
    block_name TEXT NOT NULL,
    phase_name TEXT,
    sequence_order INTEGER NOT NULL,
    start_date TEXT,
    end_date TEXT,
    duration_weeks_min INTEGER,
    duration_weeks_max INTEGER,
    objective_primary TEXT,
    objective_secondary TEXT,
    objective_complementary TEXT,
    entry_criteria TEXT,
    exit_criteria TEXT,
    key_risks TEXT,
    micro_pattern TEXT,
    progression_logic TEXT,
    markdown_path TEXT,
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

CREATE TABLE IF NOT EXISTS plan_micro_weeks (
    week_id INTEGER PRIMARY KEY,
    block_id INTEGER NOT NULL,
    week_code TEXT NOT NULL,
    sequence_in_block INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    week_role TEXT,
    entry_state TEXT,
    objective_primary TEXT,
    objective_secondary TEXT,
    key_risk TEXT,
    weight_goal TEXT,
    target_volume_hours_min REAL,
    target_volume_hours_max REAL,
    key_days TEXT,
    support_days TEXT,
    closure_rule TEXT,
    markdown_path TEXT,
    UNIQUE (block_id, week_code),
    FOREIGN KEY (block_id) REFERENCES plan_meso_blocks (block_id)
);

CREATE TABLE IF NOT EXISTS plan_planned_sessions (
    planned_session_id INTEGER PRIMARY KEY,
    week_id INTEGER NOT NULL,
    session_date TEXT NOT NULL,
    day_name TEXT NOT NULL,
    sequence_in_week INTEGER NOT NULL,
    planned_type TEXT,
    objective TEXT,
    primary_session TEXT,
    complementary_session TEXT,
    notes TEXT,
    is_key_session INTEGER NOT NULL DEFAULT 0,
    intensity_class TEXT,
    duration_min INTEGER,
    duration_max INTEGER,
    adjustment_rule TEXT,
    markdown_path TEXT,
    UNIQUE (week_id, sequence_in_week),
    FOREIGN KEY (week_id) REFERENCES plan_micro_weeks (week_id)
);

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

CREATE TABLE IF NOT EXISTS exec_activities (
    activity_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    source_system TEXT NOT NULL,
    external_activity_id TEXT,
    activity_date TEXT NOT NULL,
    started_at TEXT,
    discipline TEXT,
    activity_type TEXT,
    duration_seconds INTEGER,
    distance_meters REAL,
    ascent_meters REAL,
    calories REAL,
    avg_hr REAL,
    max_hr REAL,
    avg_power REAL,
    normalized_power REAL,
    training_load REAL,
    avg_pace_seconds_per_km REAL,
    segment_data_status TEXT NOT NULL DEFAULT 'not_checked',
    segment_effort_count INTEGER NOT NULL DEFAULT 0,
    segment_checked_at TEXT,
    quality_status TEXT NOT NULL DEFAULT 'not_checked',
    quality_checked_at TEXT,
    quality_rule_version TEXT,
    quality_decision_count INTEGER NOT NULL DEFAULT 0,
    quality_limited_metric_count INTEGER NOT NULL DEFAULT 0,
    perceived_exertion INTEGER,
    subjective_feeling TEXT,
    source_file TEXT,
    raw_payload_path TEXT,
    notes TEXT,
    UNIQUE (source_system, external_activity_id),
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

CREATE TABLE IF NOT EXISTS exec_daily_metrics (
    daily_metric_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    metric_date TEXT NOT NULL,
    source_system TEXT NOT NULL,
    weight_kg REAL,
    sleep_hours REAL,
    sleep_quality TEXT,
    resting_hr REAL,
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
    soreness TEXT,
    notes TEXT,
    UNIQUE (season_id, metric_date, source_system),
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

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

CREATE TABLE IF NOT EXISTS link_plan_execution (
    link_id INTEGER PRIMARY KEY,
    planned_session_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    link_type TEXT NOT NULL DEFAULT 'direct',
    compliance_status TEXT NOT NULL,
    rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planned_session_id) REFERENCES plan_planned_sessions (planned_session_id),
    FOREIGN KEY (activity_id) REFERENCES exec_activities (activity_id),
    UNIQUE (planned_session_id, activity_id)
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

CREATE TABLE IF NOT EXISTS review_daily_reviews (
    daily_review_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    review_date TEXT NOT NULL,
    block_id INTEGER,
    week_id INTEGER,
    planned_session_id INTEGER,
    planned_summary TEXT,
    actual_summary TEXT,
    compliance_status TEXT,
    general_feeling TEXT,
    perceived_recovery TEXT,
    motivation TEXT,
    observations TEXT,
    next_day_decision TEXT,
    UNIQUE (season_id, review_date, planned_session_id),
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id),
    FOREIGN KEY (block_id) REFERENCES plan_meso_blocks (block_id),
    FOREIGN KEY (week_id) REFERENCES plan_micro_weeks (week_id),
    FOREIGN KEY (planned_session_id) REFERENCES plan_planned_sessions (planned_session_id)
);

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

CREATE TABLE IF NOT EXISTS meta_markdown_views (
    markdown_view_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'human-view',
    sync_status TEXT NOT NULL DEFAULT 'manual',
    rendered_at TEXT,
    notes TEXT,
    FOREIGN KEY (season_id) REFERENCES plan_seasons (season_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_blocks_season_order ON plan_meso_blocks (season_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_plan_weeks_block_order ON plan_micro_weeks (block_id, sequence_in_block);
CREATE INDEX IF NOT EXISTS idx_plan_sessions_week_day ON plan_planned_sessions (week_id, session_date);
CREATE INDEX IF NOT EXISTS idx_plan_prescriptions_session ON plan_session_prescriptions (planned_session_id);
CREATE INDEX IF NOT EXISTS idx_plan_prescription_blocks_prescription ON plan_prescription_blocks (prescription_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_plan_prescription_exercises_block ON plan_prescription_exercises (prescription_block_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_exec_activities_date ON exec_activities (season_id, activity_date);
CREATE INDEX IF NOT EXISTS idx_exec_metrics_date ON exec_daily_metrics (season_id, metric_date);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON review_daily_reviews (season_id, review_date);
CREATE INDEX IF NOT EXISTS idx_weekly_reviews_status ON review_weekly_reviews (season_id, review_status);
CREATE INDEX IF NOT EXISTS idx_import_jobs_season_date ON meta_import_jobs (season_id, imported_at DESC);
CREATE INDEX IF NOT EXISTS idx_staging_garmin_activities_job ON staging_garmin_activities (import_job_id);
CREATE INDEX IF NOT EXISTS idx_staging_garmin_metrics_job ON staging_garmin_daily_metrics (import_job_id);

INSERT OR IGNORE INTO meta_schema_version (version, description)
VALUES (1, 'Initial schema for planning, execution, links, reviews and metadata.');