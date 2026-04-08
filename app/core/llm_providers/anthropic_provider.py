from anthropic import Anthropic

from app.core.config import settings
from app.core.llm_providers.base import LLMProvider
from app.core.llm_types import LLMGenerateResult, LLMUsageMetrics
from app.services.config_service import resolve_effective_anthropic_config


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"

    def __init__(self, client: Anthropic | None = None):
        effective_config = resolve_effective_anthropic_config()
        self.client = client or Anthropic(
            api_key=effective_config["api_key"] or settings.anthropic_api_key,
            base_url=effective_config["base_url"] or settings.anthropic_base_url,
        )

    def generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMGenerateResult:
        selected_model = model or settings.anthropic_model
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, object]] = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                if content:
                    system_parts.append(content)
                continue
            anthropic_role = "assistant" if role == "assistant" else "user"
            anthropic_messages.append(
                {
                    "role": anthropic_role,
                    "content": [{"type": "text", "text": content}],
                }
            )

        if not anthropic_messages:
            raise ValueError("Anthropic request requires at least one non-system message.")

        response = self.client.messages.create(
            model=selected_model,
            system="\n\n".join(part for part in system_parts if part).strip() or None,
            messages=anthropic_messages,
            temperature=temperature,
            max_tokens=settings.anthropic_max_tokens,
        )
        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ]
        content = "\n".join(text_parts).strip()
        if not content:
            raise ValueError("Model returned empty content.")

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = prompt_tokens + completion_tokens

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
