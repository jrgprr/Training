# Tasks: Garmin Segment Analysis

**Input**: Design documents from `/specs/002-garmin-segment-analysis/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/garmin-segment-analysis-api.md, quickstart.md

**Tests**: Include focused backend and frontend validation because the feature requires independently verifiable import idempotency, chronological history review, backend-owned trend computation, and a minimal GUI read surface.

**Organization**: Tasks are grouped by user story after the shared setup and foundation work so backend import/schema work, API/read model work, frontend surface work, and final validation can be delivered incrementally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when tasks touch different files and have no direct dependency.
- **[Story]**: `US1`, `US2`, or `US3` maps each task to a user story from the specification.
- Each task names the exact file paths to change or the exact command to run.

## Phase 1: Setup (Shared Context)

**Purpose**: Lock the implementation to the approved scope before schema or API work begins.

- [x] T001 Confirm the cycling-only scope, SQLite source-of-truth boundary, backend-owned trend rule, and GUI-read-only constraint in `specs/002-garmin-segment-analysis/plan.md`, `specs/002-garmin-segment-analysis/research.md`, and `specs/002-garmin-segment-analysis/contracts/garmin-segment-analysis-api.md`.
- [x] T002 Identify the concrete implementation surface in `Sistema/schema.sql`, `Sistema/views.sql`, `GUI/backend/app/db.py`, `GUI/backend/app/imports/contracts.py`, `GUI/backend/app/imports/garmin_connect.py`, `GUI/backend/app/imports/pipeline.py`, `GUI/backend/app/imports/storage.py`, `GUI/backend/app/main.py`, `GUI/backend/tests/test_garmin_connect_cli.py`, and `GUI/frontend/src/App.tsx`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Put the shared SQLite and backend model foundations in place before story work begins.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [x] T003 Update `Sistema/schema.sql` and `GUI/backend/app/db.py` so SQLite initializes and migrates the canonical segment tables (`exec_segments`, `exec_segment_efforts`), the `exec_activities.segment_*` fields, and any import-job segment traceability columns required by the contract.
- [x] T004 [P] Extend Garmin import dataclasses and serialization helpers in `GUI/backend/app/imports/contracts.py` to represent normalized segment definitions, segment efforts, activity-level segment availability, and import/run segment count summaries.
- [x] T005 [P] Add shared SQLite read-model support in `Sistema/views.sql` and a new `GUI/backend/app/segments.py` module so segment list/history queries and trend summaries have one backend-owned implementation surface.
- [x] T006 Wire the new shared segment query helpers into `GUI/backend/app/main.py` and `GUI/backend/app/imports/__init__.py` so later story work can reuse one canonical import/read model boundary.

**Checkpoint**: SQLite schema, shared contracts, and backend query helpers are ready for story implementation.

---

## Phase 3: User Story 1 - Capture Segment Facts During Import (Priority: P1) 🎯 MVP

**Goal**: Garmin cycling imports persist canonical segment definitions, segment efforts, and explicit per-activity segment availability in SQLite without duplicate writes on re-import.

**Independent Test**: Import a cycling activity with Garmin segments, re-import it, and verify canonical SQLite rows for the activity, segment, and segment effort stay idempotent while activities without segment data still record an explicit segment status.

### Tests for User Story 1

- [x] T007 [P] [US1] Add backend persistence tests in `GUI/backend/tests/test_garmin_segment_import.py` covering a cycling activity with segment data and a cycling activity with no segment payload.
- [x] T008 [P] [US1] Add backend idempotency tests in `GUI/backend/tests/test_garmin_segment_import.py` covering repeated import of the same Garmin activity, stable `external_segment_id` and `external_segment_effort_id` upserts, and non-ambiguous `segment_data_status` transitions.

### Implementation for User Story 1

- [x] T009 [US1] Extend Garmin normalization in `GUI/backend/app/imports/garmin_connect.py` and `GUI/backend/app/imports/contracts.py` so in-scope cycling activities emit canonical segment definition/effort payloads plus explicit `available`, `not_available`, or `not_applicable` outcomes.
- [x] T010 [US1] Update the Garmin run flow in `GUI/backend/app/imports/pipeline.py` and `GUI/backend/app/imports/__init__.py` so segment collections and segment count summaries move through the existing preview/run pipeline without creating a second sync path.
- [x] T011 [US1] Implement canonical segment persistence in `GUI/backend/app/imports/storage.py` so `exec_segments`, `exec_segment_efforts`, and `exec_activities.segment_*` fields are written transactionally and idempotently for repeated Garmin imports.
- [x] T012 [US1] Update `POST /api/imports/garmin-connect/run` in `GUI/backend/app/main.py` to return the segment count and metadata fields defined in `specs/002-garmin-segment-analysis/contracts/garmin-segment-analysis-api.md`.
- [x] T013 [US1] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_garmin_connect_cli tests.test_garmin_segment_import` to validate the import and persistence slice.

**Checkpoint**: Cycling Garmin imports create durable canonical segment records and remain safe to rerun.

---

## Phase 4: User Story 2 - Review Segment Performance History (Priority: P2)

**Goal**: Coaches and athletes can request a backend-driven segment list and chronological history view backed by canonical SQLite state.

**Independent Test**: After importing repeated efforts for one segment, call the segment list/history endpoints and verify the segment appears with ordered efforts, key metrics, and explicit missing-metric markers.

### Tests for User Story 2

- [x] T014 [P] [US2] Add backend query and endpoint tests in `GUI/backend/tests/test_garmin_segment_import.py` covering `GET /api/segments` list filtering, effort counts, and missing-metric counts from canonical SQLite data.
- [x] T015 [P] [US2] Add backend history tests in `GUI/backend/tests/test_garmin_segment_import.py` covering chronological effort ordering, single-effort history behavior, and `404`/`400` error semantics for invalid segment requests.

### Implementation for User Story 2

- [x] T016 [US2] Implement SQLite-backed segment list and history queries in `GUI/backend/app/segments.py` and `Sistema/views.sql` so repeated efforts can be read without duplicating query logic in the API or frontend.
- [x] T017 [US2] Add `GET /api/segments` and `GET /api/segments/{segment_id}/history` to `GUI/backend/app/main.py`, using `GUI/backend/app/segments.py` as the only source of read-model assembly.
- [x] T018 [US2] Keep the list/history payload shape aligned with `specs/002-garmin-segment-analysis/contracts/garmin-segment-analysis-api.md` by updating the response serialization in `GUI/backend/app/segments.py` and `GUI/backend/app/main.py`.
- [x] T019 [US2] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_garmin_segment_import` to validate the segment list/history slice.

**Checkpoint**: The backend exposes a minimal segment review surface with canonical history ordering and explicit missing metrics.

---

## Phase 5: User Story 3 - Compare Evolution On Relevant Metrics (Priority: P3)

**Goal**: The backend computes best effort, recent deltas, and trend readiness, while the frontend renders that analysis in a minimal read-only segment surface.

**Independent Test**: Review a segment with multiple efforts and verify the GUI shows the backend-provided best effort, recent sequence, trend status, and missing metrics without recalculating Garmin logic in React.

### Tests for User Story 3

- [x] T020 [P] [US3] Add backend trend-summary tests in `GUI/backend/tests/test_garmin_segment_import.py` covering `best_effort`, `latest_effort`, `delta_vs_best_seconds`, `delta_vs_previous_seconds`, and `trend_status` for multi-effort and single-effort segments.
- [x] T021 [P] [US3] Add backend comparison tests in `GUI/backend/tests/test_garmin_segment_import.py` covering partially missing power, cadence, and heart-rate metrics so comparison stays explicit instead of hiding efforts.

### Implementation for User Story 3

- [x] T022 [US3] Implement backend-owned segment evolution summary logic in `GUI/backend/app/segments.py` and return it from `GUI/backend/app/main.py` without moving trend interpretation into React.
- [x] T023 [US3] Extend the minimal GUI read surface in `GUI/frontend/src/App.tsx` to load the segment list and one-segment history/detail view from the new backend endpoints using backend-provided summary fields only.
- [x] T024 [P] [US3] Update `GUI/frontend/src/styles.css` only as needed to keep the new segment list, history rows, missing-metric indicators, and trend summary readable in the existing layout.
- [x] T025 [US3] Run `cd /home/jparra/Training/GUI/frontend && npm run build` to validate the thin frontend surface against the new segment API payloads.

**Checkpoint**: Segment evolution is computed in the backend and rendered through a minimal GUI read surface.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Finish contract consistency, quickstart alignment, and end-to-end validation across all stories.

- [x] T026 [P] Reconcile final field names and nullability rules across `GUI/backend/app/imports/contracts.py`, `GUI/backend/app/segments.py`, `GUI/backend/app/main.py`, and `GUI/frontend/src/App.tsx` so segment import, history, and trend payloads stay consistent.
- [x] T027 [P] Update `specs/002-garmin-segment-analysis/quickstart.md` if the concrete backend test command, frontend build command, API route names, or manual GUI review steps change during implementation.
- [x] T028 Run the full validation path from `specs/002-garmin-segment-analysis/quickstart.md`, including backend tests, `npm run build`, repeated Garmin import, SQLite inspection, and manual GUI review of one repeated cycling segment.

- [x] T029 [US1] Add Garmin segment membership fallback in `GUI/backend/app/imports/garmin_connect.py` using the activity segment list when native activity-detail efforts are absent.
- [x] T030 [US1] Reconstruct approximate segment metrics in `GUI/backend/app/imports/garmin_connect.py` from activity detail streams and segment geometry, recording reconstruction provenance in SQLite.
- [x] T031 [US1] Filter persisted activity segments to Garmin favorites and prune stale non-favorite rows for the activity in `GUI/backend/app/imports/storage.py`.
- [x] T032 Run live Garmin validation for favorite-only imports and confirm canonical SQLite rows for repeated rides in May 2026.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: starts immediately.
- **Phase 2: Foundational**: depends on Phase 1 and blocks all user stories.
- **Phase 3: US1**: depends on Phase 2 and delivers the MVP import/schema slice.
- **Phase 4: US2**: depends on Phase 2 and should build on the canonical segment records from US1.
- **Phase 5: US3**: depends on Phase 2 and should consume the read models/API payloads completed in US2.
- **Phase 6: Polish**: depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: no dependency on later stories; this is the storage and idempotent import foundation.
- **US2 (P2)**: depends on US1 because list/history queries require canonical segment definitions and efforts to exist.
- **US3 (P3)**: depends on US2 because the frontend must consume the list/history endpoints and backend summary fields rather than invent its own logic.

### Within Each User Story

- Add the focused backend tests first for the story.
- Complete canonical persistence before exposing new read endpoints.
- Complete backend summary logic before rendering it in `GUI/frontend/src/App.tsx`.
- Run the narrow executable validation for the story before moving to the next phase.

### Parallel Opportunities

- T004 and T005 can proceed in parallel after T003.
- T007 and T008 can proceed in parallel within US1.
- T014 and T015 can proceed in parallel within US2.
- T020 and T021 can proceed in parallel within US3.
- T024 and T027 can proceed in parallel once API field names are stable.

---

## Parallel Example: User Story 1

```bash
# After the foundational schema and contracts are in place:
Task: "Add backend persistence tests in GUI/backend/tests/test_garmin_segment_import.py covering a cycling activity with segment data and a cycling activity with no segment payload"
Task: "Add backend idempotency tests in GUI/backend/tests/test_garmin_segment_import.py covering repeated import of the same Garmin activity and stable segment/effort upserts"
```

---

## Parallel Example: User Story 2

```bash
# Once canonical segment rows exist:
Task: "Add backend query and endpoint tests in GUI/backend/tests/test_garmin_segment_import.py covering GET /api/segments list filtering, effort counts, and missing-metric counts"
Task: "Add backend history tests in GUI/backend/tests/test_garmin_segment_import.py covering chronological effort ordering, single-effort history behavior, and invalid segment requests"
```

---

## Parallel Example: User Story 3

```bash
# After the history endpoint payload is stable:
Task: "Add backend trend-summary tests in GUI/backend/tests/test_garmin_segment_import.py covering best effort, latest effort, deltas, and trend_status"
Task: "Update GUI/frontend/src/styles.css only as needed to keep the new segment list, history rows, missing-metric indicators, and trend summary readable"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 and validate idempotent segment persistence end to end.
3. Stop and verify cycling Garmin imports now preserve canonical segment data in SQLite.

### Incremental Delivery

1. Deliver US1 for import-time segment capture and idempotent canonical persistence.
2. Deliver US2 for backend list/history review of repeated segments.
3. Deliver US3 for backend-computed evolution summaries and the minimal GUI read surface.

### Parallel Team Strategy

1. One developer completes the schema/contracts foundation and import persistence work.
2. After US1 stabilizes, backend read-model/API work and frontend rendering can progress in parallel against the contract.

---

## Notes

- `[P]` tasks indicate different files or independently executable validation work.
- Keep SQLite as the canonical runtime source of truth for segment facts, efforts, and derived history views.
- Keep Garmin segment normalization and trend logic in backend Python code, not in `GUI/frontend/src/App.tsx`.
- Keep this feature scoped to cycling imports and the minimal GUI read surface; do not add automatic markdown updates.