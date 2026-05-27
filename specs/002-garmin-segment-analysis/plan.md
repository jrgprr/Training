# Implementation Plan: Garmin Segment Analysis

**Branch**: `002-garmin-segment-analysis` | **Date**: 2026-05-26 | **Spec**: `/specs/002-garmin-segment-analysis/spec.md`

**Input**: Feature specification from `/specs/002-garmin-segment-analysis/spec.md`

## Summary

Extend the existing Garmin Connect import slice so cycling activities can persist canonical favorite-segment definitions, segment efforts, and explicit per-activity segment availability in SQLite, then expose backend-driven segment history and evolution summaries through a minimal read-only GUI surface. The implementation stays inside the current FastAPI import/storage flow, the shared SQLite schema, and the existing React application without introducing markdown runtime dependencies or frontend Garmin logic.

## Post-Implementation Notes

- Garmin segment membership is sourced from Garmin's activity segment list endpoint and constrained to activity segments marked as favorite.
- When native Garmin segment effort metrics are absent, the backend reconstructs approximate elapsed time and supporting metrics from imported activity detail streams plus segment geometry.
- When even reconstruction cannot produce elapsed time, the import still persists a membership-only row so the segment remains visible with explicit missing metrics.
- Re-import now treats the activity's segment slice as authoritative and prunes stale non-favorite effort rows for that activity.
- The implemented slice was validated with backend tests, frontend build validation, and live Garmin imports including the May 24-25 and last-month ranges.

## Technical Context

**Language/Version**: Python 3.12 backend, TypeScript/React 18 frontend

**Primary Dependencies**: FastAPI, uvicorn, garminconnect, sqlite3, React, Vite

**Storage**: Local SQLite in `Sistema/training.sqlite`, with schema changes in `Sistema/schema.sql` and bootstrap compatibility in `GUI/backend/app/db.py`

**Testing**: Python `unittest` backend tests, targeted SQLite assertions, frontend `npm run build`, and live Garmin/API smoke validation for import plus segment review

**Target Platform**: Local Linux development environment, single-machine local-first runtime

**Project Type**: Local web application with FastAPI backend and React/Vite frontend

**Performance Goals**: Segment ingestion adds only marginal overhead to an existing Garmin import run, and a coach or athlete can identify best effort and recent trend for a segment within 2 minutes from the GUI

**Constraints**: SQLite stays canonical; scope is cycling activities from Garmin Connect only; imports remain idempotent; only favorite-tagged Garmin activity segments are in scope; analysis is backend-driven; GUI remains a thin read surface; seasonal markdown stays manually maintained

**Scale/Scope**: Existing single-athlete local dataset, existing Garmin import workflow, repeated efforts for one segment at a time in the minimal GUI analysis view

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- PASS: SQLite remains the canonical source of truth for segment facts, efforts, and derived history inputs.
- PASS: No runtime markdown dependency is introduced; seasonal markdown remains manually maintained and unaffected by this feature.
- PASS: Garmin extraction, persistence, and trend computation stay in backend/services rather than React components.
- PASS: Import traceability remains in the existing Garmin import flow and now includes segment availability/count metadata without introducing silent writes.
- PASS: Planned validation stays slice-local with backend persistence tests, SQLite checks, frontend build validation, and a minimal GUI smoke path.

## Project Structure

### Documentation (this feature)

```text
specs/002-garmin-segment-analysis/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── garmin-segment-analysis-api.md
└── tasks.md
```

### Source Code (repository root)

```text
2026/
├── Bloques/
├── Datos/
├── Ficha-usuario.md
└── Macro.md

GUI/
├── backend/
│   ├── app/
│   │   ├── db.py
│   │   ├── main.py
│   │   └── imports/
│   │       ├── contracts.py
│   │       ├── garmin_connect.py
│   │       ├── pipeline.py
│   │       └── storage.py
│   └── tests/
└── frontend/
    └── src/
        └── App.tsx

Sistema/
├── schema.sql
├── views.sql
└── Seeds/

Agentes/
└── README.md
```

**Structure Decision**: This is a brownfield slice across `GUI/backend/app/imports/` for Garmin extraction and normalization, `GUI/backend/app/main.py` for HTTP contracts, `GUI/backend/app/db.py` plus `Sistema/schema.sql` for SQLite lifecycle and schema evolution, `GUI/backend/tests/` for persistence/API validation, and the existing `GUI/frontend/src/App.tsx` surface for a minimal read-only segment history view.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Post-Design Constitution Check

- PASS: The design keeps SQLite canonical by adding canonical segment definition and segment effort records plus explicit activity-level segment availability state.
- PASS: No markdown synchronization path is introduced; segment history and trend review stay fully inside SQLite-backed backend/API/UI flows.
- PASS: The frontend remains a thin reader of backend-provided lists, histories, and comparison summaries.
- PASS: Import traceability remains anchored in the existing Garmin import job flow and preserves explicit outcomes for activities with and without segment data.
- PASS: Validation remains narrow and executable: backend import/persistence tests, SQLite assertions for idempotent re-import and stale-row pruning, frontend build, and live Garmin smoke review for repeated favorite segments.
