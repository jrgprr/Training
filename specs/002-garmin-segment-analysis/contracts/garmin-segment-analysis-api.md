# Contract: Garmin Segment Analysis API Surface

## Scope

This feature extends the existing Garmin import flow and adds a minimal backend-driven read surface for segment review. The frontend consumes backend-computed summaries and does not derive Garmin segment analysis on its own.

## Endpoints

### `POST /api/imports/garmin-connect/run`

- Purpose: launch a manual Garmin import that now also checks cycling activities for segment data.
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
    "activities_detected": 12,
    "daily_metrics_detected": 7,
    "segment_activities_checked": 5,
    "segment_activities_with_data": 4,
    "segment_efforts_detected": 18,
    "segment_efforts_loaded": 18
  },
  "metadata": {
    "notes": ["..."],
    "segment_summary": {
      "activities_with_segment_data": 4,
      "activities_without_segment_data": 1
    }
  },
  "import_job": {
    "import_job_id": 84,
    "status": "completed",
    "rows_detected": 37,
    "rows_loaded": 37,
    "retry_suitability": "safe_to_retry"
  }
}
```

### `GET /api/segments?season_id=2026&query=&limit=50`

- Purpose: return the minimal list surface for segment review.
- Response:

```json
{
  "items": [
    {
      "segment_id": 301,
      "source_system": "garmin",
      "external_segment_id": "987654321",
      "segment_name": "Subida del puerto",
      "discipline": "cycling",
      "effort_count": 6,
      "comparable_effort_count": 5,
      "first_activity_date": "2026-05-01",
      "last_activity_date": "2026-05-19",
      "best_elapsed_time_seconds": 412,
      "latest_elapsed_time_seconds": 426,
      "missing_metric_counts": {
        "avg_power": 1,
        "avg_cadence": 0,
        "avg_heart_rate": 2
      }
    }
  ]
}
```

### `GET /api/segments/{segment_id}/history?limit=20`

- Purpose: return one segment's ordered effort history and backend-derived evolution summary.
- Response:

```json
{
  "segment": {
    "segment_id": 301,
    "source_system": "garmin",
    "external_segment_id": "987654321",
    "segment_name": "Subida del puerto",
    "discipline": "cycling",
    "distance_meters": 1450.0,
    "ascent_meters": 121.0,
    "average_grade_percent": 8.3
  },
  "summary": {
    "effort_count": 6,
    "comparable_effort_count": 5,
    "membership_only_count": 1,
    "best_effort_id": 9001,
    "latest_effort_id": 9018,
    "trend_status": "stable",
    "recent_window_size": 3,
    "available_metric_names": ["elapsed_time_seconds", "avg_power", "avg_cadence"],
    "missing_metric_names": ["avg_heart_rate", "max_heart_rate"]
  },
  "efforts": [
    {
      "segment_effort_id": 9018,
      "activity_id": 440,
      "external_activity_id": "12345678901",
      "activity_date": "2026-05-19",
      "started_at": "2026-05-19T17:42:00+00:00",
      "elapsed_time_seconds": 426,
      "avg_power": 311.0,
      "avg_cadence": 82.0,
      "avg_heart_rate": null,
      "max_heart_rate": null,
      "notes": "reconstructed_from_activity_detail_stream",
      "missing_metrics": ["avg_heart_rate", "max_heart_rate"],
      "is_best_effort": false,
      "is_latest_effort": true,
      "delta_vs_best_seconds": 14,
      "delta_vs_previous_seconds": 3
    }
  ]
}
```

## Behavior Rules

- Only Garmin activity segments marked as favorite are in scope for persistence in this version.
- The history endpoint always returns efforts in chronological order suitable for review.
- Single-effort segments return `trend_status = "insufficient_data"`.
- Missing metrics are explicit in every effort row and in the summary block.
- Membership-only rows may have `elapsed_time_seconds = null` and remain visible with explicit missing metrics.
- The frontend must render backend-provided summary state rather than recalculate trend logic locally.

## Error Semantics

- `400`: invalid season, invalid segment id, or unsupported query parameters.
- `404`: segment id not found in canonical SQLite state.
- `502`: Garmin import fetch failure before canonical writes complete.
- `5xx`: unexpected backend or persistence failure.

The canonical source of truth for runtime behavior remains SQLite, not the API payloads themselves.