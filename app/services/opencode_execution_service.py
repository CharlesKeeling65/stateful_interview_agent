import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state, save_coverage_state
from app.services.opencode_session_service import ensure_opencode_session
from app.services.summarization_service import refresh_turn_answer_memory


def fetch_opencode_answer(*, project: ProjectSession, question_text: str) -> str:
    session_id = ensure_opencode_session(project)
    client = httpx.Client(
        base_url=settings.opencode_base_url,
        timeout=settings.opencode_timeout_seconds,
    )
    response = client.post(
        f"/session/{session_id}/message",
        json={"parts": [{"type": "text", "text": question_text}]},
    )
    if response.status_code == 404:
        project.opencode_session_id = None
        session_id = ensure_opencode_session(project)
        response = client.post(
            f"/session/{session_id}/message",
            json={"parts": [{"type": "text", "text": question_text}]},
        )
    response.raise_for_status()
    payload = response.json()
    for part in reversed(payload.get("parts") or []):
        if part.get("type") == "text" and part.get("text"):
            return part["text"].strip()
    raise ValueError("OpenCode returned no text answer.")


def auto_answer_turn(*, db: Session, project: ProjectSession, turn: InterviewTurn) -> InterviewTurn:
    if turn.answer_text:
        return turn
    answer_text = fetch_opencode_answer(project=project, question_text=turn.question_text)
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
