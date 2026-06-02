# Research: Training Zones

## Decision 1: Define canonical zone profiles separately for heart rate and power

- Decision: Persist zone profiles in SQLite as versioned canonical entities keyed by discipline, metric basis, and effective date range, with heart-rate and power profiles stored separately rather than blended into one generic zone model.
- Rationale: The specification now requires first-version support for both heart-rate zones and power zones. Separate canonical profiles preserve traceability, allow different refinement evidence per basis, and keep historical activity calculations explainable after profile updates.
- Alternatives considered:
  - One shared zone profile with optional heart-rate and power columns: rejected because governance, traceability, and versioning would become ambiguous when one basis changes without the other.
  - Derive zones ad hoc per activity without persisted profiles: rejected because historical comparability and acceptance governance would be lost.

## Decision 2: Calculate executed zone distributions from canonical activity summaries and metric streams, not from plan text

- Decision: Treat Garmin-imported real activities as the primary evidence for zone calculation, with executed heart-rate and power zone distributions computed in backend code from canonical activity data and persisted in SQLite.
- Rationale: The user explicitly prioritized zones derived from real data over zones inferred from planned sessions. Backend-owned persisted calculations make later refinement, weekly summaries, and plan-versus-reality analysis deterministic and queryable.
- Alternatives considered:
  - Infer zones primarily from planned prescriptions like Z2 and compare activities later: rejected because planned labels do not establish individualized boundaries.
  - Calculate zone distributions only at read time in the frontend: rejected because domain logic must stay out of the GUI and the results need canonical persistence.

## Decision 3: Treat heart-rate and power zone distributions as parallel outputs for the same activity

- Decision: When an activity has trustworthy evidence for both bases, persist separate heart-rate and power zone distributions for the same activity instead of forcing the system to choose a single "best" basis.
- Rationale: Heart rate and power describe different aspects of the same effort. Preserving both avoids hiding disagreement, enables later comparison, and matches the requirement that both bases be first-class in version one.
- Alternatives considered:
  - Choose one preferred basis globally per discipline: rejected because it would discard useful evidence and hide basis-specific limitations.
  - Blend heart-rate and power into a single hybrid zone view: rejected because the resulting boundary logic would be opaque and hard to validate.

## Decision 4: Use daily metrics only as refinement context and confidence modulation

- Decision: Daily metrics such as resting heart rate, HRV, sleep, stress, and related signals influence confidence, prudence, and proposal timing for zone refinement, but do not directly generate zone boundaries on their own.
- Rationale: The current system already treats daily metrics as recovery context rather than autonomous decision-makers. That keeps refinement evidence grounded in real training outputs while still respecting readiness and absorption signals.
- Alternatives considered:
  - Compute new zones directly from daily metrics trends: rejected because those signals do not define training intensity boundaries by themselves.
  - Ignore daily metrics entirely during refinement: rejected because the specification explicitly requires them as support for refinement prudence.

## Decision 5: Make refinement produce proposals, not silent profile updates

- Decision: Refinement analysis produces traceable pending proposals for the heart-rate profile, the power profile, or both, while accepted active profiles remain unchanged until an explicit governance action promotes the proposal.
- Rationale: Zone changes alter interpretation of past and future activities. Separating proposals from accepted profiles preserves auditability and prevents silent drift in the canonical model.
- Alternatives considered:
  - Automatically overwrite the active profile when evidence crosses a threshold: rejected because it would break trust and historical explainability.
  - Allow freeform manual edits only with no proposal state: rejected because the feature's value is structured, evidence-backed refinement.

## Decision 6: Keep planned zone structure as a secondary comparison layer

- Decision: Persist structured planned zone targets only when they are explicit or mappable from the session prescription, and use them mainly for plan-versus-reality comparison against executed heart-rate and power zone distributions.
- Rationale: Planned zones matter operationally, but they are not the primary source for individualized zone definition. Keeping them secondary matches the user's updated priority while still enabling compliance review.
- Alternatives considered:
  - Ignore planned zones entirely: rejected because sessions already reference zone intent and comparing intent versus execution remains useful.
  - Treat planned zones as the primary source of truth for zone boundaries: rejected because that contradicts the feature priority.

## Decision 7: Version executed zone results against the specific profile version used for each basis

- Decision: Every persisted executed zone distribution stores the exact heart-rate profile version or power profile version used during calculation, plus a limited/unavailable status when one basis cannot be computed.
- Rationale: Historical explainability depends on knowing which accepted boundaries governed each result. This is especially important when heart-rate and power profiles may be updated independently.
- Alternatives considered:
  - Store only the current active profile reference at read time: rejected because profile changes would retroactively alter interpretation without traceability.
  - Recompute all historical results whenever a profile changes: rejected because it would erase the historical meaning of prior decisions.

## Decision 8: Scope the first implementation to cycling activities while keeping the canonical model discipline-aware

- Decision: The first implementation focuses executed zone calculation and refinement on cycling activities, but the schema and service model remain discipline-aware so later expansion does not require redesign.
- Rationale: The current Garmin dataset and existing backend surfaces are richest for cycling, especially for power. Starting there gives the strongest evidence base for first-version heart-rate and power zone support.
- Alternatives considered:
  - Require all disciplines in the first implementation: rejected because non-cycling disciplines may not provide sufficiently consistent power evidence.
  - Hard-code cycling-specific assumptions into the canonical model: rejected because the system should remain extensible.

## Decision 9: Add a dedicated backend service module for zone logic

- Decision: Introduce a backend-owned `training_zones.py` service module to centralize profile selection, executed distribution calculation, refinement proposal generation, and read-model serialization.
- Rationale: Zone calculation and refinement are domain logic, not import glue and not frontend behavior. A dedicated module keeps the implementation coherent and testable while minimizing leakage into route handlers.
- Alternatives considered:
  - Spread the logic across `main.py` and import adapters: rejected because it would make dual-basis refinement difficult to reason about.
  - Put zone logic in SQLite views only: rejected because the proposal and refinement algorithms require richer backend logic than views alone should carry.
