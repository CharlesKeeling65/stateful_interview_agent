from app.core.config import settings
from app.core.llm_client import get_llm_provider


def test_llm_call() -> dict:
    provider = get_llm_provider()

    try:
        response = provider.generate_text(
            model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
            ],
            temperature=0,
        )

        return {
            "ok": True,
            "provider": response.provider,
            "model": response.model,
            "base_url": settings.openai_base_url if settings.llm_provider == "openai_compatible" else settings.opencode_base_url if settings.llm_provider == "opencode" else None,
            "content": response.text,
        }

    except Exception as e:
        return {
            "ok": False,
            "error_type": type(e).__name__,
            "message": str(e),
            "provider": settings.llm_provider,
            "model": settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_model,
        }
