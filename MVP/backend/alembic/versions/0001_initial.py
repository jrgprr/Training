"""Initial database schema migration.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-05-04 00:00:00.000000
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
default_schema = None


def upgrade() -> None:
    op.execute(text("""
CREATE TABLE user_profile (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    display_name TEXT NOT NULL,
    birth_date DATE,
    sex TEXT,
    height_cm NUMERIC(5,2),
    primary_sport TEXT,
    preferred_units JSONB NOT NULL DEFAULT '{}'::jsonb,
    timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_goal (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    goal_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    target_weight_kg NUMERIC(5,2),
    target_description TEXT,
    priority_order INTEGER NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_threshold (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    threshold_type TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    value NUMERIC(10,2) NOT NULL,
    unit TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_setting (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    setting_key TEXT NOT NULL,
    setting_value_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, setting_key)
);

CREATE TABLE device (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    device_type TEXT NOT NULL,
    brand TEXT,
    model TEXT,
    display_name TEXT NOT NULL,
    serial_number TEXT,
    data_origin_type TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE data_source_account (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    provider_name TEXT NOT NULL,
    account_identifier TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    last_sync_at TIMESTAMPTZ,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE import_batch (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    source_account_id BIGINT REFERENCES data_source_account(id) ON DELETE SET NULL,
    import_type TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'started',
    files_count INTEGER NOT NULL DEFAULT 0,
    records_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE import_file (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_batch_id BIGINT NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    file_type TEXT,
    file_hash TEXT,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'imported',
    raw_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (import_batch_id, original_filename, file_hash)
);

CREATE TABLE import_record (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_file_id BIGINT NOT NULL REFERENCES import_file(id) ON DELETE CASCADE,
    record_type TEXT NOT NULL,
    external_id TEXT,
    record_timestamp TIMESTAMPTZ,
    payload_json JSONB NOT NULL,
    normalized BOOLEAN NOT NULL DEFAULT FALSE,
    normalized_entity_type TEXT,
    normalized_entity_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE annual_plan (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    title TEXT NOT NULL,
    macro_objective TEXT,
    start_date DATE,
    end_date DATE,
    status TEXT NOT NULL DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, year)
);

CREATE TABLE meso_block (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    annual_plan_id BIGINT NOT NULL REFERENCES annual_plan(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    start_date DATE,
    end_date DATE,
    objective TEXT,
    characteristics_text TEXT,
    success_signals_text TEXT,
    caution_signals_text TEXT,
    target_weight_phase_text TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (annual_plan_id, code),
    UNIQUE (annual_plan_id, sequence_order)
);

CREATE TABLE planned_week (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meso_block_id BIGINT NOT NULL REFERENCES meso_block(id) ON DELETE CASCADE,
    week_number_in_block INTEGER NOT NULL,
    calendar_week_label TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    entry_state TEXT,
    weekly_objective TEXT,
    secondary_priority TEXT,
    risk_to_watch TEXT,
    expected_decision_mode TEXT,
    target_weight_note TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (meso_block_id, week_number_in_block),
    UNIQUE (start_date, end_date)
);

CREATE TABLE planned_day (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    planned_week_id BIGINT NOT NULL REFERENCES planned_week(id) ON DELETE CASCADE,
    day_date DATE NOT NULL,
    weekday SMALLINT NOT NULL CHECK (weekday BETWEEN 1 AND 7),
    primary_objective TEXT,
    primary_session_type TEXT,
    primary_session_subtype TEXT,
    target_duration_min INTEGER,
    target_duration_max_min INTEGER,
    target_intensity_text TEXT,
    target_zone_text TEXT,
    indoor_alternative_type TEXT,
    complementary_work_text TEXT,
    comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (planned_week_id, day_date)
);

CREATE TABLE planned_session (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    planned_day_id BIGINT NOT NULL REFERENCES planned_day(id) ON DELETE CASCADE,
    role_type TEXT NOT NULL,
    session_type TEXT NOT NULL,
    subtype TEXT,
    duration_min INTEGER,
    duration_max_min INTEGER,
    intensity_text TEXT,
    is_key_session BOOLEAN NOT NULL DEFAULT FALSE,
    is_indoor_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    indoor_alternative_text TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE daily_checkin (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    checkin_date DATE NOT NULL,
    wake_feeling_score SMALLINT CHECK (wake_feeling_score BETWEEN 1 AND 5),
    sleep_quality_score SMALLINT CHECK (sleep_quality_score BETWEEN 1 AND 5),
    fatigue_score SMALLINT CHECK (fatigue_score BETWEEN 1 AND 5),
    soreness_score SMALLINT CHECK (soreness_score BETWEEN 1 AND 5),
    motivation_score SMALLINT CHECK (motivation_score BETWEEN 1 AND 5),
    pain_notes TEXT,
    day_decision TEXT,
    free_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, checkin_date)
);

CREATE TABLE body_measurement (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    measurement_date DATE NOT NULL,
    measurement_time TIMESTAMPTZ,
    source_device_id BIGINT REFERENCES device(id) ON DELETE SET NULL,
    weight_kg NUMERIC(5,2),
    body_fat_pct NUMERIC(5,2),
    bmi NUMERIC(5,2),
    hydration_pct NUMERIC(5,2),
    muscle_mass_kg NUMERIC(5,2),
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sleep_record (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    sleep_date DATE NOT NULL,
    source_device_id BIGINT REFERENCES device(id) ON DELETE SET NULL,
    total_sleep_min INTEGER,
    deep_sleep_min INTEGER,
    rem_sleep_min INTEGER,
    awakenings_count INTEGER,
    device_sleep_score NUMERIC(6,2),
    perceived_sleep_score SMALLINT CHECK (perceived_sleep_score BETWEEN 1 AND 5),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, sleep_date, source_device_id)
);

CREATE TABLE daily_habit_record (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    habit_date DATE NOT NULL,
    morning_routine_done BOOLEAN NOT NULL DEFAULT FALSE,
    morning_routine_min INTEGER,
    extra_mobility_done BOOLEAN NOT NULL DEFAULT FALSE,
    extra_mobility_min INTEGER,
    night_walk_done BOOLEAN NOT NULL DEFAULT FALSE,
    night_walk_min INTEGER,
    hydration_quality TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, habit_date)
);

CREATE TABLE nutrition_check (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    nutrition_date DATE NOT NULL,
    appetite_level TEXT,
    adherence_level TEXT,
    fueling_quality_training_day TEXT,
    overeating_episode BOOLEAN,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, nutrition_date)
);

CREATE TABLE training_session (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    session_date DATE NOT NULL,
    planned_day_id BIGINT REFERENCES planned_day(id) ON DELETE SET NULL,
    planned_session_id BIGINT REFERENCES planned_session(id) ON DELETE SET NULL,
    session_type TEXT NOT NULL,
    session_subtype TEXT,
    sport_type TEXT NOT NULL,
    execution_mode TEXT NOT NULL DEFAULT 'outdoor',
    indoor BOOLEAN NOT NULL DEFAULT FALSE,
    weather_impact BOOLEAN NOT NULL DEFAULT FALSE,
    substitution_reason TEXT,
    source_device_id BIGINT REFERENCES device(id) ON DELETE SET NULL,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_min INTEGER NOT NULL,
    distance_km NUMERIC(8,2),
    elevation_gain_m INTEGER,
    avg_heart_rate NUMERIC(6,2),
    max_heart_rate NUMERIC(6,2),
    avg_power_w NUMERIC(8,2),
    normalized_power_w NUMERIC(8,2),
    max_power_w NUMERIC(8,2),
    avg_cadence_rpm NUMERIC(6,2),
    avg_speed_kmh NUMERIC(6,2),
    calories_kcal INTEGER,
    rpe_score SMALLINT CHECK (rpe_score BETWEEN 1 AND 10),
    session_comment TEXT,
    completed_as_planned BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE session_interval_summary (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    training_session_id BIGINT NOT NULL REFERENCES training_session(id) ON DELETE CASCADE,
    interval_order INTEGER NOT NULL,
    interval_type TEXT,
    duration_sec INTEGER NOT NULL,
    avg_power_w NUMERIC(8,2),
    avg_heart_rate NUMERIC(6,2),
    avg_cadence_rpm NUMERIC(6,2),
    notes TEXT,
    UNIQUE (training_session_id, interval_order)
);

CREATE TABLE session_zone_summary (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    training_session_id BIGINT NOT NULL REFERENCES training_session(id) ON DELETE CASCADE,
    zone_type TEXT NOT NULL,
    zone_label TEXT NOT NULL,
    duration_sec INTEGER NOT NULL,
    percent_of_session NUMERIC(6,2),
    UNIQUE (training_session_id, zone_type, zone_label)
);

CREATE TABLE session_device_link (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    training_session_id BIGINT NOT NULL REFERENCES training_session(id) ON DELETE CASCADE,
    device_id BIGINT NOT NULL REFERENCES device(id) ON DELETE CASCADE,
    role_type TEXT NOT NULL,
    UNIQUE (training_session_id, device_id, role_type)
);

CREATE TABLE day_execution_review (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    planned_day_id BIGINT NOT NULL REFERENCES planned_day(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    was_executed BOOLEAN NOT NULL DEFAULT FALSE,
    was_substituted BOOLEAN NOT NULL DEFAULT FALSE,
    substitution_quality TEXT,
    perceived_match_to_plan TEXT,
    daily_load_comment TEXT,
    reviewer_note TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (planned_day_id)
);

CREATE TABLE week_review (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    planned_week_id BIGINT NOT NULL REFERENCES planned_week(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    total_sessions_completed INTEGER NOT NULL DEFAULT 0,
    total_bike_sessions_completed INTEGER NOT NULL DEFAULT 0,
    total_activity_min INTEGER NOT NULL DEFAULT 0,
    total_bike_min INTEGER NOT NULL DEFAULT 0,
    long_session_completed BOOLEAN,
    strength_completed BOOLEAN,
    indoor_substitutions_count INTEGER NOT NULL DEFAULT 0,
    perceived_consistency_score SMALLINT CHECK (perceived_consistency_score BETWEEN 1 AND 5),
    fatigue_end_week_score SMALLINT CHECK (fatigue_end_week_score BETWEEN 1 AND 5),
    weight_trend_label TEXT,
    aerobic_index_value NUMERIC(8,2),
    suggested_next_decision TEXT,
    final_decision TEXT,
    review_comment TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (planned_week_id)
);

CREATE TABLE daily_metric (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    aerobic_load_value NUMERIC(10,2),
    wellness_score NUMERIC(10,2),
    weight_trend_short_value NUMERIC(10,2),
    weight_trend_long_value NUMERIC(10,2),
    readiness_flag TEXT,
    calculation_version TEXT NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, metric_date, calculation_version)
);

CREATE TABLE weekly_metric (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    planned_week_id BIGINT REFERENCES planned_week(id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    short_aerobic_load NUMERIC(10,2),
    long_aerobic_load NUMERIC(10,2),
    aerobic_index NUMERIC(10,2),
    short_weight_avg NUMERIC(6,2),
    long_weight_avg NUMERIC(6,2),
    weight_trend_delta NUMERIC(6,2),
    total_bike_hours NUMERIC(8,2),
    total_activity_hours NUMERIC(8,2),
    completion_rate_pct NUMERIC(5,2),
    consistency_label TEXT,
    calculation_version TEXT NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, week_start_date, week_end_date, calculation_version)
);

CREATE TABLE analysis_snapshot (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_type TEXT NOT NULL,
    reference_entity_type TEXT NOT NULL,
    reference_entity_id BIGINT NOT NULL,
    snapshot_date DATE NOT NULL,
    payload_json JSONB NOT NULL,
    calculation_version TEXT NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_goal_user_id ON user_goal (user_id);
CREATE INDEX idx_user_threshold_user_id_valid_from ON user_threshold (user_id, valid_from);
CREATE INDEX idx_device_user_id ON device (user_id);
CREATE INDEX idx_import_batch_user_id_started_at ON import_batch (user_id, started_at);
CREATE INDEX idx_import_file_hash ON import_file (file_hash);
CREATE INDEX idx_import_record_external_id ON import_record (external_id);
CREATE INDEX idx_import_record_record_timestamp ON import_record (record_timestamp);
CREATE INDEX idx_meso_block_annual_plan_id ON meso_block (annual_plan_id);
CREATE INDEX idx_planned_week_meso_block_id ON planned_week (meso_block_id);
CREATE INDEX idx_planned_day_week_date ON planned_day (planned_week_id, day_date);
CREATE INDEX idx_daily_checkin_user_date ON daily_checkin (user_id, checkin_date);
CREATE INDEX idx_body_measurement_user_date ON body_measurement (user_id, measurement_date);
CREATE INDEX idx_sleep_record_user_date ON sleep_record (user_id, sleep_date);
CREATE INDEX idx_daily_habit_record_user_date ON daily_habit_record (user_id, habit_date);
CREATE INDEX idx_nutrition_check_user_date ON nutrition_check (user_id, nutrition_date);
CREATE INDEX idx_training_session_user_date ON training_session (user_id, session_date);
CREATE INDEX idx_training_session_planned_day_id ON training_session (planned_day_id);
CREATE INDEX idx_training_session_planned_session_id ON training_session (planned_session_id);
CREATE INDEX idx_week_review_planned_week_id ON week_review (planned_week_id);
CREATE INDEX idx_daily_metric_user_date ON daily_metric (user_id, metric_date);
CREATE INDEX idx_weekly_metric_user_week_start ON weekly_metric (user_id, week_start_date);
CREATE INDEX idx_analysis_snapshot_reference ON analysis_snapshot (reference_entity_type, reference_entity_id, snapshot_date);
"""))


def downgrade() -> None:
    op.execute(text("""
DROP TABLE IF EXISTS analysis_snapshot CASCADE;
DROP TABLE IF EXISTS weekly_metric CASCADE;
DROP TABLE IF EXISTS daily_metric CASCADE;
DROP TABLE IF EXISTS week_review CASCADE;
DROP TABLE IF EXISTS day_execution_review CASCADE;
DROP TABLE IF EXISTS session_device_link CASCADE;
DROP TABLE IF EXISTS session_zone_summary CASCADE;
DROP TABLE IF EXISTS session_interval_summary CASCADE;
DROP TABLE IF EXISTS training_session CASCADE;
DROP TABLE IF EXISTS nutrition_check CASCADE;
DROP TABLE IF EXISTS daily_habit_record CASCADE;
DROP TABLE IF EXISTS sleep_record CASCADE;
DROP TABLE IF EXISTS body_measurement CASCADE;
DROP TABLE IF EXISTS daily_checkin CASCADE;
DROP TABLE IF EXISTS planned_session CASCADE;
DROP TABLE IF EXISTS planned_day CASCADE;
DROP TABLE IF EXISTS planned_week CASCADE;
DROP TABLE IF EXISTS meso_block CASCADE;
DROP TABLE IF EXISTS annual_plan CASCADE;
DROP TABLE IF EXISTS import_record CASCADE;
DROP TABLE IF EXISTS import_file CASCADE;
DROP TABLE IF EXISTS import_batch CASCADE;
DROP TABLE IF EXISTS data_source_account CASCADE;
DROP TABLE IF EXISTS device CASCADE;
DROP TABLE IF EXISTS user_setting CASCADE;
DROP TABLE IF EXISTS user_threshold CASCADE;
DROP TABLE IF EXISTS user_goal CASCADE;
DROP TABLE IF EXISTS user_profile CASCADE;
"""))
