# Feature Specification: Filter Bad Readings

**Feature Branch**: `003-filter-bad-readings`

**Created**: 2026-05-27

**Status**: Draft

**Input**: User description: "Filter raw imported activity data to detect bad readings and avoid distorted metrics, using heart rate bad readings as the motivating example. Cover detection and handling of implausible physiological and device readings in imported raw data so derived metrics like max heart rate, average heart rate, power summaries, cadence summaries, and other downstream analytics are not polluted by obvious sensor errors. Keep the feature scoped to data-quality filtering and traceability, not broad machine learning. Align with SQLite as canonical source of truth, backend-owned logic, thin frontend, and local-first workflow."

## Affected System Layers *(mandatory)*

- **Primary layer(s)**: `GUI/backend`, `Sistema/`, minimal `GUI/frontend` visibility for quality status and traceability only
- **Canonical data impact**: SQLite remains the source of truth for imported raw activity readings, data-quality decisions, filtered metric summaries, and traceability needed to explain why a summary changed. Markdown remains documentation only and is not used for runtime decisions.
- **External source impact**: Existing imported activity data only, including Garmin-origin raw readings already brought into the local workflow; no new external scoring or remote quality service is introduced.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Protect Activity Summaries From Bad Readings (Priority: P1)

As a coach or operator importing activity data, I need obviously implausible raw readings to be excluded from derived summaries so that max heart rate, average heart rate, power, cadence, and similar metrics stay trustworthy.

**Why this priority**: Preventing distorted summaries is the core user value. If obvious sensor spikes remain in the canonical summaries, every downstream view and training decision becomes less trustworthy.

**Independent Test**: Can be fully tested by importing an activity containing known implausible readings and confirming that affected summaries use accepted readings only while unaffected metrics remain unchanged.

**Acceptance Scenarios**:

1. **Given** an imported activity with a single implausible heart rate spike, **When** summaries are generated for that activity, **Then** the excluded spike does not determine the displayed maximum or average heart rate.
2. **Given** an imported activity with an implausible reading for one metric but valid readings for others at the same point in time, **When** summaries are generated, **Then** only the affected metric excludes the bad reading and the valid metrics remain eligible for their own summaries.
3. **Given** an imported activity with no implausible readings for an in-scope metric, **When** summaries are generated, **Then** the metric remains available without unnecessary exclusions.

---

### User Story 2 - Explain Why Readings Were Excluded (Priority: P2)

As a coach or operator reviewing an activity, I need traceability for excluded readings so that I can understand what was filtered, why it was filtered, and which summaries were affected.

**Why this priority**: Data-quality filtering is only trustworthy if the system can explain its decisions. Without traceability, users cannot distinguish real athlete performance from sensor cleanup.

**Independent Test**: Can be fully tested by reviewing an activity with excluded readings and verifying that the system exposes the affected metric, the excluded reading position within the activity, the reason for exclusion, and the impacted summaries.

**Acceptance Scenarios**:

1. **Given** an activity with excluded readings, **When** a user reviews data-quality details for that activity, **Then** the system shows which metric was affected, which readings were excluded, and why they were considered implausible.
2. **Given** an activity whose derived summaries changed because of filtering, **When** the user inspects the activity, **Then** the system makes it clear which summaries were affected by the quality filter.
3. **Given** an activity with no excluded readings, **When** the user inspects data-quality details, **Then** the system shows an explicit clean outcome rather than leaving the quality status ambiguous.

---

### User Story 3 - Keep Downstream Analytics Consistent And Bounded (Priority: P3)

As a coach relying on downstream analytics, I need all higher-level summaries derived from an activity to respect the same data-quality decisions so that follow-on analysis is not polluted by obvious device errors.

**Why this priority**: Fixing the activity screen alone is not enough. The same distorted source values would continue to damage analytics unless the quality decision is carried through consistently.

**Independent Test**: Can be fully tested by importing an activity with excluded readings and verifying that all downstream summaries based on the affected metric use the filtered result or explicitly report that the metric is not trustworthy enough to summarize.

**Acceptance Scenarios**:

1. **Given** an activity with excluded bad readings, **When** downstream analytics consume the activity summaries, **Then** they use the filtered summaries rather than the raw implausible values.
2. **Given** an activity where filtering removes too much data for one metric to remain trustworthy, **When** a summary or downstream analytic is requested, **Then** the system marks that metric as unavailable or quality-limited instead of publishing a misleading value.
3. **Given** the same source activity is imported again without source changes, **When** the quality filter is applied again, **Then** the resulting exclusions and affected summaries remain consistent and traceable.

### Edge Cases

- What happens when an activity contains a very short stream with only a few readings for a metric? The system must avoid publishing a misleading summary if filtering leaves too little trustworthy data.
- How does the system handle a prolonged device dropout rather than a single-sample spike? The system must keep the quality outcome explicit and avoid silently treating large invalid gaps as valid training signal.
- What happens when heart rate is implausible but power and cadence remain plausible at the same time point? The system must filter metrics independently so one bad sensor does not erase unrelated valid evidence.
- How does the system handle an activity where every reading for one metric is missing or implausible? The system must preserve the activity while marking the affected metric unavailable or quality-limited.
- What happens when the same activity is re-imported after it has already been filtered once? The canonical records and traceability must remain idempotent and must not accumulate duplicate quality decisions.
- How does the system handle readings that are unusual but still physiologically possible? The feature must stay bounded to obvious implausible readings and must not introduce speculative correction of legitimate hard efforts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST remain scoped to deterministic data-quality filtering for imported raw activity readings and MUST NOT attempt broad machine-learning-based anomaly detection or automatic performance prediction.
- **FR-002**: The system MUST evaluate imported raw activity readings for implausible physiological or device-generated values before final derived summaries are exposed as trusted activity metrics.
- **FR-003**: The first version of the feature MUST support heart rate filtering and MUST apply the same quality-filtering model to other imported metrics that feed canonical summaries when those metrics are in scope.
- **FR-004**: The system MUST preserve the original imported raw readings as source evidence and MUST NOT overwrite or delete them when a reading is judged implausible.
- **FR-005**: The system MUST persist a traceable data-quality decision for each excluded reading or excluded reading range, including the source activity identity, affected metric, reading position within the activity, exclusion reason, and resulting decision status.
- **FR-006**: Derived activity summaries such as maximum values, average values, and similar downstream aggregates MUST be computed from accepted readings only for the affected metric.
- **FR-007**: When a reading is implausible for one metric but other metrics at the same moment remain plausible, the system MUST filter only the affected metric and MUST preserve the unrelated valid readings for their own summaries.
- **FR-008**: When filtering leaves insufficient trustworthy data to support a summary for a metric, the system MUST mark that metric summary as unavailable or quality-limited instead of publishing a distorted value.
- **FR-009**: The system MUST expose traceability from each affected activity summary to the quality decision or decisions that caused the summary to change.
- **FR-010**: Re-importing the same source activity with unchanged raw readings and unchanged active quality rules MUST yield the same filtering outcome without creating duplicate canonical quality records.
- **FR-011**: The feature MUST state SQLite as the source of truth for imported raw readings, quality decisions, filtered summaries, and downstream analytic inputs affected by this feature.
- **FR-012**: GUI behavior introduced by this feature MUST remain thin and MUST rely on backend-provided quality status, filtered summaries, and traceability instead of reimplementing filtering logic in the frontend.
- **FR-013**: Import and synchronization flows affected by this feature MUST expose traceability for source activity identity, filtering status, and quality-related outcomes when summaries are changed or withheld.
- **FR-014**: The system MUST provide an activity-level quality outcome that distinguishes at least clean activities, activities with excluded readings that still support summaries, and activities where one or more metric summaries become unavailable or quality-limited.
- **FR-015**: The feature MUST keep downstream analytics bounded to filtered canonical summaries and MUST NOT fabricate replacement readings for excluded values in this version.
- **FR-016**: The feature MUST preserve the repository's local-first workflow and MUST NOT require a cloud dependency or external adjudication service to classify bad readings.

### Key Entities *(include if feature involves data)*

- **Raw Activity Reading**: A single imported reading for a metric within an activity stream, retained as the original source evidence.
- **Quality Decision**: A persisted determination that a reading or contiguous reading range is accepted, excluded, or leaves the metric quality-limited, along with the reason and traceability fields needed to explain the outcome.
- **Filtered Activity Summary**: The trusted per-activity summary for a metric after excluded readings are removed from the calculation.
- **Activity Quality Status**: A per-activity view of whether the activity is clean, filtered with acceptable remaining data, or limited because too little trustworthy data remains for one or more metrics.
- **Downstream Analytic Input**: Any canonical metric value consumed by later summaries or comparisons that must inherit the activity's filtering outcome rather than the raw implausible value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of activities containing readings classified as obviously implausible produce filtered summaries in which the excluded readings no longer determine the affected metric's displayed maximum, average, or equivalent aggregate.
- **SC-002**: 100% of excluded readings remain traceable to the source activity, affected metric, and exclusion reason so a reviewer can explain why a summary changed.
- **SC-003**: A coach or operator can determine within 2 minutes whether an activity summary was altered by data-quality filtering and which metric was affected.
- **SC-004**: Re-importing the same unchanged source activity does not create duplicate quality outcomes and yields the same filtered summary results.
- **SC-005**: When filtering leaves too little trustworthy data for a metric summary, the system always reports that metric as unavailable or quality-limited rather than publishing a misleading value.

## Assumptions

- Imported raw activity readings already exist or will exist in the local workflow at a granularity sufficient to evaluate implausible values for in-scope metrics.
- Heart rate is the motivating and mandatory first metric, while the same rule-driven quality model can be applied to other metrics that already contribute to canonical summaries.
- The first version focuses on obvious sensor or device errors and does not attempt to infer missing values, smooth valid hard efforts, or estimate corrected readings.
- Downstream analytics in scope are limited to analytics that consume canonical activity summaries rather than direct ad hoc inspection of every raw sample.
- Local SQLite remains the authoritative store for both raw evidence and the filtered outcomes derived from it.
- Any operator-facing visibility is delivered through existing local surfaces and remains secondary to backend-owned filtering and traceability.