---
name: weekly-zone-coherence-assessment
description: 'Assess whether the current training zones still fit the available weekly evidence. Use during weekly review to decide if zone definitions remain coherent, should be monitored, or should be updated.'
user-invocable: false
---

# Weekly Zone Coherence Assessment

This skill packages a read-only workflow to evaluate whether the active zone definitions still match the evidence available by the end of a training week.

## When To Use

- The user wants the weekly review to include whether zones are still well calibrated.
- A weekly assessment needs an explicit decision on keeping or updating zones.
- The week contains enough cycling evidence to question whether Z2 boundaries still fit.
- The coach wants to distinguish route-driven zone drift from a real stale-profile signal.

## Procedure

1. Resolve the target week and season.
2. Run:
   [analyze_week_zone_coherence.py](./scripts/analyze_week_zone_coherence.py)
3. Interpret the result with:
   [zone-coherence-framework.md](./references/zone-coherence-framework.md)
4. Feed the resulting decision into the weekly assessment output.