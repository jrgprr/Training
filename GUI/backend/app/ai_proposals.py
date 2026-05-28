from __future__ import annotations

import json
from typing import Any

from .ai_assessment_models import (
    AssessmentCadence,
    GeneratedAssessmentOutput,
    GeneratedProposalPayload,
    ProposalReferencePayload,
    ProposalStatus,
    TargetPlanningLevel,
)
from .ai_profiles import get_profile_definition


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