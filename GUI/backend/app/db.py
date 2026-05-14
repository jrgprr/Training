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
        _ensure_import_job_columns(connection)
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
    }
    for column_name, statement in expected_columns.items():
        if column_name not in existing_columns:
            connection.execute(statement)
