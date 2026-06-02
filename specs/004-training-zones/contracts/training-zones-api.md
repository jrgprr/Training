# Contract: Training Zones API Surface

## Scope

This feature extends the existing local FastAPI surface so the backend can own dual-basis zone profiles, executed time-in-zone distributions, refinement proposals, and secondary planned-versus-executed comparison. SQLite remains the canonical runtime source of truth; the frontend only renders backend-provided zone facts and statuses.

## Endpoints

### `POST /api/imports/garmin-connect/run`

- Purpose: run the existing Garmin import flow, now also calculating or refreshing executed heart-rate and power zone distributions for eligible activities.
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
    "zone_activities_checked": 6,
    "zone_results_created": 8,
    "zone_results_reused": 4,
    "zone_results_limited": 2,
    "zone_profiles_applied": 2
  },
  "metadata": {
    "notes": ["Importacion Garmin completada."],
    "zone_summary": {
      "heart_rate_results": 6,
      "power_results": 4,
      "limited_results": 2
    }
  },
  "import_job": {
    "import_job_id": 128,
    "status": "completed",
    "rows_detected": 15,
    "rows_loaded": 15,
    "retry_suitability": "safe_to_retry"
  }
}
```

### `GET /api/seasons/{season_id}/activities`

- Purpose: return the existing season activity list with a compact zone summary for each activity.
- Response additions for each item:

```json
{
  "activity_id": 440,
  "activity_date": "2026-05-19",
  "discipline": "cycling",
  "avg_hr": 149.8,
  "avg_power": 286.0,
  "zone_summary": {
    "heart_rate": {
      "calculation_status": "calculated",
      "dominant_zone_code": "Z2",
      "dominant_zone_share": 0.61,
      "zone_profile_id": 12
    },
    "power": {
      "calculation_status": "limited",
      "dominant_zone_code": null,
      "dominant_zone_share": null,
      "zone_profile_id": 8,
      "limiting_reasons": ["insufficient_power_samples"]
    }
  }
}
```

### `GET /api/activities/{activity_id}`

- Purpose: return the existing activity detail with compact zone metadata for both mandatory bases.
- Response additions:

```json
{
  "activity_id": 440,
  "activity_date": "2026-05-19",
  "discipline": "cycling",
  "quality_status": "filtered",
  "zone_summary": {
    "heart_rate": {
      "calculation_status": "calculated",
      "zone_profile_id": 12,
      "dominant_zone_code": "Z2",
      "dominant_zone_share": 0.61,
      "total_supported_seconds": 4620
    },
    "power": {
      "calculation_status": "calculated",
      "zone_profile_id": 8,
      "dominant_zone_code": "Z3",
      "dominant_zone_share": 0.44,
      "total_supported_seconds": 4310
    }
  }
}
```

### `GET /api/activities/{activity_id}/zones`

- Purpose: return the basis-specific executed time-in-zone detail for one activity.
- Response:

```json
{
  "activity": {
    "activity_id": 440,
    "activity_date": "2026-05-19",
    "discipline": "cycling",
    "quality_status": "filtered"
  },
  "results": {
    "heart_rate": {
      "metric_basis": "heart_rate",
      "calculation_status": "calculated",
      "zone_profile_id": 12,
      "profile_label": "cycling hr v2",
      "quality_status_snapshot": "filtered",
      "total_supported_seconds": 4620,
      "supported_sample_count": 458,
      "dominant_zone_code": "Z2",
      "dominant_zone_share": 0.61,
      "buckets": [
        {
          "zone_index": 1,
          "zone_code": "Z1",
          "seconds_in_zone": 820,
          "share_in_zone": 0.18
        },
        {
          "zone_index": 2,
          "zone_code": "Z2",
          "seconds_in_zone": 2818,
          "share_in_zone": 0.61
        }
      ],
      "limiting_reasons": []
    },
    "power": {
      "metric_basis": "power",
      "calculation_status": "calculated",
      "zone_profile_id": 8,
      "profile_label": "cycling power v1",
      "quality_status_snapshot": "filtered",
      "total_supported_seconds": 4310,
      "supported_sample_count": 430,
      "dominant_zone_code": "Z3",
      "dominant_zone_share": 0.44,
      "buckets": [
        {
          "zone_index": 2,
          "zone_code": "Z2",
          "seconds_in_zone": 1330,
          "share_in_zone": 0.31
        },
        {
          "zone_index": 3,
          "zone_code": "Z3",
          "seconds_in_zone": 1896,
          "share_in_zone": 0.44
        }
      ],
      "limiting_reasons": []
    }
  }
}
```

### `GET /api/seasons/{season_id}/zone-profiles/current?discipline=cycling`

- Purpose: return the currently accepted heart-rate and power zone profiles for a discipline.
- Response:

```json
{
  "season_id": 2026,
  "discipline": "cycling",
  "profiles": {
    "heart_rate": {
      "zone_profile_id": 12,
      "profile_label": "cycling hr v2",
      "governance_status": "accepted",
      "effective_start_date": "2026-05-01",
      "accepted_at": "2026-06-01T08:15:00Z",
      "boundaries": [
        {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 118, "bound_unit": "bpm"},
        {"zone_code": "Z2", "lower_bound_value": 119, "upper_bound_value": 146, "bound_unit": "bpm"}
      ]
    },
    "power": {
      "zone_profile_id": 8,
      "profile_label": "cycling power v1",
      "governance_status": "accepted",
      "effective_start_date": "2026-05-01",
      "accepted_at": "2026-06-01T08:15:00Z",
      "boundaries": [
        {"zone_code": "Z1", "lower_bound_value": 0, "upper_bound_value": 145, "bound_unit": "watts"},
        {"zone_code": "Z2", "lower_bound_value": 146, "upper_bound_value": 198, "bound_unit": "watts"}
      ]
    }
  }
}
```

### `GET /api/seasons/{season_id}/zone-proposals?discipline=cycling`

- Purpose: list pending or recent refinement proposals for one season and discipline.
- Response:

```json
{
  "items": [
    {
      "proposal_id": 31,
      "discipline": "cycling",
      "metric_basis": "heart_rate",
      "proposal_status": "pending",
      "confidence_level": "medium",
      "recommendation_kind": "rebalance",
      "proposal_summary": "Recent aerobic rides suggest Z2 upper bound is slightly low.",
      "limiting_factors": ["elevated_stress_window", "two_incomplete_power_activities"],
      "source_zone_profile_id": 12,
      "proposed_effective_start_date": "2026-06-08",
      "created_at": "2026-06-01T09:20:00Z"
    }
  ]
}
```

### `GET /api/zone-proposals/{proposal_id}`

- Purpose: inspect one refinement proposal with evidence and proposed boundary deltas.
- Response:

```json
{
  "proposal": {
    "proposal_id": 31,
    "discipline": "cycling",
    "metric_basis": "heart_rate",
    "proposal_status": "pending",
    "confidence_level": "medium",
    "recommendation_kind": "rebalance",
    "proposal_summary": "Recent aerobic rides suggest Z2 upper bound is slightly low.",
    "limiting_factors": ["elevated_stress_window"]
  },
  "boundaries": [
    {
      "zone_code": "Z2",
      "proposed_lower_bound_value": 119,
      "proposed_upper_bound_value": 149,
      "delta_vs_current_lower": 0,
      "delta_vs_current_upper": 3,
      "bound_unit": "bpm"
    }
  ],
  "evidence": [
    {
      "evidence_type": "activity",
      "evidence_role": "supporting",
      "activity_id": 440,
      "evidence_date": "2026-05-19",
      "summary": {
        "dominant_zone_code": "Z2",
        "aerobic_decoupling_hint": "stable"
      }
    },
    {
      "evidence_type": "daily_metric",
      "evidence_role": "limiting",
      "evidence_date": "2026-05-28",
      "summary": {
        "stress_avg": 46,
        "sleep_hours": 5.2,
        "note": "reduced confidence"
      }
    }
  ]
}
```

### `POST /api/zone-proposals/{proposal_id}/accept`

- Purpose: explicitly accept a pending refinement proposal and create a new accepted profile version.
- Request body:

```json
{
  "effective_start_date": "2026-06-08",
  "decision_notes": "Accepted after review of last 4 cycling endurance sessions."
}
```

- Response:

```json
{
  "proposal_id": 31,
  "proposal_status": "accepted",
  "created_zone_profile_id": 13,
  "superseded_zone_profile_id": 12,
  "metric_basis": "heart_rate",
  "effective_start_date": "2026-06-08"
}
```

### `GET /api/weeks/{week_id}/sessions`

- Purpose: return the existing planned-session list with optional structured zone intent attached to sessions that have it.
- Response additions for each applicable item:

```json
{
  "planned_session_id": 902,
  "session_date": "2026-06-04",
  "planned_type": "bike",
  "primary_session": "Rodaje Z2 75'",
  "planned_zone_target": {
    "target_kind": "single_zone",
    "target_basis": "mixed",
    "comparison_eligibility": "eligible",
    "segments": [
      {
        "sequence_order": 1,
        "target_zone_min_code": "Z2",
        "target_zone_max_code": "Z2",
        "target_duration_seconds_min": 4500,
        "target_duration_seconds_max": 4500
      }
    ]
  }
}
```

### `GET /api/weeks/{week_id}/plan-vs-real`

- Purpose: extend the existing week comparison view with zone-specific comparison summaries.
- Response additions for each comparable row:

```json
{
  "planned_session_id": 902,
  "session_date": "2026-06-04",
  "matched_activity_id": 440,
  "zone_comparison": {
    "heart_rate": {
      "comparison_status": "aligned",
      "planned_zone_summary": "Z2",
      "executed_zone_summary": "61% in Z2",
      "limiting_reasons": []
    },
    "power": {
      "comparison_status": "partially_aligned",
      "planned_zone_summary": "Z2",
      "executed_zone_summary": "31% in Z2, 44% in Z3",
      "limiting_reasons": ["extended_climb_block"]
    }
  }
}
```

## Behavior Rules

- Heart-rate and power zone results are always represented separately when both exist.
- Zone calculation must inherit activity quality limitations and must not fabricate bucket rows when evidence is insufficient.
- Daily metrics may appear in proposal evidence and limiting factors, but they must not directly define zone boundaries in any response.
- Accepting a proposal creates a new accepted profile version; it does not mutate prior accepted profile rows.
- Planned zone targets remain optional and secondary; sessions without explicit or mappable zone intent must not receive invented structured zone targets.
- The frontend must render backend-provided comparison and proposal states rather than recalculating them locally.

## Error Semantics

- `400`: invalid season id, invalid week id, invalid activity id, unsupported basis or discipline, or invalid effective date.
- `404`: requested activity, week, current profile, or proposal not found in canonical SQLite state.
- `409`: proposal acceptance requested for a non-pending proposal or for a proposal whose source profile is no longer current under the requested governance rule.
- `422`: requested zone calculation or comparison cannot be produced because the activity or plan is outside the in-scope discipline or lacks required canonical evidence.
- `502`: Garmin import fetch failure before canonical writes complete.
- `5xx`: unexpected backend, calculation, governance, or persistence failure.