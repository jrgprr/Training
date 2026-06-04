---
name: daily-performance-assessment
description: 'Assess one training day using planning, execution, physiology, load, and quality evidence. Use for daily performance review, readiness analysis, recovery assessment, plan vs reality interpretation, and next-day coaching decisions.'
user-invocable: false
---

# Daily Performance Assessment

This skill packages the workflow, script, and reference material needed to assess a single day in the training system.

## When To Use

- The user asks how a specific day went.
- The user wants a coaching recommendation for today or tomorrow.
- The user asks for a daily readiness or recovery assessment.
- The user wants a plan vs reality interpretation for one date.
- The user wants a performance verdict that combines planning, physiology, training, and load.

## Procedure

1. Resolve the target date and season.
2. Build a normalized evidence bundle with:
   [build_day_context.py](./scripts/build_day_context.py)
3. Use the assessment rubric in:
   [assessment-framework.md](./references/assessment-framework.md)
4. Apply the sport-specific interpretation rules in:
   [sport-specific-rules.md](./references/sport-specific-rules.md)
5. If the evidence bundle already includes `activity_metric_analysis`, treat that as the default structured technical read for the dominant endurance session.
6. When the dominant endurance session is cycling, running, or a meaningful walking-like session but `activity_metric_analysis` is absent, or when execution quality is still unclear, load the `activity-metric-analysis` skill and incorporate its structured outputs.
7. Format the answer using:
   [day-assessment-template.md](./assets/day-assessment-template.md)

## Required Evidence Domains

- Planning context for the date.
- Executed activities on the date.
- Linked plan-vs-execution evidence.
- Daily physiology and recovery metrics.
- Acute and chronic load context.
- Weekly context when available.
- Quality and zone evidence when available.
- Activity-level metric interpretation, preferring `activity_metric_analysis` from the day context when available and falling back to the support skill when a deeper endurance read is justified.
- Treat `walking`, `hiking`, `trail_walking`, and `nordic_walking` as eligible only when they exceed 45 minutes or 50 modeled load.

## Decision Rules

- Prefer explicit measured data over inferred narratives.
- Treat missing HRV, body battery, or subjective fields as unknown, not bad.
- Distinguish between a hard day that was appropriate and a hard day that was excessive.
- Assess today relative to the role of the day inside the week and block, not in isolation.
- Always separate observed evidence from coaching recommendation.

## Minimum Output

- Day verdict
- Main supporting evidence
- Key risk or caution flags
- Next-day recommendation
- Confidence level