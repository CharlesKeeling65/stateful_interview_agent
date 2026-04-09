from functools import lru_cache

import httpx

from app.core.config import settings


@lru_cache(maxsize=1)
def get_opencode_client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.opencode_base_url,
        timeout=settings.opencode_timeout_seconds,
    )


def close_opencode_client() -> None:
    client = get_opencode_client()
    client.close()
    get_opencode_client.cache_clear()
