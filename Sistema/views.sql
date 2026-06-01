CREATE VIEW IF NOT EXISTS vw_plan_block_summary AS
SELECT
    s.season_code,
    b.sequence_order,
    b.block_code,
    b.block_name,
    b.phase_name,
    b.start_date,
    b.end_date,
    b.duration_weeks_min,
    b.duration_weeks_max,
    b.objective_primary,
    b.exit_criteria
FROM plan_meso_blocks b
JOIN plan_seasons s ON s.season_id = b.season_id
ORDER BY b.sequence_order;

CREATE VIEW IF NOT EXISTS vw_plan_week_summary AS
SELECT
    b.block_code,
    b.block_name,
    w.week_code,
    w.sequence_in_block,
    w.start_date,
    w.end_date,
    w.week_role,
    w.objective_primary,
    w.target_volume_hours_min,
    w.target_volume_hours_max,
    w.closure_rule
FROM plan_micro_weeks w
JOIN plan_meso_blocks b ON b.block_id = w.block_id
ORDER BY b.sequence_order, w.sequence_in_block;

CREATE VIEW IF NOT EXISTS vw_exec_daily_dashboard AS
SELECT
    m.metric_date,
    m.weight_kg,
    m.sleep_hours,
    m.resting_hr,
    m.hrv,
    m.subjective_energy,
    m.subjective_fatigue,
    COUNT(a.activity_id) AS activities_count,
    COALESCE(SUM(a.duration_seconds), 0) / 3600.0 AS total_activity_hours
FROM exec_daily_metrics m
LEFT JOIN exec_activities a
    ON a.season_id = m.season_id
   AND a.activity_date = m.metric_date
GROUP BY
    m.metric_date,
    m.weight_kg,
    m.sleep_hours,
    m.resting_hr,
    m.hrv,
    m.subjective_energy,
    m.subjective_fatigue;

CREATE VIEW IF NOT EXISTS vw_plan_vs_real AS
SELECT
    ps.session_date,
    b.block_code,
    w.week_code,
    ps.day_name,
    ps.objective AS planned_objective,
    ps.primary_session AS planned_session,
    ea.activity_type AS actual_activity_type,
    ea.duration_seconds / 60.0 AS actual_duration_min,
    l.compliance_status,
    rr.general_feeling,
    rr.next_day_decision
FROM plan_planned_sessions ps
JOIN plan_micro_weeks w ON w.week_id = ps.week_id
JOIN plan_meso_blocks b ON b.block_id = w.block_id
LEFT JOIN link_plan_execution l ON l.planned_session_id = ps.planned_session_id
LEFT JOIN exec_activities ea ON ea.activity_id = l.activity_id
LEFT JOIN review_daily_reviews rr ON rr.planned_session_id = ps.planned_session_id;

CREATE VIEW IF NOT EXISTS vw_exec_segment_history AS
SELECT
    se.segment_id,
    s.source_system,
    s.external_segment_id,
    s.segment_name,
    s.discipline,
    s.distance_meters,
    s.ascent_meters,
    s.average_grade_percent,
    se.segment_effort_id,
    se.external_segment_effort_id,
    se.activity_id,
    se.activity_date,
    ea.external_activity_id,
    se.started_at,
    se.elapsed_time_seconds,
    se.avg_power,
    se.avg_cadence,
    se.avg_heart_rate,
    se.max_heart_rate,
    se.notes
FROM exec_segment_efforts se
JOIN exec_segments s ON s.segment_id = se.segment_id
JOIN exec_activities ea ON ea.activity_id = se.activity_id;