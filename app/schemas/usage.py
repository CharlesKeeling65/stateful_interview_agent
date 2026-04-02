from datetime import datetime

from pydantic import BaseModel


class LLMUsageRead(BaseModel):
    id: int
    project_id: int
    turn_id: int | None
    operation_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    is_estimated: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenUsageSummary(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_total_tokens: int = 0
