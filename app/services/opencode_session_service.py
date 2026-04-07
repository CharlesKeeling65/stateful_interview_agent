import httpx

from app.core.config import settings
from app.models.project import ProjectSession


def ensure_opencode_session(project: ProjectSession) -> str:
    if project.opencode_session_id:
        return project.opencode_session_id

    client = httpx.Client(
        base_url=settings.opencode_base_url,
        timeout=settings.opencode_timeout_seconds,
    )
    response = client.post("/session")
    response.raise_for_status()
    session_id = response.json()["id"]
    project.opencode_session_id = session_id
    return session_id
