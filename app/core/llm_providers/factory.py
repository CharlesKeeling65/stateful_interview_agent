from app.core.config import settings
from app.core.llm_providers.anthropic_provider import AnthropicProvider
from app.core.llm_providers.base import LLMProvider
from app.core.llm_providers.opencode_provider import OpenCodeProvider
from app.core.llm_providers.openai_provider import OpenAICompatibleProvider


def get_llm_provider() -> LLMProvider:
    provider_name = settings.llm_provider
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "opencode":
        return OpenCodeProvider()
    return OpenAICompatibleProvider()
