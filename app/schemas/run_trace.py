from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunStepRead(BaseModel):
    id: int
    step_index: int
    step_key: str
    label: str
    status: str
    description: str | None
    method: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    next_step_hint: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    meta: dict[str, Any] = Field(default_factory=dict)


class RunRead(BaseModel):
    id: int
    project_id: int
    turn_no: int | None
    request_id: str | None
    trace_id: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    total_llm_tokens: int
    total_llm_calls: int
    step_count: int
    current_step_key: str | None = None
    current_step_label: str | None = None
    current_step_status: str | None = None
    steps: list[RunStepRead] = Field(default_factory=list)


class ProjectRunSummary(BaseModel):
    cumulative_generation_time_ms: int
    run_count: int
    average_run_duration_ms: int
