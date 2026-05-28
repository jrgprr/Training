from __future__ import annotations

from dataclasses import dataclass

from .ai_assessment_models import AssessmentCadence, TargetPlanningLevel


@dataclass(frozen=True)
class CadenceMetadata:
    cadence: AssessmentCadence
    display_name: str
    subject_scope_prefix: str
    proposal_target_level: TargetPlanningLevel | None
    supports_season_windows: bool


@dataclass(frozen=True)
class AssessmentProfileDefinition:
    profile_key: str
    display_name: str
    cadence: AssessmentCadence
    assessment_scope: str
    description: str
    instruction_version: str = "v1"
    proposal_target_level: TargetPlanningLevel | None = None
    emits_proposals: bool = True
    status: str = "active"


CADENCE_METADATA: dict[AssessmentCadence, CadenceMetadata] = {
    AssessmentCadence.DAILY: CadenceMetadata(
        cadence=AssessmentCadence.DAILY,
        display_name="Daily",
        subject_scope_prefix="day",
        proposal_target_level=TargetPlanningLevel.WEEKLY,
        supports_season_windows=False,
    ),
    AssessmentCadence.WEEKLY: CadenceMetadata(
        cadence=AssessmentCadence.WEEKLY,
        display_name="Weekly",
        subject_scope_prefix="week",
        proposal_target_level=TargetPlanningLevel.BLOCK,
        supports_season_windows=False,
    ),
    AssessmentCadence.BLOCK: CadenceMetadata(
        cadence=AssessmentCadence.BLOCK,
        display_name="Block",
        subject_scope_prefix="block",
        proposal_target_level=TargetPlanningLevel.SEASON,
        supports_season_windows=False,
    ),
    AssessmentCadence.SEASON: CadenceMetadata(
        cadence=AssessmentCadence.SEASON,
        display_name="Season",
        subject_scope_prefix="season",
        proposal_target_level=TargetPlanningLevel.MACRO,
        supports_season_windows=True,
    ),
}


V1_ASSESSMENT_PROFILES: dict[str, AssessmentProfileDefinition] = {
    "daily_execution_v1": AssessmentProfileDefinition(
        profile_key="daily_execution_v1",
        display_name="Daily Execution Agent",
        cadence=AssessmentCadence.DAILY,
        assessment_scope="execution",
        description="Compares the intended day role against executed work and can propose weekly-plan adjustments.",
        proposal_target_level=TargetPlanningLevel.WEEKLY,
    ),
    "daily_recovery_readiness_v1": AssessmentProfileDefinition(
        profile_key="daily_recovery_readiness_v1",
        display_name="Daily Recovery And Readiness Agent",
        cadence=AssessmentCadence.DAILY,
        assessment_scope="recovery_readiness",
        description="Reviews recovery markers, recent load context, and confidence limits before the next session.",
        proposal_target_level=TargetPlanningLevel.WEEKLY,
    ),
    "weekly_adherence_adequacy_v1": AssessmentProfileDefinition(
        profile_key="weekly_adherence_adequacy_v1",
        display_name="Weekly Adherence And Adequacy Agent",
        cadence=AssessmentCadence.WEEKLY,
        assessment_scope="adherence_adequacy",
        description="Reviews the microcycle against the intended weekly structure and can propose block-level adjustments.",
        proposal_target_level=TargetPlanningLevel.BLOCK,
    ),
    "block_performance_direction_v1": AssessmentProfileDefinition(
        profile_key="block_performance_direction_v1",
        display_name="Block Performance Direction Agent",
        cadence=AssessmentCadence.BLOCK,
        assessment_scope="performance_direction",
        description="Reviews current or completed block direction and can propose season-level adjustments.",
        proposal_target_level=TargetPlanningLevel.SEASON,
    ),
}


def get_profile_definition(profile_key: str) -> AssessmentProfileDefinition:
    try:
        return V1_ASSESSMENT_PROFILES[profile_key]
    except KeyError as exc:
        raise KeyError(f"Unknown assessment profile: {profile_key}") from exc


def list_profile_definitions() -> list[AssessmentProfileDefinition]:
    return list(V1_ASSESSMENT_PROFILES.values())


def get_cadence_metadata(cadence: AssessmentCadence) -> CadenceMetadata:
    return CADENCE_METADATA[cadence]