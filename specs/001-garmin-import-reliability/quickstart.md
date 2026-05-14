# Quickstart: Garmin Import Reliability

## Goal

Validate that Garmin import attempts become durable, classifiable, and safely rerunnable without introducing duplicate canonical records.

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
- HTTP error describing Garmin configuration failure.
- A persisted import attempt row with terminal status, `configuration_authentication` failure class, failed stage, and retry suitability.

## 4. Validate history visibility

```bash
curl -s http://127.0.0.1:8000/api/import-jobs
```

Expected result after implementation:
- Latest attempt includes failure class, failed stage, retry suitability, request scope, and per-data-class breakdown.

## 5. Validate GUI operator visibility

- Open `http://127.0.0.1:5173/`.
- Use the existing Garmin import card and import-job history list.
- Confirm the latest run shows outcome, failure class, failed stage, retry suitability, and summary counts without introducing a new Garmin-specific dashboard.

## 6. Validate safe rerun behavior

With a configured Garmin environment, run the same import scope twice.

Expected result after implementation:
- Two distinct import attempt records.
- No unintended duplicate rows in canonical `exec_activities` or `exec_daily_metrics`.
- The second run records inserted/updated/skipped counts correctly.