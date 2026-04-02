from openai import APIError, OpenAI

from app.core.config import settings
from app.core.llm_client import get_openai_client


def test_llm_call() -> dict:
    client: OpenAI = get_openai_client()

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
            ],
            stream=False,
        )

        return {
            "ok": True,
            "model": settings.openai_model,
            "base_url": settings.openai_base_url,
            "content": response.choices[0].message.content,
        }

    except APIError as e:
        return {
            "ok": False,
            "error_type": type(e).__name__,
            "message": str(e),
            "base_url": settings.openai_base_url,
            "model": settings.openai_model,
        }
    except Exception as e:
        return {
            "ok": False,
            "error_type": type(e).__name__,
            "message": str(e),
            "base_url": settings.openai_base_url,
            "model": settings.openai_model,
        }
