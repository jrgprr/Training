# Feature Specification: Garmin Segment Analysis

**Feature Branch**: `002-garmin-segment-analysis`

**Created**: 2026-05-26

**Status**: Implemented

**Input**: User description: "Identify and store the information of the segments present in each cycling activity obtained from Garmin Connect, and add analysis functionality to track the athlete's performance evolution in those segments."

## Affected System Layers *(mandatory)*

- **Primary layer(s)**: `GUI/backend`, `Sistema/`, `GUI/frontend`
- **Canonical data impact**: SQLite remains the source of truth for imported segment facts, segment efforts, and derived segment-performance history. Markdown may reference outcomes later, but it is not a runtime source of truth for this feature.
- **External source impact**: Garmin Connect activity import expands to capture favorite-tagged segment information for cycling activities, keeping explicit membership records when Garmin exposes segment presence without native per-attempt metrics.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture Segment Facts During Import (Priority: P1)

As an operator importing Garmin cycling activities, I need the system to identify and store the segments associated with each imported activity so that segment data is preserved in SQLite instead of being lost after import.

**Why this priority**: Without durable ingestion of segment data, no later comparison or evolution analysis is trustworthy or repeatable.

**Independent Test**: Can be fully tested by importing a cycling activity known to contain Garmin segment information and confirming that SQLite stores the activity-to-segment relationship and the key segment effort facts needed for later analysis.

**Acceptance Scenarios**:

1. **Given** a Garmin cycling activity that includes favorite-tagged segment information, **When** the activity is imported, **Then** the system stores the detected favorite segments and the athlete's effort or membership data for each of those segments in SQLite.
2. **Given** a Garmin cycling activity that has already been imported, **When** the same source activity is imported again, **Then** the system preserves idempotent canonical records, does not create unintended duplicates, and removes previously stored out-of-scope segment rows for that activity.
3. **Given** a Garmin activity that does not contain favorite segment information, **When** it is imported, **Then** the import completes without ambiguity and records that no in-scope segment data was available for that activity.

---

### User Story 2 - Review Segment Performance History (Priority: P2)

As a coach or athlete, I need to review the history of performance on a given segment so that I can understand whether the athlete is improving, stable, or regressing over time.

**Why this priority**: Once segment data is captured, the next most valuable outcome is turning repeated efforts into a usable history rather than isolated raw records.

**Independent Test**: Can be fully tested by importing multiple cycling activities that include the same segment across different dates and verifying that a user-facing surface can show the ordered history of efforts for that segment.

**Acceptance Scenarios**:

1. **Given** multiple imported activities containing the same segment, **When** a coach or athlete reviews that segment, **Then** the system shows a chronological history of the athlete's efforts on that segment.
2. **Given** historical efforts for a segment, **When** a coach or athlete opens the segment view, **Then** the system presents the key performance values captured or reconstructed for each effort and makes membership-only rows explicit when elapsed time is unavailable.
3. **Given** a segment with only one recorded effort, **When** the user reviews it, **Then** the system still shows the effort clearly and indicates that trend interpretation is limited.

---

### User Story 3 - Compare Evolution On Relevant Metrics (Priority: P3)

As a coach or athlete, I need the system to highlight how performance has evolved across repeated efforts on the same segment so that training decisions can be grounded in comparable segment outcomes.

**Why this priority**: Historical storage alone is not enough; the feature becomes useful when repeated segment efforts can be interpreted as progress or decline.

**Independent Test**: Can be fully tested by reviewing a segment with multiple stored efforts and verifying that the system identifies progression signals from the captured metrics without requiring manual recomputation outside the product.

**Acceptance Scenarios**:

1. **Given** a segment with multiple efforts over time, **When** a coach or athlete reviews the segment analysis, **Then** the system shows how the most relevant performance metrics have changed across those efforts.
2. **Given** repeated efforts with partially missing supporting metrics or membership-only rows, **When** the analysis is shown, **Then** the system still compares the available metrics and makes missing values explicit instead of hiding the effort.
3. **Given** efforts on the same segment under different dates, **When** the user inspects the history, **Then** the system can identify best effort and recent trend without changing the underlying source records.

### Edge Cases

- What happens when Garmin returns segment information for some cycling activities in a batch but not for others? The system must store available segment data per activity without failing the full import or inventing missing segment records.
- How does the system handle repeated imports of the same cycling activity and segment effort? Canonical SQLite records must stay idempotent and traceable by stable Garmin source identity.
- What happens when a segment appears with the same name but a different source identity? The system must distinguish the source identities rather than merging distinct segments by display name alone.
- How does the system handle Garmin activities where segment membership is known but native effort metrics are not exposed? The system must preserve the membership record, avoid fabricating metrics, and mark the effort as not comparable until supported metrics are available.
- How does the system handle segment efforts where some metrics are missing, such as power, cadence, or heart rate? The effort remains stored and comparable on the metrics that are present.
- What happens when Garmin marks only a subset of activity segments as favorites? Only favorite-tagged segments are in scope for this version and non-favorite rows must not survive re-imports for the same activity.
- What happens when a coach or athlete requests analysis for a segment with only one effort or with no recent efforts? The system must still present the available history and avoid implying a trend that cannot be supported.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST identify whether an imported Garmin cycling activity includes favorite-tagged segment information relevant to athlete performance analysis.
- **FR-002**: The system MUST persist in-scope Garmin segment information in SQLite as the canonical source of truth for this feature.
- **FR-003**: The system MUST persist the relationship between an imported activity and each detected in-scope segment row for that activity, including membership-only rows when comparable metrics are unavailable.
- **FR-004**: Each persisted segment effort MUST retain the Garmin source identity needed to support idempotent re-import and historical traceability.
- **FR-005**: The system MUST preserve idempotent canonical writes so repeated import of the same Garmin activity does not create unintended duplicate segment or segment-effort records.
- **FR-006**: The system MUST store elapsed time for each segment effort when Garmin exposes it directly or when it can be derived deterministically from imported activity detail data; otherwise the segment row MUST remain visible as membership-only data.
- **FR-007**: When Garmin provides or the backend can derive supporting metrics for a segment effort, the system MUST store those metrics in SQLite for later analysis, including available power, cadence, and heart rate values.
- **FR-008**: The system MUST record the activity date and the imported activity identity associated with each stored segment effort.
- **FR-009**: The system MUST allow coach and athlete users to review the chronological history of efforts for a selected segment.
- **FR-010**: The system MUST present repeated efforts for a segment in a way that makes evolution over time understandable from the stored metrics.
- **FR-011**: The system MUST distinguish best known effort and recent efforts for a segment without overwriting the original imported effort records.
- **FR-012**: When one or more metrics are missing for a stored effort, the system MUST keep the effort visible and explicitly indicate which metrics are unavailable.
- **FR-013**: The feature MUST state SQLite as the source of truth for all imported segment facts and derived segment-history views.
- **FR-014**: Any GUI behavior introduced by this feature MUST rely on backend-provided segment data and comparison results rather than embedding non-trivial Garmin domain logic in the frontend.
- **FR-015**: The feature MUST remain scoped to cycling activities imported from Garmin Connect and MUST NOT require automatic changes to seasonal markdown files.
- **FR-016**: If Garmin segment data is unavailable for an imported cycling activity, the system MUST preserve a non-ambiguous outcome for the activity import without fabricating segment records.
- **FR-017**: This version of the feature MUST persist only Garmin segments marked as favorite for the activity.
- **FR-018**: Re-import of an activity MUST remove previously persisted segment-effort rows that are no longer in scope under the current favorite-only import rule.

### Key Entities *(include if feature involves data)*

- **Segment Definition**: A canonical record representing one Garmin segment identity that may recur across multiple imported cycling activities.
- **Segment Effort**: A canonical record of one athlete attempt on a specific segment within a specific imported cycling activity, including time and any available supporting performance metrics.
- **Activity-Segment Link**: The relationship between an imported cycling activity and the segment efforts observed within it.
- **Segment Performance History**: The ordered collection of stored efforts for a segment, used to review progression, recent form, and best known performance.
- **Segment Analysis View**: A user-facing representation of stored segment history that highlights evolution over time without altering the canonical source records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of imported cycling activities that include in-scope favorite segment information in Garmin Connect produce durable SQLite records for those segment rows.
- **SC-002**: Re-importing the same Garmin cycling activity does not create unintended duplicate canonical segment or segment-effort records.
- **SC-003**: A coach or athlete can review the stored history of a repeated segment and identify the athlete's best effort and recent effort sequence within 2 minutes.
- **SC-004**: For segment efforts where Garmin provides native metrics or the backend can reconstruct them from imported activity detail data, those metrics are visible in stored history for elapsed time and any available power, cadence, and heart rate values.
- **SC-005**: Segment analysis remains usable when some supporting metrics are missing or when a row is membership-only, with those gaps shown explicitly instead of hiding the effort from history.
- **SC-006**: Re-importing an already imported activity after scope refinement leaves no stale non-favorite segment rows attached to that activity in SQLite.

## Assumptions

- Garmin Connect provides favorite-tagged segment-related data for at least some cycling activities relevant to this training workflow.
- Segment identity from Garmin is stable enough to support canonical deduplication and repeated historical comparison.
- Cycling activities remain the only in-scope discipline for the first version of this feature.
- SQLite remains the authoritative source for imported segment data and any analysis views derived from it.
- Coach and athlete access can be delivered through the existing local GUI surfaces without introducing a separate external analytics system.
- Seasonal markdown files are not updated automatically by this feature.