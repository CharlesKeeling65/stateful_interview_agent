from datetime import datetime

from pydantic import BaseModel, Field


class TurnRead(BaseModel):
    id: int
    project_id: int
    turn_no: int
    stage: str
    question_text: str
    answer_text: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerSubmitRequest(BaseModel):
    answer_text: str = Field(..., min_length=1)


class AnswerSubmitResponse(BaseModel):
    project_id: int
    updated_turn: TurnRead
