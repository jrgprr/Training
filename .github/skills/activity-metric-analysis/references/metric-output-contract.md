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
- Borderline means the session likely sat near the ceiling of the intended aerobic control.
- Poor means the session no longer behaved like well-controlled aerobic work.

## Power And HR Relationship

- `power_hr_relationship`: aligned, hr_high_for_power, power_high_for_hr, decoupled, or unavailable
- `avg_power`
- `normalized_power`
- `avg_hr`
- `max_hr`
- `relationship_notes`

## Zone Execution

- `zone_execution`: aligned, mostly_aligned, misaligned, or unavailable
- `dominant_hr_zone`
- `dominant_power_zone`
- `zone_execution_notes`

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

### Pace Plus HR Running Session

- replace power-specific language with pace/HR equivalents where needed
- keep the same output keys when possible for consistency

## Computation Priorities

If you later add scripts, prioritize these calculations first:

1. duration vs plan
2. dominant zone execution
3. pacing stability
4. HR drift or HR-power decoupling
5. power-HR relationship classification