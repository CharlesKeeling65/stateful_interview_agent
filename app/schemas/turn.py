from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.usage import LLMUsageRead
from app.schemas.usage import TokenUsageSummary


class HumanReviewInput(BaseModel):
    verdict: Literal["sufficient", "insufficient", "drifted"] | None = None
    direction: Literal["continue", "redirect"] = "continue"
    preferred_next_focus: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    phase: str | None = Field(default=None, max_length=80)
    phase_ready: bool | None = None


class HumanGateResolutionInput(BaseModel):
    gate_id: str = Field(..., min_length=1, max_length=80)
    action: str = Field(..., min_length=1, max_length=80)
    preferred_next_focus: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    phase_ready: bool | None = None


class QuestionPlanRead(BaseModel):
    mode: str | None = None
    phase: str | None = None
    intent_mode: str | None = None
    question_intent: str | None = None
    target_branch_id: str | None = None
    target_type: str | None = None
    target_label: str | None = None
    selected_framework_gap: str | None = None
    selected_branch_ids: list[str] = Field(default_factory=list)
    selected_turn_ids: list[int] = Field(default_factory=list)
    human_review_applied: bool | None = None
    drift_detected: bool | None = None
    why_this_question: str | None = None
    rubric_task_id: str | None = None
    rubric_task_label: str | None = None
    confidence_score: float | None = None
    human_gate_triggered: bool | None = None
    reviewer_reason: str | None = None
    reviewer_modifications: list[str] = Field(default_factory=list)
    scenario_complete: bool | None = None
    scenario_missing_aspects: list[str] = Field(default_factory=list)
    repo_queries: list[str] = Field(default_factory=list)
    repo_selected_paths: list[str] = Field(default_factory=list)
    repo_selected_symbols: list[str] = Field(default_factory=list)
    repo_commit_sha: str | None = None
    repo_tool_calls: list[dict] = Field(default_factory=list)


class TranscriptEventRead(BaseModel):
    event_id: str
    event_type: str
    turn_no: int | None = None
    timestamp: str
    payload: dict = Field(default_factory=dict)


class AnswerAnalysisChunkRead(BaseModel):
    index: int
    text: str


class AnswerAnalysisRead(BaseModel):
    stage_focus: str | None = None
    summary_source: str | None = None
    key_points: list[str] = Field(default_factory=list)
    follow_up_anchors: list[str] = Field(default_factory=list)
    rag_chunks: list[AnswerAnalysisChunkRead] = Field(default_factory=list)


class TurnRead(BaseModel):
    id: int
    project_id: int
    turn_no: int
    stage: str
    question_text: str
    question_text_for_copy: str
    answer_text: str | None
    answer_text_for_display: str | None = None
    answer_summary: str | None
    answer_analysis: AnswerAnalysisRead | None = None
    human_review: HumanReviewInput | None = None
    question_plan: QuestionPlanRead | None = None
    event_log: list[TranscriptEventRead] = Field(default_factory=list)
    current_question_version_no: int = 1
    question_regeneration_count: int = 0
    human_intervention_regeneration_usage_summary: TokenUsageSummary = Field(
        default_factory=lambda: TokenUsageSummary(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_total_tokens=0,
        )
    )
    question_versions: list["QuestionVersionRead"] = Field(default_factory=list)
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    llm_usages: list[LLMUsageRead] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerSubmitRequest(BaseModel):
    answer_text: str = Field(..., min_length=1)
    human_review: HumanReviewInput | None = None


class AnswerSubmitResponse(BaseModel):
    project_id: int
    updated_turn: TurnRead
    can_generate_next: bool = False
    message: str


class OpenCodeSessionResponse(BaseModel):
    project_id: int
    session_id: str
    created: bool = False
    mode: str = "plan"


class NextQuestionRequest(BaseModel):
    human_review: HumanReviewInput | None = None
    human_gate: HumanGateResolutionInput | None = None


class OpenCodePlanStepRequest(BaseModel):
    human_review: HumanReviewInput | None = None


class QuestionVersionRead(BaseModel):
    id: int
    version_no: int
    generation_kind: str
    question_text: str
    question_plan: QuestionPlanRead | None = None
    human_review: HumanReviewInput | None = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    is_estimated: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrentQuestionRegenerateRequest(BaseModel):
    human_review: HumanReviewInput | None = None


class CurrentQuestionRegenerateAppliedChanges(BaseModel):
    review_persisted: bool
    planner_followed_review: bool
    question_changed: bool
    previous_stage: str
    current_stage: str
    stage_changed: bool
    requested_focus: str | None = None
    requested_verdict: str | None = None
    requested_direction: str | None = None
    note_applied: bool = False
    phase_ready_applied: bool = False
    question_version_before: int
    question_version_after: int
    regeneration_count_before: int
    regeneration_count_after: int


class CurrentQuestionRegenerateResponse(BaseModel):
    project_id: int
    turn: TurnRead
    run_id: int | None = None
    usage_summary: TokenUsageSummary
    applied_changes: CurrentQuestionRegenerateAppliedChanges
    message: str


class AnswerWithdrawResponse(BaseModel):
    project_id: int
    withdrawn_turn: TurnRead
    message: str


TurnRead.model_rebuild()
