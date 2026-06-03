---
name: weekly-performance-assessment
description: 'Assess one training week using planning, execution, physiology, load distribution, and day-level evidence. Use for weekly review, week-level readiness analysis, and next-week coaching decisions.'
user-invocable: false
---

# Weekly Performance Assessment

This skill packages the workflow, script, and reference material needed to assess a single training week.

## When To Use

- The user asks how a specific week went.
- The user wants a weekly coaching recommendation.
- The user wants a weekly plan vs reality interpretation.
- The user wants a decision on how to treat the next week's plan.

## Procedure

1. Resolve the target week and season.
2. Build a normalized evidence bundle with:
   [build_week_context.py](./scripts/build_week_context.py)
3. Use the assessment rubric in:
   [assessment-framework.md](./references/assessment-framework.md)
4. Format the answer using:
   [week-assessment-template.md](./assets/week-assessment-template.md)
