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

CREATE VIEW IF NOT EXISTS vw_agent_latest_assessment_summaries AS
WITH ranked_runs AS (
    SELECT
        r.assessment_run_id,
        r.agent_profile_id,
        r.assessment_window_id,
        p.profile_key,
        p.display_name AS agent_profile_name,
        p.cadence,
        p.assessment_scope,
        w.season_id,
        w.block_id,
        w.week_id,
        w.window_start_date,
        w.window_end_date,
        w.subject_scope_key,
        r.run_status,
        r.confidence_label,
        r.summary_text,
        r.created_at,
        r.started_at,
        r.completed_at,
        (
            SELECT COUNT(*)
            FROM agent_adaptation_proposals ap
            WHERE ap.assessment_run_id = r.assessment_run_id
        ) AS proposal_count,
        (
            SELECT COUNT(*)
            FROM agent_adaptation_proposals ap
            WHERE ap.assessment_run_id = r.assessment_run_id
              AND ap.proposal_status = 'pending'
        ) AS pending_proposal_count,
        ROW_NUMBER() OVER (
            PARTITION BY p.cadence, p.profile_key, w.subject_scope_key
            ORDER BY COALESCE(r.completed_at, r.started_at, r.created_at) DESC, r.assessment_run_id DESC
        ) AS run_rank
    FROM agent_assessment_runs r
    JOIN agent_assessment_profiles p ON p.agent_profile_id = r.agent_profile_id
    JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
)
SELECT
    assessment_run_id,
    agent_profile_id,
    assessment_window_id,
    profile_key,
    agent_profile_name,
    cadence,
    assessment_scope,
    season_id,
    block_id,
    week_id,
    window_start_date,
    window_end_date,
    subject_scope_key,
    run_status,
    confidence_label,
    summary_text,
    proposal_count,
    pending_proposal_count,
    created_at,
    started_at,
    completed_at
FROM ranked_runs
WHERE run_rank = 1;

CREATE VIEW IF NOT EXISTS vw_agent_assessment_detail AS
SELECT
    r.assessment_run_id,
    r.agent_profile_id,
    r.assessment_window_id,
    p.profile_key,
    p.display_name AS agent_profile_name,
    p.cadence,
    p.assessment_scope,
    p.target_planning_level,
    w.season_id,
    w.block_id,
    w.week_id,
    w.window_start_date,
    w.window_end_date,
    w.subject_scope_key,
    r.trigger_mode,
    r.run_status,
    r.provider_key,
    r.model_name,
    r.instruction_version,
    r.summary_text,
    r.confidence_label,
    r.principal_evidence_json,
    r.failure_code,
    r.failure_detail,
    (
        SELECT COUNT(*)
        FROM agent_assessment_type_results tr
        WHERE tr.assessment_run_id = r.assessment_run_id
    ) AS type_result_count,
    (
        SELECT COUNT(*)
        FROM agent_assessment_findings f
        WHERE f.assessment_run_id = r.assessment_run_id
    ) AS finding_count,
    (
        SELECT COUNT(*)
        FROM agent_adaptation_proposals ap
        WHERE ap.assessment_run_id = r.assessment_run_id
    ) AS proposal_count,
    (
        SELECT COUNT(*)
        FROM agent_adaptation_proposals ap
        WHERE ap.assessment_run_id = r.assessment_run_id
          AND ap.proposal_status = 'pending'
    ) AS pending_proposal_count,
    (
        SELECT COUNT(*)
        FROM agent_assessment_dialog_context dc
        WHERE dc.assessment_run_id = r.assessment_run_id
    ) AS dialog_entry_count,
    r.created_at,
    r.started_at,
    r.completed_at,
    r.supersedes_run_id
FROM agent_assessment_runs r
JOIN agent_assessment_profiles p ON p.agent_profile_id = r.agent_profile_id
JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id;

CREATE VIEW IF NOT EXISTS vw_agent_proposal_review_queue AS
WITH latest_decisions AS (
    SELECT
        d.proposal_id,
        d.decision_status,
        d.decision_note,
        d.decided_by,
        d.decided_at,
        d.superseding_proposal_id,
        d.applied_change_ref,
        ROW_NUMBER() OVER (
            PARTITION BY d.proposal_id
            ORDER BY d.decided_at DESC, d.proposal_decision_id DESC
        ) AS decision_rank
    FROM agent_proposal_decisions d
)
SELECT
    ap.proposal_id,
    ap.assessment_run_id,
    ap.agent_profile_id,
    p.profile_key,
    p.display_name AS agent_profile_name,
    p.cadence,
    w.season_id,
    w.block_id,
    w.week_id,
    w.window_start_date,
    w.window_end_date,
    w.subject_scope_key,
    r.run_status AS source_run_status,
    r.confidence_label AS source_confidence_label,
    ap.source_cadence,
    ap.target_planning_level,
    ap.proposal_status,
    ap.proposal_title,
    ap.proposal_summary,
    ap.change_kind,
    ap.proposed_change_json,
    ap.reasoning_summary,
    ap.conflict_group_key,
    ld.decision_status AS latest_decision_status,
    ld.decision_note AS latest_decision_note,
    ld.decided_by AS latest_decided_by,
    ld.decided_at AS latest_decided_at,
    ld.superseding_proposal_id AS latest_superseding_proposal_id,
    ld.applied_change_ref AS latest_applied_change_ref,
    ap.created_at,
    ap.updated_at
FROM agent_adaptation_proposals ap
JOIN agent_assessment_runs r ON r.assessment_run_id = ap.assessment_run_id
JOIN agent_assessment_profiles p ON p.agent_profile_id = ap.agent_profile_id
JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
LEFT JOIN latest_decisions ld
       ON ld.proposal_id = ap.proposal_id
      AND ld.decision_rank = 1;

CREATE VIEW IF NOT EXISTS vw_agent_proposal_decision_history AS
SELECT
    d.proposal_decision_id,
    d.proposal_id,
    ap.assessment_run_id,
    ap.agent_profile_id,
    p.profile_key,
    p.display_name AS agent_profile_name,
    p.cadence,
    w.season_id,
    w.block_id,
    w.week_id,
    w.window_start_date,
    w.window_end_date,
    w.subject_scope_key,
    ap.source_cadence,
    ap.target_planning_level,
    ap.proposal_status,
    ap.proposal_title,
    ap.change_kind,
    d.decision_status,
    d.decision_note,
    d.decided_by,
    d.decided_at,
    d.superseding_proposal_id,
    d.applied_change_ref
FROM agent_proposal_decisions d
JOIN agent_adaptation_proposals ap ON ap.proposal_id = d.proposal_id
JOIN agent_assessment_runs r ON r.assessment_run_id = ap.assessment_run_id
JOIN agent_assessment_profiles p ON p.agent_profile_id = ap.agent_profile_id
JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id;

CREATE VIEW IF NOT EXISTS vw_agent_accepted_plan_mutation_traceability AS
SELECT
    m.plan_mutation_id,
    m.proposal_id,
    ap.assessment_run_id,
    ap.agent_profile_id,
    p.profile_key,
    p.display_name AS agent_profile_name,
    p.cadence,
    ap.source_cadence,
    ap.target_planning_level,
    ap.proposal_title,
    ap.change_kind,
    ap.reasoning_summary,
    w.season_id,
    w.block_id,
    w.week_id,
    w.window_start_date,
    w.window_end_date,
    w.subject_scope_key,
    d.decision_status,
    d.decision_note,
    d.decided_by,
    d.decided_at,
    d.applied_change_ref,
    m.target_entity_id,
    m.mutation_summary,
    m.before_snapshot_json,
    m.after_snapshot_json,
    m.applied_at,
    m.applied_by
FROM agent_accepted_plan_mutations m
JOIN agent_adaptation_proposals ap ON ap.proposal_id = m.proposal_id
JOIN agent_assessment_runs r ON r.assessment_run_id = ap.assessment_run_id
JOIN agent_assessment_profiles p ON p.agent_profile_id = ap.agent_profile_id
JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
LEFT JOIN agent_proposal_decisions d ON d.proposal_id = m.proposal_id AND d.decision_status = 'accepted';