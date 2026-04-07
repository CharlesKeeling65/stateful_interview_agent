from app.core.llm_providers.factory import get_llm_provider
from app.core.llm_providers.openai_provider import create_openai_client


def get_openai_client():
    return create_openai_client()


__all__ = ["get_llm_provider", "get_openai_client"]
