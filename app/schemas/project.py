from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.turn import TurnRead
from app.schemas.usage import TokenUsageSummary


class ProjectCreate(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str = Field(..., min_length=1)


class ProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=255)
    system_prompt: str | None = Field(default=None, min_length=1)


class ProjectRead(BaseModel):
    id: int
    project_name: str
    system_prompt: str
    current_stage: str
    turn_count: int
    status: str
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_total_tokens: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStartResponse(BaseModel):
    project: ProjectRead
    first_turn: TurnRead


class ProjectNextResponse(BaseModel):
    project: ProjectRead
    previous_turn: TurnRead
    next_turn: TurnRead | None
    interview_finished: bool
    minimum_goal_reached: bool
    usage_summary: TokenUsageSummary
    message: str


class ProjectStatusResponse(BaseModel):
    project_id: int
    project_name: str
    status: str
    current_stage: str
    turn_count: int
    minimum_goal_reached: bool
    max_turn_limit: int
    latest_turn_no: int | None
    latest_turn_answered: bool | None
    latest_question_text: str | None
    latest_question_text_for_copy: str | None
    usage_summary: TokenUsageSummary


class TranscriptResponse(BaseModel):
    project_id: int
    project_name: str
    turn_count: int
    usage_summary: TokenUsageSummary
    transcript: str
