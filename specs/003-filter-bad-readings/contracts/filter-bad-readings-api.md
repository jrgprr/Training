# Contract: Filter Bad Readings API Surface

## Scope

This feature extends the existing Garmin import and activity review surfaces so the backend can persist and expose deterministic bad-reading outcomes. SQLite remains the canonical runtime source of truth; the frontend only renders backend-derived status and traceability.

## Endpoints

### `POST /api/imports/garmin-connect/run`

- Purpose: run the existing Garmin import flow, now including raw-reading persistence, deterministic quality evaluation, and trusted-summary recomputation.
- Request body: unchanged.

```json
{
  "season_id": 2026,
  "date_from": "2026-05-04",
  "date_to": "2026-05-10",
  "include_daily_metrics": true
}
```

- Response additions:

```json
{
  "status": "ok",
  "counts": {
    "activities_detected": 8,
    "daily_metrics_detected": 7,
    "quality_activities_checked": 6,
    "quality_activities_with_exclusions": 1,
    "quality_runs_created": 2,
    "quality_runs_reused": 4,
    "quality_decisions_recorded": 4,
    "quality_limited_metrics": 1
  },
  "metadata": {
    "notes": ["Importacion Garmin completada."],
    "quality_summary": {
      "clean_activities": 4,
      "filtered_activities": 1,
      "limited_activities": 1,
      "rule_version": "bad_reading_filter/v1"
    }
  },
  "import_job": {
    "import_job_id": 104,
    "status": "completed",
    "rows_detected": 15,
    "rows_loaded": 15,
    "retry_suitability": "safe_to_retry"
  }
}
```

### `GET /api/seasons/{season_id}/activities`

- Purpose: return the existing activity list with explicit activity-level quality state.
- Response additions for each item:

```json
{
  "activity_id": 440,
  "activity_date": "2026-05-19",
  "activity_type": "Salida larga",
  "avg_hr": 149.8,
  "max_hr": 178.0,
  "quality_status": "filtered",
  "quality_checked_at": "2026-05-27T18:34:12Z",
  "quality_rule_version": "bad_reading_filter/v1",
  "quality_decision_count": 1,
  "quality_limited_metric_count": 0
}
```

### `GET /api/activities/{activity_id}`

- Purpose: return the existing activity detail surface with trusted summary values plus quality metadata.
- Response additions:

```json
{
  "activity_id": 440,
  "source_system": "garmin",
  "activity_date": "2026-05-19",
  "avg_hr": 149.8,
  "max_hr": 178.0,
  "avg_power": 286.0,
  "quality_status": "filtered",
  "quality_checked_at": "2026-05-27T18:34:12Z",
  "quality_rule_version": "bad_reading_filter/v1",
  "quality_decision_count": 1,
  "quality_limited_metric_count": 0
}
```

### `GET /api/activities/{activity_id}/quality`

- Purpose: return detailed quality traceability for one activity.
- Response:

```json
{
  "activity": {
    "activity_id": 440,
    "external_activity_id": "12345678901",
    "activity_date": "2026-05-19",
    "quality_status": "filtered",
    "quality_checked_at": "2026-05-27T18:34:12Z",
    "quality_rule_version": "bad_reading_filter/v1",
    "source_reading_fingerprint": "hr:9f1de1d4"
  },
  "metrics": [
    {
      "metric_name": "heart_rate",
      "metric_status": "filtered",
      "evaluated_reading_count": 458,
      "accepted_reading_count": 457,
      "excluded_reading_count": 1,
      "summary_impacts": [
        {
          "summary_kind": "average",
          "source_value": 151.3,
          "trusted_value": 149.8,
          "changed_by_filter": true,
          "summary_status": "filtered"
        },
        {
          "summary_kind": "maximum",
          "source_value": 242.0,
          "trusted_value": 178.0,
          "changed_by_filter": true,
          "summary_status": "filtered"
        }
      ],
      "decisions": [
        {
          "quality_decision_id": 901,
          "decision_status": "excluded",
          "start_sample_index": 312,
          "end_sample_index": 312,
          "reason_code": "hr_above_hard_cap",
          "rule_key": "hr_absolute_ceiling",
          "threshold_high": 235.0,
          "impacted_summary_kinds": ["average", "maximum"]
        }
      ]
    }
  ]
}
```

### `POST /api/activities/{activity_id}/quality/replay`

- Purpose: re-evaluate one already imported activity from canonical raw readings or stored source artifacts without requiring a fresh live Garmin fetch.
- Request body:

```json
{
  "source_mode": "artifact"
}
```

- Supported `source_mode` values:
  - `canonical`: rebuild quality outcomes from persisted rows in `exec_activity_metric_readings`.
  - `artifact`: fall back to the stored `raw_payload_path` artifact when canonical rows are missing.

- Response:

```json
{
  "activity_id": 440,
  "quality_status": "filtered",
  "quality_rule_version": "bad_reading_filter/v1",
  "source_reading_fingerprint": "hr:9f1de1d4",
  "result": "reused_existing_run"
}
```

## Behavior Rules

- Trusted summary fields returned from activity endpoints come from accepted readings only for metrics evaluated by the active rule set.
- Raw readings remain preserved in SQLite and are never overwritten or deleted by filtering decisions.
- Quality runs are stable only when both `quality_rule_version` and `source_reading_fingerprint` are unchanged.
- If filtering leaves too little trustworthy evidence for a metric, the activity-quality detail returns `metric_status = "quality_limited"` and the affected summary entry returns `trusted_value = null`.
- Activity list and detail responses expose quality status but do not embed full reading-level traceability; detailed traceability is isolated to `GET /api/activities/{activity_id}/quality`.
- Replay must be able to reuse an existing canonical quality run for unchanged evidence or create a new run when canonical source readings change under the same rule version.
- Replay with `source_mode = "artifact"` must evaluate from the stored artifact path when canonical raw-reading rows are unavailable.
- The frontend must render backend-provided labels and traceability details rather than recomputing rule outcomes locally.

## Error Semantics

- `400`: invalid season id, invalid activity id, unsupported query parameters, or invalid limit values.
- `404`: requested activity or quality detail not found in canonical SQLite state.
- `409`: replay requested for an activity that cannot be evaluated because canonical readings and stored artifacts are both unavailable.
- `502`: Garmin fetch failure before canonical writes complete.
- `5xx`: unexpected backend, normalization, or persistence failure.