# Data Model: Garmin Segment Analysis

## 1. CanonicalActivity Extension

- Purpose: Preserve explicit segment-import outcome for each canonical imported activity.
- Storage: existing `exec_activities`.

### New fields

- `segment_data_status`: enum-like text with values:
  - `not_checked`: legacy activity or import path that has not evaluated segment payloads yet.
  - `available`: segment payload was checked and at least one segment effort was persisted.
  - `not_available`: segment payload was checked for an in-scope cycling activity and no segment efforts were available.
  - `not_applicable`: activity is outside the cycling Garmin segment scope.
- `segment_effort_count`: integer count of canonical efforts associated with the activity after the import transaction.
- `segment_checked_at`: timestamp of the last segment-evaluation pass for that activity.

### Notes

- Existing activity idempotency remains `UNIQUE (source_system, external_activity_id)`.
- `segment_data_status` removes ambiguity for FR-016 without requiring synthetic effort rows.

## 2. SegmentDefinition

- Purpose: Canonical record of one Garmin segment identity that may recur across multiple imported activities.
- Proposed storage: new table `exec_segments`.

### Core fields

- `segment_id`: integer primary key.
- `source_system`: expected value `garmin`.
- `external_segment_id`: Garmin segment identity, unique within `source_system`.
- `segment_name`: Garmin display name.
- `discipline`: normalized discipline, constrained to cycling scope for this feature.
- `distance_meters`: nullable stable segment fact.
- `ascent_meters`: nullable stable segment fact.
- `average_grade_percent`: nullable stable segment fact.
- `first_seen_activity_id`: nullable foreign key to the first activity that exposed the segment.
- `last_seen_activity_id`: nullable foreign key to the most recent activity that exposed the segment.
- `created_at`, `updated_at`: timestamps for auditability.

### Constraints

- `UNIQUE (source_system, external_segment_id)`.
- Segment definitions are never deduplicated by display name alone.

## 3. SegmentEffort

- Purpose: Canonical record of one athlete attempt on a specific segment within a specific imported activity.
- Proposed storage: new table `exec_segment_efforts`.

### Core fields

- `segment_effort_id`: integer primary key.
- `source_system`: expected value `garmin`.
- `external_segment_effort_id`: Garmin effort identity used for idempotent re-import.
- `segment_id`: foreign key to `exec_segments.segment_id`.
- `activity_id`: foreign key to `exec_activities.activity_id`.
- `activity_date`: denormalized ISO date for efficient ordering and filtering.
- `started_at`: nullable timestamp for effort context.
- `elapsed_time_seconds`: nullable canonical performance outcome; required only when Garmin exposes or the backend reconstructs a comparable effort.
- `avg_power`: nullable.
- `avg_cadence`: nullable.
- `avg_heart_rate`: nullable.
- `max_heart_rate`: nullable.
- `notes`: nullable traceability/debug text, including provenance such as `reconstructed_from_activity_detail_stream` when metrics are approximated.
- `created_at`, `updated_at`: timestamps.

### Constraints

- `UNIQUE (source_system, external_segment_effort_id)`.
- `UNIQUE (activity_id, segment_id, external_segment_effort_id)` is redundant but can be enforced logically through the primary uniqueness rule.
- Every effort must belong to exactly one canonical activity and one canonical segment.
- A membership-only row is valid when `elapsed_time_seconds` is null and supporting metrics are absent.

## 4. SegmentHistoryRow

- Purpose: Ordered read model row used to review one segment across time.
- Storage: derived from `exec_segment_efforts` joined with `exec_segments` and `exec_activities`; not persisted as a separate canonical table in the first version.

### Derived fields

- `segment_id`
- `segment_name`
- `activity_id`
- `activity_date`
- `external_activity_id`
- `elapsed_time_seconds`
- `started_at`
- `avg_power`
- `avg_cadence`
- `avg_heart_rate`
- `max_heart_rate`
- `notes`
- `missing_metrics`: list of metric identifiers missing for that effort
- `is_best_effort`: boolean
- `is_latest_effort`: boolean
- `delta_vs_best_seconds`: nullable numeric
- `delta_vs_previous_seconds`: nullable numeric

## 5. SegmentAnalysisSummary

- Purpose: Backend-computed summary for the minimal GUI detail surface.
- Storage: derived response object, not a persisted canonical table.

### Fields

- `segment_id`
- `effort_count`
- `comparable_effort_count`
- `membership_only_count`
- `best_effort_id`
- `latest_effort_id`
- `trend_status`: `insufficient_data`, `improving`, `stable`, or `declining`
- `recent_window_size`: integer count of efforts used for recent comparison
- `available_metric_names`: metrics with enough data to compare meaningfully
- `missing_metric_names`: metrics absent from one or more displayed efforts

### Rules

- Single-effort segments always return `trend_status = insufficient_data`.
- Trend summaries never overwrite or mutate canonical effort rows.

## 6. ImportTraceability Extension

- Purpose: Keep Garmin import jobs informative when segment checks occur.
- Storage: existing `meta_import_jobs`, potentially enriched with segment counts or notes.

### Implemented additions

- `segment_activities_checked`
- `segment_activities_with_data`
- `segment_efforts_detected`
- `segment_efforts_inserted`
- `segment_efforts_updated`
- `segment_efforts_skipped`

### Notes

- These fields are operational metadata only. SQLite tables for segment definitions and efforts remain the canonical source for runtime analysis.
- Re-import treats the activity's segment slice as authoritative and prunes stale `exec_segment_efforts` rows for that activity when the current normalized set is smaller than a previous import.

## State Transitions

### CanonicalActivity.segment_data_status

- `not_checked -> available`
- `not_checked -> not_available`
- `not_checked -> not_applicable`
- `available -> available`
- `available -> not_available`
- `not_available -> not_available`

Repeated imports may update `segment_effort_count` and `segment_checked_at`, but they must not create duplicate segment or effort rows and must remove previously persisted rows that are no longer in scope for the activity.