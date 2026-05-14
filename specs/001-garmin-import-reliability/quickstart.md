# Quickstart: Garmin Import Reliability

## Goal

Validate that Garmin import attempts become durable, classifiable, and safely rerunnable without introducing duplicate canonical records.

## Validation status

Validated on 2026-05-14 in the local Linux development environment:
- Focused backend test suite passes.
- The live failure path without Garmin credentials returns HTTP 400.
- Import-job history is exposed through the API and rendered in the existing GUI history surface.
- Legacy import-job rows that do not contain `request_scope` no longer break the GUI.
- A live Garmin import using environment credentials succeeds for scope `2026-05-05` to `2026-05-05`.
- Repeating that same live scope creates distinct import attempts while preserving canonical Garmin row counts.

Not yet validated in this environment:
- A live partial-completion case triggered from a real Garmin run.

## Prerequisites

- Feature branch `001-improve-garmin-import` checked out.
- Python environment available at `/home/jparra/Training/.venv`.
- Frontend dependencies already installed in `GUI/frontend/node_modules`.
- Optional Garmin configuration if validating a successful live import.

## 1. Run targeted backend tests

```bash
cd /home/jparra/Training/GUI/backend
source /home/jparra/Training/.venv/bin/activate
PYTHONPATH=. python -m unittest tests.test_garmin_connect_cli
```

## 2. Start the app

Backend:

```bash
cd /home/jparra/Training/GUI/backend
source /home/jparra/Training/.venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd /home/jparra/Training/GUI/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## 3. Validate configuration/authentication failure path

Without Garmin credentials or token store configured:

```bash
curl -s -X POST http://127.0.0.1:8000/api/imports/garmin-connect/run \
  -H 'Content-Type: application/json' \
  -d '{"season_id":2026,"date_from":"2026-05-04","date_to":"2026-05-10","include_daily_metrics":true}'
```

Expected result after implementation:
- HTTP 400 error describing Garmin configuration failure.
- A persisted import attempt row with terminal status, `configuration_authentication` failure class, failed stage, and retry suitability.

## 4. Validate history visibility

```bash
curl -s http://127.0.0.1:8000/api/import-jobs
```

Expected result after implementation:
- Latest attempt includes failure class, failed stage, retry suitability, request scope when present, and per-data-class breakdown.
- Older rows created before this feature may omit `request_scope`; the GUI should still render them through the legacy fallback path.

## 5. Validate GUI operator visibility

- Open `http://127.0.0.1:5173/`.
- Use the existing Garmin import card and import-job history list.
- Confirm the latest run shows outcome, failure class, failed stage, retry suitability, and summary counts without introducing a new Garmin-specific dashboard.
- Confirm older import rows without structured scope metadata still render instead of crashing the page.

## 6. Validate safe rerun behavior

With a configured Garmin environment, run the same import scope twice.

Expected result after implementation:
- Two distinct import attempt records.
- No unintended duplicate rows in canonical `exec_activities` or `exec_daily_metrics`.
- The second run records inserted/updated/skipped counts correctly.

Current note:
- Validated live on 2026-05-14 with scope `2026-05-05` to `2026-05-05`.
- Two distinct completed attempts were recorded as jobs `19` and `20`.
- Canonical counts for that scope remained stable at 3 Garmin activities and 2 Garmin daily metrics.
