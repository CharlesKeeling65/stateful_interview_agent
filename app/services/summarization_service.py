import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm_client import get_openai_client
from app.logging import emit_event, preview_payload
from app.models.turn import InterviewTurn
from app.prompts import get_prompt_manager
from app.services.usage_service import create_usage_record, extract_usage_metrics


def summarize_answer(
    *,
    project_id: int,
    turn: InterviewTurn,
    system_prompt: str,
):
    client = get_openai_client()
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
            "model": settings.openai_model,
            "messages": preview_payload(
                prompt.messages,
                artifact_category="llm",
                artifact_name=f"summary-turn-{turn.turn_no}-messages",
            ) if settings.log_llm_payloads else None,
        },
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=prompt.messages,
            temperature=0.2,
            stream=False,
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

    content = response.choices[0].message.content
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

        result = summarize_answer(
            project_id=project_id,
            turn=turn,
            system_prompt=system_prompt,
        )
        turn.answer_summary = result["summary"]
        db.add(result["usage_record"])
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
