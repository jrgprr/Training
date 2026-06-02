# Quickstart: Training Zones

## Goal

Validate that the system can persist accepted heart-rate and power zone profiles in SQLite, calculate executed time-in-zone from real Garmin activities, generate traceable refinement proposals using recent activity evidence plus daily metrics, and expose thin backend-driven plan-versus-executed zone summaries in the GUI.

## Prerequisites

- Local Garmin-enabled stack available through the existing GUI/backend flow.
- SQLite initialized through backend startup.
- A date range containing cycling activities with usable heart-rate data and at least some activities with usable power data.
- At least one planned week containing explicit or mappable zone language such as `Z2`, `tempo`, or `threshold`.

## 1. Start the local stack

```bash
source /home/jparra/Training/.venv/bin/activate
bash /home/jparra/Training/GUI/dev-with-garmin.sh
```

Expected outcome:
- FastAPI backend available at `http://127.0.0.1:8000`
- Vite frontend available at `http://127.0.0.1:5173`

## 2. Run focused backend validation

```bash
cd /home/jparra/Training/GUI/backend
python -m unittest \
  tests.test_garmin_connect_cli \
  tests.test_training_zones
```

Expected outcome:
- Existing Garmin import behavior still passes.
- Training-zones tests confirm accepted profile lookup, heart-rate and power bucket calculation, deterministic persistence, refinement proposal generation, and explicit limited/unavailable outcomes.

## 3. Run frontend validation

```bash
cd /home/jparra/Training/GUI/frontend
npm run build
```

Expected outcome:
- The GUI compiles with backend-driven zone summaries, proposal states, and plan-versus-executed comparison payloads.

## 4. Execute a manual Garmin import covering zone-relevant activities

1. Open the GUI at `http://127.0.0.1:5173`.
2. Select season `2026`.
3. Preview and run a Garmin import for a date range known to contain cycling activities with heart rate and power.
4. Repeat the same import once more to confirm idempotent zone-result persistence.

Expected outcome:
- The import succeeds without duplicating canonical executed zone rows or bucket rows.
- Eligible activities persist heart-rate zone results, power zone results, or both.
- Activities lacking enough evidence for one basis return explicit `limited` or `unavailable` status for that basis.

### Optional CLI validation path

```bash
cd /home/jparra/Training/GUI/backend
source /home/jparra/Training/.venv/bin/activate
set -a && source /home/jparra/Training/GUI/.env.garmin.local && set +a
PYTHONPATH=. python -m app.imports.garmin_connect \
  --season 2026 \
  --from 2026-05-01 \
  --to 2026-06-01 \
  --apply
```

Expected outcome:
- The import reports activity and daily-metric counts.
- Zone calculation runs on imported activities without requiring any cloud service.

## 5. Inspect canonical SQLite state

```bash
sqlite3 /home/jparra/Training/Sistema/training.sqlite <<'SQL'
SELECT zone_profile_id,
       discipline,
       metric_basis,
       governance_status,
       effective_start_date,
       effective_end_date
FROM zone_profiles
ORDER BY metric_basis, effective_start_date;

SELECT activity_id,
       metric_basis,
       calculation_status,
       zone_profile_id,
       dominant_zone_code,
       total_supported_seconds
FROM exec_activity_zone_results
ORDER BY activity_id DESC, metric_basis;

SELECT r.activity_id,
       r.metric_basis,
       b.zone_code,
       b.seconds_in_zone,
       ROUND(b.share_in_zone, 3) AS share_in_zone
FROM exec_activity_zone_results r
JOIN exec_activity_zone_buckets b
  ON b.activity_zone_result_id = r.activity_zone_result_id
ORDER BY r.activity_id DESC, r.metric_basis, b.zone_index;

SELECT proposal_id,
       discipline,
       metric_basis,
       proposal_status,
       confidence_level,
       recommendation_kind,
       created_at
FROM zone_refinement_proposals
ORDER BY proposal_id DESC;

SELECT planned_session_id,
       target_basis,
       target_kind,
       comparison_eligibility,
       source_kind
FROM plan_session_zone_targets
ORDER BY planned_session_id DESC;
SQL
```

Expected outcome:
- Accepted heart-rate and power profiles exist in `zone_profiles`.
- Executed activity zone results are persisted per basis in `exec_activity_zone_results`.
- Bucket rows in `exec_activity_zone_buckets` reflect the stored dominant and supporting zones.
- Refinement proposals, when present, are explicit and separate from accepted profiles.
- Structured planned zone targets exist only for sessions with explicit or approved-mapped zone intent.

## 6. Inspect zone state through the API

```bash
curl -s http://127.0.0.1:8000/api/seasons/2026/zone-profiles/current?discipline=cycling | jq
curl -s http://127.0.0.1:8000/api/seasons/2026/zone-proposals?discipline=cycling | jq
curl -s http://127.0.0.1:8000/api/activities/ACTIVITY_ID/zones | jq
curl -s http://127.0.0.1:8000/api/weeks/WEEK_ID/plan-vs-real | jq
```

Expected outcome:
- Current accepted profiles are returned independently for `heart_rate` and `power`.
- Proposal payloads include confidence, limiting factors, and explicit evidence references.
- Activity zone detail returns basis-specific buckets and limitation state without frontend recomputation.
- Week comparison payloads expose planned-versus-executed zone summaries only where comparison is meaningful.

## 7. Review the thin GUI surface

1. Open the existing GUI at `http://127.0.0.1:5173`.
2. Navigate to a week containing a zone-based planned session and at least one matched cycling activity.
3. Open an activity detail with both heart-rate and power support.
4. Review any pending zone proposal if one exists.

Expected outcome:
- The GUI shows current accepted HR and power zone information without implementing zone logic in React.
- Activity detail exposes separate heart-rate and power executed-zone summaries.
- Week review exposes zone comparison as a secondary plan-versus-reality layer.
- Proposal states are readable and traceable, including low-confidence or deferred outcomes.

## 8. Validate proposal acceptance behavior

```bash
curl -s -X POST http://127.0.0.1:8000/api/zone-proposals/PROPOSAL_ID/accept \
  -H 'Content-Type: application/json' \
  -d '{"effective_start_date":"2026-06-08","decision_notes":"Manual acceptance during quickstart validation."}' | jq
```

Expected outcome:
- The proposal transitions from `pending` to `accepted`.
- A new accepted profile version is created instead of mutating the prior one.
- Historical executed zone rows remain traceable to the prior profile version they used at calculation time.