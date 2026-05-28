from __future__ import annotations

import json
from typing import Any

from .ai_assessment_models import (
    AcceptedPlanMutationPayload,
    AssessmentCadence,
    DialogContextEntryPayload,
    GeneratedAssessmentOutput,
    GeneratedProposalPayload,
    ProposalDecisionRequest,
    ProposalDecisionPayload,
    ProposalDecisionResponse,
    ProposalDetailResponse,
    ProposalListItem,
    ProposalListResponse,
    ProposalReferencePayload,
    ProposalDecisionStatus,
    ProposalStatus,
    TargetPlanningLevel,
)
from .ai_profiles import get_profile_definition


class ProposalConflictError(RuntimeError):
    pass


def parse_generated_assessment_output(output_text: str | None) -> GeneratedAssessmentOutput:
    if not output_text:
        return GeneratedAssessmentOutput(summary_text="")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        return GeneratedAssessmentOutput(summary_text=output_text)

    if isinstance(parsed, dict) and ("summary_text" in parsed or "proposals" in parsed):
        return GeneratedAssessmentOutput.model_validate(parsed)

    return GeneratedAssessmentOutput(summary_text=output_text)


def persist_generated_proposals(
    connection,
    *,
    assessment_run_id: int,
    profile_key: str,
    proposals: list[GeneratedProposalPayload],
) -> list[int]:
    profile_definition = get_profile_definition(profile_key)
    profile_row = connection.execute(
        "SELECT agent_profile_id FROM agent_assessment_profiles WHERE profile_key = ?",
        (profile_key,),
    ).fetchone()
    if profile_row is None:
        raise LookupError(f"Unknown assessment profile: {profile_key}")

    inserted_ids: list[int] = []
    expected_source_cadence = profile_definition.cadence
    expected_target_level = profile_definition.proposal_target_level

    for proposal in proposals:
        source_cadence = proposal.source_cadence or expected_source_cadence
        target_level = proposal.target_planning_level or expected_target_level

        if source_cadence is not expected_source_cadence:
            raise ValueError(
                f"Proposal source cadence {source_cadence.value} does not match profile cadence {expected_source_cadence.value}."
            )
        if target_level is None:
            raise ValueError(f"Profile {profile_key} does not define a proposal target level.")
        if expected_target_level is not None and target_level is not expected_target_level:
            raise ValueError(
                f"Proposal target {target_level.value} does not match profile target {expected_target_level.value}."
            )

        cursor = connection.execute(
            """
            INSERT INTO agent_adaptation_proposals (
                assessment_run_id,
                agent_profile_id,
                source_cadence,
                target_planning_level,
                proposal_status,
                proposal_title,
                proposal_summary,
                change_kind,
                proposed_change_json,
                reasoning_summary,
                conflict_group_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_run_id,
                profile_row["agent_profile_id"],
                source_cadence.value,
                target_level.value,
                ProposalStatus.PENDING.value,
                proposal.proposal_title,
                proposal.proposal_summary,
                proposal.change_kind,
                json.dumps(proposal.proposed_change, ensure_ascii=True),
                proposal.reasoning_summary,
                proposal.conflict_group_key,
            ),
        )
        inserted_ids.append(int(cursor.lastrowid))

    return inserted_ids


def count_proposals_for_run(connection, assessment_run_id: int) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS proposal_count FROM agent_adaptation_proposals WHERE assessment_run_id = ?",
        (assessment_run_id,),
    ).fetchone()
    return int(row["proposal_count"]) if row else 0


def list_proposal_references(connection, assessment_run_id: int) -> list[ProposalReferencePayload]:
    rows = connection.execute(
        """
        SELECT proposal_id, proposal_status, source_cadence, target_planning_level, proposal_title
        FROM agent_adaptation_proposals
        WHERE assessment_run_id = ?
        ORDER BY proposal_id
        """,
        (assessment_run_id,),
    ).fetchall()

    return [
        ProposalReferencePayload(
            proposal_id=row["proposal_id"],
            proposal_status=ProposalStatus(row["proposal_status"]),
            source_cadence=AssessmentCadence(row["source_cadence"]),
            target_planning_level=TargetPlanningLevel(row["target_planning_level"]),
            proposal_title=row["proposal_title"],
        )
        for row in rows
    ]


def list_proposals_for_review(season_id: int, status: ProposalStatus | None = None) -> ProposalListResponse:
    filters = ["w.season_id = ?"]
    parameters: list[Any] = [season_id]
    if status is not None:
        filters.append("ap.proposal_status = ?")
        parameters.append(status.value)

    query = f"""
        SELECT ap.proposal_id,
               ap.proposal_status,
               ap.source_cadence,
               ap.target_planning_level,
               p.profile_key,
               ap.proposal_title,
               ap.proposal_summary,
               ap.conflict_group_key,
               ap.created_at
        FROM agent_adaptation_proposals ap
        JOIN agent_assessment_profiles p ON p.agent_profile_id = ap.agent_profile_id
        JOIN agent_assessment_runs r ON r.assessment_run_id = ap.assessment_run_id
        JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
        WHERE {' AND '.join(filters)}
        ORDER BY ap.created_at DESC, ap.proposal_id DESC
    """

    from .db import get_connection

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return ProposalListResponse(
        items=[
            ProposalListItem(
                proposal_id=row["proposal_id"],
                proposal_status=ProposalStatus(row["proposal_status"]),
                source_cadence=AssessmentCadence(row["source_cadence"]),
                target_planning_level=TargetPlanningLevel(row["target_planning_level"]),
                agent_profile_key=row["profile_key"],
                proposal_title=row["proposal_title"],
                proposal_summary=row["proposal_summary"],
                conflict_group_key=row["conflict_group_key"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    )


def get_proposal_detail(proposal_id: int) -> ProposalDetailResponse | None:
    from .db import get_connection

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT ap.proposal_id,
                   ap.proposal_status,
                   ap.source_cadence,
                   ap.target_planning_level,
                   ap.proposal_title,
                   ap.proposal_summary,
                   ap.change_kind,
                   ap.proposed_change_json,
                   ap.reasoning_summary,
                   r.assessment_run_id,
                   p.profile_key,
                   w.window_start_date,
                   w.window_end_date
            FROM agent_adaptation_proposals ap
            JOIN agent_assessment_runs r ON r.assessment_run_id = ap.assessment_run_id
            JOIN agent_assessment_profiles p ON p.agent_profile_id = ap.agent_profile_id
            JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
            WHERE ap.proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()
        if row is None:
            return None

        dialog_rows = connection.execute(
            """
            SELECT dialog_context_id,
                   assessment_run_id,
                   proposal_id,
                   entry_kind,
                   entry_scope,
                   clarification_kind,
                   entry_text,
                   linked_evidence_json,
                   created_at,
                   created_by
            FROM agent_assessment_dialog_context
            WHERE proposal_id = ?
            ORDER BY created_at, dialog_context_id
            """,
            (proposal_id,),
        ).fetchall()
        decision_rows = connection.execute(
            """
            SELECT proposal_decision_id,
                   decision_status,
                   decision_note,
                   decided_by,
                   decided_at,
                   superseding_proposal_id,
                   applied_change_ref
            FROM agent_proposal_decisions
            WHERE proposal_id = ?
            ORDER BY decided_at DESC, proposal_decision_id DESC
            """,
            (proposal_id,),
        ).fetchall()

    proposed_change = json.loads(row["proposed_change_json"]) if row["proposed_change_json"] else {}
    if isinstance(proposed_change, dict) and "change_kind" not in proposed_change:
        proposed_change = {"change_kind": row["change_kind"], **proposed_change}

    return ProposalDetailResponse(
        proposal_id=row["proposal_id"],
        proposal_status=ProposalStatus(row["proposal_status"]),
        source_cadence=AssessmentCadence(row["source_cadence"]),
        target_planning_level=TargetPlanningLevel(row["target_planning_level"]),
        proposal_title=row["proposal_title"],
        proposal_summary=row["proposal_summary"],
        reasoning_summary=row["reasoning_summary"],
        proposed_change=proposed_change if isinstance(proposed_change, dict) else {},
        source_assessment={
            "assessment_run_id": row["assessment_run_id"],
            "agent_profile_key": row["profile_key"],
            "window_start_date": row["window_start_date"],
            "window_end_date": row["window_end_date"],
        },
        dialog_context=[
            DialogContextEntryPayload(
                dialog_context_id=dialog_row["dialog_context_id"],
                assessment_run_id=dialog_row["assessment_run_id"],
                proposal_id=dialog_row["proposal_id"],
                entry_kind=dialog_row["entry_kind"],
                entry_scope=dialog_row["entry_scope"],
                clarification_kind=dialog_row["clarification_kind"],
                entry_text=dialog_row["entry_text"],
                linked_evidence_json=dialog_row["linked_evidence_json"],
                created_at=dialog_row["created_at"],
                created_by=dialog_row["created_by"],
            )
            for dialog_row in dialog_rows
        ],
        decision_history=[
            ProposalDecisionPayload(
                proposal_decision_id=decision_row["proposal_decision_id"],
                decision_status=ProposalDecisionStatus(decision_row["decision_status"]),
                decision_note=decision_row["decision_note"],
                decided_by=decision_row["decided_by"],
                decided_at=decision_row["decided_at"],
                superseding_proposal_id=decision_row["superseding_proposal_id"],
                applied_change_ref=decision_row["applied_change_ref"],
            )
            for decision_row in decision_rows
        ],
    )


def decide_proposal(proposal_id: int, request: ProposalDecisionRequest) -> ProposalDecisionResponse:
    from .db import get_connection

    with get_connection() as connection:
        proposal_row = connection.execute(
            """
            SELECT proposal_id,
                   proposal_status,
                   target_planning_level,
                   proposal_title,
                   proposal_summary,
                   proposed_change_json,
                   reasoning_summary
            FROM agent_adaptation_proposals
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()
        if proposal_row is None:
            raise LookupError(f"No existe la propuesta {proposal_id}.")
        if proposal_row["proposal_status"] != ProposalStatus.PENDING.value:
            raise ProposalConflictError(f"La propuesta {proposal_id} ya fue finalizada con estado {proposal_row['proposal_status']}.")

        if request.decision_status is ProposalDecisionStatus.SUPERSEDED and not (
            request.superseding_proposal_id is not None or request.decision_note
        ):
            raise ValueError("Superseded proposals require a replacement proposal or an explicit decision note.")

        if request.superseding_proposal_id is not None:
            superseding_row = connection.execute(
                "SELECT proposal_id FROM agent_adaptation_proposals WHERE proposal_id = ?",
                (request.superseding_proposal_id,),
            ).fetchone()
            if superseding_row is None:
                raise LookupError(f"No existe la propuesta {request.superseding_proposal_id}.")

        applied_change_ref: str | None = None
        mutation_payload: AcceptedPlanMutationPayload | None = None

        if request.decision_status is ProposalDecisionStatus.ACCEPTED:
            proposed_change = json.loads(proposal_row["proposed_change_json"]) if proposal_row["proposed_change_json"] else {}
            target_entity_id = "proposal:" + str(proposal_id)
            if isinstance(proposed_change, dict):
                target_entity_id = str(
                    proposed_change.get("target_entity")
                    or proposed_change.get("target_entity_id")
                    or target_entity_id
                )
            mutation_summary = request.decision_note or proposal_row["proposal_summary"] or proposal_row["proposal_title"]
            mutation_cursor = connection.execute(
                """
                INSERT INTO agent_accepted_plan_mutations (
                    proposal_id,
                    target_planning_level,
                    target_entity_id,
                    mutation_summary,
                    before_snapshot_json,
                    after_snapshot_json,
                    applied_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    proposal_row["target_planning_level"],
                    target_entity_id,
                    mutation_summary,
                    None,
                    proposal_row["proposed_change_json"],
                    request.decided_by,
                ),
            )
            plan_mutation_id = int(mutation_cursor.lastrowid)
            applied_change_ref = f"plan_mutation:{plan_mutation_id}"
            mutation_payload = AcceptedPlanMutationPayload(
                plan_mutation_id=plan_mutation_id,
                target_planning_level=TargetPlanningLevel(proposal_row["target_planning_level"]),
                mutation_summary=mutation_summary,
            )

        decision_cursor = connection.execute(
            """
            INSERT INTO agent_proposal_decisions (
                proposal_id,
                decision_status,
                decision_note,
                decided_by,
                superseding_proposal_id,
                applied_change_ref
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                request.decision_status.value,
                request.decision_note,
                request.decided_by,
                request.superseding_proposal_id,
                applied_change_ref,
            ),
        )
        decision_row = connection.execute(
            """
            SELECT proposal_decision_id,
                   decision_status,
                   decision_note,
                   decided_by,
                   decided_at,
                   superseding_proposal_id,
                   applied_change_ref
            FROM agent_proposal_decisions
            WHERE proposal_decision_id = ?
            """,
            (decision_cursor.lastrowid,),
        ).fetchone()

        connection.execute(
            """
            UPDATE agent_adaptation_proposals
            SET proposal_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE proposal_id = ?
            """,
            (request.decision_status.value, proposal_id),
        )

    return ProposalDecisionResponse(
        proposal_id=proposal_id,
        proposal_status=ProposalStatus(request.decision_status.value),
        decision=ProposalDecisionPayload(
            proposal_decision_id=decision_row["proposal_decision_id"],
            decision_status=ProposalDecisionStatus(decision_row["decision_status"]),
            decision_note=decision_row["decision_note"],
            decided_by=decision_row["decided_by"],
            decided_at=decision_row["decided_at"],
            superseding_proposal_id=decision_row["superseding_proposal_id"],
            applied_change_ref=decision_row["applied_change_ref"],
        ),
        plan_mutation=mutation_payload,
    )