# Quickstart: Garmin Segment Analysis

## Goal

Validate that Garmin cycling imports persist canonical favorite-segment data in SQLite, reconstruct approximate metrics when Garmin omits native segment efforts, and let the GUI review backend-derived segment history without adding frontend domain logic.

## Prerequisites

- Garmin Connect backend configuration available through the existing local GUI flow.
- A date range containing at least one cycling activity with favorite segments and at least one repeated favorite segment across multiple activities.
- SQLite database initialized through the GUI backend startup.

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
  tests.test_garmin_segment_import
```

Expected outcome:
- Existing Garmin import tests still pass.
- New segment-ingestion tests confirm idempotent writes, explicit `segment_data_status`, and repeated-segment history ordering.

## 3. Run frontend validation

```bash
cd /home/jparra/Training/GUI/frontend
npm run build
```

Expected outcome:
- The GUI compiles with the new segment list/detail read surface and typed API responses.

## 4. Execute a manual Garmin import with cycling segment data

1. Open the GUI at `http://127.0.0.1:5173`.
2. Select season `2026`.
3. Preview and run a Garmin import for a cycling date range known to include favorite segments.
4. Repeat the same import once more to confirm idempotency.

Expected outcome:
- The import succeeds without duplicating canonical segment definitions or segment efforts.
- Only favorite-tagged Garmin activity segments persist to SQLite.
- Activities without favorite segment payloads are still imported with an explicit non-ambiguous segment availability state.

### Optional CLI validation path

```bash
cd /home/jparra/Training/GUI/backend
source /home/jparra/Training/.venv/bin/activate
set -a && source /home/jparra/Training/GUI/.env.garmin.local && set +a
PYTHONPATH=. python -m app.imports.garmin_connect \
  --season 2026 \
  --from 2026-04-27 \
  --to 2026-05-27 \
  --apply \
  --no-daily-metrics
```

Expected outcome:
- A completed import job reports segment counts for the checked month range.
- Live validation confirms only favorite segments are persisted for the imported activities.

## 5. Inspect canonical SQLite state

```bash
sqlite3 /home/jparra/Training/Sistema/training.sqlite <<'SQL'
SELECT source_system, external_segment_id, segment_name
FROM exec_segments
ORDER BY segment_name
LIMIT 10;

SELECT activity_id, external_activity_id, activity_date, segment_data_status, segment_effort_count
FROM exec_activities
WHERE source_system = 'garmin' AND discipline IN ('road_biking', 'indoor_cycling', 'mountain_biking')
ORDER BY activity_date DESC
LIMIT 10;

SELECT ea.activity_date,
       ea.external_activity_id,
       ea.segment_effort_count,
       GROUP_CONCAT(es.segment_name, ' | ') AS segment_names
FROM exec_activities ea
LEFT JOIN exec_segment_efforts ese ON ese.activity_id = ea.activity_id
LEFT JOIN exec_segments es ON es.segment_id = ese.segment_id
WHERE ea.source_system = 'garmin'
  AND ea.segment_effort_count > 0
GROUP BY ea.activity_id
ORDER BY ea.activity_date DESC, ea.started_at DESC
LIMIT 20;
SQL
```

Expected outcome:
- Segment definitions exist in `exec_segments`.
- Cycling activities show explicit `segment_data_status` values.
- Persisted rows reflect only favorite segments for the imported activities.
- Segment efforts retain elapsed time plus any available supporting metrics, or remain visible as membership-only rows when elapsed time is unavailable.

## 6. Review segment history in the GUI

1. Open the segment analysis read surface in the existing GUI.
2. Select a segment with multiple efforts.
3. Confirm the backend-provided detail shows:
   - chronological effort history,
   - best effort,
   - recent effort sequence,
   - explicit missing metrics when data is absent,
  - `insufficient_data` when only one comparable effort exists,
  - membership-only rows labeled clearly when Garmin did not expose or support elapsed time.

Expected outcome:
- A coach or athlete can determine whether performance is improving, stable, or regressing without recalculating metrics outside the product.