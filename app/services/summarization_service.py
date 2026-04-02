from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm_client import get_openai_client
from app.models.turn import InterviewTurn
from app.services.usage_service import create_usage_record, extract_usage_metrics


def summarize_answer(
    *,
    project_id: int,
    turn: InterviewTurn,
    system_prompt: str,
):
    client = get_openai_client()
    user_instruction = f"""
Summarize this answered interview turn for future follow-up questioning.

Stage: {turn.stage}
Question: {turn.question_text}
Answer:
{turn.answer_text}

Requirements:
1. Keep the summary concise.
2. Preserve key technical details and concrete facts.
3. Preserve project-understanding progress made in this answer.
4. Preserve unresolved points or ambiguities worth revisiting later.
5. Write for future interview continuity, not for end-user display.
6. Do not add facts that were not present in the answer.
""".strip()

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_instruction},
        ],
        temperature=0.2,
        stream=False,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty summary content.")

    cleaned = content.strip()
    usage_metrics = extract_usage_metrics(
        response,
        prompt_text=user_instruction,
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
