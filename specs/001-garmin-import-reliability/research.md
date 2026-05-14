# Research: Garmin Import Reliability

## Decision 1: Extend the existing import endpoints and storage flow instead of creating a new orchestration service

- Decision: Keep the current FastAPI endpoints `/api/imports/garmin-connect/status`, `/preview`, `/run`, `/api/import-jobs`, and `/api/import-jobs/{id}` as the main interface and enrich their storage/response model.
- Rationale: The brownfield feature is explicitly scoped to the existing Garmin import flow. The current backend already routes preview and run requests through `GarminImportPipeline` and `GarminImportStorage`, so reliability improvements belong there rather than behind a new orchestration layer.
- Alternatives considered:
  - Create a dedicated import controller/service boundary above the current endpoints: rejected because it adds structure without reducing the core ambiguity in persisted outcomes.
  - Add a separate retry queue service: rejected because retry behavior was clarified as manual-only.

## Decision 2: Promote reliability-critical import attempt fields into explicit SQLite columns

- Decision: Evolve `meta_import_jobs` to store explicit scope, lifecycle, classification, retry-suitability, and per-data-class outcome fields rather than relying only on `notes` JSON.
- Rationale: The feature requires durable, queryable runtime state for diagnosis and retry. Existing `notes` JSON is insufficient for stable classification and operator-facing summaries. Explicit columns support backend logic, API filtering, and GUI rendering without parsing free-form text.
- Alternatives considered:
  - Keep all new metadata inside the existing `notes` JSON blob: rejected because it weakens queryability and risks future drift between UI and backend logic.
  - Add a separate import-attempt detail table for all metadata: rejected for now because only one import flow is in scope and a single enriched job table is simpler.

## Decision 3: Preserve canonical idempotency using existing stable source identities

- Decision: Keep canonical activity and daily metric writes idempotent using existing uniqueness constraints: `UNIQUE (source_system, external_activity_id)` for activities and `UNIQUE (season_id, metric_date, source_system)` for daily metrics.
- Rationale: The schema already expresses the stable source identities needed for safe reruns. The plan should strengthen traceability around attempts, not replace the existing canonical identity model.
- Alternatives considered:
  - Date-range snapshot replacement on rerun: rejected because it is riskier and unnecessary for local-first reliability.
  - No hard idempotency guarantee: rejected because it violates the clarified retry expectations.

## Decision 4: Represent mixed outcomes explicitly with `partial_completed`

- Decision: Use a distinct terminal status such as `partial_completed` when one data class persists successfully and another fails, while also persisting per-data-class breakdown counts.
- Rationale: Mixed outcomes are materially different from both full success and full failure. Operators need to know whether rerun risk stems from normalization/persistence on only one side of the batch.
- Alternatives considered:
  - Collapse mixed outcomes into `failed`: rejected because it hides partial canonical effects.
  - Collapse mixed outcomes into `completed` with notes: rejected because it makes retry safety ambiguous.

## Decision 5: Derive retry suitability in the backend and expose it as state, not UI logic

- Decision: Persist a backend-derived retry suitability field with at least `safe_to_retry` and `inspect_before_retry`, driven by terminal status, failure class, and failed stage.
- Rationale: The constitution requires a thin GUI. Retry safety is operational domain logic and should be computed once in backend/storage logic, then surfaced consistently in CLI and GUI responses.
- Alternatives considered:
  - Let the frontend infer retry safety from free-form notes: rejected because it duplicates domain logic in the UI.
  - Add more granular retry states immediately: rejected to keep the first reliability pass simple.