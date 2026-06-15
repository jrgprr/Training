---
name: block-performance-assessment
description: 'Assess one training block using macro intent, block plan, weekly execution, physiology trend, load progression, and exit-criteria evidence. Use for mesocycle review, block closure, progression readiness, and next-block recommendations.'
user-invocable: false
---

# Block Performance Assessment

This skill packages the workflow, script, and reference material needed to assess one training block.

## When To Use

- The user asks how a specific block went.
- The user wants a block-closure recommendation.
- The user wants to know whether it is appropriate to progress to the next block.
- The user wants a mesocycle-level plan vs reality interpretation.

## Procedure

1. Resolve the target block and season.
2. Build a normalized evidence bundle with:
   [build_block_context.py](./scripts/build_block_context.py)
3. Use the assessment rubric in:
   [assessment-framework.md](./references/assessment-framework.md)
4. Write the full assessment in English, translating Spanish source evidence into natural English unless a direct quote is necessary.
5. Format the answer using:
   [block-assessment-template.md](./assets/block-assessment-template.md)

## Required Evidence Domains

- Macro context for the season.
- Planned block role, duration, risks, and exit criteria.
- Weekly execution and weekly reviews across the block.
- Daily physiology and load trend across the block.
- Key-session completion and zone-alignment evidence when available.
- Transition context into the next block when available.

## Decision Rules

- Judge the block against its planned function, not only against total work completed.
- Treat missing subjective or recovery fields as uncertainty, not as failure.
- Separate a block that produced useful work from a block that is truly ready to hand off progression.
- Give explicit weight to exit criteria: repeatable weeks, tolerated long ride, integrated strength, and remaining freshness.
- Keep the output fully in English.

## Minimum Output

- Block verdict
- Main supporting evidence
- Exit-criteria read
- Recommendation for the next block or bridge week
- Confidence level
