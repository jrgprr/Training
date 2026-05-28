# Tasks: AI Training Assessment Agents

**Input**: Design documents from `/specs/004-ai-training-assessment/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ai-training-assessment-api.md, quickstart.md

**Tests**: Include focused backend `unittest` coverage and frontend `npm run build` validation because this feature depends on canonical SQLite persistence, explicit run statuses, proposal approval boundaries, and thin review surfaces.

**Organization**: Tasks are grouped by user story after shared setup and foundational work so specialist LLM profiles, canonical SQLite storage, approval-gated proposals, and thin frontend review surfaces can be implemented and validated incrementally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when tasks touch different files and have no direct dependency.
- **[Story]**: `US1`, `US2`, or `US3` maps each task to a user story from the specification.
- Each task names the exact file paths to change or the exact validation command to run.

## Phase 1: Setup (Shared Context)

**Purpose**: Lock the implementation to the approved local-first, backend-owned scope before changing schema, orchestration, or review surfaces.

- [ ] T001 Confirm the feature boundary, v1 specialist-agent roster, SQLite source-of-truth rule, thin-frontend rule, and approval-gated mutation rule in `specs/004-ai-training-assessment/spec.md`, `specs/004-ai-training-assessment/plan.md`, `specs/004-ai-training-assessment/research.md`, and `specs/004-ai-training-assessment/contracts/ai-training-assessment-api.md`.
- [ ] T002 Identify the concrete implementation surface in `Sistema/schema.sql`, `Sistema/views.sql`, `GUI/backend/app/db.py`, `GUI/backend/app/main.py`, `GUI/backend/app/activity_quality.py`, `GUI/backend/app/segments.py`, `GUI/backend/tests/`, `GUI/frontend/src/App.tsx`, `GUI/frontend/src/styles.css`, and `Agentes/README.md`.
- [ ] T003 [P] Document the planned backend-owned module split and local provider configuration boundary in `Agentes/README.md` and `GUI/backend/README.md` so implementation stays local-first and keeps prompt logic out of the frontend.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Put canonical SQLite tables, shared orchestration types, and provider-agnostic backend services in place before any user story work begins.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [x] T004 Update `Sistema/schema.sql` and `GUI/backend/app/db.py` to create the canonical assessment tables for profiles, windows, runs, type results, findings, proposals, proposal decisions, accepted plan mutations, and bounded dialog context with cadence and target-level constraints.
- [ ] T005 [P] Extend `Sistema/views.sql` with thin read models for latest cadence summaries, assessment detail, proposal review queues, decision history, and accepted-mutation traceability.
- [x] T006 [P] Create `GUI/backend/app/ai_assessment_models.py` for shared enums, Pydantic request/response models, and serialization helpers covering cadences, run statuses, finding kinds, proposal states, decision payloads, and assessment dialog entries.
- [x] T007 [P] Create `GUI/backend/app/ai_profiles.py` and update `Agentes/README.md` with the v1 specialist profile registry (`daily_execution_v1`, `daily_recovery_readiness_v1`, `weekly_adherence_adequacy_v1`, `block_performance_direction_v1`) plus season-capable cadence metadata.
- [x] T008 Create `GUI/backend/app/ai_gateway.py` for provider-agnostic LLM invocation, prompt/instruction version provenance, timeout handling, and explicit failed/incomplete run recording.
- [ ] T009 Create `GUI/backend/app/ai_context.py` and `GUI/backend/app/ai_assessments.py` for cadence window resolution, evidence fingerprinting, deduplication, rerun handling, and backend-owned context assembly from plan, activity, recovery, quality, segment, and review data.
- [ ] T010 Wire the shared assessment services into `GUI/backend/app/main.py` and `GUI/backend/app/db.py` so later story work reuses one API boundary, one persistence boundary, and one error-handling path.

**Checkpoint**: Canonical schema, shared models, LLM gateway, and orchestration foundations are ready for story implementation.

---

## Phase 3: User Story 1 - Daily Athlete Evolution Assessment (Priority: P1) 🎯 MVP

**Goal**: Deliver daily specialist assessments that persist traceable findings, confidence, and bounded next-step guidance from canonical SQLite context.

**Independent Test**: Trigger a daily assessment for a day with plan, activity, and recovery context and confirm the backend persists one traceable daily run with summary, findings, confidence, and explicit `completed`, `partial_context`, or `no_new_data` status.

### Tests for User Story 1

- [ ] T011 [P] [US1] Add daily-run tests in `GUI/backend/tests/test_ai_assessment_agents.py` covering manual trigger, completed daily execution output, and bounded no-activity daily assessments.
- [ ] T012 [P] [US1] Add daily deduplication and failure tests in `GUI/backend/tests/test_ai_assessment_agents.py` covering evidence fingerprint changes, `no_new_data`, `partial_context`, and `failed` run persistence.

### Implementation for User Story 1

- [ ] T013 [US1] Implement daily context assembly in `GUI/backend/app/ai_context.py` using canonical plan, activity, recovery, activity-quality, and segment surfaces from `GUI/backend/app/activity_quality.py` and `GUI/backend/app/segments.py`.
- [ ] T014 [US1] Implement the Daily Execution Agent and Daily Recovery And Readiness Agent flows in `GUI/backend/app/ai_profiles.py`, `GUI/backend/app/ai_gateway.py`, and `GUI/backend/app/ai_assessments.py`.
- [ ] T015 [US1] Persist daily assessment type results, grouped findings, confidence labels, evidence summaries, and bounded next-step guidance in `GUI/backend/app/ai_assessments.py` and `GUI/backend/app/ai_assessment_models.py`.
- [ ] T016 [US1] Extend `GUI/backend/app/main.py` to support `POST /api/assessments/runs` and `GET /api/assessments/runs/{assessment_run_id}` for the daily specialist-agent slice defined in `specs/004-ai-training-assessment/contracts/ai-training-assessment-api.md`.
- [ ] T017 [US1] Run the daily backend validation from `specs/004-ai-training-assessment/quickstart.md` with `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_ai_assessment_agents`.

**Checkpoint**: Daily assessment runs are traceable, bounded on sparse data, and reviewable through the backend API without mutating the plan.

---

## Phase 4: User Story 2 - Multi-Cadence Review With Adaptation Proposals (Priority: P2)

**Goal**: Add weekly and block specialist assessments, season-capable cadence support, and explicit proposal workflows that target the next planning level without mutating SQLite plan state until approval.

**Independent Test**: Trigger daily, weekly, and block assessments for valid windows and confirm each can persist independent runs plus reviewable proposals, while proposal approval is the only path that records a canonical plan mutation.

### Tests for User Story 2

- [ ] T018 [P] [US2] Add multi-cadence orchestration tests in `GUI/backend/tests/test_ai_assessment_agents.py` covering weekly runs, block runs, season-capable window validation, and concurrent profile runs for the same window.
- [ ] T019 [P] [US2] Add proposal workflow and contract tests in `GUI/backend/tests/test_ai_assessment_agents.py` covering proposal emission, cadence-to-target boundary validation, `GET /api/assessments/latest`, `GET /api/proposals`, `GET /api/proposals/{proposal_id}`, `POST /api/proposals/{proposal_id}/decision`, and bounded assessment-dialog persistence.

### Implementation for User Story 2

- [ ] T020 [US2] Extend `GUI/backend/app/ai_profiles.py` and `GUI/backend/app/ai_assessments.py` with the Weekly Adherence And Adequacy Agent and Block Performance Direction Agent plus season-capable cadence/window support aligned to `specs/004-ai-training-assessment/data-model.md`.
- [ ] T021 [US2] Create `GUI/backend/app/ai_proposals.py` and update `GUI/backend/app/ai_assessment_models.py` so specialist agents can emit proposals directly with conflict-group keys, source cadence, target planning level, and preserved concurrent proposal history.
- [ ] T022 [US2] Implement approval-gated canonical plan mutation tracing in `GUI/backend/app/ai_proposals.py`, `Sistema/schema.sql`, and `Sistema/views.sql` so accepted proposals update SQLite planning state first and never mutate markdown.
- [ ] T023 [US2] Extend `GUI/backend/app/main.py` to expose `GET /api/assessments/latest`, `GET /api/proposals`, `GET /api/proposals/{proposal_id}`, and `POST /api/proposals/{proposal_id}/decision` using backend-owned validation and status transitions.
- [ ] T024 [US2] Keep payload shape and manual validation aligned by updating `specs/004-ai-training-assessment/contracts/ai-training-assessment-api.md` and `specs/004-ai-training-assessment/quickstart.md` if concrete response fields or decision semantics shift during implementation.
- [ ] T025 [US2] Run the multi-cadence backend validation from `specs/004-ai-training-assessment/quickstart.md` with `cd /home/jparra/Training/GUI/backend && source /home/jparra/Training/.venv/bin/activate && PYTHONPATH=. python -m unittest tests.test_ai_assessment_agents` plus targeted SQLite assertions for proposals and decisions.

**Checkpoint**: Daily, weekly, and block specialist runs can emit reviewable proposals, season support exists in the canonical model, and only approved decisions can record plan mutations.

---

## Phase 5: User Story 3 - Coach Control And Traceability Of AI Recommendations (Priority: P3)

**Goal**: Provide thin review surfaces that show assessment provenance, grouped findings, proposal state, and operator decisions without moving coaching logic into the frontend.

**Independent Test**: Open the application, review a persisted assessment and proposal, and confirm the UI exposes supporting evidence, producing agent profile, proposal status, and approval actions while the canonical plan remains unchanged until acceptance.

### Tests for User Story 3

- [ ] T026 [P] [US3] Add review-read-model tests in `GUI/backend/tests/test_ai_assessment_agents.py` covering grouped findings, principal evidence summaries, conflicting proposals, decision history, and unchanged-plan behavior for pending proposals.

### Implementation for User Story 3

- [ ] T027 [US3] Extend `GUI/backend/app/main.py` and `GUI/backend/app/ai_assessments.py` so assessment detail, latest cadence summaries, proposal provenance, and decision history are returned in review-friendly payloads with no frontend inference.
- [ ] T028 [US3] Update `GUI/frontend/src/App.tsx` and `GUI/frontend/src/main.tsx` to render cadence summary lists, assessment detail panels, bounded dialog/clarification surfaces, pending proposal review, and approve/reject actions using backend-provided fields only.
- [ ] T029 [P] [US3] Update `GUI/frontend/src/styles.css` to keep assessment cards, evidence groups, proposal status rows, and operator decision controls readable in the existing minimal interface.
- [ ] T030 [US3] Run the frontend validation from `specs/004-ai-training-assessment/quickstart.md` with `cd /home/jparra/Training/GUI/frontend && npm run build`.

### Tests for User Story 4

- [ ] T030a [P] [US3] Add bounded-dialog tests in `GUI/backend/tests/test_ai_assessment_agents.py` covering persisted clarifications, reassessment requests, and refusal to mutate canonical records directly from dialog input.

### Implementation for User Story 4

- [ ] T030b [US3] Extend `GUI/backend/app/main.py`, `GUI/backend/app/ai_assessment_models.py`, and supporting assessment services to persist bounded dialog context and optional reassessment requests for an assessment run.

**Checkpoint**: Operators can review and act on AI assessments and proposals through thin application surfaces without hidden plan mutation or frontend-owned domain logic.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Finish contract consistency, local-first documentation, and end-to-end validation across all stories.

- [ ] T031 [P] Reconcile final field names, enum values, and nullability across `GUI/backend/app/ai_assessment_models.py`, `GUI/backend/app/main.py`, `GUI/frontend/src/App.tsx`, and `specs/004-ai-training-assessment/contracts/ai-training-assessment-api.md`.
- [ ] T032 [P] Update `Agentes/README.md`, `GUI/backend/README.md`, and `GUI/frontend/README.md` with the local-first operator workflow, provider configuration expectations, specialist-agent roster, and approval boundary for canonical plan mutations.
- [ ] T033 Add end-to-end quickstart coverage in `GUI/backend/tests/test_ai_assessment_agents.py` and `specs/004-ai-training-assessment/quickstart.md` for manual trigger, bounded dialog clarification, `no_new_data` rerun behavior, proposal approval, and SQLite inspection.
- [ ] T034 Run the full validation path from `specs/004-ai-training-assessment/quickstart.md`, including backend `unittest`, frontend build, trigger/review API commands, and SQLite inspection against `Sistema/training.sqlite`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: starts immediately.
- **Phase 2: Foundational**: depends on Phase 1 and blocks all user stories.
- **Phase 3: US1**: depends on Phase 2 and delivers the MVP daily specialist-assessment slice.
- **Phase 4: US2**: depends on US1 because proposal workflows and multi-cadence orchestration build on the shared run, finding, and evidence foundations already proven by the daily slice.
- **Phase 5: US3**: depends on US1 and US2 because the thin review UI must consume the stabilized backend assessment and proposal payloads.
- **Phase 6: Polish**: depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: no dependency on later stories; this is the MVP and should be completed first.
- **US2 (P2)**: depends on US1 because proposal persistence and approval flow reuse the canonical run/finding model and daily-trigger pathway.
- **US3 (P3)**: depends on US1 and US2 because operator review surfaces require stable summary, detail, proposal, and decision payloads.

### Within Each User Story

- Add the focused backend tests first for the story.
- Stabilize canonical persistence and orchestration before extending API read surfaces.
- Stabilize backend payloads before touching `GUI/frontend/src/App.tsx`.
- Run the narrow executable validation for the story before moving to the next phase.

### Parallel Opportunities

- T003 can run in parallel with T001-T002 once the scope is understood.
- T005, T006, and T007 can run in parallel after T004.
- T011 and T012 can run in parallel within US1.
- T018 and T019 can run in parallel within US2.
- T028 and T029 can run in parallel within US3 after backend payloads are stable.
- T031 and T032 can run in parallel during polish.

---

## Parallel Example: User Story 1

```bash
# After the foundational schema and shared services are in place:
Task: "Add daily-run tests in GUI/backend/tests/test_ai_assessment_agents.py covering manual trigger and bounded no-activity daily assessments"
Task: "Add daily deduplication and failure tests in GUI/backend/tests/test_ai_assessment_agents.py covering no_new_data, partial_context, and failed run persistence"
```

---

## Parallel Example: User Story 2

```bash
# Once the daily orchestration path is working:
Task: "Add multi-cadence orchestration tests in GUI/backend/tests/test_ai_assessment_agents.py covering weekly runs, block runs, and concurrent profile runs"
Task: "Add proposal workflow and contract tests in GUI/backend/tests/test_ai_assessment_agents.py covering GET /api/assessments/latest, GET /api/proposals, and POST /api/proposals/{proposal_id}/decision"
```

---

## Parallel Example: User Story 3

```bash
# After backend review payloads are stable:
Task: "Update GUI/frontend/src/App.tsx and GUI/frontend/src/main.tsx to render cadence summaries, assessment detail, and proposal actions"
Task: "Update GUI/frontend/src/styles.css to keep assessment cards, evidence groups, and proposal status rows readable"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 and validate daily specialist assessments end to end.
3. Stop and verify deduplication, sparse-data handling, and explicit failure states before adding proposal workflows.

### Incremental Delivery

1. Deliver US1 for daily assessment visibility and traceable persistence.
2. Deliver US2 for multi-cadence reviews and approval-gated proposals.
3. Deliver US3 for thin operator review and decision surfaces.

### Parallel Team Strategy

1. One developer completes schema, shared models, and gateway foundations.
2. After US1 stabilizes, one developer can extend backend proposal flows while another builds the thin frontend review surfaces against the contract.

---

## Notes

- `[P]` tasks indicate different files or independently executable validation work.
- Keep SQLite in `Sistema/training.sqlite` as the only canonical runtime store for runs, findings, proposals, decisions, and accepted plan mutations.
- Keep prompt logic, cadence selection, context assembly, proposal validation, and approval application in backend Python modules under `GUI/backend/app/`.
- Keep `GUI/frontend/src/App.tsx` as a thin reader/action layer that renders backend-provided state only.
- Keep markdown planning files as human-maintained context; do not add automatic markdown mutation as part of this feature.