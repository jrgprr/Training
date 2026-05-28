# Quickstart: AI Training Assessment Agents

## Goal

Validate that the local application can trigger specialist LLM assessment runs from canonical SQLite context, persist runs/findings/proposals/decisions/dialog context in SQLite, expose thin review and bounded dialog surfaces through the backend API and frontend, and enforce proposal approval before any canonical plan mutation.

## Prerequisites

- Python virtual environment available at `/home/jparra/Training/.venv`.
- Frontend dependencies installed in `GUI/frontend`.
- Local SQLite database initialized through backend startup.
- At least one season/week/day with imported Garmin activity and daily metrics data.
- LLM provider configuration available to the backend through local environment variables or config files chosen during implementation.

## 1. Start the local stack

```bash
source /home/jparra/Training/.venv/bin/activate
bash /home/jparra/Training/GUI/dev-with-garmin.sh
```

Expected outcome:
- FastAPI backend available at `http://127.0.0.1:8000`
- Vite frontend available at `http://127.0.0.1:5173`

## 2. Run focused backend validation

```bash
cd /home/jparra/Training/GUI/backend
python -m unittest \
  tests.test_garmin_connect_cli \
  tests.test_activity_quality \
  tests.test_ai_assessment_agents
```

Expected outcome:
- Existing import and activity-quality slices still pass.
- New assessment tests cover window resolution, evidence fingerprinting, explicit failed/partial/no-new-data statuses, proposal boundary validation, and approval-gated plan mutation.

## 3. Run frontend validation

```bash
cd /home/jparra/Training/GUI/frontend
npm run build
```

Expected outcome:
- The thin GUI compiles while rendering cadence summaries, assessment detail, bounded dialog context, proposal review state, and approval actions entirely from backend payloads.

## 4. Trigger a daily assessment run

```bash
curl -s -X POST http://127.0.0.1:8000/api/assessments/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "cadence": "daily",
    "agent_profile_key": "daily_execution_v1",
    "season_id": 2026,
    "window_start_date": "2026-05-27",
    "window_end_date": "2026-05-27",
    "trigger_mode": "manual"
  }' | jq
```

Expected outcome:
- The backend persists an assessment window and one run with `completed`, `partial_context`, `no_new_data`, or `failed` status.
- If the run completes, it also persists type results, findings, and any bounded proposal targeting the weekly plan.

## 5. Review the latest cadence results

```bash
curl -s 'http://127.0.0.1:8000/api/assessments/latest?season_id=2026&cadence=daily' | jq
curl -s http://127.0.0.1:8000/api/assessments/runs/RUN_ID | jq
curl -s 'http://127.0.0.1:8000/api/proposals?season_id=2026&status=pending' | jq
```

Expected outcome:
- Latest cadence payload identifies the producing agent profile, run status, analysis window, and summary.
- Run detail includes grouped findings, principal evidence references, and confidence limits.
- Proposal list shows target-planning-level changes without mutating the canonical plan.
- Proposal detail returns linked source assessment metadata, any persisted proposal dialog context, and decision history when present.

## 6. Accept or reject a proposal

```bash
curl -s -X POST http://127.0.0.1:8000/api/proposals/PROPOSAL_ID/decision \
  -H 'Content-Type: application/json' \
  -d '{
    "decision_status": "accepted",
    "decision_note": "Weekly volume should be reduced for the next 3 days.",
    "decided_by": "local-operator"
  }' | jq
```

Expected outcome:
- The proposal transitions from `pending` to `accepted` or `rejected`.
- An accepted decision creates a canonical plan-mutation trace record linked back to the proposal and source assessment run.
- The decision response includes both the persisted decision payload and, for accepted proposals, a `plan_mutation` summary plus an `applied_change_ref` on the decision.
- No canonical plan mutation occurs before this approval action.

## 7. Add a bounded clarification to an assessment

```bash
curl -s -X POST http://127.0.0.1:8000/api/assessments/runs/RUN_ID/dialog \
  -H 'Content-Type: application/json' \
  -d '{
    "entry_kind": "user_clarification",
    "entry_scope": "assessment_summary",
    "clarification_kind": "schedule_shift",
    "entry_text": "The planned Thursday ride was actually completed on Wednesday.",
    "created_by": "athlete",
    "request_reassessment": true
  }' | jq
```

Expected outcome:
- The backend persists the clarification as dialog context tied to the assessment run.
- The clarification does not silently overwrite canonical plan or execution records.
- If reassessment is requested, the system records a traceable reassessment flow rather than mutating the prior run in place.

## 8. Inspect canonical SQLite state

```bash
sqlite3 /home/jparra/Training/Sistema/training.sqlite <<'SQL'
SELECT profile_key, cadence, assessment_scope, target_planning_level, status
FROM agent_assessment_profiles
ORDER BY cadence, profile_key;

SELECT assessment_run_id,
       agent_profile_id,
       assessment_window_id,
       run_status,
       provider_key,
       model_name,
       started_at,
       completed_at
FROM agent_assessment_runs
ORDER BY assessment_run_id DESC;

SELECT assessment_run_id,
       finding_kind,
       severity,
       title
FROM agent_assessment_findings
ORDER BY assessment_run_id DESC, sort_order;

SELECT proposal_id,
       source_cadence,
       target_planning_level,
       proposal_status,
       proposal_title
FROM agent_adaptation_proposals
ORDER BY proposal_id DESC;

SELECT proposal_id,
       decision_status,
       decided_by,
       decided_at,
       applied_change_ref
FROM agent_proposal_decisions
ORDER BY proposal_decision_id DESC;

SELECT dialog_context_id,
       assessment_run_id,
       proposal_id,
       entry_kind,
       clarification_kind,
       created_by
FROM agent_assessment_dialog_context
ORDER BY dialog_context_id DESC;
SQL
```

Expected outcome:
- Profiles, runs, findings, proposals, and decisions are all persisted in SQLite.
- Failed or incomplete runs remain visible with explicit status rather than disappearing.
- Accepted proposals link to canonical plan mutation records.
- Dialog clarifications remain visible as reviewable context without silently changing canonical plan or execution rows.

## 9. Check duplicate-run behavior

1. Trigger the same daily or weekly assessment twice without importing new data or editing relevant reviews.
2. Trigger it again after changing a relevant review, daily metric, or linked activity inside the same cadence window.

Expected outcome:
- Unchanged evidence produces `no_new_data`, a reused latest assessment marker, or an equivalent deduplicated outcome rather than a second substantive assessment.
- Changed evidence produces a new assessment window fingerprint and a new traceable run.