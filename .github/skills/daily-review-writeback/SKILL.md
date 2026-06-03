---
name: daily-review-writeback
description: 'Write a structured daily review into review_daily_reviews. Use for daily review persistence, review writeback, plan vs reality conclusions, next-day decisions, and dry-run validation before saving.'
user-invocable: false
---

# Daily Review Writeback

This skill packages the contract and script for writing one row into `review_daily_reviews`.

## When To Use

- The user explicitly wants to save a daily assessment.
- The user wants to write a next-day decision into the database.
- The user wants a dry-run preview before persisting a daily review.

## Procedure

1. Resolve the target date and season.
2. Build a structured payload using:
   [review-payload-template.json](./assets/review-payload-template.json)
3. Validate the required and optional fields using:
   [field-contract.md](./references/field-contract.md)
4. Run:
   [upsert_daily_review.py](./scripts/upsert_daily_review.py)
5. Default to `--dry-run` unless the user explicitly asked to persist.

## Safety Rules

- Never write on an ambiguous request.
- Prefer explicit `planned_session_id` when known.
- If `planned_session_id` is not provided, infer it only when the day resolves unambiguously.
- Return the resolved row and warnings after every run.

## Minimum Output

- Action performed
- Resolved identifiers
- Stored fields
- Warnings
