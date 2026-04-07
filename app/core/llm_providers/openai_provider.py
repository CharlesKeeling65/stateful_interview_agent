import httpx
from openai import OpenAI

from app.core.config import settings
from app.core.llm_providers.base import LLMProvider
from app.core.llm_types import LLMGenerateResult, LLMUsageMetrics
from app.logging import emit_event


def create_openai_client() -> OpenAI:
    client_kwargs = {
        "api_key": settings.openai_api_key,
        "base_url": settings.openai_base_url,
    }

    try:
        return OpenAI(**client_kwargs)
    except ImportError as exc:
        if "socksio" not in str(exc):
            raise

        emit_event(
            "llm",
            "llm.client.proxy_fallback",
            "SOCKS proxy support is unavailable; retrying OpenAI client creation without environment proxy settings.",
            level=30,
            operation="get_openai_client",
            status="fallback",
            error_message=str(exc),
        )
        return OpenAI(
            **client_kwargs,
            http_client=httpx.Client(trust_env=False),
        )


class OpenAICompatibleProvider(LLMProvider):
    provider_name = "openai_compatible"

    def __init__(self, client: OpenAI | None = None):
        self.client = client or create_openai_client()

    def generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMGenerateResult:
        selected_model = model or settings.openai_model
        response = self.client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=temperature,
            stream=False,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Model returned empty content.")

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or (prompt_tokens + completion_tokens)
        )

        return LLMGenerateResult(
            text=content,
            model=selected_model,
            provider=self.provider_name,
            usage=LLMUsageMetrics(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                is_estimated=usage is None,
            ),
            raw_response=response,
        )
