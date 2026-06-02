# Tasks: Training Zones

**Input**: Design documents from `/specs/004-training-zones/`

**Prerequisites**: plan.md, spec.md, research.md

**Tests**: Include focused backend validation and frontend build validation because the feature depends on independently verifiable heart-rate and power profiles, deterministic executed zone calculations, traceable refinement proposals, and backend-owned plan-versus-reality summaries.

**Organization**: Tasks are grouped by user story after shared setup and foundation work so canonical SQLite storage, backend zone logic, refinement governance, comparison read models, and thin frontend visibility can be delivered incrementally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when tasks touch different files and have no direct dependency.
- **[Story]**: `US1`, `US2`, `US3`, or `US4` maps each task to a user story from the specification.
- Each task names the exact file paths to change or the exact command to run.

## Phase 1: Setup (Shared Context)

**Purpose**: Lock the implementation to the approved scope before changing schema, backend services, or GUI read models.

- [x] T001 Confirm the source-of-truth boundary, dual-basis requirement (`heart rate` and `power`), daily-metrics-as-context rule, and thin-GUI contract in `specs/004-training-zones/spec.md`, `specs/004-training-zones/research.md`, and `specs/004-training-zones/plan.md`.
- [x] T002 Identify the concrete implementation surface in `Sistema/schema.sql`, `Sistema/views.sql`, `GUI/backend/app/db.py`, `GUI/backend/app/main.py`, `GUI/backend/app/imports/contracts.py`, `GUI/backend/app/imports/garmin_connect.py`, `GUI/backend/app/imports/storage.py`, `GUI/backend/tests/`, and `GUI/frontend/src/App.tsx`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Put canonical SQLite and backend zone-model foundations in place before story work begins.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [x] T003 Update `Sistema/schema.sql` and `GUI/backend/app/db.py` so SQLite initializes and migrates canonical tables for zone profiles, zone profile boundaries, executed activity zone distributions, refinement proposals, refinement evidence, and optional planned zone targets.
- [x] T004 [P] Add or extend zone-oriented read models in `Sistema/views.sql` for active profile lookup, basis-specific activity zone summaries, pending refinement proposals, and week-level plan-versus-reality summaries. Status: `views.sql` now defines `vw_zone_active_profile_lookup`, `vw_exec_activity_zone_summary`, `vw_zone_pending_refinement_proposals`, and `vw_zone_week_comparison_summary`, and the SQL loads cleanly in SQLite.
- [x] T005 [P] Create `GUI/backend/app/training_zones.py` with shared backend-owned helpers for active profile selection, basis-specific zone-bucket calculation, proposal assembly, and serialized read models. Status: `training_zones.py` now centralizes active profile selection, accepted-profile persistence, executed-zone persistence, proposal generation and acceptance, planned-target extraction, session/week comparison assembly, and serialized read models for activities and proposals.
- [x] T006 [P] Extend `GUI/backend/app/imports/contracts.py` and `GUI/backend/app/imports/garmin_connect.py` only as needed to guarantee the canonical heart-rate and power inputs required by executed zone calculation. Status: `NormalizedActivity` already carries canonical `avg_hr`, `max_hr`, `avg_power`, `normalized_power`, and `metric_readings`, and the Garmin adapter already maps both summary-level and stream-level heart-rate/power inputs into those fields.
- [x] T007 Wire the shared zone helpers into `GUI/backend/app/main.py` and `GUI/backend/app/imports/storage.py` so later story work reuses one canonical calculation and persistence boundary. Status: current profile read endpoint, activity zone detail endpoint, compact season-activity zone summaries, and proposal list/detail endpoints are wired in `main.py`, `persist_batch()` persists executed zone results, and replay-time quality reevaluation refreshes persisted zone results through the same backend boundary.

**Checkpoint**: SQLite schema, views, shared contracts, and backend zone helpers are ready for story implementation.

---

## Phase 3: User Story 1 - Calculate Executed Time In Zone From Real Activities (Priority: P1) 🎯 MVP

**Goal**: Persist per-activity heart-rate and power zone distributions from real Garmin activities using accepted active profiles.

**Independent Test**: Process cycling activities with suitable heart-rate and power evidence and verify that SQLite persists basis-specific zone time distributions, profile-version traceability, and limited status when one basis is unavailable.

### Tests for User Story 1

- [x] T008 [P] [US1] Add backend tests in `GUI/backend/tests/test_training_zones.py` covering active profile lookup, heart-rate zone calculation, power zone calculation, and basis-limited outcomes. Status: the suite now covers active profile lookup, activity-zone detail reads, calculated heart-rate persistence, calculated power persistence, unavailable power persistence, explicit `insufficient_power_samples` limitation, a real `limited` no-bucket case, and replay refresh behavior.
- [x] T009 [P] [US1] Add backend persistence tests in `GUI/backend/tests/test_training_zones.py` covering per-activity storage of heart-rate and power zone distributions plus profile-version traceability. Status: the suite verifies persisted heart-rate and power distributions and preserves accepted `zone_profile_id` traceability for both bases.

### Implementation for User Story 1

- [x] T010 [US1] Implement canonical zone profile and boundary persistence in `GUI/backend/app/training_zones.py` and `GUI/backend/app/imports/storage.py` so accepted heart-rate and power profiles can be created and looked up by discipline and date. Status: accepted profile helpers now persist canonical profile rows plus boundaries, automatically close superseded accepted profiles, and resolve active lookup by normalized discipline and activity date.
- [x] T011 [US1] Implement executed zone calculation in `GUI/backend/app/training_zones.py` so eligible activities produce separate heart-rate and power zone distributions with basis-specific limited status when needed. Status: executed-zone persistence now calculates and stores separate `heart_rate` and `power` results with deterministic bucketization, `calculated`/`limited`/`unavailable` states, stale-result replacement, and explicit limiting reasons such as `missing_*_stream`, `insufficient_power_samples`, and `no_bucketed_samples`.
- [x] T012 [US1] Extend `GUI/backend/app/imports/storage.py` and `GUI/backend/app/main.py` so import-time or replay-time zone calculations persist executed distributions and expose them through activity-level backend responses. Status: activity-level zone read endpoint exists, season activity lists expose compact `zone_summary` payloads, import-time persistence is wired through `persist_batch()`, and replay-time persistence is wired through `replay_activity_quality()`.
- [x] T013 [US1] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_training_zones` to validate the executed-zone slice. Status: `tests.test_training_zones` passes with the focused foundation, profile-read, activity-zone-read, season-activity summary read, accepted-profile persistence, import-time persistence, replay-time persistence, calculated power persistence, and limited-status coverage in place.

**Checkpoint**: Activities persist canonical heart-rate and power zone distributions tied to accepted profile versions.

---

## Phase 4: User Story 2 - Refine Zone Definitions From Evidence Over Time (Priority: P1)

**Goal**: Generate traceable heart-rate and power zone refinement proposals from recent activity evidence plus daily-metric context without overwriting active profiles automatically.

**Independent Test**: Provide recent activities and daily metrics that support a zone shift, verify proposal generation for the relevant basis, and confirm accepted active profiles remain unchanged until explicitly applied.

### Tests for User Story 2

- [x] T014 [P] [US2] Add backend tests in `GUI/backend/tests/test_training_zones.py` covering proposal generation for heart rate, proposal generation for power, deferred proposals under poor recovery context, and no-op behavior when evidence is insufficient. Status: the suite now covers pending heart-rate proposals, pending power proposals, deferred proposals under low-sleep/high-stress/low-body-battery context, and no-op behavior when evidence is too thin.
- [x] T015 [P] [US2] Add backend governance tests in `GUI/backend/tests/test_training_zones.py` covering pending proposal persistence, explicit acceptance, and historical profile-version preservation after acceptance. Status: the suite now verifies proposal acceptance through the backend endpoint, accepted-profile creation from proposal boundaries, previous-profile closure, and `derived_from_proposal_id` traceability.

### Implementation for User Story 2

- [x] T016 [US2] Implement refinement proposal generation in `GUI/backend/app/training_zones.py` using recent activities plus `exec_daily_metrics` context to support confidence, prudence, and rationale. Status: the backend now proposes Z2-boundary refinements from recent calculated activity evidence, stores basis-specific proposal boundaries and evidence rows, and downgrades or defers proposals when recovery context is poor.
- [x] T017 [US2] Extend `GUI/backend/app/main.py` with backend endpoints or actions for listing pending refinement proposals, inspecting proposal evidence, and accepting an approved proposal into a new active heart-rate or power profile version. Status: list/detail endpoints remain in place and the backend now exposes proposal acceptance through `POST /api/zone-proposals/{proposal_id}/accept`.
- [x] T018 [US2] Extend `Sistema/views.sql` and `GUI/backend/app/training_zones.py` so proposal read models clearly distinguish heart-rate proposals, power proposals, and mixed-basis review states. Status: `views.sql` now defines `vw_zone_proposal_review_states`, and `list_zone_proposals()` now returns `review_state` plus `basis_summary` so callers can distinguish `heart_rate_only`, `power_only`, `mixed_basis`, and `no_actionable_proposals` states while preserving per-proposal `metric_basis` rows.
- [x] T019 [US2] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_training_zones` to validate the refinement-governance slice. Status: the focused backend suite passes with 25 tests.

**Checkpoint**: Refinement proposals are traceable, basis-specific, confidence-aware, and non-destructive.

---

## Phase 5: User Story 3 - Compare Planned Zones Versus Executed Zones (Priority: P2)

**Goal**: Summarize planned-versus-executed zone alignment at session and week level, distinguishing heart-rate and power views when both exist.

**Independent Test**: Review a week with explicit planned zone targets and imported activities, then verify backend responses expose comparable planned-versus-executed summaries for the available bases.

### Tests for User Story 3

- [x] T020 [P] [US3] Add backend tests in `GUI/backend/tests/test_training_zones.py` covering session-level zone comparison, week-level zone comparison, and limited comparison states when one basis is missing. Status: the suite now covers aligned session comparison, limited comparison when a planned power target lacks power execution results, and week endpoint exposure of session comparison payloads.
- [x] T021 [P] [US3] Add backend read-model tests in `GUI/backend/tests/test_training_zones.py` covering distinction between heart-rate-based and power-based comparison summaries. Status: the suite now verifies week summary aggregation keeps `heart_rate` and `power` counts separate.

### Implementation for User Story 3

- [x] T022 [US3] Implement planned-versus-executed comparison assembly in `GUI/backend/app/training_zones.py` and `Sistema/views.sql` so week/session summaries can compare explicit plan targets against executed heart-rate and power distributions. Status: backend-owned session and week comparison helpers now assemble comparison state from structured plan targets and executed zone results, and `views.sql` exposes matching session/week SQLite views.
- [x] T023 [US3] Extend `GUI/backend/app/main.py` so existing season/week/activity responses can expose thin zone comparison payloads without moving domain logic into the frontend. Status: `/api/weeks/{week_id}/plan-vs-real` rows now include `zone_comparison`, and `/api/weeks/{week_id}/review` now exposes `zone_comparison_summary`.
- [x] T024 [US3] Run `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_training_zones` to validate the comparison slice. Status: the focused backend suite passes with 28 tests.

**Checkpoint**: Session and week review can compare planned zone intent against executed heart-rate and power distributions.

---

## Phase 6: User Story 4 - Represent Planned Training Zones In The System (Priority: P3)

**Goal**: Persist structured planned zone targets only where the plan explicitly contains them or where an approved mapping rule can extract them.

**Independent Test**: Load planned sessions containing explicit zone prescriptions and verify SQLite plus backend responses expose ordered structured plan targets without inventing missing zones.

### Tests for User Story 4

- [x] T025 [P] [US4] Add backend tests in `GUI/backend/tests/test_training_zones.py` covering explicit single-zone targets, multi-segment planned targets, and sessions with no extractable zone target. Status: the suite now covers derived single-zone targets, derived multi-segment targets from prescription text, no-op behavior when no explicit zone exists, and endpoint exposure through planned-session surfaces.

### Implementation for User Story 4

- [x] T026 [US4] Extend plan-side extraction and persistence in `GUI/backend/app/training_zones.py`, `Sistema/schema.sql`, and any relevant seed or read-model layer so explicit planned zone targets are stored structurally alongside the narrative prescription. Status: `training_zones.py` now derives explicit targets from planned-session/prescription text when no structured row exists yet, persists them into `plan_session_zone_targets` and `plan_session_zone_segments`, and reuses persisted rows on later reads; no schema change was needed because the canonical tables already existed.
- [x] T027 [US4] Extend `GUI/backend/app/main.py` so planned sessions can expose structured zone targets for later comparison without making the planned layer the primary source of zone boundaries. Status: `/api/weeks/{week_id}/sessions` rows and `/api/planned-sessions/{planned_session_id}/prescription` now include `planned_zone_target`.

**Checkpoint**: Explicit planned zone targets are available structurally as a secondary comparison layer.

---

## Phase 7: Frontend Visibility & Polish

**Purpose**: Keep the GUI thin while making the new backend-owned zone information readable and validating the full slice.

- [x] T028 [P] Extend `GUI/frontend/src/App.tsx` to display activity-level heart-rate and power zone summaries, pending refinement proposal state, and week/session zone comparison payloads using backend-provided fields only. Status: sessions and prescription detail now render `planned_zone_target`, weekly comparison rows render `zone_comparison`, weekly review surfaces `zone_comparison_summary`, and the season activity area shows pending refinement proposals.
- [x] T029 [P] Update `GUI/frontend/src/styles.css` only as needed to keep zone chips, basis labels, proposal summaries, and limited-state messaging readable in the existing layout. Status: added lightweight proposal cards, target/comparison chips, and weekly zone summary styling without changing the existing layout structure.
- [x] T030 Reconcile final field names and nullability across `GUI/backend/app/training_zones.py`, `GUI/backend/app/main.py`, and `GUI/frontend/src/App.tsx` so basis-specific payloads stay consistent. Status: frontend types now match backend payload names and nullability for `planned_zone_target`, `zone_comparison`, `zone_comparison_summary`, and proposal list items.
- [x] T031 Run `cd /home/jparra/Training/GUI/frontend && npm run build` to validate the thin frontend surface against the new zone payloads. Status: `npm run build` passed.
- [x] T032 Run the full validation path: `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_training_zones` plus targeted SQLite inspection and manual backend/API smoke checks for executed zones, proposals, and comparison summaries. Status: backend suite passed; `initialize_database()` was applied to `Sistema/training.sqlite`, live inspection now shows `plan_session_zone_targets` and `plan_session_zone_segments`, week `101` materialized 3 planned targets/3 segments through the API, `/api/weeks/101/sessions`, `/api/weeks/101/plan-vs-real`, `/api/weeks/101/review`, and `/api/seasons/2026/zone-proposals?discipline=cycling` returned `200`, and `/api/activities/900186/zones` returned the expected `404` when no executed zone results exist yet.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: starts immediately.
- **Phase 2: Foundational**: depends on Phase 1 and blocks all user stories.
- **Phase 3: US1**: depends on Phase 2 and delivers the MVP executed-zone slice.
- **Phase 4: US2**: depends on US1 because refinement requires persisted basis-specific executed zone results and active profiles.
- **Phase 5: US3**: depends on US1 and can begin before US2 completes if profile selection and executed distributions are stable.
- **Phase 6: US4**: depends on Phase 2 and can proceed after the comparison model is clear, but remains secondary to US1 and US2.
- **Phase 7: Frontend Visibility & Polish**: depends on the desired backend stories being complete.

### User Story Dependencies

- **US1 (P1)**: no dependency on later stories; this is the canonical execution foundation.
- **US2 (P1)**: depends on US1 because refinement proposals require accepted profiles and recent executed zone evidence.
- **US3 (P2)**: depends on US1 for executed distributions and on US4 only where explicit planned targets exist.
- **US4 (P3)**: independent of US2 and mostly independent of US1, but operationally secondary.

### Within Each User Story

- Add the focused backend tests first for the story.
- Stabilize canonical persistence before extending route payloads.
- Stabilize backend payloads before rendering them in `GUI/frontend/src/App.tsx`.
- Run the narrow executable validation for the story before moving to the next phase.

### Parallel Opportunities

- T004, T005, and T006 can proceed in parallel after T003.
- T008 and T009 can proceed in parallel within US1.
- T014 and T015 can proceed in parallel within US2.
- T020 and T021 can proceed in parallel within US3.
- T028 and T029 can proceed in parallel once backend payloads are stable.

---

## Parallel Example: User Story 1

```bash
# After the foundational schema and shared service are in place:
Task: "Add backend tests in GUI/backend/tests/test_training_zones.py covering active profile lookup, heart-rate zone calculation, and power zone calculation"
Task: "Add backend persistence tests in GUI/backend/tests/test_training_zones.py covering basis-specific executed zone distributions and profile-version traceability"
```

---

## Parallel Example: User Story 2

```bash
# Once executed zone results are canonical:
Task: "Add backend tests in GUI/backend/tests/test_training_zones.py covering proposal generation for heart rate and power"
Task: "Add backend governance tests in GUI/backend/tests/test_training_zones.py covering pending proposal persistence and explicit acceptance"
```

---

## Parallel Example: User Story 3

```bash
# After the backend comparison payload is stable:
Task: "Extend GUI/frontend/src/App.tsx to display activity-level heart-rate and power zone summaries"
Task: "Update GUI/frontend/src/styles.css only as needed to keep zone chips, basis labels, and proposal summaries readable"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 and validate canonical heart-rate and power zone distributions end to end.
3. Stop and verify basis-specific persistence and profile-version traceability before extending refinement or comparison work.

### Incremental Delivery

1. Deliver US1 for canonical executed zone calculation.
2. Deliver US2 for traceable dual-basis refinement proposals.
3. Deliver US3 for plan-versus-reality comparison.
4. Deliver US4 for structured planned zone targets as a secondary layer.

### Parallel Team Strategy

1. One developer completes the schema/shared-service foundation and executed zone persistence work.
2. After US1 stabilizes, refinement-governance work and planned-target extraction can progress in parallel.
3. Frontend visibility starts only once the backend payloads are stable.

---

## Notes

- `[P]` tasks indicate different files or independently executable validation work.
- Keep SQLite as the canonical runtime source of truth for heart-rate zones, power zones, executed distributions, and refinement governance.
- Keep zone logic in backend Python code and SQLite-backed read models, not in `GUI/frontend/src/App.tsx`.
- Keep heart-rate and power zones as first-class, separate bases throughout schema, APIs, and refinement logic.
- Keep daily metrics as contextual support for refinement prudence, not as autonomous generators of zone boundaries.
- Keep planned zones as secondary support for comparison rather than the primary source of zone definitions.