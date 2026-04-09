import httpx

from app.core.http_clients import get_opencode_client
from app.core.llm_providers.base import LLMProvider
from app.core.llm_types import LLMGenerateResult, LLMUsageMetrics


class OpenCodeProvider(LLMProvider):
    provider_name = "opencode"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or get_opencode_client()

    def generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMGenerateResult:
        del model, temperature
        session_response = self.client.post("/session")
        session_response.raise_for_status()
        session_id = session_response.json()["id"]

        prompt_text = "\n\n".join(
            message.get("content", "")
            for message in messages
            if message.get("content")
        )
        response = self.client.post(
            f"/session/{session_id}/message",
            json={"parts": [{"type": "text", "text": prompt_text}]},
        )
        response.raise_for_status()
        payload = response.json()
        parts = payload.get("parts") or []
        text = ""
        for part in reversed(parts):
            if part.get("type") == "text" and part.get("text"):
                text = part["text"]
                break
        if not text:
            raise ValueError("OpenCode returned empty content.")

        estimated_prompt = max(1, len(prompt_text) // 4) if prompt_text else 0
        estimated_completion = max(1, len(text) // 4)
        return LLMGenerateResult(
            text=text,
            model="opencode-http",
            provider=self.provider_name,
            usage=LLMUsageMetrics(
                prompt_tokens=estimated_prompt,
                completion_tokens=estimated_completion,
                total_tokens=estimated_prompt + estimated_completion,
                is_estimated=True,
            ),
            raw_response=payload,
        )
