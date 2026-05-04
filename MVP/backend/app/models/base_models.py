from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[Date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(Text)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    primary_sport: Mapped[str | None] = mapped_column(Text)
    preferred_units: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'Europe/Madrid'"), nullable=False)


class UserGoal(TimestampMixin, Base):
    __tablename__ = "user_goal"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    goal_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Date | None] = mapped_column(Date)
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    target_description: Mapped[str | None] = mapped_column(Text)
    priority_order: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class UserThreshold(TimestampMixin, Base):
    __tablename__ = "user_threshold"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    threshold_type: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[Date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Date | None] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class UserSetting(Base):
    __tablename__ = "user_setting"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    setting_key: Mapped[str] = mapped_column(Text, nullable=False)
    setting_value_json: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "setting_key"),)


class Device(TimestampMixin, Base):
    __tablename__ = "device"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    device_type: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    serial_number: Mapped[str | None] = mapped_column(Text)
    data_origin_type: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class DataSourceAccount(TimestampMixin, Base):
    __tablename__ = "data_source_account"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    account_identifier: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"), nullable=False)
    last_sync_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"), nullable=False)


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    source_account_id: Mapped[int | None] = mapped_column(ForeignKey("data_source_account.id", ondelete="SET NULL"))
    import_type: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default=text("'started'"), nullable=False)
    files_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ImportFile(Base):
    __tablename__ = "import_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'imported'"), nullable=False)
    raw_metadata_json: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"), nullable=False)


class ImportRecord(Base):
    __tablename__ = "import_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_file_id: Mapped[int] = mapped_column(ForeignKey("import_file.id", ondelete="CASCADE"), nullable=False)
    record_type: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    record_timestamp: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"), nullable=False)
    normalized: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    normalized_entity_type: Mapped[str | None] = mapped_column(Text)
    normalized_entity_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnnualPlan(TimestampMixin, Base):
    __tablename__ = "annual_plan"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    macro_objective: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[Date | None] = mapped_column(Date)
    end_date: Mapped[Date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "year"),)


class MesoBlock(TimestampMixin, Base):
    __tablename__ = "meso_block"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    annual_plan_id: Mapped[int] = mapped_column(ForeignKey("annual_plan.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[Date | None] = mapped_column(Date)
    end_date: Mapped[Date | None] = mapped_column(Date)
    objective: Mapped[str | None] = mapped_column(Text)
    characteristics_text: Mapped[str | None] = mapped_column(Text)
    success_signals_text: Mapped[str | None] = mapped_column(Text)
    caution_signals_text: Mapped[str | None] = mapped_column(Text)
    target_weight_phase_text: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("annual_plan_id", "code"),
        UniqueConstraint("annual_plan_id", "sequence_order"),
    )


class PlannedWeek(TimestampMixin, Base):
    __tablename__ = "planned_week"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    meso_block_id: Mapped[int] = mapped_column(ForeignKey("meso_block.id", ondelete="CASCADE"), nullable=False)
    week_number_in_block: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_week_label: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Date] = mapped_column(Date, nullable=False)
    entry_state: Mapped[str | None] = mapped_column(Text)
    weekly_objective: Mapped[str | None] = mapped_column(Text)
    secondary_priority: Mapped[str | None] = mapped_column(Text)
    risk_to_watch: Mapped[str | None] = mapped_column(Text)
    expected_decision_mode: Mapped[str | None] = mapped_column(Text)
    target_weight_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'planned'"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("meso_block_id", "week_number_in_block"),
        UniqueConstraint("start_date", "end_date"),
    )


class PlannedDay(TimestampMixin, Base):
    __tablename__ = "planned_day"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planned_week_id: Mapped[int] = mapped_column(ForeignKey("planned_week.id", ondelete="CASCADE"), nullable=False)
    day_date: Mapped[Date] = mapped_column(Date, nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    primary_objective: Mapped[str | None] = mapped_column(Text)
    primary_session_type: Mapped[str | None] = mapped_column(Text)
    primary_session_subtype: Mapped[str | None] = mapped_column(Text)
    target_duration_min: Mapped[int | None] = mapped_column(Integer)
    target_duration_max_min: Mapped[int | None] = mapped_column(Integer)
    target_intensity_text: Mapped[str | None] = mapped_column(Text)
    target_zone_text: Mapped[str | None] = mapped_column(Text)
    indoor_alternative_type: Mapped[str | None] = mapped_column(Text)
    complementary_work_text: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("planned_week_id", "day_date"),
        CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_planned_day_weekday"),
    )


class PlannedSession(TimestampMixin, Base):
    __tablename__ = "planned_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planned_day_id: Mapped[int] = mapped_column(ForeignKey("planned_day.id", ondelete="CASCADE"), nullable=False)
    role_type: Mapped[str] = mapped_column(Text, nullable=False)
    session_type: Mapped[str] = mapped_column(Text, nullable=False)
    subtype: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    duration_max_min: Mapped[int | None] = mapped_column(Integer)
    intensity_text: Mapped[str | None] = mapped_column(Text)
    is_key_session: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    is_indoor_allowed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    indoor_alternative_text: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class DailyCheckin(TimestampMixin, Base):
    __tablename__ = "daily_checkin"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    checkin_date: Mapped[Date] = mapped_column(Date, nullable=False)
    wake_feeling_score: Mapped[int | None] = mapped_column(SmallInteger)
    sleep_quality_score: Mapped[int | None] = mapped_column(SmallInteger)
    fatigue_score: Mapped[int | None] = mapped_column(SmallInteger)
    soreness_score: Mapped[int | None] = mapped_column(SmallInteger)
    motivation_score: Mapped[int | None] = mapped_column(SmallInteger)
    pain_notes: Mapped[str | None] = mapped_column(Text)
    day_decision: Mapped[str | None] = mapped_column(Text)
    free_notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "checkin_date"),)


class BodyMeasurement(Base):
    __tablename__ = "body_measurement"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    measurement_date: Mapped[Date] = mapped_column(Date, nullable=False)
    measurement_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    source_device_id: Mapped[int | None] = mapped_column(ForeignKey("device.id", ondelete="SET NULL"))
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    body_fat_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    bmi: Mapped[float | None] = mapped_column(Numeric(5, 2))
    hydration_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    muscle_mass_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    payload_json: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SleepRecord(TimestampMixin, Base):
    __tablename__ = "sleep_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    sleep_date: Mapped[Date] = mapped_column(Date, nullable=False)
    source_device_id: Mapped[int | None] = mapped_column(ForeignKey("device.id", ondelete="SET NULL"))
    total_sleep_min: Mapped[int | None] = mapped_column(Integer)
    deep_sleep_min: Mapped[int | None] = mapped_column(Integer)
    rem_sleep_min: Mapped[int | None] = mapped_column(Integer)
    awakenings_count: Mapped[int | None] = mapped_column(Integer)
    device_sleep_score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    perceived_sleep_score: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("user_id", "sleep_date", "source_device_id"),
        CheckConstraint("perceived_sleep_score BETWEEN 1 AND 5", name="ck_sleep_record_perceived_score"),
    )


class DailyHabitRecord(TimestampMixin, Base):
    __tablename__ = "daily_habit_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    habit_date: Mapped[Date] = mapped_column(Date, nullable=False)
    morning_routine_done: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    morning_routine_min: Mapped[int | None] = mapped_column(Integer)
    extra_mobility_done: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    extra_mobility_min: Mapped[int | None] = mapped_column(Integer)
    night_walk_done: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    night_walk_min: Mapped[int | None] = mapped_column(Integer)
    hydration_quality: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "habit_date"),)


class NutritionCheck(TimestampMixin, Base):
    __tablename__ = "nutrition_check"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    nutrition_date: Mapped[Date] = mapped_column(Date, nullable=False)
    appetite_level: Mapped[str | None] = mapped_column(Text)
    adherence_level: Mapped[str | None] = mapped_column(Text)
    fueling_quality_training_day: Mapped[str | None] = mapped_column(Text)
    overeating_episode: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "nutrition_date"),)


class TrainingSession(TimestampMixin, Base):
    __tablename__ = "training_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    session_date: Mapped[Date] = mapped_column(Date, nullable=False)
    planned_day_id: Mapped[int | None] = mapped_column(ForeignKey("planned_day.id", ondelete="SET NULL"))
    planned_session_id: Mapped[int | None] = mapped_column(ForeignKey("planned_session.id", ondelete="SET NULL"))
    session_type: Mapped[str] = mapped_column(Text, nullable=False)
    session_subtype: Mapped[str | None] = mapped_column(Text)
    sport_type: Mapped[str] = mapped_column(Text, nullable=False)
    execution_mode: Mapped[str] = mapped_column(Text, server_default=text("'outdoor'"), nullable=False)
    indoor: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    weather_impact: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    substitution_reason: Mapped[str | None] = mapped_column(Text)
    source_device_id: Mapped[int | None] = mapped_column(ForeignKey("device.id", ondelete="SET NULL"))
    start_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Numeric(8, 2))
    elevation_gain_m: Mapped[int | None] = mapped_column(Integer)
    avg_heart_rate: Mapped[float | None] = mapped_column(Numeric(6, 2))
    max_heart_rate: Mapped[float | None] = mapped_column(Numeric(6, 2))
    avg_power_w: Mapped[float | None] = mapped_column(Numeric(8, 2))
    normalized_power_w: Mapped[float | None] = mapped_column(Numeric(8, 2))
    max_power_w: Mapped[float | None] = mapped_column(Numeric(8, 2))
    avg_cadence_rpm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    avg_speed_kmh: Mapped[float | None] = mapped_column(Numeric(6, 2))
    calories_kcal: Mapped[int | None] = mapped_column(Integer)
    rpe_score: Mapped[int | None] = mapped_column(SmallInteger)
    session_comment: Mapped[str | None] = mapped_column(Text)
    completed_as_planned: Mapped[bool | None] = mapped_column(Boolean)


class SessionIntervalSummary(Base):
    __tablename__ = "session_interval_summary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    training_session_id: Mapped[int] = mapped_column(ForeignKey("training_session.id", ondelete="CASCADE"), nullable=False)
    interval_order: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_type: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_power_w: Mapped[float | None] = mapped_column(Numeric(8, 2))
    avg_heart_rate: Mapped[float | None] = mapped_column(Numeric(6, 2))
    avg_cadence_rpm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("training_session_id", "interval_order"),)


class SessionZoneSummary(Base):
    __tablename__ = "session_zone_summary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    training_session_id: Mapped[int] = mapped_column(ForeignKey("training_session.id", ondelete="CASCADE"), nullable=False)
    zone_type: Mapped[str] = mapped_column(Text, nullable=False)
    zone_label: Mapped[str] = mapped_column(Text, nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    percent_of_session: Mapped[float | None] = mapped_column(Numeric(6, 2))

    __table_args__ = (UniqueConstraint("training_session_id", "zone_type", "zone_label"),)


class SessionDeviceLink(Base):
    __tablename__ = "session_device_link"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    training_session_id: Mapped[int] = mapped_column(ForeignKey("training_session.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id", ondelete="CASCADE"), nullable=False)
    role_type: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("training_session_id", "device_id", "role_type"),)


class DayExecutionReview(Base):
    __tablename__ = "day_execution_review"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planned_day_id: Mapped[int] = mapped_column(ForeignKey("planned_day.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    was_executed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    was_substituted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    substitution_quality: Mapped[str | None] = mapped_column(Text)
    perceived_match_to_plan: Mapped[str | None] = mapped_column(Text)
    daily_load_comment: Mapped[str | None] = mapped_column(Text)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("planned_day_id"),)


class WeekReview(TimestampMixin, Base):
    __tablename__ = "week_review"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planned_week_id: Mapped[int] = mapped_column(ForeignKey("planned_week.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    total_sessions_completed: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    total_bike_sessions_completed: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    total_activity_min: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    total_bike_min: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    long_session_completed: Mapped[bool | None] = mapped_column(Boolean)
    strength_completed: Mapped[bool | None] = mapped_column(Boolean)
    indoor_substitutions_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    perceived_consistency_score: Mapped[int | None] = mapped_column(SmallInteger)
    fatigue_end_week_score: Mapped[int | None] = mapped_column(SmallInteger)
    weight_trend_label: Mapped[str | None] = mapped_column(Text)
    aerobic_index_value: Mapped[float | None] = mapped_column(Numeric(8, 2))
    suggested_next_decision: Mapped[str | None] = mapped_column(Text)
    final_decision: Mapped[str | None] = mapped_column(Text)
    review_comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DailyMetric(Base):
    __tablename__ = "daily_metric"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    metric_date: Mapped[Date] = mapped_column(Date, nullable=False)
    aerobic_load_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    wellness_score: Mapped[float | None] = mapped_column(Numeric(10, 2))
    weight_trend_short_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    weight_trend_long_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    readiness_flag: Mapped[str | None] = mapped_column(Text)
    calculation_version: Mapped[str] = mapped_column(Text, server_default=text("'v1'"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "metric_date", "calculation_version"),)


class WeeklyMetric(Base):
    __tablename__ = "weekly_metric"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planned_week_id: Mapped[int | None] = mapped_column(ForeignKey("planned_week.id", ondelete="SET NULL"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    week_start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[Date] = mapped_column(Date, nullable=False)
    short_aerobic_load: Mapped[float | None] = mapped_column(Numeric(10, 2))
    long_aerobic_load: Mapped[float | None] = mapped_column(Numeric(10, 2))
    aerobic_index: Mapped[float | None] = mapped_column(Numeric(10, 2))
    short_weight_avg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    long_weight_avg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    weight_trend_delta: Mapped[float | None] = mapped_column(Numeric(6, 2))
    total_bike_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    total_activity_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    completion_rate_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    consistency_label: Mapped[str | None] = mapped_column(Text)
    calculation_version: Mapped[str] = mapped_column(Text, server_default=text("'v1'"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "week_start_date", "week_end_date", "calculation_version"),)


class AnalysisSnapshot(Base):
    __tablename__ = "analysis_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    snapshot_type: Mapped[str] = mapped_column(Text, nullable=False)
    reference_entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    reference_entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    snapshot_date: Mapped[Date] = mapped_column(Date, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"), nullable=False)
    calculation_version: Mapped[str] = mapped_column(Text, server_default=text("'v1'"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
