# Implementation Plan: AI Training Assessment Agents

**Branch**: `004-ai-training-assessment` | **Date**: 2026-05-28 | **Spec**: `/specs/004-ai-training-assessment/spec.md`

**Input**: Feature specification from `/specs/004-ai-training-assessment/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a backend-owned AI assessment orchestration slice that runs specialized LLM agent profiles across daily, weekly, block, and season windows using SQLite-backed plan, execution, recovery, quality, and review context; persists each assessment run, finding, proposal, operator decision, and bounded assessment-dialog clarification in SQLite; and exposes thin GUI review, dialog, and approval surfaces without allowing AI output to mutate the canonical plan until an operator approves a proposal. Version 1 starts with four explicit specialist profiles, keeps the frontend as a reader/action layer, supports guided follow-up dialog around persisted assessments, and treats markdown planning files as manually maintained human views rather than runtime state.

## Technical Context

**Language/Version**: Python 3.12 backend, TypeScript 5.5 / React 18 frontend

**Primary Dependencies**: FastAPI, Pydantic, sqlite3, uvicorn, React, Vite, provider-agnostic LLM client wrapper introduced behind backend services, existing Garmin/activity-quality/segment context modules

**Storage**: Local SQLite in `Sistema/training.sqlite` as canonical runtime store; existing season markdown remains human-authored context only

**Testing**: Python `unittest` backend tests, targeted SQLite assertions, API contract checks via FastAPI test client or equivalent, and frontend `npm run build`

**Target Platform**: Local Linux single-machine runtime with local FastAPI backend and local React/Vite frontend

**Project Type**: Local-first web application with backend-owned agent orchestration and thin frontend review/approval surfaces

**Performance Goals**: Daily assessment available from the application in under 2 minutes when new data exists; weekly/block review inspectable in under 3 minutes; duplicate runs avoided for unchanged cadence windows; explicit `no_new_data`/`partial_context`/`failed` outcomes persisted instead of silent retries or pseudo-results

**Constraints**: SQLite remains canonical; runtime assessment context is assembled from backend-owned structured data, not markdown; frontend stays thin; multiple specialist LLM agent profiles must coexist per cadence; proposal approval is required before any plan mutation; bounded follow-up dialog and user clarifications must remain anchored to persisted assessments/proposals rather than becoming free-form generic chat; local-first workflow is preserved even if an external LLM provider is used transiently; LLM failures must persist explicit failed/incomplete outcomes; markdown plan views remain manually maintained in v1 and are not mutated automatically by accepted proposals

**Scale/Scope**: Current single-athlete local dataset; v1 covers Daily Execution, Daily Recovery And Readiness, Weekly Adherence And Adequacy, and Block Performance Direction agent profiles with proposal capability targeting the next planning layer; season cadence support is designed into storage and APIs even if the first shipped roster is smaller than the full catalog

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- PASS: SQLite remains the canonical source of truth by persisting assessment windows, LLM runs, findings, proposals, approval decisions, and accepted-plan traceability in SQLite-backed tables rather than markdown or frontend state.
- PASS: Affected markdown remains manually maintained human context only; this feature does not depend on markdown as runtime assessment input and does not auto-mutate markdown when proposals are accepted in v1.
- PASS: Agent selection, context assembly, proposal validation, and approval enforcement stay in backend/services/agents; the GUI only triggers runs, lists results, and records review actions.
- PASS: External AI invocation remains traceable through persisted run status, provider/model metadata, prompt profile identity, and operator-readable failure details; no new athlete-data source is introduced.
- PASS: Planned validation is slice-local: backend unit/API tests for cadence windows, deduplication, proposal boundaries, and approval flow, plus frontend build validation for thin review surfaces.

## Project Structure

### Documentation (this feature)

```text
specs/004-ai-training-assessment/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-training-assessment-api.md
└── tasks.md
```

### Source Code (repository root)

```text
2026/
├── Bloques/
├── Datos/
├── Ficha-usuario.md
└── Macro.md

Agentes/
└── README.md

GUI/
├── backend/
│   ├── app/
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── activity_quality.py
│   │   ├── segments.py
│   │   └── imports/
│   └── tests/
│       ├── test_activity_quality.py
│       ├── test_garmin_connect_cli.py
│       └── test_garmin_segment_import.py
└── frontend/
    └── src/
        ├── App.tsx
        ├── main.tsx
        └── styles.css

Sistema/
├── schema.sql
├── views.sql
└── Seeds/
```

**Structure Decision**: This is a brownfield feature centered on `GUI/backend/app/` plus SQLite schema evolution. The implementation should add backend-owned agent profile configuration, cadence window resolution, context assembly, LLM invocation, proposal validation, and approval application inside new backend modules adjacent to `main.py` and `db.py`; extend `Sistema/schema.sql` and `Sistema/views.sql` for canonical assessment/proposal persistence; keep `Agentes/README.md` as documentation context for the specialist-agent architecture; and add only thin list/detail/action UI in `GUI/frontend/src/App.tsx` driven by stable backend APIs. Season markdown under `2026/` remains human context and is not used as mutable runtime state.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Post-Design Constitution Check

- PASS: The design keeps SQLite canonical by treating assessment runs, findings, proposals, proposal decisions, and accepted-plan traceability as structured local data.
- PASS: Markdown remains outside runtime decision paths; accepted proposals update SQLite-backed planning surfaces first and any markdown synchronization remains an explicit later workflow.
- PASS: The frontend stays thin by consuming backend-derived cadence summaries, finding groups, dialog context, proposal metadata, and approval actions rather than embedding coaching logic or prompt logic.
- PASS: External AI calls remain reviewable because each run stores agent profile identity, analysis window, relevant evidence references, provider/model metadata, and explicit failure states.
- PASS: Validation remains executable and local to touched slices: backend tests for orchestration/deduplication/approval boundaries, targeted SQLite inspection, and frontend build validation.
