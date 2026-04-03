from typing import Any

from pydantic import BaseModel, Field


class PromptDefinition(BaseModel):
    id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    system_template: str = Field(..., min_length=1)
    user_template: str = Field(..., min_length=1)
    required_variables: list[str] = Field(default_factory=list)


class RenderedPrompt(BaseModel):
    prompt_id: str
    version: str
    variables: dict[str, Any]
    messages: list[dict[str, str]]
