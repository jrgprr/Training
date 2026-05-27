# Research: Garmin Segment Analysis

## Decision 1: Extend the existing Garmin import normalization flow instead of adding a separate segment sync pipeline

- Decision: Keep Garmin segment extraction inside the current `GarminConnectAdapter -> GarminImportPipeline -> GarminImportStorage` flow and extend normalized activity payloads with optional segment collections for cycling activities.
- Rationale: The existing import path already owns Garmin authentication, fetch lifecycle, idempotent persistence, and traceability. Segment ingestion is a refinement of the same source import rather than a new operational workflow.
- Alternatives considered:
  - Add a second segment-only fetch command after activity import: rejected because it doubles operator steps and weakens import traceability.
  - Add frontend-driven segment fetch logic: rejected because Garmin logic must stay out of the GUI.

## Decision 2: Use Garmin's activity segment list as the primary membership source and scope the feature to favorites

- Decision: Use Garmin's activity segment list payload as the primary source of activity-segment membership, and persist only entries marked as `favorite` for this version.
- Rationale: The standard activity detail payloads did not reliably expose segment efforts on live rides, while the segment list endpoint consistently exposed segment membership and favorite state. The product decision for this version is to keep only favorite segments in SQLite.
- Alternatives considered:
  - Persist every segment attached to the activity: rejected because the chosen product behavior is favorite-only and would create unnecessary noise in the stored history.
  - Ignore favorite state and filter later in the UI: rejected because the database itself should reflect the product scope.

## Decision 3: Store canonical segment definitions separately from segment efforts, and record explicit segment availability on activities

- Decision: Add a canonical segment definition table plus a segment effort table, and extend canonical activity state with an explicit segment-availability outcome such as `not_checked`, `available`, `not_available`, or `not_applicable`.
- Rationale: Segment facts recur across activities, while efforts are activity-specific. An explicit activity-level availability state removes ambiguity when a cycling activity was checked and Garmin returned no segments.
- Alternatives considered:
  - Store segment facts inline as JSON on `exec_activities`: rejected because it weakens queryability, idempotency, and cross-activity analysis.
  - Infer "no segment data" only from missing effort rows: rejected because it cannot distinguish checked-no-data from legacy/unprocessed activities.

## Decision 4: Preserve idempotency with Garmin source identities at both segment and effort levels

- Decision: Use Garmin source identity as the canonical deduplication key for segment definitions and segment efforts, while continuing to anchor effort rows to the imported canonical activity.
- Rationale: The feature depends on safe re-imports and historical traceability. Stable source identities allow repeated imports to refresh or retain canonical records without creating duplicate efforts.
- Alternatives considered:
  - Deduplicate segments by display name: rejected because the spec explicitly requires distinct source identities even when names collide.
  - Treat each import as append-only history: rejected because it violates idempotent canonical writes.

## Decision 5: Reconstruct approximate segment metrics when Garmin exposes membership but omits native effort metrics

- Decision: When Garmin exposes segment membership but not native effort metrics, reconstruct approximate elapsed time and supporting metrics from the imported activity detail stream plus segment geometry.
- Rationale: This keeps the feature useful on real rides where Garmin's clean endpoints expose segment membership but not direct per-attempt metrics. It also keeps the approximation in the backend where provenance can be recorded in SQLite.
- Alternatives considered:
  - Persist membership only and never attempt reconstruction: rejected because it leaves repeated favorite segments with little analytical value when raw activity detail data is already available.
  - Reconstruct metrics in the frontend: rejected because it would duplicate Garmin-specific logic outside the canonical backend flow.

## Decision 6: Compute segment history and trend summaries in the backend, not in React

- Decision: Expose backend endpoints that return ordered effort history plus derived comparison fields such as best effort, most recent effort, and trend readiness.
- Rationale: Trend interpretation is domain logic built on canonical records and missing-metric rules. Keeping it in the backend satisfies the thin-GUI requirement and avoids duplicating analysis rules in the frontend.
- Alternatives considered:
  - Send raw effort rows and let the UI compute best effort and trend state: rejected because it embeds analysis logic in the view layer.
  - Materialize every analysis summary as a persisted table: rejected for the first version because the derived view can be queried or assembled on demand.

## Decision 7: Represent missing supporting metrics as nullable canonical fields and explicit API availability markers

- Decision: Persist supporting metrics such as power, cadence, and heart rate as nullable columns on segment efforts, and have the history API return explicit missing-metric indicators for each effort.
- Rationale: The spec requires efforts to remain visible even when some metrics are absent. Nullable canonical fields keep storage simple, while explicit API markers keep the GUI honest about what is unavailable.
- Alternatives considered:
  - Drop efforts with incomplete metrics from analysis: rejected because it hides valid effort history.
  - Fill missing metrics with zero values: rejected because it fabricates data and distorts comparison logic.

## Decision 8: Keep the first user-facing surface minimal: segment list plus segment detail/history view

- Decision: Add a minimal backend-driven read surface that lists segments with repeated efforts and a detail view for one segment's history and evolution summary.
- Rationale: This satisfies the feature stories without expanding into dashboards, markdown updates, or cross-module analytics. It fits naturally inside the existing single-page GUI.
- Alternatives considered:
  - Add a broad new analytics dashboard: rejected because it broadens scope beyond the current spec.
  - Keep the feature backend-only with no GUI read surface: rejected because the spec requires coach/athlete review through a user-facing surface.