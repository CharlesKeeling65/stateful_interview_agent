from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LLMUsageMetrics:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    is_estimated: bool = False


@dataclass(slots=True)
class LLMGenerateResult:
    text: str
    model: str
    provider: str
    usage: LLMUsageMetrics
    raw_response: Any | None = None
