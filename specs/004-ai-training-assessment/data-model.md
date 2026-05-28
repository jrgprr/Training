# Data Model: AI Training Assessment Agents

## 1. AssessmentAgentProfile

- Purpose: Define one backend-owned specialist LLM profile for a cadence and assessment purpose.
- Proposed storage: new table `agent_assessment_profiles`.

### Core fields

- `agent_profile_id`: integer primary key.
- `profile_key`: stable unique key such as `daily_execution_v1`.
- `display_name`: operator-facing name.
- `cadence`: `daily`, `weekly`, `block`, or `season`.
- `assessment_scope`: stable type grouping such as `execution`, `recovery_readiness`, `adherence_adequacy`, `performance_direction`.
- `target_planning_level`: nullable `weekly`, `block`, `season`, or `macro` for proposal targeting.
- `instruction_version`: version string for prompt/instruction bundle.
- `provider_key`: nullable default provider identifier.
- `model_name`: nullable default model identifier.
- `execution_policy`: JSON/text with limits such as timeout, maximum context size, and whether proposal emission is allowed.
- `status`: `active`, `inactive`, or `experimental`.
- `created_at`, `updated_at`: timestamps.

### Constraints

- `UNIQUE (profile_key)`.
- Multiple active profiles may share the same `cadence`.

## 2. AssessmentWindow

- Purpose: Represent the bounded time window and evidence identity for a cadence review.
- Proposed storage: new table `agent_assessment_windows`.

### Core fields

- `assessment_window_id`: integer primary key.
- `cadence`: `daily`, `weekly`, `block`, or `season`.
- `season_id`: foreign key to `plan_seasons.season_id`.
- `block_id`: nullable foreign key to `plan_meso_blocks.block_id`.
- `week_id`: nullable foreign key to `plan_micro_weeks.week_id`.
- `window_start_date`: ISO date.
- `window_end_date`: ISO date.
- `subject_scope_key`: stable identifier for the planning surface under review, such as `season:2026`, `block:B2`, `week:2026-B2-W03`, or `day:2026-05-28`.
- `evidence_fingerprint`: backend-computed digest representing the relevant canonical evidence set.
- `latest_materialized_at`: timestamp when the fingerprint and evidence snapshot were last computed.

### Constraints

- `UNIQUE (cadence, subject_scope_key, evidence_fingerprint)` for materially distinct evidence states.
- A later evidence change within the same date window produces a new row with a new fingerprint.

## 3. LLMAssessmentRun

- Purpose: Persist one LLM invocation for one profile over one assessment window.
- Proposed storage: new table `agent_assessment_runs`.

### Core fields

- `assessment_run_id`: integer primary key.
- `agent_profile_id`: foreign key to `agent_assessment_profiles.agent_profile_id`.
- `assessment_window_id`: foreign key to `agent_assessment_windows.assessment_window_id`.
- `trigger_mode`: `manual`, `rerun`, or `scheduled`.
- `run_status`: `queued`, `running`, `completed`, `no_new_data`, `partial_context`, `failed`, or `cancelled`.
- `provider_key`: nullable provider used for the run.
- `model_name`: nullable model used for the run.
- `instruction_version`: persisted copy of the profile instruction version used.
- `prompt_hash`: hash of the rendered prompt payload for reproducibility without storing unsafe raw prompt text inline in every query surface.
- `summary_text`: nullable high-level assessment summary.
- `confidence_label`: nullable bounded label such as `high`, `medium`, or `limited`.
- `principal_evidence_json`: JSON/text summary of main evidence categories and references.
- `failure_code`: nullable stable error code.
- `failure_detail`: nullable operator-readable failure text.
- `started_at`, `completed_at`, `created_at`: timestamps.
- `supersedes_run_id`: nullable self-reference when a rerun replaces a prior latest run for the same profile/window.

### Constraints

- Independent runs for different profiles within the same cadence/window are allowed.
- `run_status = completed` requires either `summary_text` or at least one child finding.
- `run_status = failed` or `partial_context` must preserve failure or limitation detail instead of synthetic completed output.

## 4. AssessmentTypeResult

- Purpose: Persist the structured outputs for one named assessment type inside a run.
- Proposed storage: new table `agent_assessment_type_results`.

### Core fields

- `assessment_type_result_id`: integer primary key.
- `assessment_run_id`: foreign key to `agent_assessment_runs.assessment_run_id`.
- `assessment_type_key`: stable key such as `daily_execution`, `daily_recovery_readiness`, `weekly_adherence`, `weekly_plan_adequacy`, `block_performance_direction`.
- `result_label`: concise interpretation such as `on_plan`, `fatigue_risk`, `plateau`, `regressing`, `maintain_plan`.
- `confidence_label`: nullable `high`, `medium`, `limited`.
- `narrative_text`: operator-facing explanation for this assessment type.
- `evidence_summary_json`: JSON/text listing key supporting signals and explicit gaps.
- `created_at`: timestamp.

### Constraints

- `UNIQUE (assessment_run_id, assessment_type_key)`.
- A single run may have multiple type results.

## 5. AssessmentFinding

- Purpose: Store structured findings extracted from an assessment run.
- Proposed storage: new table `agent_assessment_findings`.

### Core fields

- `assessment_finding_id`: integer primary key.
- `assessment_run_id`: foreign key to `agent_assessment_runs.assessment_run_id`.
- `assessment_type_result_id`: nullable foreign key to `agent_assessment_type_results.assessment_type_result_id`.
- `finding_kind`: `positive_signal`, `risk_signal`, `adherence_observation`, `recovery_observation`, `performance_signal`, `next_action`, or `data_confidence`.
- `severity`: nullable `info`, `watch`, `warning`, or `critical`.
- `title`: short operator-facing label.
- `detail_text`: supporting explanation.
- `evidence_refs_json`: JSON/text references to canonical entities such as activities, daily metrics, segments, reviews, or weeks.
- `sort_order`: integer display order.
- `created_at`: timestamp.

### Constraints

- Findings remain independent records so the GUI can filter and group them without reparsing full assessment text.

## 6. AdaptationProposal

- Purpose: Persist one AI-generated proposal to adjust the next planning level above the source cadence.
- Proposed storage: new table `agent_adaptation_proposals`.

### Core fields

- `proposal_id`: integer primary key.
- `assessment_run_id`: foreign key to `agent_assessment_runs.assessment_run_id`.
- `agent_profile_id`: foreign key to `agent_assessment_profiles.agent_profile_id`.
- `source_cadence`: `daily`, `weekly`, `block`, or `season`.
- `target_planning_level`: `weekly`, `block`, `season`, or `macro`.
- `proposal_status`: `pending`, `accepted`, `rejected`, or `superseded`.
- `proposal_title`: short summary.
- `proposal_summary`: operator-facing explanation of the proposed change.
- `change_kind`: stable category such as `reduce_volume`, `preserve_intensity`, `extend_stabilization`, `revise_block_emphasis`, `adjust_macro_priority`.
- `proposed_change_json`: structured payload describing intended mutations at the target planning level.
- `reasoning_summary`: concise AI rationale stored separately from full narrative findings.
- `conflict_group_key`: nullable key used to group overlapping proposals on the same planning surface.
- `created_at`, `updated_at`: timestamps.

### Constraints

- Proposals do not mutate plan tables by themselves.
- Multiple concurrent proposals for the same target planning surface are allowed.

## 7. ProposalDecision

- Purpose: Record operator review of a proposal.
- Proposed storage: new table `agent_proposal_decisions`.

### Core fields

- `proposal_decision_id`: integer primary key.
- `proposal_id`: foreign key to `agent_adaptation_proposals.proposal_id`.
- `decision_status`: `accepted`, `rejected`, or `superseded`.
- `decision_note`: nullable operator note.
- `decided_by`: text actor identifier for the local operator.
- `decided_at`: timestamp.
- `superseding_proposal_id`: nullable foreign key when this proposal is superseded by another.
- `applied_change_ref`: nullable reference to the resulting accepted plan mutation record.

### Constraints

- The latest decision determines the current proposal state, but prior decisions remain preserved for history.

## 8. AcceptedPlanMutation

- Purpose: Trace the canonical SQLite plan change produced by accepting a proposal.
- Proposed storage: new table `review_plan_mutations` or equivalent review namespace table.

### Core fields

- `plan_mutation_id`: integer primary key.
- `proposal_id`: foreign key to `agent_adaptation_proposals.proposal_id`.
- `target_planning_level`: `weekly`, `block`, `season`, or `macro`.
- `target_entity_id`: identifier of the changed canonical planning record.
- `mutation_summary`: concise description of what changed.
- `before_snapshot_json`: structured before-state.
- `after_snapshot_json`: structured after-state.
- `applied_at`: timestamp.
- `applied_by`: actor identifier.

### Constraints

- Every accepted proposal that mutates the canonical plan should have exactly one mutation linkage record.

## 9. AssessmentDialogContext

- Purpose: Persist bounded follow-up questions and user clarifications tied to a specific assessment run or proposal.
- Proposed storage: new table `agent_assessment_dialog_context`.

### Core fields

- `dialog_context_id`: integer primary key.
- `assessment_run_id`: nullable foreign key to `agent_assessment_runs.assessment_run_id`.
- `proposal_id`: nullable foreign key to `agent_adaptation_proposals.proposal_id`.
- `entry_kind`: `user_question`, `user_clarification`, `assistant_response`, or `system_note`.
- `entry_scope`: bounded scope such as `assessment_summary`, `finding`, `proposal`, or `reassessment_request`.
- `clarification_kind`: nullable stable key such as `schedule_shift`, `session_swap`, `missing_context`, `device_issue`, or `execution_intent`.
- `entry_text`: persisted dialog text.
- `linked_evidence_json`: nullable JSON/text references to canonical entities or affected proposal fields.
- `created_at`: timestamp.
- `created_by`: text actor identifier such as `local-operator`, `athlete`, or `system`.

### Constraints

- At least one of `assessment_run_id` or `proposal_id` must be present.
- Dialog context does not mutate canonical plan or execution state directly.
- Clarifications remain reviewable inputs and may be linked to a later reassessment run or proposal decision.

## 10. AssessmentReviewView

- Purpose: Provide a thin read model for the GUI and API.
- Storage: derived from the canonical tables above in `Sistema/views.sql` or backend query helpers.

### Derived fields

- latest run per cadence/profile/window
- run status and freshness
- grouped findings
- confidence and evidence summary
- linked proposals and current decision state
- linked bounded dialog context and clarification history
- source cadence to target planning level mapping

## State Transitions

### `agent_assessment_runs.run_status`

- `queued -> running`
- `running -> completed`
- `running -> partial_context`
- `running -> no_new_data`
- `running -> failed`
- `queued -> cancelled`

### `agent_adaptation_proposals.proposal_status`

- `pending -> accepted`
- `pending -> rejected`
- `pending -> superseded`
- `accepted -> superseded` only if a later accepted change explicitly replaces it and the history is preserved

## Validation Rules

- Daily-generated proposals must target `weekly` only.
- Weekly-generated proposals must target `block` only.
- Block-generated proposals must target `season` only.
- Season-generated proposals must target `macro` only.
- `completed` runs must store the producing `agent_profile_id` and the resolved `assessment_window_id`.
- `failed` and `partial_context` runs must still persist provider/model/profile provenance.
- Accepted proposals cannot be applied without a recorded operator decision.
- Multiple profiles in the same cadence may produce independent runs and proposals for the same window without being collapsed automatically.
- User clarifications must persist as dialog context first and only influence canonical conclusions through a traceable reassessment or proposal-decision flow.