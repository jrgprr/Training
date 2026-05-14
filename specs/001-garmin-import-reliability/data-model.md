# Data Model: Garmin Import Reliability

## 1. GarminImportAttempt

- Purpose: Canonical record of one execution of the Garmin import flow for a given request scope.
- Storage: `meta_import_jobs` (expanded).

### Core fields

- `import_job_id`: integer primary key.
- `season_id`: target season.
- `source_system`: expected value `garmin`.
- `import_type`: expected value `garminconnect`.
- `source_path`: legacy textual scope reference; retained for compatibility.
- `request_date_from`: requested lower date bound.
- `request_date_to`: requested upper date bound.
- `include_daily_metrics`: boolean-like flag for request scope.
- `started_at`: timestamp when the attempt is opened.
- `finished_at`: timestamp when the attempt reaches a terminal state.
- `status`: one of `running`, `completed`, `failed`, `partial_completed`.
- `failure_stage`: nullable enum such as `configuration`, `fetch`, `normalize`, `persist`.
- `failure_class`: nullable enum with values `configuration_authentication`, `transport_rate_limit`, `source_data_normalization`, `persistence_transaction`.
- `retry_suitability`: `safe_to_retry` or `inspect_before_retry`.
- `rows_detected`: total rows detected across all data classes.
- `rows_loaded`: total canonical rows inserted or updated.
- `partial_completion`: boolean-like indicator for mixed outcomes.
- `operator_detail`: short operator-readable failure or outcome summary.
- `notes`: JSON or text field retained for supplemental messages.

### Per-data-class breakdown fields

- `activity_rows_detected`
- `activity_rows_inserted`
- `activity_rows_updated`
- `activity_rows_skipped`
- `daily_metric_rows_detected`
- `daily_metric_rows_inserted`
- `daily_metric_rows_updated`
- `daily_metric_rows_skipped`

### State transitions

- `running -> completed`
- `running -> failed`
- `running -> partial_completed`

No terminal state may transition back to `running` or overwrite a previous attempt; retries create a new row.

## 2. StagedGarminActivity

- Purpose: Persist fetched and normalized Garmin activity evidence associated with one import attempt.
- Storage: existing `staging_garmin_activities`.
- Relationship: many staged activity rows to one `GarminImportAttempt` via `import_job_id`.
- Key identifying field: `external_activity_id` from Garmin.

## 3. StagedGarminDailyMetric

- Purpose: Persist fetched and normalized Garmin daily metrics associated with one import attempt.
- Storage: existing `staging_garmin_daily_metrics`.
- Relationship: many staged daily metric rows to one `GarminImportAttempt` via `import_job_id`.
- Key identifying field: `season_id + metric_date + source_system`.

## 4. CanonicalActivity

- Purpose: Final canonical imported activity stored in SQLite.
- Storage: existing `exec_activities`.
- Idempotency rule: unique by `source_system + external_activity_id`.

## 5. CanonicalDailyMetric

- Purpose: Final canonical imported daily metric stored in SQLite.
- Storage: existing `exec_daily_metrics`.
- Idempotency rule: unique by `season_id + metric_date + source_system`.

## 6. RetrySuitability

- Purpose: Backend-derived operational guidance for rerun behavior.
- Values:
  - `safe_to_retry`: failures or zero-result outcomes that did not leave ambiguous canonical side effects.
  - `inspect_before_retry`: partial completion, normalization failure, or persistence failure that may require operator review before rerun.

## 7. FailureClassification

- Purpose: Durable operational categorization of a failed attempt.
- Values:
  - `configuration_authentication`
  - `transport_rate_limit`
  - `source_data_normalization`
  - `persistence_transaction`