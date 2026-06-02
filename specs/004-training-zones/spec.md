# Feature Specification: Training Zones

**Feature Branch**: `004-training-zones`

**Created**: 2026-06-01

**Status**: Closed

**Closed**: 2026-06-02

**Closure Note**: Implemented with canonical SQLite support for accepted physiological anchors and derived heart-rate/power zone profiles, executed time-in-zone persistence, traceable refinement proposals, structured planned zone targets, thin GUI visibility, active HRR/FTP profiles for 2026 cycling, and end-to-end validation across backend tests, frontend build, live API checks, and runtime SQLite updates.

**Input**: User description: "I want to have the information of the training zones in the system. Some scheduled activities already indicate zones like Z2, but the main priority is that the system calculate and refine my zones from my real activities and daily metrics. Zones should be defined both for power and for heart rate. Planned zones should be represented too, but as secondary support."

## Affected System Layers *(mandatory)*

- **Primary layer(s)**: `Sistema/`, `GUI/backend`, thin `GUI/frontend` visibility for zone profiles, executed time in zone, refinement status, and optional planned-zone comparison
- **Canonical data impact**: SQLite remains the source of truth for zone definitions, executed zone distributions, refinement evidence, accepted zone updates, and any structured planned zone targets used for comparison. Markdown remains narrative context and documentation only.
- **External source impact**: Existing Garmin-imported activities and daily metrics become source evidence for zone calculation and refinement; no cloud zone engine or third-party coaching platform is introduced.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Calculate Executed Time In Zone From Real Activities (Priority: P1)

As an athlete or coach reviewing execution, I need the system to calculate how much time an activity spent in each zone using the currently active zone model so that zone information comes primarily from real training data.

**Why this priority**: This is the core user value. If the system cannot derive zones from real activities, then zone information remains descriptive rather than operational.

**Independent Test**: Can be fully tested by processing imported activities with suitable heart-rate and power data and confirming that the system persists executed zone distributions using the active heart-rate and power zone definitions for that date and discipline.

**Acceptance Scenarios**:

1. **Given** an imported cycling activity with suitable heart-rate and power readings, **When** the system analyzes the activity, **Then** it stores total time and proportion spent in each applicable heart-rate zone and each applicable power zone.
2. **Given** an activity whose available data supports one mandatory zone basis such as heart rate but not the other mandatory basis such as power, **When** zone calculation runs, **Then** the system calculates zones from the supported basis, records the missing basis as unavailable or limited, and preserves which basis was successfully used.
3. **Given** an activity with insufficient trustworthy data to calculate a defensible zone distribution, **When** the system evaluates that activity, **Then** it marks the zone outcome as unavailable or limited instead of fabricating a distribution.

---

### User Story 2 - Refine Zone Definitions From Evidence Over Time (Priority: P1)

As an athlete or coach, I need the system to propose refined training zones from recent activities and daily metrics so that the zone model evolves from my real data instead of remaining static.

**Why this priority**: Calculating zones once is not enough if the boundaries drift away from current fitness and state. Refinement from real evidence is the second half of the core goal.

**Independent Test**: Can be fully tested by providing a set of recent activities and daily metrics that support a zone shift and confirming that the system produces a traceable refinement proposal without silently overwriting the accepted zone profile.

**Acceptance Scenarios**:

1. **Given** a sufficient body of recent activities that indicates the current zone boundaries are stale, **When** refinement analysis runs, **Then** the system produces a traceable refinement proposal describing the suggested zone changes and the evidence behind them.
2. **Given** recent activities suggesting a shift but daily metrics indicating poor recovery or unstable state, **When** refinement analysis runs, **Then** the system lowers confidence, defers the proposal, or narrows its recommendation instead of treating the activity evidence as unconditionally final.
3. **Given** an accepted zone profile already in force, **When** refinement analysis generates a new proposal, **Then** the active profile remains unchanged until the proposal is explicitly accepted by the system's governance flow.

---

### User Story 3 - Compare Planned Zones Versus Executed Zones (Priority: P2)

As an athlete or coach reviewing plan versus reality, I need to compare planned zone intent with executed zone distribution so I can see whether sessions and weeks are being completed in the intended intensity ranges.

**Why this priority**: Once zones are derived from real data, the next operational value is to compare planned intent against executed distribution.

**Independent Test**: Can be fully tested by reviewing a week containing planned zone prescriptions and imported activities, then confirming that the backend and frontend expose comparable planned-versus-executed zone summaries.

**Acceptance Scenarios**:

1. **Given** a planned Z2 session and an executed activity with a stored zone distribution, **When** the system presents plan versus reality, **Then** it can show whether the majority of the execution actually stayed in the intended zone range.
2. **Given** a week mixing zone-based endurance sessions and non-zone strength or mobility work, **When** the week is summarized, **Then** only sessions with meaningful zone prescriptions contribute to zone-compliance summaries.
3. **Given** a session whose executed zone basis differs from the planned basis or is too weak to compare fairly, **When** plan versus reality is shown, **Then** the system marks the comparison as limited rather than implying false precision.

---

### User Story 4 - Represent Planned Training Zones In The System (Priority: P3)

As an athlete or coach reviewing the plan, I need scheduled sessions that refer to zones such as Z1, Z2, or threshold work to store that intent structurally so planned zones can be compared against real data when they exist.

**Why this priority**: Planned zones matter, but they are secondary to deriving and refining zone profiles from real evidence.

**Independent Test**: Can be fully tested by loading a planned week containing zone-based prescriptions and confirming that each applicable planned session exposes its zone target structurally through SQLite and backend responses.

**Acceptance Scenarios**:

1. **Given** a planned session whose prescription indicates a target zone such as Z2, **When** the session is loaded from the system, **Then** the zone target is available as structured data rather than only narrative text.
2. **Given** a planned session that prescribes more than one zone segment, **When** the session is reviewed, **Then** the system preserves the ordered zone structure instead of collapsing it into a single label.
3. **Given** a planned session without an explicit zone prescription, **When** the session is loaded, **Then** the system leaves the zone target empty instead of inferring one without evidence.

### Edge Cases

- What happens when a planned session uses narrative wording like "comfortable aerobic" rather than an explicit zone label? The system must keep the plan readable but zone calculation and refinement must remain grounded in real evidence, generating structured plan targets only when the evidence is explicit or mapped through an approved rule.
- What happens when heart rate and power suggest different zone interpretations for the same activity? The system must preserve both zone views when both are available, rather than blending them into one opaque result.
- What happens when daily metrics indicate unusual fatigue, illness, travel, heat stress, or poor absorption? The system must treat those metrics as contextual evidence that can reduce confidence or defer refinement, not as a standalone generator of new zones.
- What happens when a discipline such as yoga or strength has no meaningful aerobic zone model? The system must allow activities and sessions to remain outside zone analysis without forcing an artificial zone label.
- What happens when a refined zone proposal would change historical comparability? The system must keep traceability of which zone profile version was used for each activity calculation and each accepted plan comparison.
- What happens when imported activity quality is limited by missing or filtered readings? The zone calculation must inherit those limitations and avoid producing misleading distributions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define canonical zone profiles in SQLite for both heart rate and power, including the discipline, basis used for zoning, boundary definitions, effective dates, and profile versioning needed for traceability.
- **FR-002**: The system MUST calculate executed time in zone for eligible activities using the active heart-rate zone profile and the active power zone profile applicable to the activity date and discipline whenever the required data is available.
- **FR-003**: The system MUST record the executed zone distribution separately by metric basis, at minimum for heart rate and power, and MUST NOT imply a different basis than the one actually used.
- **FR-004**: When an activity does not contain enough trustworthy data to calculate a defensible heart-rate or power zone distribution, the system MUST record a limited or unavailable result for that basis rather than fabricating zone time.
- **FR-005**: Zone calculations MUST inherit existing quality decisions on raw activity data so that filtered or limited readings do not silently distort time-in-zone summaries.
- **FR-006**: The system MUST generate zone-refinement proposals from recent activity evidence and relevant daily metrics when enough evidence exists to justify a review of the active heart-rate zone profile, the active power zone profile, or both.
- **FR-007**: Daily metrics such as resting heart rate, HRV, body battery, stress, sleep, and similar recovery signals MUST be used only as contextual support for confidence and prudence in zone refinement and MUST NOT, by themselves, directly overwrite zone boundaries.
- **FR-008**: A zone-refinement proposal MUST preserve traceability to the activities, periods, and daily metrics that informed the recommendation, along with a confidence level and rationale.
- **FR-009**: The active zone profile MUST NOT be overwritten automatically by a refinement proposal; a proposal must remain pending until an explicit acceptance action applies it.
- **FR-010**: The system MUST version accepted zone profiles so historical activity calculations and plan-versus-reality comparisons remain traceable to the specific heart-rate profile version and power profile version used at that time.
- **FR-011**: The system MUST be able to summarize planned-versus-executed zone alignment at both session and week level for sessions whose prescriptions and activity evidence support comparison, distinguishing heart-rate-based and power-based comparisons when both exist.
- **FR-012**: The system MUST distinguish sessions and activities that are not meaningfully zone-based from sessions and activities that are zone-based but lack enough evidence for comparison.
- **FR-013**: The system MUST store structured planned zone targets for scheduled sessions when the prescription explicitly contains zone information or maps through an approved plan-to-zone rule.
- **FR-014**: The system MUST support zone targets that can represent at least a single target zone, a zone range, or an ordered multi-segment session prescription.
- **FR-015**: The system MUST preserve the original narrative prescription for a session even when structured zone targets are also stored.
- **FR-016**: The backend MUST own all zone calculation, comparison, and refinement logic; the frontend MUST remain a thin consumer of backend-provided zone targets, zone summaries, and proposal status.
- **FR-017**: The first version MUST support both heart-rate zones and power zones, and the canonical model MUST remain extensible to additional bases later without redesigning the model.
- **FR-018**: The system MUST make it possible to inspect why a zone refinement was suggested, deferred, or rejected, including the limiting factors when confidence is low.
- **FR-019**: The system MUST preserve SQLite as the authoritative store for zone definitions, calculated zone outcomes, refinement governance state, and any structured planned zone targets used in comparison.
- **FR-020**: The system MUST preserve the local-first workflow and MUST NOT require a cloud scoring service or external training platform to calculate or refine zones.

### Key Entities *(include if feature involves data)*

- **Zone Profile**: A versioned set of zone boundaries for a discipline and a specific metric basis, at minimum heart rate or power, including effective dates and governance status.
- **Planned Zone Target**: Structured zone intent attached to a planned session, which may describe a single zone, a zone range, or a multi-step prescription.
- **Executed Zone Distribution**: The calculated time and share spent in each zone for a real activity, recorded separately for heart rate and power when available, including basis-specific quality limitation status.
- **Zone Refinement Proposal**: A pending recommendation to adjust the active zone profile based on recent evidence, with rationale, confidence, and traceability.
- **Zone Refinement Evidence**: The underlying activities, periods, and daily metrics used to support or limit a zone update recommendation.
- **Zone Comparison Result**: A session-level or week-level interpretation of how planned zone intent aligned with executed heart-rate zone distribution, executed power zone distribution, or both.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of eligible imported activities with sufficient trustworthy data produce a persisted executed zone distribution for heart rate, for power, or for both, each tied to the corresponding zone profile version used for calculation.
- **SC-002**: Every refinement proposal includes traceability to the recent evidence set and an explicit confidence assessment before any accepted zone update can occur.
- **SC-003**: Historical zone calculations remain explainable after a profile update because the system preserves which heart-rate zone profile version and which power zone profile version governed each stored result.
- **SC-004**: A coach or athlete can determine within 2 minutes whether a zone-based session was executed broadly in line with its planned zone intent.
- **SC-005**: 100% of scheduled sessions with explicit zone prescriptions can be retrieved from SQLite and backend endpoints with structured zone targets rather than relying only on free text.

## Assumptions

- Garmin-imported activities already provide enough canonical evidence in heart rate and in power for a meaningful first version of time-in-zone calculation and later refinement.
- Daily metrics are useful for interpreting whether apparent fitness signals are stable enough to support a zone update, but they are not a primary estimator of zone boundaries by themselves.
- Some planned sessions already contain explicit or mappable zone intent, such as Z2, threshold, or similar labels that can be structured without inventing missing prescriptions.
- The first version must support both heart-rate zones and power zones even if the initial discipline scope remains narrow, provided the canonical model remains extensible to more disciplines and bases later.
- Zone refinement is a governance problem as much as a calculation problem, so proposals and accepted profiles must remain separate states.