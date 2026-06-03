---
name: daily-review-writeback
description: 'Write a structured daily review into review_daily_reviews. Use for daily review persistence, review writeback, plan vs reality conclusions, next-day decisions, and dry-run validation before saving.'
user-invocable: false
---

# Daily Review Writeback

This skill packages the contract and script for writing one row into `review_daily_reviews`.
It also writes a markdown logbook file for the same assessment under the season folder.

## When To Use

- The user explicitly wants to save a daily assessment.
- The user wants to write a next-day decision into the database.
- The user wants a dry-run preview before persisting a daily review.

## Procedure

1. Resolve the target date and season.
2. When persisting a coaching assessment, include the exact coach response as `detailed_assessment_markdown`.
3. If the request arrives via handoff from `Daily Performance Coach`, treat the handed-off response body as the default `detailed_assessment_markdown` with no manual rewriting.
4. Build a structured payload using:
   [review-payload-template.json](./assets/review-payload-template.json)
5. Validate the required and optional fields using:
   [field-contract.md](./references/field-contract.md)
6. Run:
   [upsert_daily_review.py](./scripts/upsert_daily_review.py)
7. Default to `--dry-run` unless the user explicitly asked to persist.

## Safety Rules

- Never write on an ambiguous request.
- Prefer explicit `planned_session_id` when known.
- If `planned_session_id` is not provided, infer it only when the day resolves unambiguously.
- Return the resolved row and warnings after every run.

## Minimum Output

- Action performed
- Resolved identifiers
- Stored fields
- Markdown logbook path
- Warnings
