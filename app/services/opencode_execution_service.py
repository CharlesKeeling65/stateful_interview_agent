import json
import re
import threading
import time
from queue import Empty, Queue

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.http_clients import get_opencode_client
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


def extract_opencode_error(payload: dict) -> str | None:
    info = payload.get("info")
    if isinstance(info, dict):
        error = info.get("error")
        if isinstance(error, dict):
            data = error.get("data")
            if isinstance(data, dict):
                message = data.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

    error = payload.get("error")
    if isinstance(error, dict):
        data = error.get("data")
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    return None


def extract_opencode_text(payload: dict) -> str | None:
    parts = payload.get("parts") or []
    for part in reversed(parts):
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
            return clean_opencode_answer(str(part["text"]))

    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return clean_opencode_answer(text)

    return None


def parse_opencode_sse_data(line: str) -> dict | None:
    if not line.startswith("data: "):
        return None
    raw_json = line[6:].strip()
    if not raw_json:
        return None
    return json.loads(raw_json)


def wait_for_opencode_response_from_events(*, event_iter, session_id: str) -> str:
    assistant_message_id: str | None = None
    text_parts: dict[str, str] = {}

    for event in event_iter:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        properties = payload.get("properties")
        if not isinstance(properties, dict):
            continue

        if properties.get("sessionID") != session_id:
            continue

        event_type = payload.get("type")
        if event_type == "message.updated":
            info = properties.get("info")
            if not isinstance(info, dict):
                continue
            if info.get("role") != "assistant":
                continue
            assistant_message_id = info.get("id") or assistant_message_id
            error_message = extract_opencode_error({"info": info})
            if error_message:
                raise RuntimeError(error_message)

        if event_type == "message.part.updated":
            part = properties.get("part")
            if not isinstance(part, dict):
                continue
            if assistant_message_id and part.get("messageID") != assistant_message_id:
                continue
            if part.get("type") != "text":
                continue
            part_id = part.get("id")
            part_text = part.get("text")
            if isinstance(part_id, str) and isinstance(part_text, str):
                text_parts[part_id] = part_text

        if event_type == "session.status":
            status = properties.get("status")
            if not isinstance(status, dict):
                continue
            if status.get("type") != "idle":
                continue
            combined = "".join(text_parts.values()).strip()
            if combined:
                return clean_opencode_answer(combined)

    raise TimeoutError("OpenCode event stream ended before an assistant answer was received.")


def _build_opencode_background_client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.opencode_base_url,
        timeout=httpx.Timeout(
            connect=10.0,
            read=None,
            write=settings.opencode_timeout_seconds,
            pool=settings.opencode_timeout_seconds,
        ),
    )


def _collect_opencode_answer_via_events(*, session_id: str, question_text: str) -> str:
    event_queue: Queue[dict] = Queue()
    stop_event = threading.Event()
    sender_result: dict[str, object] = {}
    listener_result: dict[str, object] = {}

    def event_listener() -> None:
        try:
            with _build_opencode_background_client() as client:
                with client.stream("GET", "/global/event", headers={"Accept": "text/event-stream"}) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if stop_event.is_set():
                            break
                        if not line:
                            continue
                        event = parse_opencode_sse_data(line)
                        if event is not None:
                            event_queue.put(event)
        except Exception as exc:  # pragma: no cover - depends on local OpenCode availability
            listener_result["error"] = exc

    def send_message() -> None:
        try:
            with _build_opencode_background_client() as client:
                response = client.post(
                    f"/session/{session_id}/message",
                    json={
                        "agent": "plan",
                        "parts": [{"type": "text", "text": question_text}],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                sender_result["payload"] = response.json()
        except Exception as exc:  # pragma: no cover - exercised through integration behavior
            sender_result["error"] = exc
        finally:
            sender_result["done"] = True

    listener_thread = threading.Thread(target=event_listener, daemon=True)
    sender_thread = threading.Thread(target=send_message, daemon=True)
    listener_thread.start()
    sender_thread.start()

    deadline = time.monotonic() + max(settings.opencode_timeout_seconds, 300.0)
    try:
        while time.monotonic() < deadline:
            try:
                answer_text = wait_for_opencode_response_from_events(
                    event_iter=iter([event_queue.get(timeout=0.5)]),
                    session_id=session_id,
                )
                return answer_text
            except Empty:
                pass
            except TimeoutError:
                pass

            payload = sender_result.get("payload")
            if isinstance(payload, dict):
                error_message = extract_opencode_error(payload)
                if error_message:
                    raise RuntimeError(error_message)
                answer_text = extract_opencode_text(payload)
                if answer_text:
                    return answer_text
                if sender_result.get("done"):
                    raise ValueError("OpenCode returned no text answer.")

            listener_error = listener_result.get("error")
            if listener_error is not None:
                raise RuntimeError(f"OpenCode event stream failed: {listener_error}")

            if sender_result.get("done") and "error" in sender_result:
                raise sender_result["error"]  # type: ignore[misc]

        raise TimeoutError("OpenCode did not produce an answer before the event wait deadline.")
    finally:
        stop_event.set()


def fetch_opencode_answer(
    *,
    project: ProjectSession,
    question_text: str,
) -> str:
    session_id = ensure_opencode_session(project)
    try:
        return _collect_opencode_answer_via_events(
            session_id=session_id,
            question_text=question_text,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise

    project.opencode_session_id = None
    session_id = ensure_opencode_session(project)
    return _collect_opencode_answer_via_events(
        session_id=session_id,
        question_text=question_text,
    )


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
