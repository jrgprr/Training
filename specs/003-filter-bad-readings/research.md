# Research: Filter Bad Readings

## Decision 1: Persist canonical raw readings in SQLite as one row per metric sample

- Decision: Add a canonical `exec_activity_metric_readings` table keyed by activity, metric, and sample order, with optional timestamp and offset context for each raw sample.
- Rationale: The current system stores activity-level summary fields in `exec_activities` but not the underlying sample evidence needed to explain why one heart-rate spike or cadence drop was excluded. A per-metric row model keeps filtering deterministic, queryable, and traceable in SQLite.
- Alternatives considered:
  - Re-parse TCX or Garmin payload artifacts on demand: rejected because it makes runtime decisions depend on external files instead of canonical SQLite state.
  - Store a JSON blob of all samples on `exec_activities`: rejected because it weakens queryability, summary traceability, and range-level decisions.

## Decision 2: Tie each quality run to both the active rule version and a fingerprint of the canonical source evidence

- Decision: Persist a source-evidence fingerprint or equivalent canonical reading revision on each activity quality run, and use it alongside the rule-set version to determine whether a run is the same evaluation or a new one.
- Rationale: Determinism is defined by unchanged rules and unchanged source evidence, not by rule version alone. A corrected or re-imported activity under the same rules must be able to produce a new traceable run without destroying the identity of the earlier one.
- Alternatives considered:
  - Make runs unique only by activity and rule version: rejected because changed source evidence under the same version would have no clean identity.
  - Ignore stable run identity and always append a new run: rejected because unchanged re-evaluations would accumulate duplicate canonical outcomes.

## Decision 3: Run quality evaluation in the backend import flow and support replay from canonical evidence for already imported activities

- Decision: Evaluate bad-reading rules in backend code immediately after normalized samples are available and persist the resulting quality run, decisions, and summary impacts in the same canonical persistence flow, while also supporting replay evaluation from canonical raw readings or stored artifacts for already imported activities.
- Rationale: The existing Garmin pipeline already owns normalization, idempotent writes, and import traceability, but the feature must also cover historical activities already in SQLite without requiring a fresh live Garmin fetch.
- Alternatives considered:
  - Add a second manual cleanup command after import: rejected because it weakens determinism and invites drift between imported evidence and trusted summaries.
  - Let the frontend classify spikes during rendering: rejected because domain logic must stay out of the view layer.

## Decision 4: Separate raw evidence, quality decisions, and filtered summaries while keeping `exec_activities` as the backward-compatible trusted activity surface

- Decision: Preserve raw sample evidence in dedicated canonical tables, persist per-metric filtered summaries with both source and trusted values, and continue filling `exec_activities.avg_hr`, `max_hr`, `avg_power`, and similar fields with the trusted filtered results used by downstream analytics.
- Rationale: Existing activity endpoints and review flows already read `exec_activities`. Keeping that table as the trusted summary surface minimizes downstream churn while still preserving raw evidence and traceability elsewhere in SQLite.
- Alternatives considered:
  - Leave `exec_activities` untouched and add only parallel filtered columns: rejected because downstream analytics would continue reading distorted source summaries until every consumer migrated.
  - Overwrite activity summaries without preserving source values anywhere: rejected because traceability requires showing how a summary changed.

## Decision 5: Express activity quality as an explicit backend-derived status with `clean`, `filtered`, and `limited`, plus a transitional `not_checked` state for legacy rows

- Decision: Add activity-level quality status derived from persisted per-metric summary outcomes: `clean`, `filtered`, `limited`, and `not_checked` for legacy or not-yet-evaluated records.
- Rationale: The specification requires an explicit activity-level quality outcome and forbids ambiguous silence when filtering changes or withholds a summary.
- Alternatives considered:
  - Infer activity quality only from the presence of quality decision rows: rejected because it cannot distinguish a clean evaluation from an unprocessed activity.
  - Collapse clean and filtered into one generic processed state: rejected because reviewers need to know quickly whether the summary changed.

## Decision 6: Scope the first version to metrics with available point-level streams, with heart rate mandatory and power/cadence opportunistic

- Decision: Heart rate is mandatory in the first version. Power and cadence enter scope only when the import source exposes enough point-level readings to evaluate them deterministically for the activity.
- Rationale: The current adapter already extracts mixed activity-detail points for segment reconstruction, including heart rate, power, and bike cadence when present. Reusing that evidence keeps the feature grounded in data the repo already knows how to normalize.
- Alternatives considered:
  - Require full support for every activity summary metric before shipping: rejected because it blocks the feature on source gaps and violates the explicit heart-rate-first priority.
  - Evaluate only heart rate forever: rejected because the spec allows the same model to extend to other metrics already in scope.

## Decision 7: Persist exclusion decisions at reading-range granularity, not only as aggregate counts

- Decision: Store one quality decision per excluded sample or contiguous excluded range, including metric, position within the activity, rule key, reason code, and impacted summary kinds.
- Rationale: Traceability depends on being able to show which reading or run of readings was rejected and why, not just how many samples were removed.
- Alternatives considered:
  - Store only per-metric exclusion counts: rejected because reviewers could not inspect which readings changed a summary.
  - Store only free-form notes: rejected because deterministic filtering needs structured traceability.

## Decision 8: Mark filtered summaries as unavailable or quality-limited instead of fabricating replacements when too much evidence is excluded

- Decision: If filtering removes enough samples that a metric can no longer support a trustworthy aggregate, persist the metric summary as `quality_limited` or unavailable and surface that state explicitly.
- Rationale: The specification forbids fabricated replacement readings and requires explicit bounded downstream analytics when evidence becomes too weak.
- Alternatives considered:
  - Interpolate or smooth missing readings: rejected because it exceeds deterministic bad-reading filtering and would invent performance data.
  - Keep publishing the source summary despite exclusions: rejected because it would preserve the original distortion.

## Decision 9: Surface traceability through existing activity endpoints plus one dedicated activity-quality detail endpoint

- Decision: Extend existing activity list/detail payloads with quality summary state and add a dedicated `GET /api/activities/{activity_id}/quality` endpoint for per-metric summary deltas and excluded reading ranges.
- Rationale: This keeps the GUI thin and leverages the repo's existing activity surfaces without creating a separate dashboard just for filtering.
- Alternatives considered:
  - Build a standalone quality dashboard first: rejected because it broadens scope beyond the requested minimal visibility.
  - Hide traceability inside import-job history only: rejected because reviewers need to inspect an individual activity after import.