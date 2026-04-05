from typing import Any

from pydantic import BaseModel, Field

from app.schemas.turn import HumanReviewInput


class QuestionPlanDebug(BaseModel):
    """Debug information for why a question was generated."""

    mode: str = "understand_current_code"
    phase: str = "Panorama Mapping"
    rubric_task_id: str | None = None
    rubric_task_label: str | None = None
    target_branch_ids: list[str] = Field(default_factory=list)
    target_artifact: str | None = None
    framework_gap: str | None = None
    confidence_score: float = 0.5
    human_gate_triggered: bool = False
    human_gate_reason: str | None = None
    why_this_question: str = ""
    planning_steps: list[str] = Field(default_factory=list)
    reviewer_modifications: list[str] = Field(default_factory=list)
    evidence_turn_ids: list[int] = Field(default_factory=list)
    question_intent: str | None = None
    intent_mode: str | None = None
    drift_detected: bool = False
    human_review_applied: bool = False


class TaskBoardDebug(BaseModel):
    """Debug information for task board state."""

    current_phase: str = "panorama_mapping"
    phase_status: dict[str, str] = Field(default_factory=dict)
    incomplete_tasks: list[dict[str, Any]] = Field(default_factory=list)
    next_priority_task: dict[str, Any] | None = None
    human_gate_pending: bool = False


class ModeDebug(BaseModel):
    """Debug information for mode state."""

    current_mode: str = "understand_current_code"
    mode_constraints: dict[str, Any] = Field(default_factory=dict)
    can_propose_changes: bool = False
    valid_transitions: list[str] = Field(default_factory=list)


class ScenarioDebug(BaseModel):
    """Debug information for scenario completion."""

    is_complete: bool = False
    confidence: float = 0.0
    scenario_count: int = 0
    missing_aspects: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class DebugInfoResponse(BaseModel):
    """Complete debug information response."""

    question_plan: QuestionPlanDebug | None = None
    task_board: TaskBoardDebug | None = None
    mode: ModeDebug | None = None
    scenario: ScenarioDebug | None = None
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class CoverageBranchDebug(BaseModel):
    branch_id: str
    label: str
    stage: str
    status: str
    priority: float
    keywords: list[str]
    evidence_turn_ids: list[int]
    evidence_turn_nos: list[int]
    summary: str
    unresolved_points: list[str]
    last_turn_no: int


class QuestionHistoryDebug(BaseModel):
    turn_no: int
    stage: str
    intent: str
    branch_id: str
    target_type: str
    target_label: str
    signature: str
    question_text: str


class CoverageDebugResponse(BaseModel):
    version: int
    branch_count: int
    updated_through_turn_no: int
    branches: list[CoverageBranchDebug]
    question_history: list[QuestionHistoryDebug]
    framework: dict


class ContextPreviewRequest(BaseModel):
    answer_text: str
    human_review: HumanReviewInput | None = None


class ContextPreviewResponse(BaseModel):
    current_stage: str
    next_turn_no: int
    stage_objective: str
    framework_gaps: list[str]
    recent_context: str
    retrieved_context: str
    coverage_priorities: str
    selected_turn_ids: list[int]
    selected_branch_ids: list[str]
    branch_selection_meta: dict[str, dict]
    question_history: list[QuestionHistoryDebug]
    stage_decision: dict
    planner_decision: dict
    validation_preview: dict
    prompt_id: str
    prompt_version: str
    prompt_messages: list[dict[str, str]]
