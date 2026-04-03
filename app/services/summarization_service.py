from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm_client import get_openai_client
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

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=prompt.messages,
        temperature=0.2,
        stream=False,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty summary content.")

    cleaned = content.strip()
    usage_metrics = extract_usage_metrics(
        response,
        prompt_text="\n\n".join(message["content"] for message in prompt.messages),
        completion_text=cleaned,
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

    db.flush()
    return summarized_count
