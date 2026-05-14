# Contract: Garmin Import API Reliability Surface

## Scope

This feature keeps the existing endpoints and enriches their payloads so operators can diagnose failures and retry safely without moving Garmin logic into the GUI.

## Endpoints

### `GET /api/imports/garmin-connect/status`

- Purpose: return Garmin configuration readiness.
- Change: no contract-breaking change required.

### `POST /api/imports/garmin-connect/preview`

- Purpose: preview counts before import.
- Change: no contract-breaking change required; notes may include clarified fetch warnings.

### `POST /api/imports/garmin-connect/run`

- Purpose: launch one manual import attempt.
- Request body:

```json
{
  "season_id": 2026,
  "date_from": "2026-05-04",
  "date_to": "2026-05-10",
  "include_daily_metrics": true
}
```

- Response shape additions to `import_job`:

```json
{
  "status": "ok",
  "counts": {
    "activities_detected": 12,
    "daily_metrics_detected": 7
  },
  "metadata": {
    "notes": ["..."]
  },
  "import_job": {
    "import_job_id": 42,
    "status": "completed|failed|partial_completed",
    "rows_detected": 19,
    "rows_loaded": 15,
    "failure_stage": null,
    "failure_class": null,
    "retry_suitability": "safe_to_retry",
    "partial_completion": false,
    "request_scope": {
      "season_id": 2026,
      "date_from": "2026-05-04",
      "date_to": "2026-05-10",
      "include_daily_metrics": true
    },
    "breakdown": {
      "activity_rows_detected": 12,
      "activity_rows_inserted": 10,
      "activity_rows_updated": 2,
      "activity_rows_skipped": 0,
      "daily_metric_rows_detected": 7,
      "daily_metric_rows_inserted": 3,
      "daily_metric_rows_updated": 0,
      "daily_metric_rows_skipped": 4
    },
    "notes": ["..."],
    "operator_detail": "..."
  }
}
```

### `GET /api/import-jobs`

- Purpose: list import history for operator review.
- Change: each listed job includes the same reliability fields needed by the existing Garmin history UI:
  - `status`
  - `failure_stage`
  - `failure_class`
  - `retry_suitability`
  - `partial_completion`
  - per-data-class `breakdown`
  - request scope fields

### `GET /api/import-jobs/{import_job_id}`

- Purpose: inspect one attempt in detail.
- Change: expose the full attempt record and staging-aware summary fields for backend/GUI diagnostics.

## Error semantics

- `400`: configuration/authentication issue or invalid request scope.
- `502`: Garmin transport/rate-limit issue.
- `5xx`: unexpected persistence/transaction failure after request acceptance.

The terminal import job row in SQLite remains the source of truth even when the HTTP response is an error.