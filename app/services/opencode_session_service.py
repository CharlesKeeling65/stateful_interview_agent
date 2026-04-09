from app.core.config import settings
from app.core.http_clients import get_opencode_client
from app.models.project import ProjectSession


def ensure_opencode_session_with_status(project: ProjectSession) -> tuple[str, bool]:
    if project.opencode_session_id:
        return project.opencode_session_id, False

    client = get_opencode_client()
    payload = {
        "model": settings.opencode_model,
        "plan": True,
        "stream": False,
    }
    response = client.post("/session", json=payload)
    response.raise_for_status()
    session_id = response.json()["id"]
    project.opencode_session_id = session_id
    return session_id, True


def ensure_opencode_session(project: ProjectSession) -> str:
    session_id, _ = ensure_opencode_session_with_status(project)
    return session_id
