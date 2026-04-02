from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.turn import TurnRead


class ProjectCreate(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str = Field(..., min_length=1)


class ProjectRead(BaseModel):
    id: int
    project_name: str
    system_prompt: str
    current_stage: str
    turn_count: int
    status: str
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
    message: str
