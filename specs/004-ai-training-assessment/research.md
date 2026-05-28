# Research: AI Training Assessment Agents

## Decision 1: Use backend-owned specialist agent profiles, not one generic assessment prompt

- Decision: Model the feature around explicit agent profiles with cadence and purpose metadata, starting with the v1 roster from the spec: Daily Execution, Daily Recovery And Readiness, Weekly Adherence And Adequacy, and Block Performance Direction.
- Rationale: The spec requires multiple specialized LLM-based profiles and allows more than one profile per cadence. Backend-owned profiles keep prompt logic and execution policy out of the frontend while making persisted provenance clear.
- Alternatives considered:
  - One generic assessment agent with a `cadence` parameter: rejected because it weakens provenance and makes profile-level specialization, testing, and rollout control harder.
  - Separate proposal-only agent: rejected because the spec explicitly requires specialist assessment agents to emit proposals directly when justified.

## Decision 2: Persist cadence windows and run fingerprints so unchanged evidence yields `no_new_data` or reused outcomes instead of duplicate substantive assessments

- Decision: Define a canonical assessment window identity based on cadence, window bounds, subject scope, selected agent profile, and a backend-computed evidence fingerprint derived from relevant SQLite rows.
- Rationale: The spec requires avoiding duplicate assessments when nothing changed while still preserving rerun history. A persisted window plus evidence fingerprint allows the backend to distinguish `no_new_data`, explicit rerun, and genuinely new evidence.
- Alternatives considered:
  - Deduplicate only by date window: rejected because source evidence can change inside the same window after imports or review edits.
  - Always create a new assessment run on every trigger: rejected because it would generate redundant AI commentary and violate FR-014 / SC-005.

## Decision 3: Keep assessment context assembly deterministic and local in backend services, with SQLite as the only runtime source of athlete state

- Decision: Assemble LLM context from canonical plan, execution, recovery, activity quality, segment history, and review tables in backend services, and persist both the resolved analysis window and the principal evidence references used by each run.
- Rationale: The constitution and spec both require SQLite as the runtime source of truth and the GUI to remain thin. Deterministic context assembly also makes runs explainable and replayable.
- Alternatives considered:
  - Read markdown planning files directly during runtime assessment: rejected because markdown is a human view and would create dual runtime truth.
  - Let the frontend shape assessment payloads: rejected because domain and prompt logic must stay out of the view layer.

## Decision 4: Separate assessment runs, structured findings, and adaptation proposals as related but independent records

- Decision: Persist one LLM assessment run per agent-profile/window execution, store structured findings as child records grouped by assessment type, and store proposals as separate reviewable records linked back to their source run.
- Rationale: The spec requires traceability, multiple findings per run, and concurrent proposals that may conflict. Separate tables keep descriptive analysis and approval-governed plan-change suggestions distinct.
- Alternatives considered:
  - Store findings and proposals inline as one JSON blob on the assessment run: rejected because it weakens querying, approval workflow, and conflict review.
  - Collapse all same-cadence runs into one synthesized assessment row: rejected because the spec requires multiple profiles in the same cadence to persist independently.

## Decision 5: Proposal approval mutates SQLite planning state only through an explicit backend approval workflow

- Decision: Treat proposals as pending records until an operator accepts, rejects, or supersedes them, and apply accepted changes through a backend approval action that records the resulting plan mutation linkage.
- Rationale: The spec explicitly forbids silent canonical plan mutation and requires accepted changes to remain traceable to both the source assessment and the operator decision.
- Alternatives considered:
  - Allow the LLM run to update plan tables directly: rejected because it violates the approval rule and reduces auditability.
  - Keep proposals as comments only with no structured approval state: rejected because the GUI needs stable review surfaces and canonical proposal state.

## Decision 6: Expose a thin API surface organized around runs, latest cadence summaries, proposals, and approval actions

- Decision: Add backend APIs for triggering cadence runs, listing latest assessments by cadence/profile, retrieving assessment detail with evidence summaries, listing proposals, and recording operator decisions.
- Rationale: The existing app is already a local FastAPI + React/Vite system. A small, backend-owned API surface preserves the thin frontend model and supports both manual triggering and future scheduling.
- Alternatives considered:
  - Make the frontend call the LLM directly: rejected because it breaks traceability and local-first governance.
  - Build only a CLI surface first: rejected because the spec requires an application review surface for assessments and proposals.

## Decision 7: Store provider/model metadata and failure state on every LLM run, but keep the provider integration abstract behind one backend gateway

- Decision: Introduce a provider-agnostic backend LLM gateway that records provider, model, prompt profile version, execution timestamps, and explicit error/incomplete states on each run.
- Rationale: The spec requires all assessments to be LLM-based and failures to be persisted explicitly. A gateway abstraction avoids binding the data model to one provider while preserving run provenance.
- Alternatives considered:
  - Hardcode one provider directly into each agent profile: rejected because it increases duplication and makes misconfiguration handling inconsistent.
  - Hide provider/model details entirely: rejected because operator traceability requires seeing which profile and model produced an assessment.

## Decision 8: Support season cadence structurally in v1 even if the first shipped operational roster focuses on daily, weekly, and block value

- Decision: Include season cadence in the canonical enums, APIs, and window model now, while keeping the v1 operational roster limited to the explicit high-value profiles named in the spec.
- Rationale: The spec requires the system to support daily, weekly, block, and season cadences, but also narrows first-version implementation to a smaller roster. Building cadence support into storage and contracts now avoids a later schema split.
- Alternatives considered:
  - Omit season from the initial design entirely: rejected because it would leave FR-001 only partially modeled.
  - Implement the entire catalog in v1: rejected because it would broaden scope beyond the first-version boundary.

## Decision 9: Accepted proposals update SQLite planning surfaces first; markdown synchronization is deferred and explicit

- Decision: In v1, accepted proposals should write only to canonical SQLite planning tables plus review metadata. Any markdown regeneration or manual markdown update stays outside this feature's runtime path.
- Rationale: The repository constitution treats markdown as a human view, and the spec states proposal approval must precede plan mutation. Keeping markdown out of the first approval path reduces risk and keeps plan mutation local and auditable.
- Alternatives considered:
  - Auto-edit markdown immediately on proposal acceptance: rejected because it couples runtime approval to human-view files and introduces synchronization risk.
  - Treat markdown edits as the approval artifact: rejected because SQLite must remain canonical.

## Decision 10: Start with operator-triggered runs and design for future automatic scheduling without making scheduling a v1 dependency

- Decision: The initial workflow should support operator-triggered execution from the application/API, while the data model and run statuses remain compatible with future scheduled invocations.
- Rationale: The spec emphasizes traceability and reviewability, not autonomous background scheduling. Starting with explicit triggers reduces operational ambiguity while preserving room for later automation.
- Alternatives considered:
  - Require a scheduler in v1: rejected because no scheduler surface exists in the current repository and it is not necessary to satisfy the first user stories.
  - Disallow future scheduled runs in the data model: rejected because cadence-based assessment architecture should remain extensible.