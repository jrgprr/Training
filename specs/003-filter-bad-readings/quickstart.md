# Quickstart: Filter Bad Readings

## Goal

Validate that imported activities persist canonical raw metric readings in SQLite, deterministic bad-reading decisions exclude implausible samples from trusted summaries, activity-level quality status plus traceability are available through the backend and thin GUI surface, and already imported activities can be re-evaluated without requiring a fresh Garmin fetch.

## Prerequisites

- Garmin Connect local configuration available through the existing GUI/backend flow.
- At least one activity or test fixture with a known implausible heart-rate spike and one clean comparison activity.
- SQLite initialized through backend startup.

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
  tests.test_activity_quality
```

Expected outcome:
- Import CLI and API behavior still pass.
- New quality tests confirm raw-reading persistence, deterministic exclusion, idempotent re-import, artifact replay/backfill, and summary withholding when too much evidence is removed.

## 3. Run frontend validation

```bash
cd /home/jparra/Training/GUI/frontend
npm run build
```

Expected outcome:
- The GUI compiles with activity-level quality status and detail traceability rendering driven entirely by backend payloads.

## 4. Execute a manual Garmin import with bad-reading detection enabled

1. Open the GUI at `http://127.0.0.1:5173`.
2. Select season `2026`.
3. Preview and run a Garmin import for a date range known to include an activity with an implausible heart-rate spike.
4. Repeat the same import once more without changing the source activity.

Expected outcome:
- The import succeeds without duplicating raw-reading rows, quality runs, or quality decisions.
- Trusted summaries in `exec_activities` exclude the implausible reading from affected metrics.
- Clean activities return explicit `clean` status instead of ambiguous silence.

## 5. Replay quality evaluation for already imported activities

```bash
curl -s -X POST http://127.0.0.1:8000/api/activities/ACTIVITY_ID/quality/replay \
  -H 'Content-Type: application/json' \
  -d '{"source_mode":"artifact"}' | jq

curl -s -X POST http://127.0.0.1:8000/api/activities/ACTIVITY_ID/quality/replay \
  -H 'Content-Type: application/json' \
  -d '{"source_mode":"artifact"}' | jq
```

Expected outcome:
- The first replay evaluates the activity from canonical raw readings or, when those are missing, from the stored artifact without requiring a new live Garmin fetch.
- The second replay resolves to the same source-evidence fingerprint and returns `result = "reused_existing_run"` when the evidence is unchanged.

## 6. Inspect canonical SQLite state

```bash
sqlite3 /home/jparra/Training/Sistema/training.sqlite <<'SQL'
SELECT activity_id,
       quality_status,
       quality_rule_version,
      quality_checked_at,
       quality_decision_count,
       quality_limited_metric_count
FROM exec_activities
WHERE source_system = 'garmin'
ORDER BY activity_date DESC, COALESCE(started_at, activity_date) DESC
LIMIT 10;

SELECT activity_id,
       rule_set_version,
       source_reading_fingerprint,
       excluded_reading_count,
       limited_metric_count
FROM exec_activity_quality_runs
ORDER BY activity_id DESC, quality_run_id DESC;

SELECT activity_id,
       metric_name,
       COUNT(*) AS reading_count,
       MIN(raw_value) AS min_value,
       MAX(raw_value) AS max_value
FROM exec_activity_metric_readings
GROUP BY activity_id, metric_name
ORDER BY activity_id DESC, metric_name;

SELECT activity_id,
       metric_name,
       summary_kind,
       source_value,
       trusted_value,
       summary_status,
       excluded_reading_count
FROM exec_activity_metric_summaries
ORDER BY activity_id DESC, metric_name, summary_kind;

SELECT activity_id,
       metric_name,
       start_sample_index,
       end_sample_index,
       reason_code,
       impacted_summary_kinds
FROM exec_activity_quality_decisions
ORDER BY activity_id DESC, metric_name, start_sample_index;
SQL
```

Expected outcome:
- Canonical activity rows show explicit quality status and rule version.
- Quality runs remain stable for unchanged evidence and create new rows only when the source-evidence fingerprint or rule version changes.
- Raw-reading rows exist for evaluated metrics.
- Source and trusted summary values differ only for metrics affected by filtering.
- Each exclusion remains traceable to a metric, position, and reason.

## 7. Review quality status and traceability through the API or GUI

```bash
curl -s http://127.0.0.1:8000/api/seasons/2026/activities | jq '.[0]'
curl -s http://127.0.0.1:8000/api/activities/ACTIVITY_ID/quality | jq
```

Expected outcome:
- Activity list payloads expose `quality_status`, `quality_checked_at`, `quality_rule_version`, `quality_decision_count`, and `quality_limited_metric_count`.
- Activity quality detail shows per-metric summary deltas, excluded reading ranges, and reasons without requiring frontend recalculation.