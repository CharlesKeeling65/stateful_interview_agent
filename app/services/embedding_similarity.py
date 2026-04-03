import math
from typing import Sequence

from app.core.config import settings
from app.core.llm_client import get_openai_client
from app.logging import emit_event


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot_product = sum(left * right for left, right in zip(a, b))
    left_norm = math.sqrt(sum(value * value for value in a))
    right_norm = math.sqrt(sum(value * value for value in b))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def get_embedding_similarity(a: str, b: str) -> float | None:
    if not settings.duplicate_guard_use_embeddings or not settings.openai_embedding_model:
        return None

    client = get_openai_client()
    try:
        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=[a, b],
        )
        vectors = [item.embedding for item in response.data]
        if len(vectors) != 2:
            return None
        return _cosine_similarity(vectors[0], vectors[1])
    except Exception as exc:
        emit_event(
            "llm",
            "embedding.similarity.error",
            "Embedding-based similarity check failed",
            level=30,
            operation="embedding_similarity",
            exc_info=exc,
        )
        return None
