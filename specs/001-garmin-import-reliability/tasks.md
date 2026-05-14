# Tasks: Garmin Import Reliability

**Input**: Design documents from `/specs/001-garmin-import-reliability/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/garmin-import-api.md

**Tests**: Include focused backend tests because the feature specification requires independently verifiable outcomes for success, failure, retry safety, and minimal operator visibility.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the shared foundation is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when they touch different files and have no direct dependency.
- **[Story]**: `US1`, `US2`, or `US3` maps each task to a user story from the spec.
- Each task names the exact files to change.

## Phase 1: Setup (Shared Context)

**Purpose**: Lock the task slice to the existing Garmin import flow and prepare shared implementation targets.

- [x] T001 Confirm the feature scope and validation path in `specs/001-garmin-import-reliability/plan.md`, `specs/001-garmin-import-reliability/contracts/garmin-import-api.md`, and `specs/001-garmin-import-reliability/quickstart.md` before code changes begin.
- [x] T002 Identify the shared implementation surface in `Sistema/schema.sql`, `GUI/backend/app/imports/contracts.py`, `GUI/backend/app/imports/storage.py`, `GUI/backend/app/main.py`, `GUI/backend/tests/test_garmin_connect_cli.py`, and `GUI/frontend/src/App.tsx`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create the shared persistence and serialization foundation that every user story depends on.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [x] T003 Update `Sistema/schema.sql` so `meta_import_jobs` stores request scope, finished timestamp, failure stage, failure class, retry suitability, partial-completion state, operator detail, and per-data-class breakdown columns.
- [x] T004 [P] Extend Garmin import dataclasses and serialization helpers in `GUI/backend/app/imports/contracts.py` to represent the enriched attempt state and breakdown fields returned by the API.
- [x] T005 [P] Refactor shared import-job persistence and serialization in `GUI/backend/app/imports/storage.py` so start, success, failure, and listing/detail reads use explicit structured fields instead of notes-only state.
- [x] T006 Add shared backend rules for terminal status, failure classification, and retry suitability in `GUI/backend/app/imports/storage.py` and `GUI/backend/app/imports/pipeline.py` so all stories consume one canonical interpretation.

**Checkpoint**: SQLite schema and shared backend import-job model are ready for story work.

---

## Phase 3: User Story 1 - Complete Or Explain Each Import Attempt (Priority: P1) 🎯 MVP

**Goal**: Every Garmin import attempt ends with one durable, classifiable terminal outcome in SQLite.

**Independent Test**: Run the Garmin import flow through successful, configuration-failure, and persistence-failure paths and verify one terminal attempt row with counts, failure class, failed stage, and operator detail for each run.

### Tests for User Story 1

- [x] T007 [P] [US1] Add backend tests in `GUI/backend/tests/test_garmin_connect_cli.py` covering successful completion and zero-result completion with enriched terminal import-job fields.
- [x] T008 [P] [US1] Add backend tests in `GUI/backend/tests/test_garmin_connect_cli.py` covering configuration/authentication failure, transport failure, and persistence failure classification with terminal import-job persistence.

### Implementation for User Story 1

- [x] T009 [US1] Update Garmin fetch/pipeline flow in `GUI/backend/app/imports/pipeline.py` and `GUI/backend/app/imports/garmin_connect.py` so fetch and normalization failures surface the stage and class required by the spec.
- [x] T010 [US1] Update run-path persistence in `GUI/backend/app/imports/storage.py` so successful, failed, zero-result, and partial attempts write finished timestamps, operator detail, and per-data-class counts.
- [x] T011 [US1] Update Garmin run/preview endpoints in `GUI/backend/app/main.py` so HTTP responses and terminal job writes stay aligned with the enriched contract for success and failure cases.
- [x] T012 [US1] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_garmin_connect_cli` to validate the P1 slice.

**Checkpoint**: Garmin import attempts are always durably recorded with explicit completion or classified failure.

---

## Phase 4: User Story 2 - Diagnose And Retry Safely (Priority: P2)

**Goal**: Operators can inspect scope, retry suitability, and prior failures while reruns remain idempotent for canonical SQLite records.

**Independent Test**: Trigger a failed attempt, retry the same scope, and verify two distinct attempt rows plus no unintended duplicate canonical rows for activities or daily metrics.

### Tests for User Story 2

- [x] T013 [P] [US2] Add backend tests in `GUI/backend/tests/test_garmin_connect_cli.py` covering repeated scope retries creating new attempt rows without overwriting prior history.
- [x] T014 [P] [US2] Add backend tests in `GUI/backend/tests/test_garmin_connect_cli.py` covering partial completion and `inspect_before_retry` outcomes plus idempotent canonical writes on rerun.

### Implementation for User Story 2

- [x] T015 [US2] Update canonical persistence logic in `GUI/backend/app/imports/storage.py` to record inserted, updated, and skipped counts per data class while preserving the existing stable-identity upsert behavior.
- [x] T016 [US2] Extend import-job list/detail reads in `GUI/backend/app/imports/storage.py` to expose request scope, failure stage, failure class, retry suitability, and partial-completion fields for history review.
- [x] T017 [US2] Update `GET /api/import-jobs`, `GET /api/import-jobs/{import_job_id}`, and `POST /api/imports/garmin-connect/run` in `GUI/backend/app/main.py` to return the enriched retry-safety fields defined in `specs/001-garmin-import-reliability/contracts/garmin-import-api.md`.
- [x] T018 [US2] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_garmin_connect_cli` and verify the retry/history scenarios from `specs/001-garmin-import-reliability/quickstart.md`.

**Checkpoint**: Operators can diagnose prior attempts and rerun the same scope safely without losing history or creating unintended duplicates.

---

## Phase 5: User Story 3 - Keep Operator Visibility Minimal And Useful (Priority: P3)

**Goal**: Reuse the existing Garmin import card and history surface to show the latest outcome, failure details, retry suitability, and per-run breakdown without moving Garmin logic into the UI.

**Independent Test**: Open the existing GUI, run or inspect import history, and verify the UI shows backend-derived outcome, failure class, failed stage, retry suitability, and breakdown data with no new dedicated Garmin module.

### Tests for User Story 3

- [x] T019 [P] [US3] Add or update frontend-facing API/state tests in `GUI/backend/tests/test_garmin_connect_cli.py` for import-job payload fields needed by the existing history surface.

### Implementation for User Story 3

- [x] T020 [US3] Extend Garmin import and history state types plus rendering in `GUI/frontend/src/App.tsx` to display backend-provided status, failure class, failed stage, retry suitability, and per-run breakdown.
- [x] T021 [P] [US3] Update presentation styling in `GUI/frontend/src/styles.css` only as needed to keep the added Garmin history metadata readable in the existing surface.
- [x] T022 [US3] Confirm `GUI/frontend/src/App.tsx` does not derive Garmin retry logic locally and consumes only backend-provided fields for operator visibility.
- [x] T023 [US3] Run the GUI smoke path from `specs/001-garmin-import-reliability/quickstart.md` against `http://127.0.0.1:5173/` and verify the existing Garmin surfaces show the new state without a new dashboard.

**Checkpoint**: Operator visibility is sufficient and minimal, with Garmin logic still owned by the backend.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish cross-story validation and documentation consistency.

- [x] T024 [P] Reconcile the final API/state field names across `GUI/backend/app/imports/contracts.py`, `GUI/backend/app/imports/storage.py`, `GUI/backend/app/main.py`, and `GUI/frontend/src/App.tsx`.
- [x] T025 [P] Update implementation notes in `specs/001-garmin-import-reliability/quickstart.md` if the concrete validation commands or expected payload fields change during implementation.
- [x] T026 Run the full quickstart validation in `specs/001-garmin-import-reliability/quickstart.md`, including backend tests, failure-path curl checks, import history inspection, GUI visibility, and safe rerun verification.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: starts immediately.
- **Phase 2: Foundational**: depends on Phase 1 and blocks all user stories.
- **Phase 3: US1**: depends on Phase 2 and delivers the MVP.
- **Phase 4: US2**: depends on Phase 2 and should build on the P1 persistence model.
- **Phase 5: US3**: depends on Phase 2 and should consume the backend fields completed in US1 and US2.
- **Phase 6: Polish**: depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: no dependency on later stories.
- **US2 (P2)**: depends on the shared import-attempt model from Foundational and the terminal outcome behavior from US1.
- **US3 (P3)**: depends on the API payloads from US1 and US2 but remains a thin presentation layer.

### Within Each User Story

- Add the focused tests first for the story.
- Implement backend storage/pipeline/API changes before frontend rendering.
- Run the narrow executable validation for the story before moving on.

### Parallel Opportunities

- T004 and T005 can proceed in parallel after T003.
- T007 and T008 can proceed in parallel within US1.
- T013 and T014 can proceed in parallel within US2.
- T019 and T021 can proceed in parallel once the backend payload shape is stable.
- T024 and T025 can proceed in parallel during polish.

---

## Parallel Example: Foundational Work

```bash
# After the schema shape is agreed in Sistema/schema.sql:
Task: "Extend Garmin import dataclasses and serialization helpers in GUI/backend/app/imports/contracts.py"
Task: "Refactor shared import-job persistence and serialization in GUI/backend/app/imports/storage.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 and its backend validation.
3. Stop and verify every Garmin import run now leaves one durable terminal outcome.

### Incremental Delivery

1. Deliver US1 for durable success/failure recording.
2. Deliver US2 for retry-safe history and idempotent reruns.
3. Deliver US3 for minimal operator visibility in the existing GUI surface.

### Parallel Team Strategy

1. One developer completes the schema/shared backend foundation.
2. After foundation stabilizes, backend retry/history work and frontend visibility work can proceed in parallel.

---

## Notes

- `[P]` tasks indicate different files or independently executable validation work.
- Keep SQLite as the runtime source of truth; do not move reliability state into markdown.
- Keep Garmin retry-suitability logic in backend code, not in `GUI/frontend/src/App.tsx`.
- Use the quickstart document as the final cross-story validation checklist.