---
name: weight-control-assessment
description: 'Assess body-mass trend, weight evolution, and training-compatible weight control. Use for weight trend review, target progress, volatility checks, stalled or too-fast loss, and whether current weight change fits recovery and load context.'
user-invocable: false
---

# Weight Control Assessment

This skill packages the workflow, script, and reference material needed to assess current weight evolution inside the training system.

## When To Use

- The user asks whether weight is trending in the right direction.
- The user wants a coaching read on body-mass evolution.
- The user asks if weight loss is too fast, stalled, or too noisy.
- The user wants to know whether the current weight trend is compatible with training and recovery.
- The user wants a date-specific weight-control assessment grounded in the season plan.

## Procedure

1. Resolve the target date and season.
2. Build a normalized evidence bundle with:
   [build_weight_context.py](./scripts/build_weight_context.py)
3. Use the assessment rubric in:
   [assessment-framework.md](./references/assessment-framework.md)
4. Format the answer using:
   [weight-assessment-template.md](./assets/weight-assessment-template.md)

## Required Evidence Domains

- Weight target context from the season profile and macro rules.
- Weekly weight-goal context from the active microcycle.
- Recent weigh-in series from `exec_daily_metrics`.
- Body-composition series from Garmin when available: body fat, body water, muscle mass, bone mass, BMI, and related scale outputs.
- Recovery markers near the same dates: sleep, resting HR, stress, and subjective or review signals when present.
- Load context near the same dates: daily load, ATL, CTL, TSB.
- Recent review notes when they help interpret whether the process remains repeatable.

## Decision Rules

- Prefer smoothed trend over single-day weigh-ins.
- Treat short-term water fluctuation as noise unless corroborated by several days.
- Treat a favorable weight trend with worsening body-fat %, falling muscle mass, or unstable water balance as lower quality than weight alone suggests.
- Treat stable weight with improving body-fat % or preserved muscle mass as potentially positive during demanding training phases.
- Weight loss is only positive when it remains compatible with repeatable training, recovery, and preserved structural work.
- Upward drift is not automatically bad if recovery, load, and week role suggest normal fluctuation.
- Missing nutrition or appetite data limits certainty; do not infer energy balance directly.

## Minimum Output

- Weight-control verdict
- Main supporting evidence
- Key caution flags
- Near-term recommendation
- Confidence level