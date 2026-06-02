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

CREATE VIEW IF NOT EXISTS vw_zone_active_profile_lookup AS
SELECT
        profile.zone_profile_id,
        profile.season_id,
        profile.discipline,
        profile.metric_basis,
        profile.profile_label,
        profile.governance_status,
        profile.effective_start_date,
        profile.effective_end_date,
        profile.accepted_at,
        boundary.zone_profile_boundary_id,
        boundary.zone_index,
        boundary.zone_code,
        boundary.zone_name,
        boundary.lower_bound_value,
        boundary.upper_bound_value,
        boundary.bound_unit,
        boundary.target_kind
FROM zone_profiles profile
LEFT JOIN zone_profile_boundaries boundary
    ON boundary.zone_profile_id = profile.zone_profile_id
WHERE profile.governance_status = 'accepted'
    AND (profile.effective_end_date IS NULL OR profile.effective_end_date = '')
ORDER BY profile.season_id, profile.discipline, profile.metric_basis, boundary.zone_index;

CREATE VIEW IF NOT EXISTS vw_exec_activity_zone_summary AS
SELECT
        result.activity_zone_result_id,
        result.activity_id,
        activity.season_id,
        activity.activity_date,
        activity.started_at,
        activity.discipline,
        activity.activity_type,
        result.metric_basis,
        result.zone_profile_id,
        profile.profile_label,
        result.calculation_status,
        result.quality_status_snapshot,
        result.supported_sample_count,
        result.total_supported_seconds,
        result.dominant_zone_code,
        result.dominant_zone_share,
        result.calculation_notes,
        result.calculated_at,
        GROUP_CONCAT(
                bucket.zone_code || ':' || bucket.seconds_in_zone || ':' || COALESCE(bucket.share_in_zone, 0),
                '|'
        ) AS bucket_summary
FROM exec_activity_zone_results result
JOIN exec_activities activity ON activity.activity_id = result.activity_id
JOIN zone_profiles profile ON profile.zone_profile_id = result.zone_profile_id
LEFT JOIN exec_activity_zone_buckets bucket
    ON bucket.activity_zone_result_id = result.activity_zone_result_id
GROUP BY
        result.activity_zone_result_id,
        result.activity_id,
        activity.season_id,
        activity.activity_date,
        activity.started_at,
        activity.discipline,
        activity.activity_type,
        result.metric_basis,
        result.zone_profile_id,
        profile.profile_label,
        result.calculation_status,
        result.quality_status_snapshot,
        result.supported_sample_count,
        result.total_supported_seconds,
        result.dominant_zone_code,
        result.dominant_zone_share,
        result.calculation_notes,
        result.calculated_at;

CREATE VIEW IF NOT EXISTS vw_zone_pending_refinement_proposals AS
SELECT
        proposal.proposal_id,
        proposal.season_id,
        proposal.discipline,
        proposal.metric_basis,
        proposal.proposal_status,
        proposal.confidence_level,
        proposal.recommendation_kind,
        proposal.proposal_summary,
        proposal.limiting_factors,
        proposal.proposed_effective_start_date,
        proposal.created_at,
        proposal.decided_at,
        proposal.decision_notes,
        proposal.source_zone_profile_id,
        source_profile.profile_label AS source_profile_label,
        COUNT(DISTINCT evidence.proposal_evidence_id) AS evidence_count,
        SUM(CASE WHEN evidence.evidence_role = 'supporting' THEN 1 ELSE 0 END) AS supporting_evidence_count,
        SUM(CASE WHEN evidence.evidence_role = 'limiting' THEN 1 ELSE 0 END) AS limiting_evidence_count,
        COUNT(DISTINCT boundary.proposal_boundary_id) AS proposed_boundary_count
FROM zone_refinement_proposals proposal
LEFT JOIN zone_profiles source_profile
    ON source_profile.zone_profile_id = proposal.source_zone_profile_id
LEFT JOIN zone_refinement_evidence evidence
    ON evidence.proposal_id = proposal.proposal_id
LEFT JOIN zone_refinement_proposal_boundaries boundary
    ON boundary.proposal_id = proposal.proposal_id
WHERE proposal.proposal_status = 'pending'
GROUP BY
        proposal.proposal_id,
        proposal.season_id,
        proposal.discipline,
        proposal.metric_basis,
        proposal.proposal_status,
        proposal.confidence_level,
        proposal.recommendation_kind,
        proposal.proposal_summary,
        proposal.limiting_factors,
        proposal.proposed_effective_start_date,
        proposal.created_at,
        proposal.decided_at,
        proposal.decision_notes,
        proposal.source_zone_profile_id,
        source_profile.profile_label;

CREATE VIEW IF NOT EXISTS vw_zone_proposal_review_states AS
WITH basis_actionable_counts AS (
    SELECT
        season_id,
        discipline,
        metric_basis,
        SUM(CASE WHEN proposal_status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
        SUM(CASE WHEN proposal_status = 'deferred' THEN 1 ELSE 0 END) AS deferred_count,
        SUM(CASE WHEN proposal_status IN ('pending', 'deferred') THEN 1 ELSE 0 END) AS actionable_count,
        COUNT(*) AS total_count
    FROM zone_refinement_proposals
    GROUP BY season_id, discipline, metric_basis
)
SELECT
    season_id,
    discipline,
    COALESCE(SUM(CASE WHEN metric_basis = 'heart_rate' THEN total_count ELSE 0 END), 0) AS heart_rate_total_count,
    COALESCE(SUM(CASE WHEN metric_basis = 'heart_rate' THEN pending_count ELSE 0 END), 0) AS heart_rate_pending_count,
    COALESCE(SUM(CASE WHEN metric_basis = 'heart_rate' THEN deferred_count ELSE 0 END), 0) AS heart_rate_deferred_count,
    COALESCE(SUM(CASE WHEN metric_basis = 'heart_rate' THEN actionable_count ELSE 0 END), 0) AS heart_rate_actionable_count,
    COALESCE(SUM(CASE WHEN metric_basis = 'power' THEN total_count ELSE 0 END), 0) AS power_total_count,
    COALESCE(SUM(CASE WHEN metric_basis = 'power' THEN pending_count ELSE 0 END), 0) AS power_pending_count,
    COALESCE(SUM(CASE WHEN metric_basis = 'power' THEN deferred_count ELSE 0 END), 0) AS power_deferred_count,
    COALESCE(SUM(CASE WHEN metric_basis = 'power' THEN actionable_count ELSE 0 END), 0) AS power_actionable_count,
    CASE
        WHEN COALESCE(SUM(CASE WHEN metric_basis = 'heart_rate' THEN actionable_count ELSE 0 END), 0) > 0
         AND COALESCE(SUM(CASE WHEN metric_basis = 'power' THEN actionable_count ELSE 0 END), 0) > 0
            THEN 'mixed_basis'
        WHEN COALESCE(SUM(CASE WHEN metric_basis = 'heart_rate' THEN actionable_count ELSE 0 END), 0) > 0
            THEN 'heart_rate_only'
        WHEN COALESCE(SUM(CASE WHEN metric_basis = 'power' THEN actionable_count ELSE 0 END), 0) > 0
            THEN 'power_only'
        ELSE 'no_actionable_proposals'
    END AS review_state
FROM basis_actionable_counts
GROUP BY season_id, discipline;

CREATE VIEW IF NOT EXISTS vw_zone_session_comparison_summary AS
SELECT
    block.season_id,
    block.block_id,
    block.block_code,
    week.week_id,
    week.week_code,
    planned.planned_session_id,
    planned.session_date,
    target.target_basis AS metric_basis,
    target.target_kind,
    target.comparison_eligibility,
    link.activity_id,
    result.calculation_status,
    result.dominant_zone_code,
    result.dominant_zone_share,
    MIN(CASE WHEN segment.target_zone_min_code GLOB 'Z[0-9]*' THEN CAST(SUBSTR(segment.target_zone_min_code, 2) AS INTEGER) END) AS target_zone_min_index,
    MAX(CASE WHEN segment.target_zone_max_code GLOB 'Z[0-9]*' THEN CAST(SUBSTR(segment.target_zone_max_code, 2) AS INTEGER) END) AS target_zone_max_index,
    COUNT(DISTINCT any_result.activity_zone_result_id) AS any_result_count,
    CASE
        WHEN target.comparison_eligibility = 'not_comparable' THEN 'not_comparable'
        WHEN target.target_basis IS NULL OR target.target_basis = 'mixed' THEN 'limited'
        WHEN link.activity_id IS NULL THEN 'not_comparable'
        WHEN target.target_kind = 'multi_segment' THEN 'limited'
        WHEN result.calculation_status != 'calculated' THEN 'limited'
        WHEN result.dominant_zone_code IS NULL THEN 'limited'
        WHEN CAST(SUBSTR(result.dominant_zone_code, 2) AS INTEGER)
             BETWEEN COALESCE(MIN(CASE WHEN segment.target_zone_min_code GLOB 'Z[0-9]*' THEN CAST(SUBSTR(segment.target_zone_min_code, 2) AS INTEGER) END), -999999)
                 AND COALESCE(MAX(CASE WHEN segment.target_zone_max_code GLOB 'Z[0-9]*' THEN CAST(SUBSTR(segment.target_zone_max_code, 2) AS INTEGER) END), 999999)
            THEN 'aligned'
        ELSE 'misaligned'
    END AS comparison_status
FROM plan_planned_sessions planned
JOIN plan_micro_weeks week ON week.week_id = planned.week_id
JOIN plan_meso_blocks block ON block.block_id = week.block_id
LEFT JOIN plan_session_zone_targets target ON target.planned_session_id = planned.planned_session_id
LEFT JOIN plan_session_zone_segments segment ON segment.planned_zone_target_id = target.planned_zone_target_id
LEFT JOIN link_plan_execution link ON link.planned_session_id = planned.planned_session_id
LEFT JOIN exec_activity_zone_results result
    ON result.activity_id = link.activity_id
 AND result.metric_basis = target.target_basis
LEFT JOIN exec_activity_zone_results any_result
    ON any_result.activity_id = link.activity_id
WHERE target.planned_session_id IS NOT NULL
GROUP BY
    block.season_id,
    block.block_id,
    block.block_code,
    week.week_id,
    week.week_code,
    planned.planned_session_id,
    planned.session_date,
    target.target_basis,
    target.target_kind,
    target.comparison_eligibility,
    link.activity_id,
    result.activity_zone_result_id,
    result.calculation_status,
    result.dominant_zone_code,
    result.dominant_zone_share;

CREATE VIEW IF NOT EXISTS vw_zone_week_comparison_summary AS
SELECT
        season_id,
        block_id,
        block_code,
        week_id,
        week_code,
    metric_basis,
        COUNT(*) AS planned_session_count,
        SUM(CASE WHEN activity_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_activity_count,
        SUM(CASE WHEN comparison_status = 'aligned' THEN 1 ELSE 0 END) AS aligned_count,
        SUM(CASE WHEN comparison_status = 'misaligned' THEN 1 ELSE 0 END) AS misaligned_count,
        SUM(CASE WHEN comparison_status = 'limited' THEN 1 ELSE 0 END) AS limited_count,
        SUM(CASE WHEN comparison_status = 'not_comparable' THEN 1 ELSE 0 END) AS not_comparable_count,
        GROUP_CONCAT(
                planned_session_id || ':' || comparison_status || ':' || COALESCE(dominant_zone_code, 'none'),
                '|'
        ) AS session_status_summary
    FROM vw_zone_session_comparison_summary
    WHERE metric_basis IS NOT NULL
    GROUP BY season_id, block_id, block_code, week_id, week_code, metric_basis
    ORDER BY season_id, block_id, week_id, metric_basis;