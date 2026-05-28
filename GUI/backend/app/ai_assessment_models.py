from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AssessmentCadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BLOCK = "block"
    SEASON = "season"


class TargetPlanningLevel(StrEnum):
    WEEKLY = "weekly"
    BLOCK = "block"
    SEASON = "season"
    MACRO = "macro"


class RunTriggerMode(StrEnum):
    MANUAL = "manual"
    RERUN = "rerun"
    SCHEDULED = "scheduled"


class AssessmentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    NO_NEW_DATA = "no_new_data"
    PARTIAL_CONTEXT = "partial_context"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConfidenceLabel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LIMITED = "limited"


class FindingKind(StrEnum):
    POSITIVE_SIGNAL = "positive_signal"
    RISK_SIGNAL = "risk_signal"
    ADHERENCE_OBSERVATION = "adherence_observation"
    RECOVERY_OBSERVATION = "recovery_observation"
    PERFORMANCE_SIGNAL = "performance_signal"
    NEXT_ACTION = "next_action"
    DATA_CONFIDENCE = "data_confidence"


class FindingSeverity(StrEnum):
    INFO = "info"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ProposalDecisionStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class DialogEntryKind(StrEnum):
    USER_QUESTION = "user_question"
    USER_CLARIFICATION = "user_clarification"
    ASSISTANT_RESPONSE = "assistant_response"
    SYSTEM_NOTE = "system_note"


class DialogEntryScope(StrEnum):
    ASSESSMENT_SUMMARY = "assessment_summary"
    FINDING = "finding"
    PROPOSAL = "proposal"
    REASSESSMENT_REQUEST = "reassessment_request"


class ClarificationKind(StrEnum):
    SCHEDULE_SHIFT = "schedule_shift"
    SESSION_SWAP = "session_swap"
    MISSING_CONTEXT = "missing_context"
    DEVICE_ISSUE = "device_issue"
    EXECUTION_INTENT = "execution_intent"


class AgentProfileSummary(BaseModel):
    profile_key: str
    display_name: str
    cadence: AssessmentCadence
    instruction_version: str | None = None


class AssessmentWindowSummary(BaseModel):
    assessment_window_id: int | None = None
    window_start_date: str
    window_end_date: str
    subject_scope_key: str


class AssessmentRunTriggerRequest(BaseModel):
    cadence: AssessmentCadence
    agent_profile_key: str
    season_id: int
    window_start_date: str
    window_end_date: str
    trigger_mode: RunTriggerMode = RunTriggerMode.MANUAL
    block_id: int | None = None
    week_id: int | None = None


class AssessmentSummaryPayload(BaseModel):
    summary_text: str | None = None
    confidence_label: ConfidenceLabel | None = None
    proposal_count: int = 0


class AssessmentRunTriggerResponse(BaseModel):
    assessment_run_id: int
    assessment_window_id: int
    agent_profile: AgentProfileSummary
    run_status: AssessmentRunStatus
    window: AssessmentWindowSummary
    result_summary: AssessmentSummaryPayload


class AssessmentTypeResultPayload(BaseModel):
    assessment_type_key: str
    result_label: str
    confidence_label: ConfidenceLabel | None = None
    narrative_text: str | None = None
    evidence_summary_json: str | None = None


class AssessmentFindingPayload(BaseModel):
    finding_kind: FindingKind
    severity: FindingSeverity | None = None
    title: str
    detail_text: str | None = None
    evidence_refs_json: str | None = None
    sort_order: int = 0


class ProposalListItem(BaseModel):
    proposal_id: int
    proposal_status: ProposalStatus
    source_cadence: AssessmentCadence
    target_planning_level: TargetPlanningLevel
    agent_profile_key: str
    proposal_title: str
    proposal_summary: str | None = None
    conflict_group_key: str | None = None
    created_at: str


class ProposalReferencePayload(BaseModel):
    proposal_id: int
    proposal_status: ProposalStatus
    source_cadence: AssessmentCadence
    target_planning_level: TargetPlanningLevel
    proposal_title: str


class DialogContextEntryPayload(BaseModel):
    dialog_context_id: int | None = None
    assessment_run_id: int | None = None
    proposal_id: int | None = None
    entry_kind: DialogEntryKind
    entry_scope: DialogEntryScope
    clarification_kind: ClarificationKind | None = None
    entry_text: str
    linked_evidence_json: str | None = None
    created_at: str | None = None
    created_by: str


class ReassessmentStatusPayload(BaseModel):
    requested: bool
    status: str


class AssessmentDialogRequest(BaseModel):
    entry_kind: DialogEntryKind
    entry_scope: DialogEntryScope
    clarification_kind: ClarificationKind | None = None
    entry_text: str
    created_by: str
    linked_evidence_json: str | None = None
    request_reassessment: bool = False


class AssessmentDialogResponse(DialogContextEntryPayload):
    reassessment: ReassessmentStatusPayload | None = None


class AssessmentRunLatestItem(BaseModel):
    assessment_run_id: int
    cadence: AssessmentCadence
    agent_profile_key: str
    agent_profile_name: str
    window_start_date: str
    window_end_date: str
    run_status: AssessmentRunStatus
    confidence_label: ConfidenceLabel | None = None
    summary_text: str | None = None
    proposal_count: int = 0
    pending_proposal_count: int = 0


class LatestAssessmentsResponse(BaseModel):
    items: list[AssessmentRunLatestItem] = Field(default_factory=list)


class AssessmentRunDetailResponse(BaseModel):
    assessment_run_id: int
    run_status: AssessmentRunStatus
    agent_profile: AgentProfileSummary
    window: AssessmentWindowSummary
    summary_text: str | None = None
    confidence_label: ConfidenceLabel | None = None
    principal_evidence: list[str] = Field(default_factory=list)
    assessment_type_results: list[AssessmentTypeResultPayload] = Field(default_factory=list)
    findings: list[AssessmentFindingPayload] = Field(default_factory=list)
    proposals: list[ProposalReferencePayload] = Field(default_factory=list)
    dialog_context: list[DialogContextEntryPayload] = Field(default_factory=list)


class ProposalDecisionRequest(BaseModel):
    decision_status: ProposalDecisionStatus
    decided_by: str
    decision_note: str | None = None
    superseding_proposal_id: int | None = None


class ProposalDecisionPayload(BaseModel):
    proposal_decision_id: int
    decision_status: ProposalDecisionStatus
    decision_note: str | None = None
    decided_by: str
    decided_at: str
    superseding_proposal_id: int | None = None
    applied_change_ref: str | None = None


class ProposalDetailResponse(BaseModel):
    proposal_id: int
    proposal_status: ProposalStatus
    source_cadence: AssessmentCadence
    target_planning_level: TargetPlanningLevel
    proposal_title: str
    proposal_summary: str | None = None
    reasoning_summary: str | None = None
    proposed_change: dict[str, Any] = Field(default_factory=dict)
    source_assessment: dict[str, Any] = Field(default_factory=dict)
    dialog_context: list[DialogContextEntryPayload] = Field(default_factory=list)
    decision_history: list[ProposalDecisionPayload] = Field(default_factory=list)


class ProposalListResponse(BaseModel):
    items: list[ProposalListItem] = Field(default_factory=list)


def serialize_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)