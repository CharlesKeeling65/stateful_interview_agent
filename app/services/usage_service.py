from collections.abc import Iterable

from app.core.llm_types import LLMGenerateResult
from app.models.llm_usage import LLMUsage


def estimate_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def extract_usage_metrics(
    response: LLMGenerateResult | None = None,
    *,
    prompt_text: str = "",
    completion_text: str = "",
):
    if response is not None:
        usage = response.usage
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

        if prompt_tokens is None:
            prompt_tokens = getattr(usage, "input_tokens", None)
        if completion_tokens is None:
            completion_tokens = getattr(usage, "output_tokens", None)
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        if prompt_tokens is not None and completion_tokens is not None and total_tokens is not None:
            return {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(total_tokens),
                "is_estimated": bool(getattr(usage, "is_estimated", False)),
            }

    estimated_prompt = estimate_token_count(prompt_text)
    estimated_completion = estimate_token_count(completion_text)

    return {
        "prompt_tokens": estimated_prompt,
        "completion_tokens": estimated_completion,
        "total_tokens": estimated_prompt + estimated_completion,
        "is_estimated": True,
    }


def create_usage_record(
    *,
    project_id: int,
    turn_id: int | None,
    operation_type: str,
    usage_metrics: dict,
):
    return LLMUsage(
        project_id=project_id,
        turn_id=turn_id,
        operation_type=operation_type,
        prompt_tokens=usage_metrics["prompt_tokens"],
        completion_tokens=usage_metrics["completion_tokens"],
        total_tokens=usage_metrics["total_tokens"],
        is_estimated=usage_metrics["is_estimated"],
    )


def aggregate_project_usage(usages: Iterable[LLMUsage]):
    prompt_tokens = sum(usage.prompt_tokens for usage in usages)
    completion_tokens = sum(usage.completion_tokens for usage in usages)
    total_tokens = sum(usage.total_tokens for usage in usages)
    estimated_total_tokens = sum(
        usage.total_tokens for usage in usages if getattr(usage, "is_estimated", False)
    )

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_total_tokens": estimated_total_tokens,
    }
