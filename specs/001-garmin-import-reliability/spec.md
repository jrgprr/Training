# Feature Specification: Garmin Import Reliability

**Feature Branch**: `001-improve-garmin-import`

**Created**: 2026-05-14

**Status**: Draft

**Input**: User description: "Improve Garmin import reliability and error handling."

## Affected System Layers *(mandatory)*

- **Primary layer(s)**: `GUI/backend`, `Sistema/`, minimal `GUI/frontend` visibility only if required for operator diagnosis and retry
- **Canonical data impact**: SQLite remains the source of truth for import attempts, staging data, final imported records, and retry outcomes. Markdown remains a human-facing view and is not changed as runtime truth by this feature.
- **External source impact**: Existing Garmin import flow only, including Garmin Connect fetch, normalization, persistence, import attempt history, and operator-visible status for safe retry

## Clarifications

### Session 2026-05-14

- Q: How should retry behavior work for failed Garmin imports? → A: Manual retry only; every retry must be explicitly triggered by the operator.
- Q: Which failure categories should be distinguished? → A: Use four durable classes: configuration/authentication, transport/rate-limit, source-data/normalization, and persistence/transaction.
- Q: What is the idempotency rule for canonical Garmin data? → A: Canonical Garmin activities and daily metrics are deduplicated or upserted by stable source identity, while every import run always creates a new import attempt record.
- Q: What minimum import-attempt metadata must be persisted in SQLite? → A: Persist season, requested date range, include-daily-metrics flag, source system, started and finished timestamps, terminal status, failed stage when applicable, failure class when applicable, operator-readable detail, detected counts, inserted counts, updated counts, skipped counts, and a partial-completion indicator.
- Q: What is the minimum operator-facing visibility required in the GUI? → A: Reuse the existing Garmin import status/history surfaces and extend them only enough to show latest outcome, failure class, failed stage, retry suitability, and per-run summary; no new dedicated dashboard or Garmin logic in the UI.
- Q: How should mixed outcomes be represented when one data class succeeds and another fails? → A: Record a distinct terminal status for partial completion and persist per-data-class breakdown so the operator can see what succeeded, what failed, and what remains safe to retry.
- Q: How should retry suitability be exposed? → A: Persist an explicit backend-derived retry suitability state with at least `safe_to_retry` and `inspect_before_retry`; partial completion, normalization failures, and persistence failures default to `inspect_before_retry`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Or Explain Each Import Attempt (Priority: P1)

As an operator running the existing Garmin import flow, I need every import attempt to end in a clearly recorded success or classified failure so that I can trust SQLite as the canonical record of what happened.

**Why this priority**: Reliability starts with removing ambiguous outcomes. If an import can fail without a durable, classifiable record, the operator cannot safely decide whether the system is current or whether to retry.

**Independent Test**: Can be fully tested by running the current Garmin import flow under successful and failing conditions and confirming that each attempt creates one durable import record with a terminal status, traceable counts, and failure classification when applicable.

**Acceptance Scenarios**:

1. **Given** a valid Garmin import request, **When** the import completes successfully, **Then** SQLite records one completed import attempt with detected and loaded counts, source range, timestamps, and enough detail to inspect what was persisted.
2. **Given** a valid Garmin import request, **When** the fetch, normalization, or persistence flow fails, **Then** SQLite records one failed import attempt with the failed stage, failure classification, operator-readable detail, and no ambiguous terminal state.
3. **Given** an import attempt that fails after partial work has begun, **When** the operator inspects the attempt, **Then** the system makes it clear which parts completed, which parts did not, and whether the canonical records remain safe to retry.
4. **Given** an import attempt that fails because of configuration, authentication, transport, normalization, or persistence reasons, **When** the operator reviews the attempt, **Then** the failure class is stored durably and distinguishes the operational response required.

---

### User Story 2 - Diagnose And Retry Safely (Priority: P2)

As an operator maintaining the local-first training system, I need to see enough history and failure detail to determine whether a Garmin import can be retried safely without creating duplicate canonical records or hiding prior failures.

**Why this priority**: Recoverability depends on traceable job history and explicit retry behavior. Without that, the operator either avoids retries or risks corrupting the source of truth.

**Independent Test**: Can be fully tested by triggering a failure, reviewing the persisted attempt history, retrying the same import scope, and verifying that the operator can distinguish the old failure from the new attempt while canonical records remain consistent.

**Acceptance Scenarios**:

1. **Given** a previously failed import attempt, **When** the operator reviews import history, **Then** the system shows enough context to understand the request scope, failure class, failure stage, and retry suitability.
2. **Given** a repeated import request for the same season and date range, **When** the operator retries after a failure or uncertainty, **Then** the system records a new attempt linked by scope while preserving idempotent canonical outcomes.
3. **Given** a retry of data that was already imported successfully, **When** the import runs again, **Then** the system does not create unintended duplicate canonical activity or daily metric records and still records the new attempt outcome.
4. **Given** a failed import attempt, **When** a retry is needed, **Then** the retry only occurs after an explicit operator action and is never launched automatically by the system.
5. **Given** an attempt with partial completion or a local persistence problem, **When** the operator reviews the attempt, **Then** the system marks the retry as requiring inspection before rerun rather than implying it is automatically safe.

---

### User Story 3 - Keep Operator Visibility Minimal And Useful (Priority: P3)

As an operator using the existing GUI or CLI surfaces, I need minimal but sufficient visibility into Garmin import health so that I can inspect status, diagnose failures, and retry without introducing Garmin business logic into the UI.

**Why this priority**: The constitution requires a thin GUI. Operator visibility matters, but the feature should avoid redesigning the product or moving import rules into the interface.

**Independent Test**: Can be fully tested by inspecting the existing operator-facing surface for import status and confirming it presents persisted backend results without embedding classification or retry rules in the UI.

**Acceptance Scenarios**:

1. **Given** existing operator-facing import access, **When** the operator views Garmin import status or history, **Then** they can see the latest attempt result, relevant failure details, and whether a retry is available.
2. **Given** a need for additional operator visibility, **When** the feature adds it, **Then** the surface remains minimal and reads backend-provided import state rather than reimplementing Garmin logic in the GUI.
3. **Given** the existing Garmin import card and history surfaces, **When** the operator inspects them, **Then** they can see latest outcome, failure class, failed stage, retry suitability, and per-run breakdown without navigating to a new dedicated module.

### Edge Cases

- What happens when Garmin returns no activities or no daily metrics for a valid date range? The attempt must still be recorded with a non-ambiguous outcome and zero-result traceability.
- How does the system handle repeated imports for the same Garmin activities or daily metrics? Canonical SQLite records must remain idempotent, while attempt history must still capture each run.
- How does the system handle a failure after the attempt record is created but before final persistence completes? The stored attempt must show the failed stage and leave the operator with a safe retry decision.
- What happens when one data class succeeds and another fails within the same request scope? The attempt record must expose that mixed outcome clearly enough to diagnose recoverability.
- What happens when canonical records are already present for the same Garmin source identities? The rerun must preserve canonical idempotency while still recording the new attempt and its breakdown.
- How does the system handle malformed or incomplete source payload details from Garmin? The failure must be classifiable and operator-visible without requiring markdown inspection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST remain scoped to the existing Garmin import flow and must not redesign unrelated planning, analysis, or non-Garmin execution flows.
- **FR-002**: The system MUST persist an import attempt record at the start of every Garmin import run before external fetch or canonical persistence proceeds.
- **FR-003**: Every Garmin import attempt MUST end in one explicit terminal status recorded in SQLite, including at minimum successful completion and classified failure outcomes.
- **FR-004**: Each persisted import attempt MUST capture the request scope needed for traceability, including season, requested date range, source system, attempt timestamp, and whether daily metrics were included.
- **FR-005**: Each failed import attempt MUST record a failure stage and operator-readable error detail that distinguish at least external source/configuration failures, data/normalization failures, and persistence failures.
- **FR-005a**: Failure classification MUST use the four durable categories `configuration_authentication`, `transport_rate_limit`, `source_data_normalization`, and `persistence_transaction`.
- **FR-006**: Failed import attempts MUST remain visible in import history after later retries so operators can reconstruct what happened across attempts.
- **FR-007**: The system MUST preserve SQLite as the source of truth for import attempt history, staging evidence, and final imported records; markdown may reflect the outcome for humans but MUST NOT be required to diagnose runtime state.
- **FR-008**: Garmin import persistence MUST support safe retry behavior for the same source scope without creating unintended duplicate canonical activity or daily metric records in SQLite.
- **FR-009**: When a retry occurs for a previously attempted scope, the system MUST create a new attempt record rather than overwriting prior attempt history.
- **FR-009a**: The system MUST NOT perform automatic background or implicit retries for failed Garmin imports; every retry MUST be explicitly initiated by an operator.
- **FR-009b**: Canonical Garmin activity and daily metric persistence MUST be idempotent by stable source identity so that rerunning the same scope does not create unintended duplicates even when a new import attempt record is created.
- **FR-010**: The system MUST record enough persisted detail for an operator to determine whether a retry is safe, including what data classes were detected, what was loaded, and whether canonical records were inserted, updated, skipped, or left incomplete.
- **FR-010a**: Each import attempt MUST persist, at minimum, season, requested date range, include-daily-metrics flag, source system, started timestamp, finished timestamp, terminal status, failed stage when applicable, failure class when applicable, operator-readable detail, detected counts, inserted counts, updated counts, skipped counts, and a partial-completion indicator.
- **FR-011**: If an import attempt fails after partial progress, the persisted outcome MUST make partial completion visible enough to support diagnosis and safe retry decisions.
- **FR-011a**: Mixed outcomes where one data class succeeds and another fails MUST be represented with a distinct terminal status separate from full success and full failure.
- **FR-012**: Any operator-facing visibility introduced by this feature MUST remain minimal and MUST read backend-provided import state rather than embedding Garmin business logic in the GUI.
- **FR-012a**: The minimum operator-facing visibility for this feature MUST be delivered through the existing Garmin import status/history surfaces rather than a new dedicated dashboard module.
- **FR-013**: The feature MUST preserve the existing local-first operating model and must not require a remote service, cloud dependency, or full product redesign.
- **FR-014**: The feature MUST preserve existing operator access to review import history for both GUI and CLI-driven runs when those runs use the same backend import flow.
- **FR-015**: The feature MUST avoid silent writes or irreversible state transitions in the Garmin import flow; each meaningful import action must remain traceable through persisted metadata or status history.
- **FR-016**: The backend MUST persist an explicit retry suitability state for each import attempt, with at least `safe_to_retry` and `inspect_before_retry` values derived from the recorded outcome.

### Key Entities *(include if feature involves data)*

- **Garmin Import Attempt**: A persisted record of one execution of the Garmin import flow for a given season and date range, including scope, timestamps, status, counts, failure classification, and operator-facing notes.
- **Import Scope**: The requested season, date range, and inclusion choices that define what the attempt tried to import.
- **Import Breakdown**: A persisted summary of what the attempt detected and what effect it had on canonical records, including inserted, updated, skipped, or incomplete outcomes per data class.
- **Failure Classification**: A durable categorization of why an attempt failed and at which stage, used to support diagnosis, retry safety, and history review.
- **Retry Suitability**: A backend-derived operational signal indicating whether an attempt is safe to rerun immediately or should be inspected before retry.
- **Staged Garmin Evidence**: Persisted intermediate import evidence associated with an attempt so the operator can audit what was fetched and what reached canonical persistence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of Garmin import runs started by the existing flow produce exactly one persisted attempt record with a terminal outcome visible in SQLite.
- **SC-002**: 100% of failed Garmin import attempts expose a stored failure class, failed stage, and operator-readable detail sufficient for a human operator to decide whether to retry without inspecting source code.
- **SC-003**: Re-running the same Garmin import scope after a prior attempt leaves canonical SQLite activity and daily metric records free of unintended duplicates for the imported source data.
- **SC-003a**: 100% of Garmin import failures are recorded under one of the four approved failure classes and expose the failed stage in SQLite.
- **SC-004**: An operator can identify the latest status and retry suitability of a Garmin import attempt within 2 minutes using the existing history surface plus any minimal visibility added by this feature.
- **SC-005**: The feature introduces no requirement for markdown edits or markdown inspection to determine runtime import state or recover from Garmin import failures.

## Assumptions

- The feature applies only to the existing Garmin Connect-backed import path and its current CLI and GUI entry points.
- Existing canonical uniqueness and upsert behavior for imported Garmin activities and daily metrics will continue to be used as the basis for idempotent retry behavior.
- Stable Garmin source identities are available or derivable for canonical deduplication and upsert decisions.
- Retry behavior is operator-driven only; no automatic retry loop is introduced by this feature.
- Any operator-facing changes remain incremental extensions of current import status/history visibility rather than a new workflow or major UI redesign.
- The existing Garmin status/history surfaces are sufficient to host the minimum additional visibility required by this feature.
- SQLite stays on the local machine as the authoritative store for import attempts and imported data.
- Markdown files remain human-readable views and documentation artifacts only; they are not part of Garmin runtime decision-making.
- The backend remains responsible for Garmin-specific rules, failure classification, and retry semantics.