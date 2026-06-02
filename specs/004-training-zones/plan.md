# Implementation Plan: Training Zones

**Branch**: `004-training-zones` | **Date**: 2026-06-01 | **Spec**: `/specs/004-training-zones/spec.md`

**Input**: Feature specification from `/specs/004-training-zones/spec.md`

## Summary

Add a canonical dual-basis zone system to the existing local-first training stack so SQLite stores versioned heart-rate and power zone profiles, executed time-in-zone distributions per activity, traceable refinement proposals driven by recent activities plus daily metrics, and optional structured planned zone targets for plan-versus-reality comparison. The implementation stays backend-owned, uses Garmin-imported cycling data as the primary evidence source, keeps daily metrics as contextual support rather than autonomous estimators, and surfaces only thin read models to the React GUI.

## Technical Context

**Language/Version**: Python 3.12 backend, TypeScript/React 18 frontend

**Primary Dependencies**: FastAPI, uvicorn, garminconnect, sqlite3, React, Vite

**Storage**: Local SQLite in `Sistema/training.sqlite`, with canonical schema changes in `Sistema/schema.sql`, bootstrap compatibility in `GUI/backend/app/db.py`, and existing Garmin artifacts under season-local `Datos/Importaciones/Garmin/Actividades`

**Testing**: Python `unittest` backend tests, targeted SQLite assertions, backend API smoke checks, and frontend `npm run build`

**Target Platform**: Local Linux development environment, single-machine local-first runtime

**Project Type**: Local web application with FastAPI backend and React/Vite frontend

**Performance Goals**: Zone calculation should add only moderate overhead to import or replay workflows; zone refinement should remain explainable and inspectable in minutes; a coach or athlete can review executed heart-rate and power zones for an activity or week within 2 minutes

**Constraints**: SQLite remains canonical; first version must support both heart-rate zones and power zones; daily metrics only modulate confidence and prudence; profile changes must remain versioned and non-destructive; frontend stays thin; markdown remains narrative and out of runtime decision paths; zone logic must be backend-owned and traceable

**Scale/Scope**: Existing single-athlete local dataset, Garmin-imported cycling activities as first execution scope, dual-basis per-activity zone distributions, proposal-based refinement, and session/week plan-versus-reality summaries where planned zone structure exists

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- PASS: SQLite stays the canonical source of truth by adding canonical zone profiles, executed zone distributions, refinement proposals, and optional planned zone targets rather than relying on markdown or frontend state.
- PASS: No markdown runtime dependency is introduced; seasonal markdown remains manually maintained and unaffected by zone calculations.
- PASS: Zone calculation, refinement, and comparison stay in backend/services and SQLite-backed read models rather than React components.
- PASS: Traceability remains explicit through versioned profiles, basis-specific calculation results, proposal evidence, and acceptance governance.
- PASS: Planned validation remains slice-local with backend unit/API tests, SQLite inspection, and frontend build validation.

## Project Structure

### Documentation (this feature)

```text
specs/004-training-zones/
├── plan.md
├── research.md
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
│   │   ├── training_zones.py
│   │   └── imports/
│   │       ├── contracts.py
│   │       ├── garmin_connect.py
│   │       └── storage.py
│   └── tests/
│       ├── test_training_zones.py
│       └── test_garmin_connect_cli.py
└── frontend/
    └── src/
        ├── App.tsx
        └── styles.css

Sistema/
├── schema.sql
├── views.sql
└── Seeds/
```

**Structure Decision**: This is a brownfield feature anchored in the existing Garmin import and review slice. The implementation extends `Sistema/schema.sql`, `Sistema/views.sql`, and `GUI/backend/app/db.py` for canonical persistence; adds a dedicated backend-owned `GUI/backend/app/training_zones.py` service for profile selection, per-basis distribution calculation, refinement proposal generation, and read-model serialization; updates Garmin normalization/persistence under `GUI/backend/app/imports/` where needed to guarantee the necessary canonical inputs; exposes zone read models and governance actions through `GUI/backend/app/main.py`; and keeps `GUI/frontend/src/App.tsx` as a thin reader of backend-provided zone payloads.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Post-Design Constitution Check

- PASS: The design keeps SQLite canonical by persisting versioned heart-rate and power profiles, basis-specific executed zone results, refinement proposals, and structured plan targets.
- PASS: No markdown synchronization path is introduced; runtime state remains inside SQLite-backed backend/API/UI flows.
- PASS: The frontend remains a thin reader of backend-computed distributions, proposal states, and comparison summaries.
- PASS: Traceability remains explicit through basis-specific profile versions, proposal evidence rows, and non-destructive acceptance governance.
- PASS: Validation remains narrow and executable: backend tests for profile selection, per-basis distributions, proposal generation, read models, and frontend build validation.
