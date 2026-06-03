# Field Contract

The writeback payload is a JSON object.

## Required

- `review_date`: ISO date string

## Optional Identifiers

- `season_id`
- `planned_session_id`
- `activity_id`
- `block_id`
- `week_id`

## Optional Review Fields

- `planned_summary`
- `actual_summary`
- `compliance_status`
- `general_feeling`
- `perceived_recovery`
- `motivation`
- `observations`
- `next_day_decision`

At least one optional review field must be present for a writeback to be valid.

## Inference Rules

- `season_id`: infer from `review_date` if omitted.
- `planned_session_id`: infer from `activity_id` through `link_plan_execution` if possible.
- `planned_session_id`: otherwise infer from the plan only when the target date has exactly one planned session.
- `week_id` and `block_id`: infer from the week that contains `review_date` if omitted.
- `planned_summary`: infer from the planned session text if omitted and a planned session resolves.

## Conflict Rule

The script writes with the unique key:

- `season_id`
- `review_date`
- `planned_session_id`

If a row already exists for that key, the script updates it.

## Dry-Run Rule

- `--dry-run`: validate and resolve the row without changing the database.
- `--write`: perform the upsert.
