from abc import ABC, abstractmethod

from app.core.llm_types import LLMGenerateResult


class LLMProvider(ABC):
    provider_name: str

    @abstractmethod
    def generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMGenerateResult:
        raise NotImplementedError
