from pydantic import BaseModel

from app.schemas.turn import HumanReviewInput


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
