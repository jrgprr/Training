# Feature Specification: AI Training Assessment Agents

**Feature Branch**: `004-ai-training-assessment`

**Created**: 2026-05-28

**Status**: Draft

**Input**: User description: "Add specific AI agents in the application to assess the training process. Examples include a daily agent that assesses the athlete's evolution by analyzing the plan, activities, recovery, and related context, plus weekly, block, and season assessment agents that review results and can propose adaptations to the training plan."

## Affected System Layers *(mandatory)*

- **Primary layer(s)**: `Agentes/`, `GUI/backend`, minimal `GUI/frontend`, `Sistema/`
- **Canonical data impact**: SQLite remains the source of truth for athlete data, plan state, agent runs, findings, recommendations, adaptation proposals, and operator approval state. Markdown remains documentation and human-authored planning context only; it may be referenced by backend ingestion or planning workflows but is not the runtime source of truth for agent decisions.
- **External source impact**: Existing imported athlete data only, including Garmin-backed activities, daily metrics, and existing plan/review data. The feature may call an AI model provider to generate assessments, but it must not require any new external athlete-data source.

## LLM Assessment Rule *(mandatory)*

- All coaching assessments covered by this feature are performed by an LLM-based agent.
- Deterministic backend logic may assemble context, validate inputs, persist outputs, enforce approval rules, and apply accepted plan changes, but it does not replace the LLM as the component that performs the assessment itself.
- The system may use different prompts, agent instructions, or LLM configurations by cadence or assessment type, and the design should support multiple specialized agent profiles within the same cadence.
- The persisted assessment must always identify which LLM-driven agent profile generated it.
- If the LLM is unavailable, misconfigured, or fails during execution, the system must record an explicit failed or incomplete assessment outcome rather than falling back silently to a rule-only pseudo-assessment.

## Agent Profile Model *(mandatory)*

- The feature should support separate agent profiles rather than a single generic assessment agent.
- A cadence may contain more than one agent profile when different assessments benefit from distinct instructions, context selection, or reasoning style.
- Agent profiles may be specialized by cadence, assessment type, or both. For example, a daily recovery agent and a daily execution agent may coexist within the daily cadence.
- The system should allow the application to invoke one or more agent profiles for the same cadence window and persist each run independently.
- The operator must be able to distinguish which agent profile produced each assessment and proposal.

## Interaction Model *(mandatory)*

- The athlete or coach should be able to receive assessments through a review surface in the application, not only through backend records.
- The athlete or coach should be able to ask for an assessment explicitly, such as requesting today's assessment, this week's review, or the latest block evaluation.
- The interaction model should support both pull and push behavior.
- Pull behavior means the user can open the application, browse the latest assessments by cadence, and request a new run manually.
- Push behavior means the application can surface newly completed assessments, pending proposals, and important warnings in a visible inbox, feed, or notification-style summary within the app.
- The athlete or coach should be able to open an assessment and start a bounded coaching dialog about it, such as asking why the agent reached a conclusion, what evidence it used, or what change it is proposing.
- The interaction model should allow the athlete or coach to provide contextual corrections or explanations tied to the assessment window, such as clarifying that a planned activity was completed on the previous day, that an activity was intentionally swapped, or that relevant recovery context was missing from the imported data.
- Follow-up interaction must stay grounded in persisted assessment context, proposal context, and explicit user-provided clarifications rather than generating detached free-form coaching chat.
- User-provided clarifications should be treated as reviewable contextual inputs, not silent edits to canonical plan or execution records.
- Proposal review should be an explicit interaction surface where the user can inspect rationale, compare conflicts, and accept or reject changes.
- The first version does not need a full open-ended chat product, but it should support guided dialog around existing assessments and proposals, including user-supplied context that may justify a rerun, a revised interpretation, or a proposal adjustment.

## Assessment Catalog *(mandatory)*

The feature is not just "daily, weekly, block, and season agents". It is a set of concrete assessment types that may be grouped by the planning cadences already used by the system.

Each assessment type may be implemented by its own specialized agent profile, and multiple profiles may coexist within the same cadence.

### Daily Assessment Types

- **Daily Execution Assessment**: Compares the intended session or day role against what was actually completed and states whether the day matched, exceeded, fell short of, or diverged from the plan.
- **Daily Load And Absorption Assessment**: Interprets the most recent training load in the context of the prior days to judge whether the athlete appears to be absorbing work, carrying residual fatigue, or unexpectedly underloaded.
- **Daily Recovery And Readiness Assessment**: Reviews available recovery markers such as sleep, resting heart rate, weight trend context, subjective review notes, and recent fatigue signals to estimate readiness for the next session.
- **Daily Performance Signal Assessment**: Reviews the latest activity quality, benchmark route behavior, repeated segment efforts, and other comparable execution signals to identify whether the athlete showed positive, neutral, or negative performance evolution.
- **Daily Data Confidence Assessment**: States whether the day can be assessed confidently or whether missing activity linkage, sparse recovery data, import uncertainty, or quality-limited metrics reduce confidence.
- **Daily Next-Step Guidance**: Produces a bounded recommendation for the next 24 to 48 hours, such as maintain plan, cut volume, preserve intensity, or prioritize recovery, and may emit an explicit proposal to adjust the current or upcoming weekly plan when the evidence justifies it.

### Weekly Assessment Types

- **Weekly Adherence Assessment**: Reviews how the athlete followed the intended week structure, including planned versus executed session types, frequency, and major deviations.
- **Weekly Load Distribution Assessment**: Evaluates whether volume and difficulty were distributed appropriately across the week or concentrated in a way that increases risk or undermines the week's purpose.
- **Weekly Recovery Pattern Assessment**: Reviews whether recovery opportunities, freshness, and signal quality across the week were consistent with the intended week role.
- **Weekly Performance Progress Assessment**: Synthesizes route, segment, load, and session-level evidence to determine whether the athlete is progressing, plateauing, or regressing over the week.
- **Weekly Plan Adequacy Assessment**: Judges whether the week's design matched the athlete's current state and whether the remaining or upcoming week should stay on plan.
- **Weekly Adaptation Proposal Assessment**: Generates a proposal when the current block or the upcoming block progression should be adjusted, such as reducing planned progression, extending stabilization, or changing block-level emphasis.

### Block Assessment Types

- **Block Consistency Assessment**: Reviews whether the athlete is accumulating enough consistent work across the mesocycle to support the intended block direction.
- **Block Response Assessment**: Evaluates whether the athlete is responding to the current block as intended, including tolerance of load, coexistence of strength and endurance, and emerging limitations.
- **Block Performance Direction Assessment**: Uses multi-week benchmark signals to determine whether aerobic fitness, durability, and execution quality are moving in the desired direction during the block.
- **Block Risk Accumulation Assessment**: Looks for repeated signs of excessive fatigue, recurring plan breakdown, stagnation, or data-quality blind spots that should influence the end-of-block decision.
- **Block Planning Adequacy Assessment**: Judges whether the current block assumptions remain valid or need revision for the next block or phase.
- **Block Adaptation Proposal**: Produces a higher-level recommendation for the next season-level planning decisions, such as revising the next block sequence, phase emphasis, or macro assumptions, while leaving final plan changes to operator approval.

### Season Assessment Types

- **Season Direction Assessment**: Reviews whether the season is moving in the intended macro direction relative to the stated objectives and planning priorities.
- **Season Progress Assessment**: Evaluates whether the athlete is building the intended capabilities across blocks, including continuity, aerobic development, force support, and tolerance of progression.
- **Season Risk And Constraint Assessment**: Identifies season-level risks such as recurring setbacks, persistent recovery limitations, adherence instability, or unrealistic planning assumptions.
- **Season Planning Coherence Assessment**: Judges whether the sequence of completed and upcoming blocks still makes sense as a macro plan.
- **Season Adaptation Proposal**: Produces strategic proposals for updating the macro season plan itself, including priorities, success criteria, or future block sequencing, while leaving final plan changes to operator approval.

### Cross-Cadence Proposal Rule

- Daily assessments may propose updates to the weekly plan.
- Weekly assessments may propose updates to the block plan.
- Block assessments may propose updates to the season plan.
- Season assessments may propose updates to the macro season definition, strategic priorities, or future season-level planning assumptions.
- Assessments may also produce descriptive findings without proposals when the evidence does not justify a planning change.

### Initial Agent Roster *(v1)*

The first implementation should start with a small, explicit roster of specialized agent profiles.

- **Daily Execution Agent**: Reviews the intended day versus executed work and produces the daily execution assessment. It may also emit direct proposals for weekly-plan adjustments when the evidence supports change.
- **Daily Recovery And Readiness Agent**: Reviews recovery markers, recent load context, and confidence limits to produce the daily recovery/readiness assessment. It may also emit direct proposals for weekly-plan adjustments when the evidence supports change.
- **Weekly Adherence And Adequacy Agent**: Reviews the microcycle against the intended weekly structure and produces weekly adherence and weekly plan adequacy assessments. It may also emit direct proposals for block-level adjustments when the evidence supports change.
- **Block Performance Direction Agent**: Reviews the current or completed block to determine whether performance and adaptation are moving in the intended direction. It may also emit direct proposals for season-level adjustments when the evidence supports change.

Version 1 does not need a full roster for every assessment type in the catalog. It needs a viable starting set that covers daily visibility, weekly control, and block direction, with proposal capability embedded directly in the specialist agents.

### First-Version Scope Boundary

- Version 1 should prioritize a small number of assessments that are both high value and well supported by existing data.
- The minimum first-version assessment set should include Daily Execution Assessment, Daily Recovery And Readiness Assessment, Weekly Adherence Assessment, Weekly Plan Adequacy Assessment, Block Performance Direction Assessment, and Weekly Adaptation Proposal Assessment.
- Any assessment type may generate an adaptation proposal when its evidence is strong enough, but the proposal should target the next planning level above the cadence that produced it.
- The first-version implementation should use the explicit v1 agent roster defined above rather than attempting to cover the entire long-term assessment catalog immediately.
- Broader assessments such as long-horizon strategic planning or highly prescriptive nutrition guidance are out of scope unless later versions explicitly add them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily Athlete Evolution Assessment (Priority: P1)

As a coach or athlete, I need a daily assessment agent that reviews the latest plan context, executed activities, and recovery signals so that I can understand whether the athlete is progressing, absorbing load, or showing early warning signs.

**Why this priority**: Daily situational awareness is the core value. Without a reliable daily assessment, the higher-level weekly and monthly reviews become retrospective only and lose their practical coaching value.

**Independent Test**: Can be fully tested by loading a week with planned sessions, imported activities, and daily metrics, then triggering the daily agent and confirming that it produces one traceable assessment with findings, confidence, and next-step guidance.

**Acceptance Scenarios**:

1. **Given** a day with new activities or recovery metrics, **When** the daily assessment agent runs, **Then** it produces a persisted assessment that summarizes adherence, load context, recovery context, and athlete evolution signals for that day.
2. **Given** a day with no completed activity but available plan and recovery context, **When** the daily assessment agent runs, **Then** it produces a bounded assessment that explains the missing execution context rather than failing silently.
3. **Given** recent data that suggests unusual fatigue, loss of adherence, or emerging positive adaptation, **When** the daily assessment agent runs, **Then** the assessment makes that signal explicit and includes the evidence used to support it.
4. **Given** a completed daily assessment, **When** the athlete opens the application, **Then** the athlete can read the assessment in a clear review surface and identify whether follow-up action is needed.

---

### User Story 2 - Multi-Cadence Review With Adaptation Proposals (Priority: P2)

As a coach, I need assessment agents at all planning cadences to review the training process and propose plan adaptations when the results justify it so that the plan can evolve with the athlete instead of remaining static.

**Why this priority**: Daily commentary is useful, but the system becomes materially more valuable when any assessment that detects a meaningful mismatch or opportunity can turn that conclusion into a reviewable plan proposal.

**Independent Test**: Can be fully tested by running assessments across different cadences, including daily, and confirming that each can generate a persisted review with explicit plan-adaptation proposals when the evidence warrants change.

**Acceptance Scenarios**:

1. **Given** a daily assessment that detects a meaningful mismatch between athlete state and the immediate plan, **When** the daily assessment agent runs, **Then** it may create a traceable proposal to adjust the current or upcoming weekly plan rather than mutating the canonical plan silently.
2. **Given** a completed training week, **When** the weekly assessment agent runs, **Then** it produces a review of adherence, load progression, recovery pattern, and may propose a block-level adjustment when the weekly evidence justifies it.
3. **Given** a completed mesocycle or block, **When** the block assessment agent runs, **Then** it produces a broader evaluation of block response, performance direction, and may propose season-level planning changes when the block evidence justifies it.
4. **Given** a completed macro period or enough season evidence, **When** the season assessment agent runs, **Then** it produces a strategic evaluation of season direction and macro-planning coherence and may propose updates to the macro season plan itself.
5. **Given** evidence that the current or upcoming plan should change, **When** any assessment agent identifies that need, **Then** it creates a traceable proposal targeting the next planning level rather than mutating the canonical plan silently.

---

### User Story 3 - Coach Control And Traceability Of AI Recommendations (Priority: P3)

As a coach or operator, I need every AI assessment and adaptation proposal to be reviewable, explainable, and approval-driven so that the system augments coaching judgment instead of becoming an opaque autonomous planner.

**Why this priority**: AI-generated coaching advice is only useful if the operator can inspect the basis of the recommendation and control whether it changes the plan.

**Independent Test**: Can be fully tested by reviewing an assessment and a plan-adaptation proposal in the application, confirming that both expose supporting evidence, status, and approval workflow without requiring code or log inspection.

**Acceptance Scenarios**:

1. **Given** a persisted AI assessment, **When** a user inspects it, **Then** the system shows the assessment summary, major findings, supporting signals, and the data window used.
2. **Given** a persisted adaptation proposal, **When** a user reviews it, **Then** the system shows the proposed change, the reason, the affected planning surface, and whether it is pending, accepted, rejected, or superseded.
3. **Given** an AI recommendation that would change plan intent, **When** the user has not approved it, **Then** the canonical plan remains unchanged.
4. **Given** a persisted assessment or proposal, **When** the athlete or coach asks a bounded follow-up question about it, **Then** the system answers in the context of that persisted assessment rather than as an ungrounded generic chat response.
5. **Given** a persisted assessment, **When** the athlete or coach provides a contextual clarification such as "this activity was moved to the previous day," **Then** the system records that clarification as explicit dialog context and uses it only through a reviewable reassessment or proposal flow.

---

### User Story 4 - Ask For And Receive Assessments Interactively (Priority: P3)

As an athlete or coach, I need to request assessments explicitly and receive them through a usable in-app interaction flow so that the assessment system feels operational rather than hidden.

**Why this priority**: The feature is not useful if assessments exist only as backend artifacts. The user needs a direct way to trigger, receive, review, and question them.

**Independent Test**: Can be fully tested by requesting a cadence-specific assessment from the application, reviewing the generated result in the app, and asking a bounded follow-up question tied to that assessment.

**Acceptance Scenarios**:

1. **Given** the athlete wants today's view, **When** they request a daily assessment from the application, **Then** the system triggers or returns the relevant persisted daily assessment.
2. **Given** new assessments or pending proposals exist, **When** the athlete or coach opens the application, **Then** the app surfaces them through a visible latest-results or inbox-style review area.
3. **Given** the athlete or coach opens one persisted assessment, **When** they ask a bounded follow-up question, **Then** the system answers using the stored assessment context and linked evidence.
4. **Given** the athlete or coach opens one persisted assessment, **When** they provide a contextual clarification about schedule changes, swapped sessions, missing context, or execution intent, **Then** the system captures that clarification inside the same assessment dialog and makes it available for reassessment or proposal review.

### Edge Cases

- What happens when a daily, weekly, block, or season agent runs with incomplete source data, such as missing activity links, missing recovery metrics, or partial imports? The system must still produce a bounded assessment that states the missing evidence and lowers confidence where appropriate.
- What happens when no new athlete data exists since the last agent run? The system must avoid creating redundant assessments that pretend new analysis occurred.
- How does the system handle conflicting signals, such as better route performance but worsening recovery markers? The assessment must surface the conflict explicitly rather than collapsing it into a single unsupported conclusion.
- What happens when any assessment agent recommends a plan change that conflicts with the current higher-level plan intent or with a pending proposal? The system must keep proposals traceable and distinct instead of overwriting prior planning decisions.
- What happens when multiple assessments at different cadences generate overlapping or contradictory proposals? The system must preserve each proposal independently and make conflicts reviewable by the operator.
- How does the system handle AI-service errors, timeouts, or unavailable model configuration? The run must be persisted with an explicit failure or incomplete status and operator-readable detail.
- What happens when the athlete completes extra unplanned work that materially changes week load? The assessment must factor that execution into its conclusion even if the original plan expected a lighter week.
- What happens when the athlete asks a follow-up question about an assessment that no longer matches the latest source data? The system must make clear whether the answer refers to the stored historical assessment or requires a new run.
- What happens when no completed assessment exists yet for the requested cadence window? The application must either trigger a run explicitly or show that no assessment is available yet instead of pretending one exists.
- What happens when the athlete provides contextual information that conflicts with canonical records, such as claiming a session happened on a different day? The system must preserve the clarification as dialog context and require an explicit reconciliation or reassessment path rather than overwriting canonical records silently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support AI assessment cadences aligned to the planning structure already used by the system: daily, weekly, block, and season.
- **FR-0010**: All supported assessments in this feature MUST be executed by an LLM-based agent rather than by deterministic rule evaluation alone.
- **FR-0011**: Backend services MAY compute supporting metrics, summaries, confidence inputs, and validation checks, but the interpretive assessment output itself MUST come from an LLM-driven run.
- **FR-0012**: The system MUST support separate agent profiles for different assessment purposes rather than requiring a single shared agent profile for all cadences and assessments.
- **FR-0013**: A single cadence MUST be allowed to contain multiple agent profiles when different assessments require distinct instructions, context selection, or output style.
- **FR-0014**: The first version MUST include at least the following agent profiles: Daily Execution Agent, Daily Recovery And Readiness Agent, Weekly Adherence And Adequacy Agent, and Block Performance Direction Agent.
- **FR-0015**: Specialist agent profiles in the first version MUST be allowed to emit adaptation proposals directly when their evidence supports change at the next planning level.
- **FR-001a**: The feature MUST define supported assessment types explicitly rather than treating each cadence as a single undifferentiated analysis.
- **FR-001b**: The first version MUST ship with an explicit minimum assessment set covering daily execution, daily recovery/readiness, weekly adherence, weekly plan adequacy, block performance direction, and weekly adaptation proposals.
- **FR-002**: The daily assessment agent MUST analyze the relevant plan context, recent executed activities, available daily metrics, and stored review context for its assessment window.
- **FR-002a**: Daily assessments MUST be able to distinguish at least execution, recovery/readiness, performance signal, and data-confidence outputs within the persisted result.
- **FR-003**: The weekly assessment agent MUST analyze the completed or active training week against the intended weekly plan, actual execution, load distribution, and recovery pattern.
- **FR-003a**: Weekly assessments MUST be able to distinguish at least adherence, load distribution, recovery pattern, performance progress, and plan adequacy outputs within the persisted result.
- **FR-004**: The block assessment agent MUST analyze the current or completed mesocycle against the intended block objectives, actual execution pattern, accumulated response, and emerging risks.
- **FR-004a**: Block assessments MUST be able to distinguish at least consistency, block response, performance direction, risk accumulation, and planning adequacy outputs within the persisted result.
- **FR-004b**: The season assessment agent MUST analyze the macro period across completed and active blocks to evaluate season direction, progress toward major objectives, persistent risks, and macro-planning coherence.
- **FR-004c**: Season assessments MUST be able to distinguish at least season direction, season progress, season risk/constraints, and planning coherence outputs within the persisted result.
- **FR-005**: Every AI assessment run MUST persist a traceable record in SQLite, including cadence, analysis window, status, generated summary, findings, timestamps, and enough provenance to identify which athlete data was considered.
- **FR-005a**: Every persisted assessment run MUST record the agent profile that generated it.
- **FR-006**: The system MUST persist structured findings for each assessment, including at least positive signals, risk signals, adherence observations, and recommended next actions when those are present.
- **FR-007**: The system MUST allow any supported assessment type to create an explicit plan-adaptation proposal when the evidence suggests the plan should change.
- **FR-0070**: The system MUST NOT require a separate proposal-only agent in order for a specialist assessment agent to emit a proposal.
- **FR-007a**: Daily-generated proposals MUST target the weekly plan and MUST still require explicit operator approval before affecting the canonical plan.
- **FR-007b**: Weekly-generated proposals MUST target the block plan rather than directly rewriting daily sessions or season strategy.
- **FR-007c**: Block-generated proposals MUST target the season plan rather than directly rewriting unrelated lower-level execution details.
- **FR-007d**: Season-generated proposals MUST target the macro season plan, strategic priorities, or future season-structure assumptions.
- **FR-008**: Plan-adaptation proposals MUST remain separate from the canonical plan until an operator explicitly approves them.
- **FR-009**: The system MUST preserve SQLite as the source of truth for agent runs, findings, recommendations, proposal state, and approval decisions.
- **FR-010**: GUI behavior introduced by this feature MUST remain thin and MUST read backend-provided assessments, findings, proposal state, and traceability rather than embedding planning or coaching logic in the frontend.
- **FR-010a**: The application MUST provide a user-facing review surface for latest assessments and pending proposals rather than leaving assessment consumption to logs or direct database inspection.
- **FR-010b**: The application MUST allow the athlete or coach to trigger a cadence-specific assessment run explicitly from the UI or an equivalent application interaction surface.
- **FR-010c**: The application MUST support bounded follow-up interaction tied to a persisted assessment or proposal so the user can ask why a conclusion was reached or what evidence supports it.
- **FR-010d**: Follow-up interaction MUST stay anchored to a specific persisted assessment run or proposal and MUST NOT degrade into an unscoped generic chat that ignores stored context.
- **FR-010e**: The application MUST support structured user clarifications tied to a persisted assessment or proposal, including schedule shifts, swapped sessions, missing-context notes, and execution-intent explanations.
- **FR-010f**: Structured user clarifications MUST be persisted as reviewable dialog context and MUST NOT silently mutate canonical plan, activity, or review records.
- **FR-010g**: The system MUST allow a persisted clarification to trigger or support a reassessment flow so the athlete or coach can see whether the additional context changes the conclusion.
- **FR-011**: The backend MUST assemble the analysis context for each agent from canonical plan, activity, recovery, quality, segment, and review data that already exists in the system when those surfaces are relevant and available.
- **FR-012**: The system MUST expose enough traceability for a user to understand why an assessment or proposal was produced, including the assessed time window and the principal evidence considered.
- **FR-013**: The system MUST represent assessment-run outcomes explicitly, including successful completion, no-new-data, partial-context, and failed execution states.
- **FR-013a**: Failed or incomplete LLM calls MUST be persisted as explicit assessment-run outcomes and MUST NOT be represented as completed assessments.
- **FR-014**: The system MUST avoid generating duplicate daily, weekly, block, or season assessments for the same cadence and analysis window unless a rerun is explicitly requested or source evidence changed.
- **FR-015**: The system MUST support operator-initiated reruns of an assessment window while preserving prior run history.
- **FR-016**: The system MUST record operator decisions on plan-adaptation proposals, including at minimum pending, accepted, rejected, and superseded states.
- **FR-016a**: The system MUST preserve multiple concurrent proposals, including conflicting proposals from different assessment types or cadences, until an operator resolves them.
- **FR-016b**: The system MUST preserve concurrent assessments and proposals produced by different agent profiles within the same cadence without collapsing them into a single synthetic result unless an explicit aggregation step is defined.
- **FR-017**: Accepted adaptation proposals MUST be traceable to the planning surface they changed, the assessment that generated them, and the operator decision that approved them.
- **FR-017a**: Each adaptation proposal MUST record both its source cadence and its target planning level so the review workflow can distinguish, for example, a daily-to-week proposal from a weekly-to-block proposal.
- **FR-018**: The feature MUST remain scoped to assessment and plan adaptation support; it MUST NOT autonomously execute or rewrite the training plan without explicit operator action.
- **FR-019**: The feature MUST preserve the repository's local-first operating model for athlete data; temporary AI-service invocation may be used for reasoning, but canonical athlete state and decision history MUST remain local in SQLite.
- **FR-020**: The system MUST provide an application surface where users can review the latest daily, weekly, block, and season assessments and inspect pending adaptation proposals.
- **FR-020a**: The application surface MUST expose which v1 agent profile produced each persisted assessment or proposal.
- **FR-020b**: The application surface MUST support an inbox, feed, or equivalent latest-results view that makes newly completed assessments and pending proposals discoverable without requiring the user to know exact run identifiers.
- **FR-021**: The system MUST allow assessment prompts or agent instructions to be specialized by cadence without requiring the frontend to duplicate those instructions.
- **FR-022**: When source activity quality or import traceability indicates uncertainty, the assessment context MUST carry that uncertainty into the persisted assessment rather than treating all inputs as equally trustworthy.
- **FR-023**: The system MUST support bounded behavior when the athlete has sparse data, such as weeks with incomplete activity linkage or missing recovery markers, by producing a limited-confidence assessment instead of fabricating precision.
- **FR-024**: The system MUST expose backend-derived recommendation status and proposal status through stable application APIs rather than only through logs or markdown artifacts.

### Key Entities *(include if feature involves data)*

- **Assessment Agent Profile**: A configured agent identity for a specific cadence and purpose, including its scope, instruction set, and execution policy.
- **Cadence Agent Set**: The collection of one or more agent profiles that may run for the same cadence window.
- **LLM Assessment Run**: A persisted invocation of an LLM-based agent that receives assembled athlete context and returns an interpretive assessment for a defined cadence and window.
- **Assessment Type Definition**: A named coaching analysis surface, such as daily recovery/readiness or weekly plan adequacy, that defines what question the agent is expected to answer.
- **Assessment Run**: One persisted execution of a daily, weekly, block, or season agent over a defined analysis window, including status, summary, provenance, and timestamps.
- **Assessment Finding**: A structured conclusion extracted from an assessment run, such as a positive adaptation signal, recovery risk, adherence issue, or planning recommendation.
- **Assessment Dialog Context**: A persisted, reviewable record of bounded follow-up questions and user clarifications tied to a specific assessment run or proposal.
- **Adaptation Proposal**: A traceable proposal to change some part of the current or future training plan, linked to the assessment run that created it.
- **Proposal Decision**: The operator approval state and decision metadata associated with an adaptation proposal.
- **Assessment Window**: The bounded date or period that defines which plan, activity, recovery, and review records were included in a run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can obtain a daily athlete assessment for a day with new data in under 2 minutes from the application surface.
- **SC-002**: 100% of completed AI assessment runs persist a traceable record of cadence, analysis window, status, and generated findings in SQLite.
- **SC-003**: 100% of AI-generated plan-adaptation proposals remain pending until an operator explicitly accepts or rejects them.
- **SC-004**: A coach can review the latest weekly or block assessment and determine within 3 minutes whether the next planning unit should remain unchanged or be adapted.
- **SC-005**: When no new source data exists for a cadence window, the system records a `no_new_data` style outcome instead of generating a redundant substantive assessment.
- **SC-006**: At least 90% of assessment runs that complete successfully expose enough supporting evidence for a coach to understand the main recommendation without inspecting raw database rows.

## Assumptions

- The feature targets the current single-athlete local workflow first, even if the data model remains extensible for future multi-athlete support.
- Existing canonical sources such as plan tables, imported activities, daily metrics, review records, quality flags, and segment history are sufficient to build the first version of assessment context.
- The first version focuses on assessment and recommendation, not fully autonomous plan editing or closed-loop coaching.
- Any plan changes suggested by AI are reviewed by a human operator before they affect the canonical plan.
- The frontend remains a thin reader and action surface for assessments and approvals, while orchestration and prompt construction stay in backend or agent-layer services.
- Markdown planning artifacts may still exist for human planning workflows, but the runtime agent context is assembled from backend-owned canonical data and explicit derived context.
- The system may use different prompts or specialized agent instructions for daily, weekly, block, and season assessments while keeping a shared persistence and review model.
- The feature assumes specialized agent profiles are preferable to one generic prompt, and multiple profiles may run within the same cadence when that improves assessment quality.
- The feature assumes that every persisted assessment outcome originates from an LLM run, even when deterministic backend logic precomputes context or validates proposal boundaries.