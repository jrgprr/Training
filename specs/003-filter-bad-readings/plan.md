# Implementation Plan: Filter Bad Readings

**Branch**: `003-filter-bad-readings` | **Date**: 2026-05-27 | **Spec**: `/specs/003-filter-bad-readings/spec.md`

**Input**: Feature specification from `/specs/003-filter-bad-readings/spec.md`

## Summary

Extend the existing Garmin-backed activity import slice so SQLite persists canonical per-metric raw readings, deterministic bad-reading decisions, and filtered metric summaries, then expose backend-derived activity quality status and traceability through the current activity APIs and a minimal GUI detail surface. The implementation stays local-first, keeps raw evidence intact, recomputes trusted summaries from accepted readings only, preserves backward compatibility by continuing to serve trusted activity summary fields from `exec_activities`, and defines both import-time evaluation and replay evaluation for already imported activities.

## Technical Context

**Language/Version**: Python 3.12 backend, TypeScript/React 18 frontend

**Primary Dependencies**: FastAPI, uvicorn, garminconnect, sqlite3, React, Vite

**Storage**: Local SQLite in `Sistema/training.sqlite` plus imported Garmin artifacts under season-local `Datos/Importaciones/Garmin/Actividades`

**Testing**: Python `unittest` backend tests, targeted SQLite assertions, import CLI/API checks, and frontend `npm run build`

**Target Platform**: Local Linux development environment, single-machine local-first runtime

**Project Type**: Local web application with FastAPI backend and React/Vite frontend

**Performance Goals**: Quality evaluation should add only marginal overhead to the current import flow; an operator can determine within 2 minutes whether filtering changed an activity and why; repeated imports of unchanged source data with unchanged active rules must produce identical outcomes

**Constraints**: SQLite remains canonical; raw readings are preserved and never overwritten; filtering is deterministic and rule-based; no fabricated replacement values; frontend stays thin; markdown remains manually maintained and out of runtime decision paths; the first version evaluates heart rate and any other metrics already available as sample streams from the import source; unchanged source evidence plus unchanged rule version must produce a stable quality-run identity, while changed source evidence under the same rule version must produce a new traceable run

**Scale/Scope**: Existing single-athlete local dataset, Garmin and already imported local activity data, per-activity filtering of heart rate first and power/cadence when point-level readings are available, with downstream analytics consuming filtered canonical summaries rather than raw spikes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- PASS: SQLite stays the canonical source of truth by adding canonical raw-reading, quality-decision, and filtered-summary tables instead of relying on markdown or frontend state.
- PASS: No markdown runtime dependency is introduced; seasonal markdown remains manually maintained and unaffected by quality filtering.
- PASS: Detection, summary recomputation, and traceability stay in backend/services and SQLite-backed read models rather than in React components.
- PASS: Import traceability remains inside the existing Garmin pipeline and import-job history, now extended with quality-evaluation counts and outcomes.
- PASS: Planned validation remains slice-local with backend unit/API tests, SQLite inspection, and frontend build validation.

## Project Structure

### Documentation (this feature)

```text
specs/003-filter-bad-readings/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── filter-bad-readings-api.md
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
│   │   ├── segments.py
│   │   ├── activity_quality.py
│   │   └── imports/
│   │       ├── contracts.py
│   │       ├── garmin_connect.py
│   │       ├── pipeline.py
│   │       └── storage.py
│   └── tests/
│       ├── test_garmin_connect_cli.py
│       └── test_activity_quality.py
└── frontend/
    └── src/
        ├── App.tsx
        └── styles.css

Sistema/
├── schema.sql
├── views.sql
└── Seeds/

Agentes/
└── README.md
```

**Structure Decision**: This is a brownfield feature anchored in the existing Garmin import flow. The implementation extends `GUI/backend/app/imports/` to emit canonical sample-level readings and quality counts, adds a dedicated backend-owned `GUI/backend/app/activity_quality.py` module for deterministic filtering, source-evidence fingerprinting, replay execution, and traceability assembly, evolves `Sistema/schema.sql` and `Sistema/views.sql` for canonical storage/read models, updates `GUI/backend/app/main.py` to expose quality status/details, and keeps `GUI/frontend/src/App.tsx` as a thin consumer of backend-provided quality payloads.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Post-Design Constitution Check

- PASS: The design keeps SQLite canonical by persisting raw metric readings, source-fingerprint-aware rule-versioned quality runs, explicit exclusion decisions, and filtered metric summaries in SQLite.
- PASS: No markdown synchronization path is introduced; all runtime quality state stays in SQLite-backed backend/API/UI flows.
- PASS: The frontend remains a thin reader of backend-computed quality status, impacted summaries, and traceability details.
- PASS: Import traceability remains explicit through import-job breakdowns, source activity identity, source-evidence fingerprint, rule version, and summary-impact records.
- PASS: Validation stays narrow and executable: backend tests for normalization, idempotency, and traceability, targeted SQLite assertions, and frontend build validation.
