# Implementation Plan: Garmin Import Reliability

**Branch**: `001-improve-garmin-import` | **Date**: 2026-05-14 | **Spec**: `/specs/001-garmin-import-reliability/spec.md`

**Input**: Feature specification from `/specs/001-garmin-import-reliability/spec.md`

## Summary

Improve the existing Garmin import flow so every run records a durable, classifiable outcome in SQLite, preserves idempotent canonical writes by stable Garmin source identity, exposes explicit retry suitability, and extends the existing GUI history/status surfaces just enough to diagnose and rerun failed imports safely. The implementation stays inside the current FastAPI import endpoints, Garmin pipeline/storage layer, SQLite schema, and existing import cards/history list in the GUI.

## Technical Context

**Language/Version**: Python 3.12 backend, TypeScript/React 18 frontend

**Primary Dependencies**: FastAPI, uvicorn, garminconnect, sqlite3, React, Vite

**Storage**: Local SQLite in `Sistema/` and the GUI backend DB adapter; staging tables and import job metadata already exist

**Testing**: Python unittest-based backend tests, targeted API/persistence checks, frontend smoke validation via existing GUI surface

**Target Platform**: Local Linux development environment, single-machine local-first runtime

**Project Type**: Local web application with FastAPI backend and React/Vite frontend

**Performance Goals**: Operators can determine the result and retry suitability of an import run within 2 minutes; import outcome persistence must add negligible overhead relative to the existing fetch/persist flow

**Constraints**: SQLite remains canonical, retries are manual-only, no Garmin business logic in the GUI, no cloud services, no markdown dependency for runtime diagnosis

**Scale/Scope**: Existing Garmin import flow only; one operator-triggered date-range import at a time; activities and daily metrics for a single season/date scope per run

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- PASS: SQLite remains the canonical source of truth for import attempts, staging evidence, and canonical Garmin records.
- PASS: No markdown runtime changes are introduced; markdown remains a human-facing view and is unaffected by import-state diagnosis.
- PASS: GUI changes are limited to existing status/history surfaces and consume backend-derived fields only.
- PASS: The design extends traceability around source scope, failure stage/class, per-data-class breakdown, and retry suitability.
- PASS: Planned validation includes focused backend tests plus a manual GUI/API smoke path for success, duplicate rerun, failure, and partial-completion outcomes.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
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
│   └── tests/
└── frontend/
  └── src/

Sistema/
├── schema.sql
├── views.sql
└── Seeds/

Agentes/
└── [agent docs or future automation surfaces]
```

**Structure Decision**: The feature is implemented as a brownfield slice across `GUI/backend/app/imports/`, the FastAPI endpoints in `GUI/backend/app/main.py`, SQLite schema in `Sistema/schema.sql`, backend tests in `GUI/backend/tests/`, and the existing Garmin status/history UI in `GUI/frontend/src/App.tsx`. No new top-level modules or dashboards are introduced.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Post-Design Constitution Check

- PASS: The design keeps SQLite canonical by extending import-job metadata and relying on existing canonical uniqueness constraints for `exec_activities` and `exec_daily_metrics`.
- PASS: No markdown synchronization path is added; runtime diagnosis stays fully inside SQLite-backed backend/API/UI flows.
- PASS: Operator-facing changes stay limited to the existing Garmin status/history surfaces and consume backend-derived fields only.
- PASS: Traceability is improved through explicit scope, stage, class, breakdown, and retry-suitability fields on import attempts plus existing staging evidence tables.
- PASS: Validation remains slice-local: backend unit/API checks, SQLite state assertions, and a minimal GUI smoke path.
