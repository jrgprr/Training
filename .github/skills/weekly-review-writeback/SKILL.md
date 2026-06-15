---
name: weekly-review-writeback
description: 'Write a structured weekly review into review_weekly_reviews. Use for weekly review persistence, plan-vs-reality week conclusions, and next-week plan decisions.'
user-invocable: false
---

# Weekly Review Writeback

This skill packages the contract and script for writing one row into `review_weekly_reviews`.
It also writes a markdown logbook file for the same assessment under the season folder.

## When To Use

- The user explicitly wants to save a weekly assessment.
- The user wants to write a next-week decision into the database.
- The user wants a dry-run preview before persisting a weekly review.
- The request arrives as a persistence handoff from `Weekly Performance Coach` after a concrete week assessment.

## Procedure

1. Resolve the target week and season.
2. When persisting a coaching assessment, include the exact coach response as `detailed_assessment_markdown`.
3. If the request arrives via handoff from `Weekly Performance Coach`, treat the handed-off response body as the default `detailed_assessment_markdown` with no manual rewriting.
4. Keep the persisted markdown fully in English. If the source assessment contains Spanish week text or day-level evidence snippets, translate them before persistence unless a brief direct quote is necessary.
5. Build a structured payload using:
   [review-payload-template.json](./assets/review-payload-template.json)
6. Validate the required and optional fields using:
   [field-contract.md](./references/field-contract.md)
7. If the request is a persistence handoff from `Weekly Performance Coach` and there is no read-only or dry-run override, run write mode directly.
8. Otherwise run:
   [upsert_weekly_review.py](./scripts/upsert_weekly_review.py)
9. Default to `--dry-run` unless the request is that explicit persistence handoff or the user explicitly asked to persist.

## Language Rule

- Persist the assessment markdown entirely in English.
- Translate Spanish planning text, week notes, and source evidence into natural English before writing.
- Keep original Spanish only for brief direct quotes when the exact wording matters.
- Do not mix English and Spanish headings, labels, or coaching interpretation in persisted markdown.

## Safety Rules

- Never write on an ambiguous request.
- Prefer explicit `week_id` and `season_id` when known.
- If derived fields are omitted, infer them only when the target week resolves unambiguously.
- Return the resolved row and warnings after every run.

## Minimum Output

- Action performed
- Resolved identifiers
- Stored fields
- Markdown logbook path
- Warnings
