import json
import re
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm_client import get_llm_provider
from app.logging import emit_event, preview_payload
from app.models.turn import InterviewTurn
from app.prompts import get_prompt_manager
from app.services.usage_service import create_usage_record, extract_usage_metrics

PANORAMA_SIGNAL_MAP = {
    "Primary users": ("user", "users", "customer", "customers", "operator", "operators", "admin", "admins", "analyst"),
    "System purpose": ("purpose", "goal", "problem", "achieve", "support", "help"),
    "System boundaries": ("boundary", "boundaries", "scope", "inside", "outside"),
    "Major modules": ("module", "modules", "service", "services", "component", "components", "gateway"),
    "High-level workflow": ("workflow", "flow", "handoff", "request", "pipeline", "routing"),
}

ARCHITECTURE_SIGNAL_MAP = {
    "Architecture organization": ("layer", "layered", "architecture", "tier", "pipeline", "monolith", "microservice"),
    "Module responsibilities": ("responsibility", "responsibilities", "owns", "split", "separate"),
    "Collaboration mechanism": ("http", "rpc", "event", "queue", "message", "async", "sync", "call"),
    "Execution path": ("request path", "execution path", "call chain", "handoff", "routes to", "->"),
    "Design rationale": ("rationale", "tradeoff", "maintainability", "performance", "reliability", "why"),
}

FOLLOW_UP_MARKERS = (
    "unclear",
    "unknown",
    "unresolved",
    "not yet",
    "still",
    "needs",
    "missing",
    "tbd",
    "later",
)


def summarize_answer(
    *,
    project_id: int,
    turn: InterviewTurn,
    system_prompt: str,
):
    provider = get_llm_provider()
    prompt = get_prompt_manager().render(
        "answer_summary",
        {
            "system_prompt": system_prompt,
            "stage": turn.stage,
            "question_text": turn.question_text,
            "answer_text": turn.answer_text,
        },
    )
    prompt_text = "\n\n".join(message["content"] for message in prompt.messages)
    start_time = time.perf_counter()
    emit_event(
        "llm",
        "llm.call.start",
        "Starting answer summarization LLM call",
        operation="answer_summarization",
        project_id=project_id,
        turn_no=turn.turn_no,
        stage=turn.stage,
        status="started",
        input={
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "model": (
                settings.anthropic_model if settings.llm_provider == "anthropic"
                else "opencode-http" if settings.llm_provider == "opencode"
                else settings.openai_model
            ),
            "messages": preview_payload(
                prompt.messages,
                artifact_category="llm",
                artifact_name=f"summary-turn-{turn.turn_no}-messages",
            ) if settings.log_llm_payloads else None,
        },
    )

    try:
        response = provider.generate_text(
            model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
            messages=prompt.messages,
            temperature=0.2,
        )
    except Exception as exc:
        emit_event(
            "llm",
            "llm.call.error",
            "Answer summarization LLM call failed",
            level=40,
            operation="answer_summarization",
            project_id=project_id,
            turn_no=turn.turn_no,
            stage=turn.stage,
            status="error",
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            exc_info=exc,
        )
        raise

    content = response.text
    if not content:
        error = ValueError("Model returned empty summary content.")
        emit_event(
            "llm",
            "llm.call.error",
            "Answer summarization LLM call returned empty content",
            level=40,
            operation="answer_summarization",
            project_id=project_id,
            turn_no=turn.turn_no,
            stage=turn.stage,
            status="error",
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            exc_info=error,
        )
        raise error

    cleaned = content.strip()
    usage_metrics = extract_usage_metrics(
        response,
        prompt_text=prompt_text,
        completion_text=cleaned,
    )
    emit_event(
        "llm",
        "llm.call.complete",
        "Completed answer summarization LLM call",
        operation="answer_summarization",
        project_id=project_id,
        turn_no=turn.turn_no,
        stage=turn.stage,
        status="success",
        duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
        usage=usage_metrics,
        output={
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "summary": preview_payload(
                cleaned,
                artifact_category="summaries",
                artifact_name=f"summary-turn-{turn.turn_no}",
            ),
        },
    )

    return {
        "summary": cleaned,
        "usage_metrics": usage_metrics,
        "usage_record": create_usage_record(
            project_id=project_id,
            turn_id=turn.id,
            operation_type="answer_summarization",
            usage_metrics=usage_metrics,
        ),
    }


def _split_sentences(*texts: str) -> list[str]:
    sentences: list[str] = []
    for text in texts:
        if not text:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
            cleaned = sentence.strip()
            if cleaned and cleaned not in sentences:
                sentences.append(cleaned)
    return sentences


def _fallback_summary(answer_text: str) -> str:
    sentences = _split_sentences(answer_text)
    if not sentences:
        return answer_text.strip()[:280]
    return " ".join(sentences[:2])[:320]


def _chunk_text(answer_text: str, *, max_chars: int = 260) -> list[dict[str, str | int]]:
    sentences = _split_sentences(answer_text)
    if not sentences:
        stripped = answer_text.strip()
        return [{"index": 1, "text": stripped}] if stripped else []

    chunks: list[dict[str, str | int]] = []
    current: list[str] = []
    current_len = 0
    chunk_index = 1
    for sentence in sentences:
        extra_len = len(sentence) + (1 if current else 0)
        if current and current_len + extra_len > max_chars:
            chunks.append({"index": chunk_index, "text": " ".join(current)})
            chunk_index += 1
            current = [sentence]
            current_len = len(sentence)
            continue
        current.append(sentence)
        current_len += extra_len

    if current:
        chunks.append({"index": chunk_index, "text": " ".join(current)})
    return chunks


def _pick_stage_points(stage: str, sentences: list[str]) -> list[str]:
    signal_map = {}
    if stage == "Panorama Mapping":
        signal_map = PANORAMA_SIGNAL_MAP
    elif stage == "Architecture Understanding":
        signal_map = ARCHITECTURE_SIGNAL_MAP

    selected: list[str] = []
    seen_sentences: set[str] = set()
    for label, markers in signal_map.items():
        for sentence in sentences:
            lowered = sentence.lower()
            if any(marker in lowered for marker in markers):
                point = f"{label}: {sentence}"
                if point not in selected:
                    selected.append(point)
                    seen_sentences.add(sentence)
                break

    if len(selected) >= 3:
        return selected[:5]

    for sentence in sentences:
        if sentence in seen_sentences:
            continue
        selected.append(sentence)
        if len(selected) >= 5:
            break
    return selected[:5]


def _extract_follow_up_anchors(stage: str, sentences: list[str], key_points: list[str]) -> list[str]:
    anchors: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(marker in lowered for marker in FOLLOW_UP_MARKERS):
            anchors.append(sentence)

    if stage in {"Panorama Mapping", "Architecture Understanding"} and len(anchors) < 2:
        for point in key_points:
            lowered = point.lower()
            if any(marker in lowered for marker in ("boundary", "workflow", "module", "handoff", "responsibility", "path")):
                anchor = f"Follow up on: {point}"
                if anchor not in anchors:
                    anchors.append(anchor)
            if len(anchors) >= 3:
                break
    return anchors[:4]


def build_answer_analysis(*, stage: str, answer_text: str, summary: str, summary_source: str) -> dict:
    sentences = _split_sentences(summary, answer_text)
    key_points = _pick_stage_points(stage, sentences)
    return {
        "stage_focus": stage,
        "summary_source": summary_source,
        "key_points": key_points,
        "follow_up_anchors": _extract_follow_up_anchors(stage, sentences, key_points),
        "rag_chunks": _chunk_text(answer_text),
    }


def refresh_turn_answer_memory(
    *,
    db: Session,
    project_id: int,
    system_prompt: str,
    turn: InterviewTurn,
) -> dict:
    if not turn.answer_text:
        turn.answer_summary = None
        turn.answer_analysis_json = None
        return {
            "summary": None,
            "summary_source": None,
            "usage_record": None,
            "analysis": None,
        }

    summary_source = "llm"
    usage_record = None
    try:
        result = summarize_answer(
            project_id=project_id,
            turn=turn,
            system_prompt=system_prompt,
        )
        summary = result["summary"]
        usage_record = result["usage_record"]
        db.add(usage_record)
    except Exception:
        summary = _fallback_summary(turn.answer_text)
        summary_source = "fallback"

    analysis = build_answer_analysis(
        stage=turn.stage,
        answer_text=turn.answer_text,
        summary=summary,
        summary_source=summary_source,
    )
    turn.answer_summary = summary
    turn.answer_analysis_json = json.dumps(analysis, ensure_ascii=True, sort_keys=True)
    return {
        "summary": summary,
        "summary_source": summary_source,
        "usage_record": usage_record,
        "analysis": analysis,
    }


def ensure_turn_summaries(
    *,
    db: Session,
    project_id: int,
    system_prompt: str,
    turns_to_summarize: list[InterviewTurn],
):
    emit_event(
        "workflow",
        "summarization.batch.start",
        "Checking whether answered turns need summaries",
        operation="ensure_turn_summaries",
        project_id=project_id,
        input={"candidate_turn_ids": [turn.id for turn in turns_to_summarize]},
    )
    summarized_count = 0
    for turn in turns_to_summarize:
        if not turn.answer_text or turn.answer_summary:
            continue

        result = refresh_turn_answer_memory(
            db=db,
            project_id=project_id,
            system_prompt=system_prompt,
            turn=turn,
        )
        summarized_count += 1
        emit_event(
            "workflow",
            "summarization.turn.complete",
            "Persisted summary for answered turn",
            operation="ensure_turn_summaries",
            project_id=project_id,
            turn_no=turn.turn_no,
            stage=turn.stage,
            status="success",
        )

    db.flush()
    emit_event(
        "workflow",
        "summarization.batch.complete",
        "Finished summary refresh",
        operation="ensure_turn_summaries",
        project_id=project_id,
        status="success",
        output={"summarized_count": summarized_count},
    )
    return summarized_count
