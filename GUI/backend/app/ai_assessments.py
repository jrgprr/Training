from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .ai_assessment_models import (
    AgentProfileSummary,
    AssessmentDialogRequest,
    AssessmentDialogResponse,
    AssessmentCadence,
    AssessmentRunDetailResponse,
    AssessmentRunLatestItem,
    AssessmentRunStatus,
    AssessmentRunTriggerRequest,
    AssessmentRunTriggerResponse,
    AssessmentSummaryPayload,
    ClarificationKind,
    ConfidenceLabel,
    DialogContextEntryPayload,
    DialogEntryKind,
    DialogEntryScope,
    AssessmentTypeResultPayload,
    AssessmentFindingPayload,
    FindingKind,
    FindingSeverity,
    GeneratedAssessmentOutput,
    LatestAssessmentsResponse,
    AssessmentWindowSummary,
    ReassessmentStatusPayload,
    RunTriggerMode,
)
from .ai_context import AssessmentContextSnapshot, build_assessment_context_with_connection
from .ai_gateway import AssessmentLLMGateway, GatewayProvider, GatewayResult, GatewayInvocation
from .ai_profiles import get_profile_definition, list_profile_definitions
from .ai_proposals import count_proposals_for_run, list_proposal_references, parse_generated_assessment_output, persist_generated_proposals
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


_gateway = AssessmentLLMGateway()


def register_gateway_provider(provider_key: str, provider: GatewayProvider) -> None:
    _gateway.register_provider(provider_key, provider)


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
    with get_connection() as connection:
        run_row = _fetch_one(
            connection,
            """
            SELECT summary_text, confidence_label
            FROM agent_assessment_runs
            WHERE assessment_run_id = ?
            """,
            (prepared_run.assessment_run_id,),
        )
        proposal_count = count_proposals_for_run(connection, prepared_run.assessment_run_id)

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
            summary_text=run_row["summary_text"] if run_row else None,
            confidence_label=ConfidenceLabel(run_row["confidence_label"]) if run_row and run_row["confidence_label"] else None,
            proposal_count=proposal_count,
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
    if context.get("daily_reviews"):
        review_dates = [row["review_date"] for row in context["daily_reviews"]]
        evidence.append(f"review_daily_reviews dates={','.join(review_dates)}")
    if context.get("weekly_review"):
        evidence.append("review_weekly_reviews available")
    return evidence


def _build_prompt(prepared_run: PreparedAssessmentRun) -> str:
    context = prepared_run.context_snapshot.context
    activity_count = len(context.get("activities", []))
    planned_count = len(context.get("planned_sessions", []))
    metric_count = len(context.get("daily_metrics", []))
    return (
        f"Profile: {prepared_run.profile_key}\n"
        f"Window: {prepared_run.context_snapshot.window.subject_scope_key}\n"
        f"Activities: {activity_count}\n"
        f"Planned sessions: {planned_count}\n"
        f"Daily metrics: {metric_count}\n"
        f"Evidence: {_principal_evidence_from_context(context)}"
    )


def _has_recovery_readiness_evidence(context: dict[str, Any]) -> bool:
    return bool(context.get("daily_metrics") or context.get("daily_reviews") or context.get("activities"))


def _has_weekly_evidence(context: dict[str, Any]) -> bool:
    return bool(context.get("planned_sessions") or context.get("activities") or context.get("daily_reviews") or context.get("weekly_review"))


def _has_block_evidence(context: dict[str, Any]) -> bool:
    return bool(context.get("activities") or context.get("segment_summary") or context.get("daily_reviews") or context.get("planned_sessions"))


def _derive_confidence(prepared_run: PreparedAssessmentRun) -> ConfidenceLabel:
    context = prepared_run.context_snapshot.context
    if prepared_run.profile_key == "daily_recovery_readiness_v1":
        if context.get("daily_metrics") or context.get("daily_reviews"):
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LIMITED
    if prepared_run.profile_key == "weekly_adherence_adequacy_v1":
        if context.get("planned_sessions") and (context.get("activities") or context.get("weekly_review")):
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LIMITED
    if prepared_run.profile_key == "block_performance_direction_v1":
        if context.get("activities") and context.get("segment_summary"):
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LIMITED
    if context.get("activities") and context.get("daily_metrics"):
        return ConfidenceLabel.MEDIUM
    return ConfidenceLabel.LIMITED


def _derive_run_status(prepared_run: PreparedAssessmentRun) -> AssessmentRunStatus:
    context = prepared_run.context_snapshot.context
    if prepared_run.profile_key == "daily_execution_v1" and not context.get("activities"):
        return AssessmentRunStatus.PARTIAL_CONTEXT
    if prepared_run.profile_key == "daily_recovery_readiness_v1" and not _has_recovery_readiness_evidence(context):
        return AssessmentRunStatus.PARTIAL_CONTEXT
    if prepared_run.profile_key == "weekly_adherence_adequacy_v1" and not _has_weekly_evidence(context):
        return AssessmentRunStatus.PARTIAL_CONTEXT
    if prepared_run.profile_key == "block_performance_direction_v1" and not _has_block_evidence(context):
        return AssessmentRunStatus.PARTIAL_CONTEXT
    return AssessmentRunStatus.COMPLETED


def _derive_assessment_type_key(profile_key: str) -> str:
    if profile_key == "daily_execution_v1":
        return "daily_execution"
    if profile_key == "daily_recovery_readiness_v1":
        return "daily_recovery_readiness"
    return profile_key.removesuffix("_v1")


def _derive_result_label(prepared_run: PreparedAssessmentRun) -> str:
    context = prepared_run.context_snapshot.context
    has_activities = bool(context.get("activities"))
    if prepared_run.profile_key == "daily_execution_v1":
        return "executed" if has_activities else "no_activity_recorded"
    if prepared_run.profile_key == "daily_recovery_readiness_v1":
        return "ready_check" if _has_recovery_readiness_evidence(context) else "limited_readiness"
    if prepared_run.profile_key == "weekly_adherence_adequacy_v1":
        return "weekly_on_plan" if _has_weekly_evidence(context) else "limited_week_review"
    if prepared_run.profile_key == "block_performance_direction_v1":
        return "direction_established" if _has_block_evidence(context) else "limited_block_review"
    return "ready_check" if has_activities else "limited_readiness"


def _derive_finding(prepared_run: PreparedAssessmentRun, output_text: str, confidence: ConfidenceLabel) -> tuple[FindingKind, FindingSeverity, str]:
    context = prepared_run.context_snapshot.context
    if prepared_run.profile_key == "daily_recovery_readiness_v1":
        if _has_recovery_readiness_evidence(context):
            return FindingKind.RECOVERY_OBSERVATION, FindingSeverity.INFO, output_text
        return FindingKind.DATA_CONFIDENCE, FindingSeverity.WATCH, output_text
    if prepared_run.profile_key == "weekly_adherence_adequacy_v1":
        if _has_weekly_evidence(context):
            return FindingKind.ADHERENCE_OBSERVATION, FindingSeverity.INFO, output_text
        return FindingKind.DATA_CONFIDENCE, FindingSeverity.WATCH, output_text
    if prepared_run.profile_key == "block_performance_direction_v1":
        if _has_block_evidence(context):
            return FindingKind.PERFORMANCE_SIGNAL, FindingSeverity.INFO, output_text
        return FindingKind.DATA_CONFIDENCE, FindingSeverity.WATCH, output_text
    if context.get("activities"):
        return FindingKind.NEXT_ACTION, FindingSeverity.INFO, output_text
    return FindingKind.DATA_CONFIDENCE, FindingSeverity.WATCH, output_text


def _persist_gateway_failure(connection, assessment_run_id: int, gateway_result: GatewayResult) -> None:
    connection.execute(
        """
        UPDATE agent_assessment_runs
        SET run_status = ?,
            provider_key = ?,
            model_name = ?,
            prompt_hash = ?,
            failure_code = ?,
            failure_detail = ?,
            started_at = ?,
            completed_at = ?
        WHERE assessment_run_id = ?
        """,
        (
            gateway_result.run_status.value,
            gateway_result.provider_key,
            gateway_result.model_name,
            gateway_result.prompt_hash,
            gateway_result.failure_code,
            gateway_result.failure_detail,
            gateway_result.started_at,
            gateway_result.completed_at,
            assessment_run_id,
        ),
    )


def _persist_completed_run(connection, prepared_run: PreparedAssessmentRun, gateway_result: GatewayResult) -> None:
    principal_evidence = _principal_evidence_from_context(prepared_run.context_snapshot.context)
    confidence = _derive_confidence(prepared_run)
    run_status = _derive_run_status(prepared_run)
    result_label = _derive_result_label(prepared_run)
    generated_output = parse_generated_assessment_output(gateway_result.output_text)
    finding_kind, finding_severity, finding_text = _derive_finding(
        prepared_run,
        generated_output.summary_text,
        confidence,
    )

    connection.execute(
        """
        UPDATE agent_assessment_runs
        SET run_status = ?,
            provider_key = ?,
            model_name = ?,
            prompt_hash = ?,
            summary_text = ?,
            confidence_label = ?,
            principal_evidence_json = ?,
            failure_code = NULL,
            failure_detail = NULL,
            started_at = ?,
            completed_at = ?
        WHERE assessment_run_id = ?
        """,
        (
            run_status.value,
            gateway_result.provider_key,
            gateway_result.model_name,
            gateway_result.prompt_hash,
            generated_output.summary_text,
            confidence.value,
            json.dumps(principal_evidence, ensure_ascii=True),
            gateway_result.started_at,
            gateway_result.completed_at,
            prepared_run.assessment_run_id,
        ),
    )

    cursor = connection.execute(
        """
        INSERT INTO agent_assessment_type_results (
            assessment_run_id,
            assessment_type_key,
            result_label,
            confidence_label,
            narrative_text,
            evidence_summary_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(assessment_run_id, assessment_type_key) DO UPDATE SET
            result_label = excluded.result_label,
            confidence_label = excluded.confidence_label,
            narrative_text = excluded.narrative_text,
            evidence_summary_json = excluded.evidence_summary_json
        RETURNING assessment_type_result_id
        """,
        (
            prepared_run.assessment_run_id,
            _derive_assessment_type_key(prepared_run.profile_key),
            result_label,
            confidence.value,
            generated_output.summary_text,
            json.dumps(principal_evidence, ensure_ascii=True),
        ),
    )
    type_result_id = cursor.fetchone()[0]

    connection.execute(
        """
        INSERT INTO agent_assessment_findings (
            assessment_run_id,
            assessment_type_result_id,
            finding_kind,
            severity,
            title,
            detail_text,
            evidence_refs_json,
            sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            prepared_run.assessment_run_id,
            type_result_id,
            finding_kind.value,
            finding_severity.value,
            prepared_run.profile_display_name,
            finding_text,
            json.dumps(principal_evidence, ensure_ascii=True),
        ),
    )

    persist_generated_proposals(
        connection,
        assessment_run_id=prepared_run.assessment_run_id,
        profile_key=prepared_run.profile_key,
        proposals=generated_output.proposals,
    )


def execute_assessment_run(request: AssessmentRunTriggerRequest) -> PreparedAssessmentRun:
    prepared_run = prepare_assessment_run(request)
    if prepared_run.run_status is AssessmentRunStatus.NO_NEW_DATA:
        return prepared_run

    prompt_text = _build_prompt(prepared_run)
    gateway_result = _gateway.invoke(
        GatewayInvocation(
            profile_key=prepared_run.profile_key,
            instruction_version=prepared_run.profile_instruction_version,
            prompt_text=prompt_text,
            context_metadata={"subject_scope_key": prepared_run.context_snapshot.window.subject_scope_key},
        )
    )

    with get_connection() as connection:
        if gateway_result.run_status is AssessmentRunStatus.COMPLETED:
            try:
                _persist_completed_run(connection, prepared_run, gateway_result)
            except (LookupError, ValidationError, ValueError) as exc:
                failure_result = GatewayResult(
                    run_status=AssessmentRunStatus.FAILED,
                    provider_key=gateway_result.provider_key,
                    model_name=gateway_result.model_name,
                    instruction_version=gateway_result.instruction_version,
                    prompt_hash=gateway_result.prompt_hash,
                    failure_code="invalid_output",
                    failure_detail=str(exc),
                    started_at=gateway_result.started_at,
                    completed_at=gateway_result.completed_at,
                )
                _persist_gateway_failure(connection, prepared_run.assessment_run_id, failure_result)
                return PreparedAssessmentRun(
                    assessment_run_id=prepared_run.assessment_run_id,
                    assessment_window_id=prepared_run.assessment_window_id,
                    run_status=AssessmentRunStatus.FAILED,
                    context_snapshot=prepared_run.context_snapshot,
                    profile_key=prepared_run.profile_key,
                    profile_display_name=prepared_run.profile_display_name,
                    profile_instruction_version=prepared_run.profile_instruction_version,
                    reused_run_id=prepared_run.reused_run_id,
                )
            persisted_run_status = _derive_run_status(prepared_run)
            return PreparedAssessmentRun(
                assessment_run_id=prepared_run.assessment_run_id,
                assessment_window_id=prepared_run.assessment_window_id,
                run_status=persisted_run_status,
                context_snapshot=prepared_run.context_snapshot,
                profile_key=prepared_run.profile_key,
                profile_display_name=prepared_run.profile_display_name,
                profile_instruction_version=prepared_run.profile_instruction_version,
                reused_run_id=prepared_run.reused_run_id,
            )

        _persist_gateway_failure(connection, prepared_run.assessment_run_id, gateway_result)
        return PreparedAssessmentRun(
            assessment_run_id=prepared_run.assessment_run_id,
            assessment_window_id=prepared_run.assessment_window_id,
            run_status=gateway_result.run_status,
            context_snapshot=prepared_run.context_snapshot,
            profile_key=prepared_run.profile_key,
            profile_display_name=prepared_run.profile_display_name,
            profile_instruction_version=prepared_run.profile_instruction_version,
            reused_run_id=prepared_run.reused_run_id,
        )


def create_assessment_dialog_entry(assessment_run_id: int, request: AssessmentDialogRequest) -> AssessmentDialogResponse:
    with get_connection() as connection:
        run_row = _fetch_one(
            connection,
            """
            SELECT r.assessment_run_id,
                   p.profile_key,
                   p.cadence,
                   w.season_id,
                   w.block_id,
                   w.week_id,
                   w.window_start_date,
                   w.window_end_date
            FROM agent_assessment_runs r
            JOIN agent_assessment_profiles p ON p.agent_profile_id = r.agent_profile_id
            JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
            WHERE r.assessment_run_id = ?
            """,
            (assessment_run_id,),
        )
        if run_row is None:
            raise LookupError(f"No existe la evaluacion {assessment_run_id}.")

        dialog_row = connection.execute(
            """
            INSERT INTO agent_assessment_dialog_context (
                assessment_run_id,
                entry_kind,
                entry_scope,
                clarification_kind,
                entry_text,
                linked_evidence_json,
                created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING dialog_context_id, created_at
            """,
            (
                assessment_run_id,
                request.entry_kind.value,
                request.entry_scope.value,
                request.clarification_kind.value if request.clarification_kind else None,
                request.entry_text,
                request.linked_evidence_json,
                request.created_by,
            ),
        ).fetchone()

    reassessment: ReassessmentStatusPayload | None = None
    if request.request_reassessment:
        rerun = execute_assessment_run(
            AssessmentRunTriggerRequest(
                cadence=AssessmentCadence(run_row["cadence"]),
                agent_profile_key=run_row["profile_key"],
                season_id=run_row["season_id"],
                block_id=run_row["block_id"],
                week_id=run_row["week_id"],
                window_start_date=run_row["window_start_date"],
                window_end_date=run_row["window_end_date"],
                trigger_mode=RunTriggerMode.RERUN,
            )
        )
        reassessment = ReassessmentStatusPayload(requested=True, status=rerun.run_status.value)

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO agent_assessment_dialog_context (
                    assessment_run_id,
                    entry_kind,
                    entry_scope,
                    entry_text,
                    linked_evidence_json,
                    created_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_run_id,
                    DialogEntryKind.SYSTEM_NOTE.value,
                    DialogEntryScope.REASSESSMENT_REQUEST.value,
                    f"Reassessment requested from assessment run {assessment_run_id}; created assessment run {rerun.assessment_run_id} with status {rerun.run_status.value}.",
                    json.dumps([f"reassessment_run_id={rerun.assessment_run_id}"], ensure_ascii=True),
                    "system",
                ),
            )

    return AssessmentDialogResponse(
        dialog_context_id=dialog_row["dialog_context_id"],
        assessment_run_id=assessment_run_id,
        proposal_id=None,
        entry_kind=request.entry_kind,
        entry_scope=request.entry_scope,
        clarification_kind=request.clarification_kind,
        entry_text=request.entry_text,
        linked_evidence_json=request.linked_evidence_json,
        created_at=dialog_row["created_at"],
        created_by=request.created_by,
        reassessment=reassessment,
    )


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

        type_results = connection.execute(
            """
            SELECT assessment_type_key, result_label, confidence_label, narrative_text, evidence_summary_json
            FROM agent_assessment_type_results
            WHERE assessment_run_id = ?
            ORDER BY assessment_type_result_id
            """,
            (assessment_run_id,),
        ).fetchall()
        findings = connection.execute(
            """
            SELECT finding_kind, severity, title, detail_text, evidence_refs_json, sort_order
            FROM agent_assessment_findings
            WHERE assessment_run_id = ?
            ORDER BY sort_order, assessment_finding_id
            """,
            (assessment_run_id,),
        ).fetchall()
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
            WHERE assessment_run_id = ?
            ORDER BY created_at, dialog_context_id
            """,
            (assessment_run_id,),
        ).fetchall()
        proposals = list_proposal_references(connection, assessment_run_id)

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
            confidence_label=ConfidenceLabel(row["confidence_label"]) if row["confidence_label"] else None,
            principal_evidence=principal_evidence,
            assessment_type_results=[
                AssessmentTypeResultPayload(
                    assessment_type_key=type_row["assessment_type_key"],
                    result_label=type_row["result_label"],
                    confidence_label=ConfidenceLabel(type_row["confidence_label"]) if type_row["confidence_label"] else None,
                    narrative_text=type_row["narrative_text"],
                    evidence_summary_json=type_row["evidence_summary_json"],
                )
                for type_row in type_results
            ],
            findings=[
                AssessmentFindingPayload(
                    finding_kind=FindingKind(finding_row["finding_kind"]),
                    severity=FindingSeverity(finding_row["severity"]) if finding_row["severity"] else None,
                    title=finding_row["title"],
                    detail_text=finding_row["detail_text"],
                    evidence_refs_json=finding_row["evidence_refs_json"],
                    sort_order=finding_row["sort_order"],
                )
                for finding_row in findings
            ],
            proposals=proposals,
            dialog_context=[
                DialogContextEntryPayload(
                    dialog_context_id=dialog_row["dialog_context_id"],
                    assessment_run_id=dialog_row["assessment_run_id"],
                    proposal_id=dialog_row["proposal_id"],
                    entry_kind=DialogEntryKind(dialog_row["entry_kind"]),
                    entry_scope=DialogEntryScope(dialog_row["entry_scope"]),
                    clarification_kind=ClarificationKind(dialog_row["clarification_kind"]) if dialog_row["clarification_kind"] else None,
                    entry_text=dialog_row["entry_text"],
                    linked_evidence_json=dialog_row["linked_evidence_json"],
                    created_at=dialog_row["created_at"],
                    created_by=dialog_row["created_by"],
                )
                for dialog_row in dialog_rows
            ],
        )


def list_latest_assessment_runs(
    season_id: int,
    cadence: AssessmentCadence | None = None,
    block_id: int | None = None,
    week_id: int | None = None,
) -> LatestAssessmentsResponse:
    filters = ["w.season_id = ?"]
    parameters: list[Any] = [season_id]

    if cadence is not None:
        filters.append("p.cadence = ?")
        parameters.append(cadence.value)
    if block_id is not None:
        filters.append("w.block_id = ?")
        parameters.append(block_id)
    if week_id is not None:
        filters.append("w.week_id = ?")
        parameters.append(week_id)

    query = f"""
        WITH ranked_runs AS (
            SELECT
                r.assessment_run_id,
                p.cadence,
                p.profile_key,
                p.display_name AS agent_profile_name,
                w.window_start_date,
                w.window_end_date,
                r.run_status,
                r.confidence_label,
                r.summary_text,
                (
                    SELECT COUNT(*)
                    FROM agent_adaptation_proposals ap
                    WHERE ap.assessment_run_id = r.assessment_run_id
                ) AS proposal_count,
                (
                    SELECT COUNT(*)
                    FROM agent_adaptation_proposals ap
                    WHERE ap.assessment_run_id = r.assessment_run_id
                      AND ap.proposal_status = 'pending'
                ) AS pending_proposal_count,
                ROW_NUMBER() OVER (
                    PARTITION BY p.cadence, p.profile_key, w.subject_scope_key
                    ORDER BY COALESCE(r.completed_at, r.started_at, r.created_at) DESC, r.assessment_run_id DESC
                ) AS run_rank
            FROM agent_assessment_runs r
            JOIN agent_assessment_profiles p ON p.agent_profile_id = r.agent_profile_id
            JOIN agent_assessment_windows w ON w.assessment_window_id = r.assessment_window_id
            WHERE {' AND '.join(filters)}
        )
        SELECT assessment_run_id,
               cadence,
               profile_key,
               agent_profile_name,
               window_start_date,
               window_end_date,
               run_status,
               confidence_label,
               summary_text,
               proposal_count,
               pending_proposal_count
        FROM ranked_runs
        WHERE run_rank = 1
        ORDER BY window_start_date DESC, assessment_run_id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return LatestAssessmentsResponse(
        items=[
            AssessmentRunLatestItem(
                assessment_run_id=row["assessment_run_id"],
                cadence=AssessmentCadence(row["cadence"]),
                agent_profile_key=row["profile_key"],
                agent_profile_name=row["agent_profile_name"],
                window_start_date=row["window_start_date"],
                window_end_date=row["window_end_date"],
                run_status=AssessmentRunStatus(row["run_status"]),
                confidence_label=ConfidenceLabel(row["confidence_label"]) if row["confidence_label"] else None,
                summary_text=row["summary_text"],
                proposal_count=row["proposal_count"],
                pending_proposal_count=row["pending_proposal_count"],
            )
            for row in rows
        ]
    )