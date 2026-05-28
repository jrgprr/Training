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
    ConfidenceLabel,
    AssessmentTypeResultPayload,
    AssessmentFindingPayload,
    FindingKind,
    FindingSeverity,
    AssessmentWindowSummary,
    RunTriggerMode,
)
from .ai_context import AssessmentContextSnapshot, build_assessment_context_with_connection
from .ai_gateway import AssessmentLLMGateway, GatewayProvider, GatewayResult, GatewayInvocation
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


def _derive_confidence(snapshot: AssessmentContextSnapshot) -> ConfidenceLabel:
    context = snapshot.context
    if context.get("activities") and context.get("daily_metrics"):
        return ConfidenceLabel.MEDIUM
    return ConfidenceLabel.LIMITED


def _derive_run_status(prepared_run: PreparedAssessmentRun) -> AssessmentRunStatus:
    if prepared_run.profile_key == "daily_execution_v1" and not prepared_run.context_snapshot.context.get("activities"):
        return AssessmentRunStatus.PARTIAL_CONTEXT
    return AssessmentRunStatus.COMPLETED


def _derive_assessment_type_key(profile_key: str) -> str:
    if profile_key == "daily_execution_v1":
        return "daily_execution"
    if profile_key == "daily_recovery_readiness_v1":
        return "daily_recovery_readiness"
    return profile_key.removesuffix("_v1")


def _derive_result_label(prepared_run: PreparedAssessmentRun) -> str:
    has_activities = bool(prepared_run.context_snapshot.context.get("activities"))
    if prepared_run.profile_key == "daily_execution_v1":
        return "executed" if has_activities else "no_activity_recorded"
    return "ready_check" if has_activities else "limited_readiness"


def _derive_finding(prepared_run: PreparedAssessmentRun, output_text: str, confidence: ConfidenceLabel) -> tuple[FindingKind, FindingSeverity, str]:
    if prepared_run.context_snapshot.context.get("activities"):
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
    confidence = _derive_confidence(prepared_run.context_snapshot)
    run_status = _derive_run_status(prepared_run)
    result_label = _derive_result_label(prepared_run)
    finding_kind, finding_severity, finding_text = _derive_finding(
        prepared_run,
        gateway_result.output_text or "",
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
            gateway_result.output_text,
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
            gateway_result.output_text,
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
            _persist_completed_run(connection, prepared_run, gateway_result)
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
            proposals=[],
            dialog_context=[],
        )