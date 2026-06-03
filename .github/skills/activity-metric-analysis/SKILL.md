---
name: activity-metric-analysis
description: 'Analyze activity-level metrics for cycling or running sessions. Use for heart-rate and power review, pacing stability, decoupling, execution-vs-plan analysis, efficiency flags, and deeper ride or run interpretation inside a daily assessment.'
user-invocable: false
---

# Activity Metric Analysis

This skill defines when and how to deepen a daily assessment with activity-level metric interpretation.

## When To Use

- The main session is cycling or running.
- The session was long enough or important enough to drive the day meaningfully.
- The planned intent and observed execution may not match.
- There are signs of pacing drift, excessive effort, unusual restraint, or durability issues.
- The user explicitly wants technical ride or run analysis.

## When Not To Use

- The day was dominated by walking, yoga, or short strength work.
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

## Output Rule

- Always separate observed metric facts from coaching interpretation.
- Prefer a short structured block over a long freeform technical explanation.
- If a metric cannot be computed credibly, mark it as unavailable and say why.