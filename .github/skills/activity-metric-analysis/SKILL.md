---
name: activity-metric-analysis
description: 'Analyze activity-level metrics for endurance sessions. Use for heart-rate and power review, pacing stability, decoupling, execution-vs-plan analysis, efficiency flags, and deeper ride, run, or meaningful walk interpretation inside a daily assessment.'
user-invocable: false
---

# Activity Metric Analysis

This skill defines when and how to deepen a daily assessment with activity-level metric interpretation.

## When To Use

- The main session is cycling, running, or a walking-like session with meaningful duration or modeled load.
- Walking-like Garmin labels include `walking`, `hiking`, `trail_walking`, and `nordic_walking`.
- The session was long enough or important enough to drive the day meaningfully.
- The planned intent and observed execution may not match.
- There are signs of pacing drift, excessive effort, unusual restraint, or durability issues.
- The user explicitly wants technical ride or run analysis.

## When Not To Use

- The day was dominated by yoga or short strength work.
- The walking-like session stayed below the explicit trigger threshold: under 45 minutes and under 50 modeled load.
- The available metrics are too sparse or low-quality to support interpretation.
- The daily decision is already obvious from plan, physiology, and load alone.

## Procedure

1. Start from the normalized day context built by the daily assessment workflow.
2. Identify the dominant endurance activity for the day.
3. Use the trigger rules in:
   [trigger-rules.md](./references/trigger-rules.md)
4. Compute the first metric-analysis block from stored activity data using:
   [compute_activity_metric_analysis.py](./scripts/compute_activity_metric_analysis.py)
5. Produce only the metrics justified by the available data using:
   [metric-output-contract.md](./references/metric-output-contract.md)
6. Return a concise structured metric-analysis block that supports the day-level conclusion.
7. When Garmin exposed Performance Condition credibly, include an explicit `performance_condition_evolution` paragraph that describes how the signal changed across the activity and what that pattern usually means.
8. When available, include the richer technical sub-blocks for segment efforts and recent similar-session comparison, but keep them evidence-first and compact.

## Output Rule

- Always separate observed metric facts from coaching interpretation.
- Prefer a short structured block over a long freeform technical explanation.
- If a metric cannot be computed credibly, mark it as unavailable and say why.
- Treat Performance Condition as a secondary freshness hint: do not let it override drift, decoupling, load, or execution quality.
- Read the trajectory, not just the average: a bad opening can recover, and a good opening can fade.
- Give more weight to the late-session signal than to the first 10-20 minutes.
