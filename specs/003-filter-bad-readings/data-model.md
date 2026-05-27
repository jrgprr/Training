# Data Model: Filter Bad Readings

## 1. CanonicalActivity Extension

- Purpose: Keep `exec_activities` as the trusted activity summary surface while making activity-level quality state explicit.
- Storage: existing `exec_activities`.

### New fields

- `quality_status`: enum-like text with values:
  - `not_checked`: legacy or not-yet-evaluated activity.
  - `clean`: all evaluated metrics kept trustworthy summaries without exclusions.
  - `filtered`: one or more readings were excluded, but all affected metric summaries remain trustworthy.
  - `limited`: one or more metric summaries became unavailable or quality-limited after filtering.
- `quality_checked_at`: timestamp of the last completed quality evaluation.
- `quality_rule_version`: active deterministic rule-set version used for the last evaluation.
- `quality_decision_count`: integer count of persisted exclusion decisions for the activity.
- `quality_limited_metric_count`: integer count of metric summaries withheld or marked quality-limited.

### Trusted summary rule

- `avg_hr`, `max_hr`, `avg_power`, `normalized_power`, and other in-scope activity-level summary columns remain the canonical trusted values consumed by existing downstream readers.
- Source values imported before filtering are preserved in `exec_activity_metric_summaries.source_value` rather than lost.

## 2. ActivityMetricReading

- Purpose: Canonical raw evidence for one metric sample inside an imported activity.
- Proposed storage: new table `exec_activity_metric_readings`.

### Core fields

- `activity_metric_reading_id`: integer primary key.
- `activity_id`: foreign key to `exec_activities.activity_id`.
- `source_system`: expected value `garmin` for the first implementation path.
- `metric_name`: normalized metric key such as `heart_rate`, `power`, or `bike_cadence`.
- `sample_index`: zero-based reading order within the activity for that metric.
- `seconds_offset`: nullable numeric offset from activity start when available.
- `recorded_at`: nullable timestamp when the source provides a sample time.
- `raw_value`: numeric raw sample value preserved without filtering.
- `source_payload_kind`: origin hint such as `activity_detail_stream` or future importer-specific values.
- `created_at`: timestamp.

### Constraints

- `UNIQUE (activity_id, metric_name, sample_index)`.
- Index on `(activity_id, metric_name)` for recomputation and traceability reads.
- Raw values are immutable evidence; new imports replace by stable identity, not by in-place mutation of meaning.

## 3. ActivityQualityRun

- Purpose: Record one deterministic evaluation pass for an activity against a specific rule set.
- Proposed storage: new table `exec_activity_quality_runs`.

### Core fields

- `quality_run_id`: integer primary key.
- `activity_id`: foreign key to `exec_activities.activity_id`.
- `rule_set_key`: stable identifier such as `bad_reading_filter`.
- `rule_set_version`: version string used for deterministic re-evaluation and idempotency.
- `source_reading_fingerprint`: stable fingerprint or canonical reading revision representing the exact source evidence evaluated by the run.
- `source_payload_path`: nullable traceability pointer to the raw payload or stored artifact set used to create the canonical readings.
- `evaluated_at`: timestamp.
- `evaluated_metric_names`: JSON/text list of metrics evaluated during the run.
- `skipped_metric_names`: JSON/text list of ineligible or unavailable metrics with short reasons.
- `evaluated_reading_count`: integer count of samples considered.
- `excluded_reading_count`: integer count of samples excluded.
- `limited_metric_count`: integer count of metrics left unavailable or quality-limited.
- `status`: `completed` or `completed_with_limits`.

### Constraints

- `UNIQUE (activity_id, rule_set_key, rule_set_version, source_reading_fingerprint)` for deterministic reruns against unchanged evidence.
- One activity may have multiple runs when the active rule version changes or when the canonical source evidence changes under the same rule version.

## 4. ActivityQualityDecision

- Purpose: Persist one exclusion or limit decision with traceability to the affected metric and summary impacts.
- Proposed storage: new table `exec_activity_quality_decisions`.

### Core fields

- `quality_decision_id`: integer primary key.
- `quality_run_id`: foreign key to `exec_activity_quality_runs.quality_run_id`.
- `activity_id`: foreign key to `exec_activities.activity_id`.
- `metric_name`: normalized metric key.
- `decision_status`: `excluded` or `quality_limited`.
- `start_sample_index`: first affected sample index.
- `end_sample_index`: last affected sample index.
- `reason_code`: stable explanation code such as `hr_above_hard_cap` or `cadence_zero_dropout`.
- `rule_key`: stable per-rule identifier inside the rule set.
- `threshold_low`: nullable numeric lower threshold used by the decision.
- `threshold_high`: nullable numeric upper threshold used by the decision.
- `evidence_json`: structured details needed to explain the decision, such as neighboring values or run length.
- `impacted_summary_kinds`: JSON/text list of summary kinds changed or withheld by this decision.
- `created_at`: timestamp.

### Constraints

- `UNIQUE (quality_run_id, metric_name, start_sample_index, end_sample_index, rule_key)`.
- One decision may represent a single-sample spike or a contiguous excluded range.

## 5. ActivityMetricSummary

- Purpose: Persist source and trusted per-metric aggregate summaries plus the quality state needed to explain deltas.
- Proposed storage: new table `exec_activity_metric_summaries`.

### Core fields

- `activity_metric_summary_id`: integer primary key.
- `activity_id`: foreign key to `exec_activities.activity_id`.
- `quality_run_id`: foreign key to `exec_activity_quality_runs.quality_run_id`.
- `metric_name`: normalized metric key.
- `summary_kind`: normalized aggregate type such as `average`, `maximum`, or `normalized`.
- `source_value`: nullable numeric value from the imported source summary or raw unfiltered recomputation.
- `trusted_value`: nullable numeric value after exclusions.
- `summary_status`: `clean`, `filtered`, or `quality_limited`.
- `evaluated_reading_count`: integer.
- `accepted_reading_count`: integer.
- `excluded_reading_count`: integer.
- `changed_by_filter`: boolean flag for fast UI and query use.
- `created_at`, `updated_at`: timestamps.

### Constraints

- `UNIQUE (activity_id, metric_name, summary_kind)`.
- `trusted_value` is null when `summary_status = quality_limited`.

## 6. ActivityQualityTraceView

- Purpose: SQLite-backed read model for activity-level quality review.
- Storage: derived from `exec_activities`, `exec_activity_quality_runs`, `exec_activity_quality_decisions`, and `exec_activity_metric_summaries`; implemented in `Sistema/views.sql` or backend query helpers rather than as a separate canonical table.

### Derived fields

- `activity_id`
- `quality_status`
- `quality_checked_at`
- `quality_rule_version`
- `impacted_metric_names`
- `changed_summary_count`
- `limited_metric_count`
- `decision_count`
- `metrics`: list of per-metric status blocks with source/trusted summary deltas
- `decisions`: ordered exclusion or limit decisions suitable for GUI traceability

## State Transitions

### `exec_activities.quality_status`

- `not_checked -> clean`
- `not_checked -> filtered`
- `not_checked -> limited`
- `clean -> clean`
- `clean -> filtered`
- `filtered -> filtered`
- `filtered -> limited`
- `limited -> limited`

Repeated imports with unchanged source samples and unchanged `quality_rule_version` must not create duplicate `exec_activity_quality_runs`, `exec_activity_quality_decisions`, or `exec_activity_metric_summaries`. When source samples change or the rule version changes, the canonical activity keeps the latest trusted summary state and traceability points to the new quality run.

## 7. Historical Replay Path

- Purpose: Support quality evaluation for activities already imported before the feature exists or before raw-reading persistence was enabled.
- Storage impact: No separate canonical table is required beyond the run and reading tables above; replay either consumes canonical `exec_activity_metric_readings` rows directly or first backfills them from stored activity artifacts.

### Rules

- Replay against unchanged canonical readings and unchanged `quality_rule_version` must resolve to the same `source_reading_fingerprint` and therefore the same canonical quality run.
- Replay against rebuilt or corrected canonical readings must create a new quality run with a different `source_reading_fingerprint` while keeping prior traceability intact.