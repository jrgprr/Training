# Data Model: Training Zones

## 1. ZoneMetricProfile

- Purpose: Persist the user-owned physiological anchors that define zones for one discipline and metric basis over time.
- Proposed storage: table `zone_metric_profiles`.

### Core fields

- `zone_metric_profile_id`: integer primary key.
- `season_id`: nullable foreign key to `plan_seasons.season_id` when the values are season-scoped.
- `discipline`: normalized discipline such as `cycling`.
- `metric_basis`: normalized basis such as `heart_rate` or `power`.
- `profile_label`: human-readable label such as `cycling hr reserve 5 zones v1`.
- `model_key`: derivation model such as `heart_rate_reserve_5_zone` or `ftp_coggan_7_zone`.
- `resting_hr`: nullable numeric anchor used by HR reserve models.
- `max_hr`: nullable numeric anchor used by HR reserve models.
- `ftp`: nullable numeric anchor used by FTP-based power models.
- `effective_start_date`: first date where the metric profile becomes active.
- `effective_end_date`: nullable closing date when a newer metric profile supersedes it.
- `accepted_at`: nullable timestamp.
- `notes`: nullable governance notes for how the values were chosen.
- `created_at`, `updated_at`: timestamps.

### Constraints

- `UNIQUE (discipline, metric_basis, effective_start_date)` is sufficient for the current accepted-only workflow.
- Only one current metric profile per `(discipline, metric_basis)` may remain open-ended at a time.
- Heart-rate and power anchors must version independently.

## 2. ZoneProfile

- Purpose: Define one accepted or historical canonical zone profile for a discipline and metric basis.
- Proposed storage: new table `zone_profiles`.

### Core fields

- `zone_profile_id`: integer primary key.
- `season_id`: nullable foreign key to `plan_seasons.season_id` when the profile is season-scoped; null allowed if later the model supports cross-season canonical baselines.
- `discipline`: normalized discipline such as `cycling`.
- `metric_basis`: normalized basis such as `heart_rate` or `power`.
- `profile_label`: human-readable label such as `cycling hr v1`.
- `source_metric_profile_id`: nullable foreign key to `zone_metric_profiles.zone_metric_profile_id` when the accepted boundaries were derived from user anchors.
- `calculation_model_key`: nullable model identifier such as `heart_rate_reserve_5_zone` or `ftp_coggan_7_zone`.
- `governance_status`: `pending`, `accepted`, `superseded`, or `rejected`.
- `effective_start_date`: first date where the profile may govern executed-zone calculations.
- `effective_end_date`: nullable closing date when a newer accepted profile supersedes it.
- `derived_from_proposal_id`: nullable foreign key to `zone_refinement_proposals.proposal_id`.
- `accepted_at`: nullable timestamp.
- `created_at`, `updated_at`: timestamps.

### Constraints

- `UNIQUE (discipline, metric_basis, effective_start_date, governance_status)` is a defensible first-pass uniqueness guard.
- Only one `accepted` profile per `(discipline, metric_basis, effective date)` window may be active at a time.
- The canonical model must allow heart-rate and power profiles to version independently.
- Derived zone profiles should preserve the source metric profile so historical calculations remain traceable back to the HRR or FTP anchor set in force at that time.

## 3. ZoneProfileBoundary

- Purpose: Persist the ordered zone boundaries that belong to one canonical profile.
- Proposed storage: new table `zone_profile_boundaries`.

### Core fields

- `zone_profile_boundary_id`: integer primary key.
- `zone_profile_id`: foreign key to `zone_profiles.zone_profile_id`.
- `zone_index`: integer ordinal such as `1` for Z1, `2` for Z2.
- `zone_code`: stable label such as `Z1`, `Z2`, `Z3`, `Z4`, `Z5`.
- `zone_name`: nullable descriptive label such as `endurance` or `threshold`.
- `lower_bound_value`: nullable numeric lower bound.
- `upper_bound_value`: nullable numeric upper bound.
- `bound_unit`: basis-aligned unit such as `bpm` or `watts`.
- `target_kind`: `closed`, `open_ended`, or `range`.
- `created_at`, `updated_at`: timestamps.

### Constraints

- `UNIQUE (zone_profile_id, zone_index)`.
- `UNIQUE (zone_profile_id, zone_code)`.
- Boundaries must be ordered and non-overlapping inside one accepted profile.
- `upper_bound_value` may be null only for the top open-ended zone.

## 4. ExecutedActivityZoneResult

- Purpose: Persist the canonical executed time-in-zone outcome for one activity and one metric basis.
- Proposed storage: new table `exec_activity_zone_results`.

### Core fields

- `activity_zone_result_id`: integer primary key.
- `activity_id`: foreign key to `exec_activities.activity_id`.
- `zone_profile_id`: foreign key to `zone_profiles.zone_profile_id`.
- `metric_basis`: normalized basis such as `heart_rate` or `power`.
- `calculation_status`: `calculated`, `limited`, `unavailable`, or `not_applicable`.
- `quality_status_snapshot`: nullable copy of the governing activity quality status at calculation time.
- `supported_sample_count`: integer count of samples or effective intervals used.
- `total_supported_seconds`: integer total seconds contributing to the distribution.
- `dominant_zone_code`: nullable zone label with the highest supported duration.
- `dominant_zone_share`: nullable numeric fraction in `[0, 1]`.
- `calculated_at`: timestamp.
- `calculation_notes`: nullable traceability text.

### Constraints

- `UNIQUE (activity_id, metric_basis, zone_profile_id)`.
- Only one latest canonical result per `(activity_id, metric_basis)` should remain active if recalculation is deterministic under unchanged inputs.
- `calculation_status = calculated` requires at least one related bucket row.

## 5. ExecutedActivityZoneBucket

- Purpose: Persist one zone bucket inside a canonical executed activity result.
- Proposed storage: new table `exec_activity_zone_buckets`.

### Core fields

- `activity_zone_bucket_id`: integer primary key.
- `activity_zone_result_id`: foreign key to `exec_activity_zone_results.activity_zone_result_id`.
- `zone_index`: integer ordinal matching the accepted profile boundary.
- `zone_code`: stable label such as `Z2`.
- `seconds_in_zone`: integer supported seconds in that zone.
- `share_in_zone`: numeric fraction in `[0, 1]`.
- `sample_count`: nullable integer count of contributing samples.
- `created_at`: timestamp.

### Constraints

- `UNIQUE (activity_zone_result_id, zone_index)`.
- `share_in_zone` rows for one `activity_zone_result_id` should sum to approximately `1.0` when `calculation_status = calculated`.

## 6. ZoneRefinementProposal

- Purpose: Represent one backend-generated recommendation to adjust the active zone profile for one basis.
- Proposed storage: new table `zone_refinement_proposals`.

### Core fields

- `proposal_id`: integer primary key.
- `season_id`: foreign key to `plan_seasons.season_id`.
- `discipline`: normalized discipline such as `cycling`.
- `metric_basis`: normalized basis such as `heart_rate` or `power`.
- `source_zone_profile_id`: foreign key to `zone_profiles.zone_profile_id` for the currently accepted profile.
- `proposal_status`: `pending`, `accepted`, `rejected`, `deferred`, or `expired`.
- `confidence_level`: `low`, `medium`, or `high`.
- `recommendation_kind`: `tighten`, `loosen`, `rebalance`, or `no_change`.
- `proposal_summary`: human-readable rationale summary.
- `limiting_factors`: nullable JSON/text list of reasons confidence is reduced.
- `proposed_effective_start_date`: nullable ISO date.
- `created_at`: timestamp.
- `decided_at`: nullable timestamp.
- `decision_notes`: nullable governance notes.

### Constraints

- Multiple pending proposals may exist historically, but at most one latest actionable `pending` proposal per `(season_id, discipline, metric_basis)` should be exposed in the first version.
- Accepting a proposal must not mutate or delete the source profile; it creates a new accepted profile version.

## 7. ZoneRefinementProposalBoundary

- Purpose: Store the proposed boundary set attached to a refinement proposal.
- Proposed storage: new table `zone_refinement_proposal_boundaries`.

### Core fields

- `proposal_boundary_id`: integer primary key.
- `proposal_id`: foreign key to `zone_refinement_proposals.proposal_id`.
- `zone_index`: integer ordinal.
- `zone_code`: stable zone label.
- `proposed_lower_bound_value`: nullable numeric lower bound.
- `proposed_upper_bound_value`: nullable numeric upper bound.
- `bound_unit`: basis-aligned unit such as `bpm` or `watts`.
- `delta_vs_current_lower`: nullable numeric lower-bound shift.
- `delta_vs_current_upper`: nullable numeric upper-bound shift.

### Constraints

- `UNIQUE (proposal_id, zone_index)`.
- Proposal boundary rows are immutable evidence once the proposal is created.

## 8. ZoneRefinementEvidence

- Purpose: Preserve traceability to the activities and daily metrics that supported, limited, or deferred a proposal.
- Proposed storage: new table `zone_refinement_evidence`.

### Core fields

- `proposal_evidence_id`: integer primary key.
- `proposal_id`: foreign key to `zone_refinement_proposals.proposal_id`.
- `evidence_type`: `activity`, `daily_metric`, or `window_summary`.
- `activity_id`: nullable foreign key to `exec_activities.activity_id`.
- `daily_metric_id`: nullable foreign key to `exec_daily_metrics.daily_metric_id`.
- `evidence_date`: nullable ISO date for ordering and review.
- `evidence_role`: `supporting`, `limiting`, or `context`.
- `metric_basis`: nullable basis when the evidence is basis-specific.
- `summary_json`: structured explanation payload describing why this evidence matters.
- `created_at`: timestamp.

### Constraints

- `activity_id` and `daily_metric_id` are mutually optional, but at least one evidence anchor or a `window_summary` payload must exist.
- The first version should support both concrete evidence rows and one synthetic window summary row per proposal.

## 9. PlannedSessionZoneTarget

- Purpose: Persist structured planned zone intent for one planned session while preserving the narrative prescription elsewhere.
- Proposed storage: new table `plan_session_zone_targets`.

### Core fields

- `planned_zone_target_id`: integer primary key.
- `planned_session_id`: foreign key to `plan_planned_sessions.planned_session_id`.
- `target_basis`: nullable basis such as `heart_rate`, `power`, or `mixed`.
- `target_kind`: `single_zone`, `zone_range`, or `multi_segment`.
- `source_kind`: `explicit`, `mapped_rule`, or `manual`.
- `source_text`: nullable original plan fragment from which the structure was derived.
- `comparison_eligibility`: `eligible`, `limited`, or `not_comparable`.
- `created_at`, `updated_at`: timestamps.

### Constraints

- A planned session may have zero or one canonical structured target record in the first version.
- The original session narrative remains in `plan_planned_sessions` and `plan_session_prescriptions`.

## 10. PlannedSessionZoneSegment

- Purpose: Represent one ordered segment inside a structured planned zone target.
- Proposed storage: new table `plan_session_zone_segments`.

### Core fields

- `planned_zone_segment_id`: integer primary key.
- `planned_zone_target_id`: foreign key to `plan_session_zone_targets.planned_zone_target_id`.
- `sequence_order`: integer order inside the planned session.
- `segment_label`: nullable text such as `warmup`, `main set`, or `cooldown`.
- `target_zone_min_code`: nullable lower zone label such as `Z2`.
- `target_zone_max_code`: nullable upper zone label such as `Z3`.
- `target_duration_seconds_min`: nullable integer.
- `target_duration_seconds_max`: nullable integer.
- `notes`: nullable text.

### Constraints

- `UNIQUE (planned_zone_target_id, sequence_order)`.
- A `single_zone` target has one segment row; a `zone_range` target also has one row but both min/max labels may be set.

## 11. ZoneComparisonResult

- Purpose: Provide a backend-owned read model describing how planned zone intent aligned with executed distributions for one session or aggregated week view.
- Storage: derived from `plan_session_zone_targets`, `exec_activity_zone_results`, `exec_activity_zone_buckets`, `exec_activities`, and existing week/session joins; not persisted as a canonical table in the first version.

### Derived fields

- `planned_session_id`
- `activity_id`: nullable when the planned session has no matched execution.
- `comparison_scope`: `session` or `week`
- `metric_basis`: `heart_rate` or `power`
- `comparison_status`: `aligned`, `partially_aligned`, `misaligned`, `limited`, or `not_comparable`
- `planned_zone_summary`: concise structured target summary.
- `executed_zone_summary`: dominant zone and notable shares from the canonical executed result.
- `alignment_score`: nullable numeric score kept backend-owned.
- `limiting_reasons`: list of reasons comparison is partial or limited.

## State Transitions

### `zone_profiles.governance_status`

- `pending -> accepted`
- `pending -> rejected`
- `accepted -> superseded`
- `accepted -> accepted`

### `zone_refinement_proposals.proposal_status`

- `pending -> accepted`
- `pending -> rejected`
- `pending -> deferred`
- `deferred -> pending`
- `pending -> expired`

### `exec_activity_zone_results.calculation_status`

- `unavailable -> calculated`
- `unavailable -> limited`
- `limited -> calculated`
- `calculated -> calculated`
- `calculated -> limited`

Repeated recalculation with unchanged canonical inputs, unchanged accepted profile version, and unchanged quality-governed readings must not create duplicate executed zone results or duplicate bucket rows.