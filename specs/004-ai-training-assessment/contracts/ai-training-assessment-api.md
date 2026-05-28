# Contract: AI Training Assessment API Surface

## Scope

This feature adds thin, backend-owned APIs for specialist AI assessment runs, assessment review, adaptation proposal review, and approval-gated plan mutation. SQLite remains the canonical runtime source of truth. The frontend only renders backend-provided assessment and proposal state.

## Endpoints

### `POST /api/assessments/runs`

- Purpose: trigger one cadence-specific assessment run for one agent profile.

Request body:

```json
{
  "cadence": "daily",
  "agent_profile_key": "daily_execution_v1",
  "season_id": 2026,
  "window_start_date": "2026-05-27",
  "window_end_date": "2026-05-27",
  "trigger_mode": "manual"
}
```

Response:

```json
{
  "assessment_run_id": 18,
  "assessment_window_id": 11,
  "agent_profile": {
    "profile_key": "daily_execution_v1",
    "display_name": "Daily Execution Agent",
    "cadence": "daily"
  },
  "run_status": "completed",
  "window": {
    "window_start_date": "2026-05-27",
    "window_end_date": "2026-05-27",
    "subject_scope_key": "day:2026-05-27"
  },
  "result_summary": {
    "summary_text": "The day diverged from the planned role because the athlete added unplanned volume after a poor-sleep marker.",
    "confidence_label": "medium",
    "proposal_count": 1
  }
}
```

Behavior notes:
- If no relevant source evidence changed, the response may return `run_status = "no_new_data"`.
- If the LLM fails, the response returns `run_status = "failed"` with persisted failure detail.
- `cadence` and `agent_profile_key` must be compatible.

### `GET /api/assessments/latest`

- Purpose: list the latest reviewable assessment per cadence/profile for a season or narrower planning scope.

Example query:

```text
/api/assessments/latest?season_id=2026&cadence=weekly
```

Response:

```json
{
  "items": [
    {
      "assessment_run_id": 24,
      "cadence": "weekly",
      "agent_profile_key": "weekly_adherence_adequacy_v1",
      "agent_profile_name": "Weekly Adherence And Adequacy Agent",
      "window_start_date": "2026-05-19",
      "window_end_date": "2026-05-25",
      "run_status": "completed",
      "confidence_label": "medium",
      "summary_text": "The week met frequency goals but concentrated fatigue too early.",
      "proposal_count": 1,
      "pending_proposal_count": 1
    }
  ]
}
```

### `GET /api/assessments/runs/{assessment_run_id}`

- Purpose: return assessment detail, including grouped findings and linked proposals.

Response:

```json
{
  "assessment_run_id": 24,
  "run_status": "completed",
  "agent_profile": {
    "profile_key": "weekly_adherence_adequacy_v1",
    "display_name": "Weekly Adherence And Adequacy Agent",
    "cadence": "weekly",
    "instruction_version": "v1"
  },
  "window": {
    "assessment_window_id": 14,
    "window_start_date": "2026-05-19",
    "window_end_date": "2026-05-25",
    "subject_scope_key": "week:2026-B2-W03"
  },
  "summary_text": "The week maintained adherence but the block progression now looks too aggressive.",
  "confidence_label": "medium",
  "principal_evidence": [
    "plan_planned_sessions for week 2026-B2-W03",
    "linked Garmin rides on 2026-05-20, 2026-05-22, 2026-05-24",
    "exec_daily_metrics for 2026-05-19 to 2026-05-25"
  ],
  "assessment_type_results": [
    {
      "assessment_type_key": "weekly_adherence",
      "result_label": "mostly_on_plan",
      "confidence_label": "high",
      "narrative_text": "The athlete completed the intended key sessions but added unplanned volume on Saturday."
    },
    {
      "assessment_type_key": "weekly_plan_adequacy",
      "result_label": "reduce_next_step",
      "confidence_label": "medium",
      "narrative_text": "The next weekly step should consolidate rather than progress because recovery lag accumulated across the final three days."
    }
  ],
  "findings": [
    {
      "finding_kind": "risk_signal",
      "severity": "warning",
      "title": "Recovery lag after the second hard ride",
      "detail_text": "Resting HR remained elevated for two mornings after the key session cluster."
    }
  ],
  "proposals": [
    {
      "proposal_id": 7,
      "proposal_status": "pending",
      "source_cadence": "weekly",
      "target_planning_level": "block",
      "proposal_title": "Hold block progression for one extra week"
    }
  ],
  "dialog_context": [
    {
      "dialog_context_id": 3,
      "entry_kind": "user_clarification",
      "entry_scope": "assessment_summary",
      "clarification_kind": "schedule_shift",
      "entry_text": "The planned Thursday ride was actually completed on Wednesday.",
      "created_at": "2026-05-28T10:00:00Z",
      "created_by": "athlete"
    }
  ]
}
```

### `POST /api/assessments/runs/{assessment_run_id}/dialog`

- Purpose: record a bounded follow-up question or user clarification tied to an assessment run.

Request body:

```json
{
  "entry_kind": "user_clarification",
  "entry_scope": "assessment_summary",
  "clarification_kind": "schedule_shift",
  "entry_text": "The planned Thursday ride was actually completed on Wednesday.",
  "created_by": "athlete",
  "request_reassessment": true
}
```

Response:

```json
{
  "dialog_context_id": 3,
  "assessment_run_id": 24,
  "entry_kind": "user_clarification",
  "entry_scope": "assessment_summary",
  "clarification_kind": "schedule_shift",
  "entry_text": "The planned Thursday ride was actually completed on Wednesday.",
  "created_at": "2026-05-28T10:00:00Z",
  "reassessment": {
    "requested": true,
    "status": "queued"
  }
}
```

Behavior notes:
- This endpoint persists dialog context; it does not mutate canonical plan or execution records directly.
- `request_reassessment = true` may trigger a bounded reassessment flow tied to the same cadence window.
- Free-form generic chat outside a persisted assessment or proposal context is out of scope.

### `GET /api/proposals`

- Purpose: list persisted proposals for review.

Example query:

```text
/api/proposals?season_id=2026&status=pending
```

Response:

```json
{
  "items": [
    {
      "proposal_id": 7,
      "proposal_status": "pending",
      "source_cadence": "weekly",
      "target_planning_level": "block",
      "agent_profile_key": "weekly_adherence_adequacy_v1",
      "proposal_title": "Hold block progression for one extra week",
      "proposal_summary": "Extend the current stabilization period before the next load increase.",
      "conflict_group_key": "block:B2:progression",
      "created_at": "2026-05-28T09:22:11Z"
    }
  ]
}
```

### `GET /api/proposals/{proposal_id}`

- Purpose: return full proposal detail and linked assessment provenance.

Response:

```json
{
  "proposal_id": 7,
  "proposal_status": "pending",
  "source_cadence": "weekly",
  "target_planning_level": "block",
  "proposal_title": "Hold block progression for one extra week",
  "proposal_summary": "Extend stabilization because recovery signal quality deteriorated late in the week.",
  "reasoning_summary": "The athlete kept frequency but showed rising recovery cost.",
  "proposed_change": {
    "change_kind": "extend_stabilization",
    "target_entity": "plan_meso_blocks.block_id=2",
    "changes": {
      "duration_weeks_min": 4,
      "duration_weeks_max": 5
    }
  },
  "source_assessment": {
    "assessment_run_id": 24,
    "agent_profile_key": "weekly_adherence_adequacy_v1",
    "window_start_date": "2026-05-19",
    "window_end_date": "2026-05-25"
  },
  "dialog_context": [
    {
      "dialog_context_id": 4,
      "entry_kind": "user_question",
      "entry_scope": "proposal",
      "entry_text": "Why does this proposal extend stabilization instead of reducing intensity?",
      "created_at": "2026-05-28T10:05:00Z",
      "created_by": "local-operator"
    }
  ],
  "current_decision": null
}
```

### `POST /api/proposals/{proposal_id}/decision`

- Purpose: record operator approval, rejection, or supersession.

Request body:

```json
{
  "decision_status": "accepted",
  "decision_note": "Reduce the next progression step and keep intensity stable.",
  "decided_by": "local-operator"
}
```

Response:

```json
{
  "proposal_id": 7,
  "proposal_status": "accepted",
  "decision": {
    "proposal_decision_id": 4,
    "decision_status": "accepted",
    "decided_by": "local-operator",
    "decided_at": "2026-05-28T09:31:00Z"
  },
  "plan_mutation": {
    "plan_mutation_id": 3,
    "target_planning_level": "block",
    "mutation_summary": "Block B2 progression held for one additional week."
  }
}
```

Behavior notes:
- `accepted` applies the canonical SQLite plan mutation through backend validation logic.
- `rejected` preserves the proposal history without mutating the plan.
- `superseded` requires either a replacement proposal or an explicit supersession note.

## Behavior Rules

- All completed assessment outputs must originate from an LLM run tied to an `agent_profile_key`.
- The backend may compute evidence summaries and validation guards, but the interpretive assessment text must come from the LLM-backed run.
- Multiple profiles may produce independent runs for the same cadence window.
- Assessment detail and proposal detail may include bounded dialog context and user clarifications tied to the persisted artifact.
- Proposal targets must obey cadence boundaries: daily to weekly, weekly to block, block to season, season to macro.
- The frontend must not infer approval state or coaching conclusions locally; it renders backend-provided status and details only.
- If the LLM is unavailable or misconfigured, the run must still persist with `failed` or `partial_context` status and operator-readable detail.
- If no new data exists for the requested window and profile, the backend must not fabricate a new substantive assessment.

## Error Semantics

- `400`: invalid cadence/profile pairing, malformed dates, unsupported decision status, or invalid proposal target.
- `404`: requested run, proposal, season, week, or block not found in canonical SQLite state.
- `409`: approval attempted for a proposal that is already finalized or conflicts with an unreconciled state transition.
- `422`: requested run cannot be assembled because required identifiers are inconsistent for the cadence.
- `5xx`: unexpected backend or LLM gateway failure; canonical failure status should still be persisted when possible.