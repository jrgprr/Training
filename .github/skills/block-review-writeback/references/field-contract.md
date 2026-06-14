# Field Contract

The writeback payload is a JSON object.

## Required

- `block_id`: integer block id

## Optional Identifiers

- `season_id`

## Optional Review Fields

- `summary_text`
- `recommendation_text`
- `risk_level`

## Optional Markdown Field

- `detailed_assessment_markdown`

If present, this text becomes the primary markdown document body for the block logbook entry.
The structured review fields are then written as an appendix snapshot below it.
If omitted, the script still writes a markdown file using the structured review fields alone.

At least one optional review field must be present for a writeback to be valid.
