import httpx
import re
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state, save_coverage_state
from app.services.opencode_session_service import ensure_opencode_session
from app.services.summarization_service import refresh_turn_answer_memory


def clean_opencode_answer(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(
        r"^\s*(?:\*\*\s*)?(?:Q|Question)\s*\d+\s*[:：]\s*(?:\*\*\s*)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def fetch_opencode_answer(
    *,
    project: ProjectSession,
    question_text: str,
) -> str:
    session_id = ensure_opencode_session(project)
    client = httpx.Client(
        base_url=settings.opencode_base_url,
        timeout=settings.opencode_timeout_seconds,
    )
    response = client.post(
        f"/session/{session_id}/message",
        json={"agent": "plan", "parts": [{"type": "text", "text": question_text}], "stream": False},
    )
    if response.status_code == 404:
        project.opencode_session_id = None
        session_id = ensure_opencode_session(project)
        response = client.post(
            f"/session/{session_id}/message",
            json={"agent": "plan", "parts": [{"type": "text", "text": question_text}], "stream": False},
        )
    response.raise_for_status()
    payload = response.json()
    parts = payload.get("parts") or []
    for part in reversed(parts):
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
            return clean_opencode_answer(str(part["text"]))
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return clean_opencode_answer(text)
    raise ValueError("OpenCode returned no text answer.")


def persist_turn_answer(
    *,
    db: Session,
    project: ProjectSession,
    turn: InterviewTurn,
    answer_text: str,
) -> InterviewTurn:
    turn.answer_text = answer_text
    refresh_turn_answer_memory(
        db=db,
        project_id=project.id,
        system_prompt=project.system_prompt,
        turn=turn,
    )
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project.id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    save_coverage_state(project, rebuild_coverage_state(turns))
    db.flush()
    return turn


def auto_answer_turn(*, db: Session, project: ProjectSession, turn: InterviewTurn) -> InterviewTurn:
    if turn.answer_text:
        return turn
    answer_text = fetch_opencode_answer(project=project, question_text=turn.question_text)
    return persist_turn_answer(db=db, project=project, turn=turn, answer_text=answer_text)
