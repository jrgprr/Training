# Metric Output Contract

Return a compact JSON-like analysis block conceptually shaped as follows.

## Core Fields

- `activity_id`
- `sport`
- `analysis_scope`
- `data_quality`

## Data Quality

- `quality_status`: clean, limited, unreliable, or unavailable
- `quality_notes`: key caveats
- `metric_sources`: heart_rate, power, pace, respiration_rate, zones, segments, running_dynamics

## Execution Versus Plan

- `execution_vs_plan`: on_target, slightly_above, slightly_below, mismatched, or unknown
- `duration_vs_plan_minutes`
- `intensity_execution`: controlled, creeping_high, too_high, too_low, variable, or unknown
- `plan_alignment_notes`

## Pacing Stability

- `pacing_stability_status`: stable, mildly_variable, highly_variable, or unavailable
- `pacing_stability_evidence`
- `late_session_fade`: yes, no, unclear

## Aerobic Control

- `aerobic_control_status`: good, borderline, poor, or unavailable
- `hr_drift_percent`
- `hr_power_decoupling_percent`
- `aerobic_control_notes`

Interpretation guidance:

- Good aerobic control usually means low drift and no progressive loss of efficiency.
- For running and walking/hiking, clearly negative HR drift should not be treated as poor by default; first read it as containment, easing terrain, or a controlled finish unless other evidence contradicts that.
- Borderline means the session likely sat near the ceiling of the intended aerobic control.
- Poor means the session no longer behaved like well-controlled aerobic work.

## Power And HR Relationship

- `power_hr_relationship`: aligned, hr_high_for_power, power_high_for_hr, decoupled, or unavailable
- `avg_power`
- `normalized_power`
- `avg_hr`
- `max_hr`
- `avg_pace_seconds_per_km`
- `avg_pace_formatted`
- `grade_adjusted_pace`: optional for running and walking/hiking when terrain-adjusted pace can be estimated credibly
- `relationship_notes`

## Zone Execution

- `zone_execution`: aligned, mostly_aligned, misaligned, or unavailable
- `dominant_hr_zone`
- `dominant_power_zone`
- `zone_execution_notes`

## Activity Efficiency

When the activity has enough summary, power, zone, or respiration data, you may add:

- `activity_efficiency.efficiency_factor` with current value, basis, and recent comparison
- `activity_efficiency.grade_adjusted_pace` for running and walking/hiking when terrain adjustment is credible
- `activity_efficiency.variability_index` with current value, recent comparison, and status
- `activity_efficiency.target_zone_compliance` with in-target, above-target, and below-target shares
- `activity_efficiency.load_density` with current value and recent comparison
- `activity_efficiency.coasting_or_low_output_share` when low-power share can be estimated credibly
- `activity_efficiency.climbing_efficiency` when ascent is meaningful
- `activity_efficiency.respiration_relationship` when respiration summaries are available

Interpretation guidance:

- `efficiency_factor` should read as internal-cost efficiency, not as an absolute fitness score.
- For pace-based disciplines, `efficiency_factor` may be based on speed or grade-adjusted speed per average HR rather than power.
- `grade_adjusted_pace` is an interpretation aid, not a standalone verdict; use it to separate terrain effect from aerobic execution.
- `variability_index` helps distinguish clean endurance execution from materially surgy riding.
- `target_zone_compliance` is especially important for recovery and aerobic-control rides.
- `load_density` shows how much stimulus was packed into each hour.
- `coasting_or_low_output_share` prevents over-interpreting low density when the route or stop-start pattern explains it.
- `climbing_efficiency` should only appear when the route had meaningful ascent.
- `respiration_relationship` is optional and should stay observational unless recent comparison gives it context.

## Efficiency Flags

- `efficiency_flags`: array of short labels

Suggested labels:

- `cardiac_drift`
- `late_fade`
- `early_overreach`
- `underloaded_for_intent`
- `power_spiky`
- `hr_suppressed`
- `hr_elevated`
- `durability_good`

## Optional Segment Analysis

When the activity has stored segment efforts, you may add:

- `segment_analysis.segment_count`
- `segment_analysis.comparable_segment_count`
- `segment_analysis.highlights[]` with `segment_name`, `elapsed_time_seconds`, `avg_power`, `avg_heart_rate`, `history_sample_count`, `delta_vs_previous_seconds`, `delta_vs_best_seconds`, and `trend_status`

Interpretation guidance:

- Use the block to explain whether key segments were better, worse, or unchanged relative to recent history.
- Keep the segment read compact and avoid turning the assessment into a segment-by-segment dump.

## Optional Recent Comparison

When the activity has recent same-discipline comparables in a similar duration band, you may add:

- `recent_comparison.matching_basis`
- `recent_comparison.sample_count`
- `recent_comparison.window_start_date`
- `recent_comparison.window_end_date`
- `recent_comparison.similar_activities[]`
- `recent_comparison.current_vs_recent` keyed by metric name

Interpretation guidance:

- Use this block to position the session against recent norms for duration, load, and intensity.
- Prefer averages and directionality over exhaustive historical detail.

## Optional Running Dynamics

When the activity is a running session and Garmin exposed the metrics credibly, you may add:

- `running_dynamics.status`: available, partial, or unavailable
- `running_dynamics.available_metric_count`
- `running_dynamics.metrics`: compact metric dictionary using stored average values
- `running_dynamics.flags`: short labels for notable mechanical signals
- `running_dynamics.notes`: concise observed facts, not long prose

Interpretation guidance:

- Prefer cadence, ground contact time, vertical ratio, stride length, and performance condition first.
- Mark the block as `partial` when Garmin omitted the full mechanical set.
- Keep the notes observational and let the coaching summary decide overall significance.

## Coaching Summary

- `metric_verdict`: one short paragraph
- `coaching_implication`: how the metric analysis changes or supports the day-level assessment

## Minimal Output By Data Availability

### HR Only

- data_quality
- execution_vs_plan
- pacing_stability
- aerobic_control
- zone_execution from HR if available
- coaching_summary

### Power Plus HR

- all core sections
- optional segment analysis and recent comparison when available

### Pace Plus HR Running Or Walking/Hiking Session

- replace power-specific language with pace/HR equivalents where needed
- prefer grade-adjusted pace when terrain materially changes the read
- keep the same output keys when possible for consistency

## Computation Priorities

If you later add scripts, prioritize these calculations first:

1. duration vs plan
2. dominant zone execution
3. pacing stability
4. HR drift or HR-power decoupling
5. power-HR relationship classification
6. segment trend and recent comparable positioning
