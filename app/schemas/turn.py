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
