from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ai_assessment_models import AssessmentRunStatus, AssessmentRunTriggerRequest, RunTriggerMode
from .ai_context import AssessmentContextSnapshot, build_assessment_context_with_connection
from .ai_profiles import get_profile_definition, list_profile_definitions
from .db import get_connection


@dataclass(frozen=True)
class PreparedAssessmentRun:
    assessment_run_id: int
    assessment_window_id: int
    run_status: AssessmentRunStatus
    context_snapshot: AssessmentContextSnapshot
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
            reused_run_id=latest_run["assessment_run_id"] if latest_run is not None else None,
        )