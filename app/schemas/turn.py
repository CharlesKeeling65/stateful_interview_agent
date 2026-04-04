from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.usage import LLMUsageRead


class HumanReviewInput(BaseModel):
    verdict: Literal["sufficient", "insufficient", "drifted"] | None = None
    direction: Literal["continue", "redirect"] = "continue"
    preferred_next_focus: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    phase_ready: bool | None = None


class QuestionPlanRead(BaseModel):
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


class TurnRead(BaseModel):
    id: int
    project_id: int
    turn_no: int
    stage: str
    question_text: str
    question_text_for_copy: str
    answer_text: str | None
    answer_summary: str | None
    human_review: HumanReviewInput | None = None
    question_plan: QuestionPlanRead | None = None
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
