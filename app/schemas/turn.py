from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.usage import LLMUsageRead


class TurnRead(BaseModel):
    id: int
    project_id: int
    turn_no: int
    stage: str
    question_text: str
    question_text_for_copy: str
    answer_text: str | None
    answer_summary: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    llm_usages: list[LLMUsageRead] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerSubmitRequest(BaseModel):
    answer_text: str = Field(..., min_length=1)


class AnswerSubmitResponse(BaseModel):
    project_id: int
    updated_turn: TurnRead
