---
name: weight-review-writeback
description: 'Write a structured weight review into review_weight_reviews. Use for weight-trend review persistence, body-mass control conclusions, next-step decisions, and dry-run validation before saving.'
user-invocable: false
---

# Weight Review Writeback

This skill packages the contract and script for writing one row into `review_weight_reviews`.
It also writes a markdown logbook file for the same assessment under the season folder.

## When To Use

- The user explicitly wants to save a weight-control assessment.
- The user wants to write a weight-trend conclusion into the database.
- The user wants a dry-run preview before persisting a weight review.
- The request arrives as a persistence handoff from `Weight Control Coach` after a concrete assessment.

## Procedure

1. Resolve the target date and season.
2. When persisting a coaching assessment, include the exact coach response as `detailed_assessment_markdown`.
3. If the request arrives via handoff from `Weight Control Coach`, treat the handed-off response body as the default `detailed_assessment_markdown` with no manual rewriting.
4. Keep the persisted markdown fully in English. If the source assessment contains Spanish evidence snippets or planning notes, translate them before persistence unless a brief direct quote is necessary.
5. Build a structured payload using:
   [review-payload-template.json](./assets/review-payload-template.json)
6. Validate the required and optional fields using:
   [field-contract.md](./references/field-contract.md)
7. If the request is a persistence handoff from `Weight Control Coach` and there is no read-only or dry-run override, run write mode directly.
8. Otherwise run:
   [upsert_weight_review.py](./scripts/upsert_weight_review.py)
9. Default to `--dry-run` unless the request is that explicit persistence handoff or the user explicitly asked to persist.

## Language Rule

- Persist the assessment markdown entirely in English.
- Translate Spanish source evidence and planning notes into natural English before writing.
- Keep original Spanish only for brief direct quotes when the exact wording matters.
- Do not mix English and Spanish headings, labels, or coaching interpretation in persisted markdown.

## Safety Rules

- Never write on an ambiguous request.
- Prefer explicit `review_date` and `season_id` when known.
- If the payload omits computed trend fields, infer them from the weight-control context for the same date.
- Return the resolved row and warnings after every run.

## Minimum Output

- Action performed
- Resolved identifiers
- Stored fields
- Markdown logbook path
- Warnings
