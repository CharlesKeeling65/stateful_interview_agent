import httpx
from openai import OpenAI

from app.core.config import settings
from app.logging import emit_event


def get_openai_client() -> OpenAI:
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
