from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .ai_assessment_models import (
    AgentProfileSummary,
    AssessmentRunDetailResponse,
    AssessmentRunStatus,
    AssessmentRunTriggerRequest,
    AssessmentRunTriggerResponse,
    AssessmentSummaryPayload,
    AssessmentWindowSummary,
    RunTriggerMode,
)
from .ai_context import AssessmentContextSnapshot, build_assessment_context_with_connection
from .ai_profiles import get_profile_definition, list_profile_definitions
from .db import get_connection


@dataclass(frozen=True)
class PreparedAssessmentRun:
    assessment_run_id: int
    assessment_window_id: int
    run_status: AssessmentRunStatus
    context_snapshot: AssessmentContextSnapshot
    profile_key: str
    profile_display_name: str
    profile_instruction_version: str
    reused_run_id: int | None = None


def _fetch_one(connection, query: str, parameters: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = connection.execute(query, parameters).fetchone()
    return dict(row) if row else None


def sync_assessment_profiles(connection) -> None:
    for profile in list_profile_definitions():
        connection.execute(
            """
            INSERT INTO agent_assessment_profiles (
                profile_key,
                display_name,
                cadence,
                assessment_scope,
                target_planning_level,
                instruction_version,
                execution_policy,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_key) DO UPDATE SET
                display_name = excluded.display_name,
                cadence = excluded.cadence,
                assessment_scope = excluded.assessment_scope,
                target_planning_level = excluded.target_planning_level,
                instruction_version = excluded.instruction_version,
                execution_policy = excluded.execution_policy,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                profile.profile_key,
                profile.display_name,
                profile.cadence.value,
                profile.assessment_scope,
                profile.proposal_target_level.value if profile.proposal_target_level else None,
                profile.instruction_version,
                None,
                profile.status,
            ),
        )


def _get_profile_row(connection, profile_key: str) -> dict[str, Any]:
    profile_row = _fetch_one(
        connection,
        """
        SELECT agent_profile_id,
               profile_key,
               display_name,
               cadence,
               assessment_scope,
               target_planning_level,
               instruction_version,
               provider_key,
               model_name,
               status
        FROM agent_assessment_profiles
        WHERE profile_key = ?
        """,
        (profile_key,),
    )
    if profile_row is None:
        raise LookupError(f"Unknown assessment profile: {profile_key}")
    return profile_row


def _materialize_assessment_window(connection, snapshot: AssessmentContextSnapshot) -> int:
    existing = _fetch_one(
        connection,
        """
        SELECT assessment_window_id
        FROM agent_assessment_windows
        WHERE cadence = ?
          AND subject_scope_key = ?
          AND evidence_fingerprint = ?
        """,
        (
            snapshot.window.cadence.value,
            snapshot.window.subject_scope_key,
            snapshot.evidence_fingerprint,
        ),
    )
    if existing is not None:
        return existing["assessment_window_id"]

    cursor = connection.execute(
        """
        INSERT INTO agent_assessment_windows (
            cadence,
            season_id,
            block_id,
            week_id,
            window_start_date,
            window_end_date,
            subject_scope_key,
            evidence_fingerprint,
            latest_materialized_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            snapshot.window.cadence.value,
            snapshot.window.season_id,
            snapshot.window.block_id,
            snapshot.window.week_id,
            snapshot.window.window_start_date,
            snapshot.window.window_end_date,
            snapshot.window.subject_scope_key,
            snapshot.evidence_fingerprint,
        ),
    )
    return int(cursor.lastrowid)


def _get_latest_run_for_window(connection, agent_profile_id: int, assessment_window_id: int) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT assessment_run_id, run_status
        FROM agent_assessment_runs
        WHERE agent_profile_id = ? AND assessment_window_id = ?
        ORDER BY created_at DESC, assessment_run_id DESC
        LIMIT 1
        """,
        (agent_profile_id, assessment_window_id),
    )


def prepare_assessment_run(request: AssessmentRunTriggerRequest) -> PreparedAssessmentRun:
    profile_definition = get_profile_definition(request.agent_profile_key)
    if profile_definition.cadence is not request.cadence:
        raise ValueError(
            f"Profile {request.agent_profile_key} is registered for {profile_definition.cadence.value}, not {request.cadence.value}."
        )

    with get_connection() as connection:
        sync_assessment_profiles(connection)
        profile_row = _get_profile_row(connection, request.agent_profile_key)
        snapshot = build_assessment_context_with_connection(
            connection,
            request.cadence,
            request.season_id,
            request.window_start_date,
            request.window_end_date,
            block_id=request.block_id,
            week_id=request.week_id,
        )
        assessment_window_id = _materialize_assessment_window(connection, snapshot)
        latest_run = _get_latest_run_for_window(connection, profile_row["agent_profile_id"], assessment_window_id)

        if latest_run is not None and request.trigger_mode is not RunTriggerMode.RERUN:
            return PreparedAssessmentRun(
                assessment_run_id=latest_run["assessment_run_id"],
                assessment_window_id=assessment_window_id,
                run_status=AssessmentRunStatus.NO_NEW_DATA,
                context_snapshot=snapshot,
                profile_key=profile_definition.profile_key,
                profile_display_name=profile_definition.display_name,
                profile_instruction_version=profile_definition.instruction_version,
                reused_run_id=latest_run["assessment_run_id"],
            )

        cursor = connection.execute(
            """
            INSERT INTO agent_assessment_runs (
                agent_profile_id,
                assessment_window_id,
                trigger_mode,
                run_status,
                provider_key,
                model_name,
                instruction_version,
                supersedes_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_row["agent_profile_id"],
                assessment_window_id,
                request.trigger_mode.value,
                AssessmentRunStatus.QUEUED.value,
                profile_row["provider_key"],
                profile_row["model_name"],
                profile_row["instruction_version"],
                latest_run["assessment_run_id"] if latest_run is not None and request.trigger_mode is RunTriggerMode.RERUN else None,
            ),
        )

        return PreparedAssessmentRun(
            assessment_run_id=int(cursor.lastrowid),
            assessment_window_id=assessment_window_id,
            run_status=AssessmentRunStatus.QUEUED,
            context_snapshot=snapshot,
            profile_key=profile_definition.profile_key,
            profile_display_name=profile_definition.display_name,
            profile_instruction_version=profile_definition.instruction_version,
            reused_run_id=latest_run["assessment_run_id"] if latest_run is not None else None,
        )


def build_assessment_run_trigger_response(prepared_run: PreparedAssessmentRun) -> AssessmentRunTriggerResponse:
    profile_definition = get_profile_definition(prepared_run.profile_key)

    return AssessmentRunTriggerResponse(
        assessment_run_id=prepared_run.assessment_run_id,
        assessment_window_id=prepared_run.assessment_window_id,
        agent_profile=AgentProfileSummary(
            profile_key=prepared_run.profile_key,
            display_name=prepared_run.profile_display_name,
            cadence=profile_definition.cadence,
            instruction_version=prepared_run.profile_instruction_version,
        ),
        run_status=prepared_run.run_status,
        window=AssessmentWindowSummary(
            assessment_window_id=prepared_run.assessment_window_id,
            window_start_date=prepared_run.context_snapshot.window.window_start_date,
            window_end_date=prepared_run.context_snapshot.window.window_end_date,
            subject_scope_key=prepared_run.context_snapshot.window.subject_scope_key,
        ),
        result_summary=AssessmentSummaryPayload(
            summary_text=None,
            confidence_label=None,
            proposal_count=0,
        ),
    )


def _principal_evidence_from_context(context: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    if context.get("planned_sessions"):
        evidence.append(f"plan_planned_sessions count={len(context['planned_sessions'])}")
    if context.get("activities"):
        activity_dates = [row["activity_date"] for row in context["activities"]]
        evidence.append(f"exec_activities dates={','.join(activity_dates)}")
    if context.get("daily_metrics"):
        metric_dates = [row["metric_date"] for row in context["daily_metrics"]]
        evidence.append(f"exec_daily_metrics dates={','.join(metric_dates)}")
    if context.get("weekly_review"):
        evidence.append("review_weekly_reviews available")
    return evidence


def get_assessment_run_detail(assessment_run_id: int) -> AssessmentRunDetailResponse | None:
    with get_connection() as connection:
        row = _fetch_one(
            connection,
            """
            SELECT r.assessment_run_id,
                   r.run_status,
                   r.summary_text,
                   r.confidence_label,
                   r.principal_evidence_json,
                   p.profile_key,
                   p.display_name,
                   p.cadence,
                   p.instruction_version,
                   w.assessment_window_id,
                   w.window_start_date,
                   w.window_end_date,
                   w.subject_scope_key,
                   w.season_id,
                   w.block_id,
                   w.week_id
            FROM agent_assessment_runs r
            JOIN agent_assessment_profiles p ON p.agent_profile_id = r.agent_profile_id
            JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
            WHERE r.assessment_run_id = ?
            """,
            (assessment_run_id,),
        )
        if row is None:
            return None

        snapshot = build_assessment_context_with_connection(
            connection,
            get_profile_definition(row["profile_key"]).cadence,
            row["season_id"],
            row["window_start_date"],
            row["window_end_date"],
            block_id=row["block_id"],
            week_id=row["week_id"],
        )

        principal_evidence = []
        if row.get("principal_evidence_json"):
            try:
                parsed = json.loads(row["principal_evidence_json"])
                if isinstance(parsed, list):
                    principal_evidence = [str(item) for item in parsed]
            except json.JSONDecodeError:
                principal_evidence = [row["principal_evidence_json"]]
        if not principal_evidence:
            principal_evidence = _principal_evidence_from_context(snapshot.context)

        return AssessmentRunDetailResponse(
            assessment_run_id=row["assessment_run_id"],
            run_status=AssessmentRunStatus(row["run_status"]),
            agent_profile=AgentProfileSummary(
                profile_key=row["profile_key"],
                display_name=row["display_name"],
                cadence=get_profile_definition(row["profile_key"]).cadence,
                instruction_version=row["instruction_version"],
            ),
            window=AssessmentWindowSummary(
                assessment_window_id=row["assessment_window_id"],
                window_start_date=row["window_start_date"],
                window_end_date=row["window_end_date"],
                subject_scope_key=row["subject_scope_key"],
            ),
            summary_text=row["summary_text"],
            confidence_label=None,
            principal_evidence=principal_evidence,
            assessment_type_results=[],
            findings=[],
            proposals=[],
            dialog_context=[],
        )