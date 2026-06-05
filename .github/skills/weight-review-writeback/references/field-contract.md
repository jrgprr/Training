# Field Contract

The writeback payload is a JSON object.

## Required

- `review_date`: ISO date string

## Optional Identifiers

- `season_id`
- `block_id`
- `week_id`

## Optional Weight Fields

- `weight_kg`
- `weight_7d_avg_kg`
- `delta_7d_avg_kg`
- `weight_14d_avg_kg`
- `delta_14d_avg_kg`
- `volatility_7d_kg`
- `gap_to_target_kg`

## Optional Review Fields

- `classification`
- `recommendation_text`
- `summary_text`

## Optional Markdown Field

- `detailed_assessment_markdown`

If present, this text becomes the primary markdown document body for the logbook entry.
The structured review fields are then written as an appendix snapshot below it.
If omitted, the script still writes a markdown file using the structured review fields alone.

At least one optional review field must be present for a writeback to be valid.

## Inference Rules

- `season_id`: infer from `review_date` if omitted.
- `week_id` and `block_id`: infer from the week that contains `review_date` if omitted.
- trend fields: infer from the weight-control context for the same `review_date` when omitted.

## Conflict Rule

The script writes with the unique key:

- `season_id`
- `review_date`

If a row already exists for that key, the script updates it.

## Dry-Run Rule

- `--dry-run`: validate and resolve the row without changing the database.
- `--write`: perform the upsert.