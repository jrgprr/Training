# Tasks: Filter Bad Readings

**Input**: Design documents from `/specs/003-filter-bad-readings/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/filter-bad-readings-api.md, quickstart.md

**Tests**: Include focused backend validation and frontend build validation because the feature depends on independently verifiable raw-reading persistence, deterministic rule outcomes, idempotent re-imports, and backend-owned traceability.

**Organization**: Tasks are grouped by user story after shared setup and foundation work so canonical SQLite storage, backend rule evaluation, API surfaces, thin frontend visibility, and final validation can be delivered incrementally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when tasks touch different files and have no direct dependency.
- **[Story]**: `US1`, `US2`, or `US3` maps each task to a user story from the specification.
- Each task names the exact file paths to change or the exact command to run.

## Phase 1: Setup (Shared Context)

**Purpose**: Lock the implementation to the approved scope before changing schema, import logic, or activity APIs.

- [x] T001 Confirm the SQLite source-of-truth boundary, deterministic rule-only scope, raw-evidence preservation requirement, and thin-GUI contract in `specs/003-filter-bad-readings/plan.md`, `specs/003-filter-bad-readings/research.md`, and `specs/003-filter-bad-readings/contracts/filter-bad-readings-api.md`.
- [x] T002 Identify the concrete implementation surface in `Sistema/schema.sql`, `Sistema/views.sql`, `GUI/backend/app/db.py`, `GUI/backend/app/imports/contracts.py`, `GUI/backend/app/imports/garmin_connect.py`, `GUI/backend/app/imports/pipeline.py`, `GUI/backend/app/imports/storage.py`, `GUI/backend/app/main.py`, `GUI/backend/tests/test_garmin_connect_cli.py`, and `GUI/frontend/src/App.tsx`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Put canonical SQLite and backend quality-model foundations in place before story work begins.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [x] T003 Update `Sistema/schema.sql` and `GUI/backend/app/db.py` so SQLite initializes and migrates the canonical quality tables (`exec_activity_metric_readings`, `exec_activity_quality_runs`, `exec_activity_quality_decisions`, `exec_activity_metric_summaries`) plus `exec_activities.quality_*` fields.
- [x] T004 [P] Extend Garmin import dataclasses and serialization helpers in `GUI/backend/app/imports/contracts.py` to represent normalized per-metric readings, evaluation-scope metadata, and quality count summaries.
- [x] T005 [P] Add shared quality-evaluation and traceability assembly support in `Sistema/views.sql` and a new `GUI/backend/app/activity_quality.py` module so rule execution, summary recomputation, and activity-quality reads have one backend-owned implementation surface.
- [x] T006 Wire the shared quality helpers into `GUI/backend/app/imports/__init__.py` and `GUI/backend/app/main.py` so later story work reuses one canonical import and read-model boundary.
- [x] T007 [P] Add source-evidence fingerprinting in `GUI/backend/app/activity_quality.py` and `GUI/backend/app/imports/storage.py` so unchanged source readings plus unchanged rule version resolve to the same canonical quality run, while changed source readings create a new traceable run.

**Checkpoint**: SQLite schema, shared contracts, and backend quality helpers are ready for story implementation.

---

## Phase 3: User Story 1 - Protect Activity Summaries From Bad Readings (Priority: P1) 🎯 MVP

**Goal**: Persist raw metric readings and deterministic quality decisions so trusted activity summaries exclude implausible samples without losing source evidence.

**Independent Test**: Import an activity with a known implausible heart-rate spike, re-import it unchanged, and verify canonical SQLite rows remain idempotent while trusted `avg_hr` and `max_hr` exclude the spike.

### Tests for User Story 1

- [x] T008 [P] [US1] Add backend normalization and persistence tests in `GUI/backend/tests/test_activity_quality.py` covering raw reading extraction, single-sample heart-rate exclusion, and clean-activity outcomes.
- [x] T009 [P] [US1] Add backend idempotency tests in `GUI/backend/tests/test_activity_quality.py` covering repeated import of unchanged activity data, stable raw-reading keys, stable quality decisions, unchanged trusted summaries, and stable source-evidence fingerprints.

### Implementation for User Story 1

- [x] T010 [US1] Extend Garmin normalization in `GUI/backend/app/imports/garmin_connect.py` and `GUI/backend/app/imports/contracts.py` so in-scope activities emit normalized `heart_rate`, `power`, and `bike_cadence` samples when point-level readings exist.
- [x] T011 [US1] Update `GUI/backend/app/imports/pipeline.py`, `GUI/backend/app/activity_quality.py`, and `GUI/backend/app/imports/storage.py` so imports persist canonical raw readings, run the deterministic quality evaluator, and write trusted summary values back to `exec_activities` transactionally.
- [x] T012 [US1] Extend `GUI/backend/app/imports/storage.py`, `GUI/backend/app/imports/contracts.py`, and `GUI/backend/app/main.py` so `POST /api/imports/garmin-connect/run` exposes quality evaluation counts, source-fingerprint-aware idempotency metadata, and rule-version metadata.
- [x] T013 [US1] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_garmin_connect_cli tests.test_activity_quality` to validate the import and canonical summary slice.

**Checkpoint**: Imports preserve raw evidence, trusted summaries exclude implausible values, and reruns stay deterministic.

---

## Phase 4: User Story 2 - Explain Why Readings Were Excluded (Priority: P2)

**Goal**: Reviewers can inspect backend-owned traceability for excluded readings, affected metrics, and changed summaries on a per-activity basis.

**Independent Test**: Request activity quality detail for an activity with exclusions and confirm the response shows excluded reading ranges, reason codes, and summary deltas; request a clean activity and confirm it returns an explicit clean outcome.

### Tests for User Story 2

- [x] T014 [P] [US2] Add backend endpoint tests in `GUI/backend/tests/test_activity_quality.py` covering `GET /api/activities/{activity_id}` quality metadata and `GET /api/activities/{activity_id}/quality` traceability responses.
- [x] T015 [P] [US2] Add backend query tests in `GUI/backend/tests/test_activity_quality.py` covering clean, filtered, and limited activity states plus per-metric summary deltas and reason-code traceability.

### Implementation for User Story 2

- [x] T016 [US2] Implement SQLite-backed activity-quality list/detail queries in `GUI/backend/app/activity_quality.py` and `Sistema/views.sql` so traceability assembly lives in one backend-owned read-model surface.
- [x] T017 [US2] Extend `GUI/backend/app/main.py` so `GET /api/seasons/{season_id}/activities` and `GET /api/activities/{activity_id}` expose activity-level quality fields and add `GET /api/activities/{activity_id}/quality` for detailed traceability.
- [x] T018 [US2] Keep payload shape aligned with `specs/003-filter-bad-readings/contracts/filter-bad-readings-api.md` by updating response serialization in `GUI/backend/app/activity_quality.py` and `GUI/backend/app/main.py`.
- [x] T019 [US2] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_activity_quality` to validate the traceability slice.

**Checkpoint**: Activity-level traceability is available through backend endpoints with explicit clean, filtered, and limited outcomes.

---

## Phase 5: User Story 3 - Keep Downstream Analytics Consistent And Bounded (Priority: P3)

**Goal**: Existing activity consumers and the minimal GUI surface rely on trusted filtered summaries and explicit quality-limited states rather than raw distorted values.

**Independent Test**: Load an activity list containing clean, filtered, and limited activities and verify the GUI renders backend-provided quality status and metric impacts without recomputing filtering logic locally.

### Tests for User Story 3

- [x] T020 [P] [US3] Add backend read-model tests in `GUI/backend/tests/test_activity_quality.py` covering quality-limited summaries, withheld trusted values, and downstream consumers that continue reading `exec_activities` trusted summary columns.
- [x] T021 [P] [US3] Add frontend payload-handling coverage or typed integration checks in `GUI/frontend/src/App.tsx` for activity quality status, impacted metrics, and traceability entry rendering.

### Implementation for User Story 3

- [x] T022 [US3] Update `GUI/backend/app/activity_quality.py`, `GUI/backend/app/main.py`, and any downstream activity queries so trusted canonical summaries and quality-limited states are the values consumed by existing activity surfaces.
- [x] T023 [US3] Extend the existing GUI in `GUI/frontend/src/App.tsx` to display activity-level quality status, affected metrics, and per-activity traceability details using backend-provided fields only.
- [x] T024 [P] [US3] Update `GUI/frontend/src/styles.css` only as needed to keep the new quality pills, summary-delta rows, and exclusion trace list readable in the existing layout.
- [x] T025 [US3] Run `cd /home/jparra/Training/GUI/frontend && npm run build` to validate the thin frontend surface against the new activity-quality payloads.

**Checkpoint**: Existing activity consumers use filtered canonical summaries, and the GUI exposes explicit quality state without embedding domain logic.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Finish contract consistency, quickstart alignment, and end-to-end validation across all stories.

- [x] T026 [P] Reconcile final field names and nullability across `GUI/backend/app/imports/contracts.py`, `GUI/backend/app/activity_quality.py`, `GUI/backend/app/main.py`, and `GUI/frontend/src/App.tsx` so import, activity, and traceability payloads stay consistent.
- [x] T027 [P] Update `specs/003-filter-bad-readings/quickstart.md` if concrete test commands, endpoint shapes, or manual validation steps change during implementation.
- [x] T028 Add a replay or backfill path in `GUI/backend/app/activity_quality.py`, `GUI/backend/app/main.py`, and `GUI/backend/tests/test_activity_quality.py` so already imported activities can be evaluated from canonical raw readings or stored artifacts without requiring a fresh live Garmin fetch.
- [x] T029 Run the full validation path from `specs/003-filter-bad-readings/quickstart.md`, including backend tests, frontend build, repeated import, replay/backfill execution, SQLite inspection, and manual activity-quality review.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: starts immediately.
- **Phase 2: Foundational**: depends on Phase 1 and blocks all user stories.
- **Phase 3: US1**: depends on Phase 2 and delivers the MVP raw-reading and trusted-summary slice.
- **Phase 4: US2**: depends on US1 because traceability requires canonical quality runs, decisions, and summary deltas to exist.
- **Phase 5: US3**: depends on US1 and US2 because the GUI must consume the stabilized backend quality surfaces.
- **Phase 6: Polish**: depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: no dependency on later stories; this is the canonical evidence and filtering foundation.
- **US2 (P2)**: depends on US1 because traceability requires persisted quality decisions and summary impacts.
- **US3 (P3)**: depends on US1 for trusted summaries and on US2 for detailed activity-quality payloads.

### Within Each User Story

- Add the focused backend tests first for the story.
- Complete canonical persistence before extending activity read surfaces.
- Stabilize backend payloads before rendering them in `GUI/frontend/src/App.tsx`.
- Run the narrow executable validation for the story before moving to the next phase.

### Parallel Opportunities

- T004 and T005 can proceed in parallel after T003.
- T008 and T009 can proceed in parallel within US1.
- T014 and T015 can proceed in parallel within US2.
- T020 and T023 can proceed in parallel within US3 once payload fields are stable.

---

## Parallel Example: User Story 1

```bash
# After the foundational schema and contracts are in place:
Task: "Add backend normalization and persistence tests in GUI/backend/tests/test_activity_quality.py covering raw reading extraction and single-sample heart-rate exclusion"
Task: "Add backend idempotency tests in GUI/backend/tests/test_activity_quality.py covering repeated import of unchanged activity data and stable quality decisions"
```

---

## Parallel Example: User Story 2

```bash
# Once canonical quality runs and decisions exist:
Task: "Add backend endpoint tests in GUI/backend/tests/test_activity_quality.py covering GET /api/activities/{activity_id} quality metadata and GET /api/activities/{activity_id}/quality"
Task: "Add backend query tests in GUI/backend/tests/test_activity_quality.py covering clean, filtered, and limited activity states plus summary deltas"
```

---

## Parallel Example: User Story 3

```bash
# After the activity-quality payload is stable:
Task: "Add frontend payload handling in GUI/frontend/src/App.tsx for activity quality status and traceability rendering"
Task: "Update GUI/frontend/src/styles.css only as needed to keep quality pills and summary-delta rows readable"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 and validate raw-reading persistence plus trusted summary recomputation end to end.
3. Stop and verify unchanged re-imports remain deterministic before extending traceability or UI work.

### Incremental Delivery

1. Deliver US1 for canonical evidence capture and trusted-summary filtering.
2. Deliver US2 for backend traceability on one activity.
3. Deliver US3 for thin GUI visibility and bounded downstream consumption.

### Parallel Team Strategy

1. One developer completes the schema/contracts foundation and import persistence work.
2. After US1 stabilizes, backend read-model/API work and frontend rendering can progress in parallel against the contract.

---

## Notes

- `[P]` tasks indicate different files or independently executable validation work.
- Keep SQLite as the canonical runtime source of truth for raw readings, quality decisions, and trusted summaries.
- Keep filtering and traceability logic in backend Python code, not in `GUI/frontend/src/App.tsx`.
- Keep this feature scoped to deterministic bad-reading filtering and traceability; do not add machine learning, interpolation, or markdown synchronization.