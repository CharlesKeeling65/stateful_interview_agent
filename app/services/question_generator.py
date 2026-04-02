from app.core.config import settings
from app.core.llm_client import get_openai_client
from app.models.turn import InterviewTurn
from app.services.question_postprocessor import clean_generated_question
from app.services.stage_manager import get_stage_instruction


def generate_first_question(system_prompt: str) -> str:
    client = get_openai_client()

    user_instruction = """
Start the interview for a software project understanding task.

Current stage: Panorama Mapping
Stage objective: Focus on the overall purpose, target users, project boundaries, major modules, and high-level workflow. Avoid deep implementation details.

Requirements:
1. Ask exactly one question only.
2. The question must be in English.
3. This is the first question, so label it as Q1.
4. The question should establish the overall understanding of the project.
5. Prefer a precise overview question over a generic introductory question.
6. Do not answer the question.
7. Do not provide multiple options or explanations.
""".strip()

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_instruction},
        ],
        temperature=0.3,
        stream=False,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty content.")

    print(f"[DEBUG] Generated first question raw output: {content!r}")
    cleaned = clean_generated_question(content, 1)
    print(f"[DEBUG] Cleaned first question: {cleaned!r}")

    return cleaned


def format_turn_history(turns: list[InterviewTurn]) -> str:
    lines = []
    for turn in turns:
        lines.append(f"Turn {turn.turn_no}")
        lines.append(f"Question: {turn.question_text}")
        lines.append(f"Answer: {turn.answer_text or '[No answer yet]'}")
        lines.append("")
    return "\n".join(lines).strip()


def generate_next_question(
    system_prompt: str,
    turns: list[InterviewTurn],
    next_turn_no: int,
    current_stage: str,
) -> str:
    client = get_openai_client()

    history_text = format_turn_history(turns)
    stage_instruction = get_stage_instruction(current_stage)
    is_near_end = next_turn_no >= settings.interview_min_turns
    closing_instruction = (
        "The interview is now in its closing phase. Prefer questions that help complete coverage cleanly "
        "instead of opening entirely new broad topics."
        if is_near_end
        else ""
    )
    user_instruction = f"""
Continue the interview for software project understanding.

Current stage: {current_stage}
Stage objective: {stage_instruction}
Next question number: Q{next_turn_no}
Closing guidance: {closing_instruction}

Conversation history:
{history_text}

Requirements:
1. Ask exactly one question only.
2. The question must be in English.
3. Label it as Q{next_turn_no}.
4. The question must follow naturally from the previous conversation.
5. Do not repeat earlier questions.
6. Prefer a specific follow-up question over a broad summary question.
7. Keep the question aligned with the current stage objective.
8. Do not answer the question.
9. Do not provide explanations, bullet points, or multiple alternatives.
""".strip()

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_instruction},
        ],
        temperature=0.4,
        stream=False,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty content.")
    print(f"[DEBUG] Generated next question raw output: {content!r}")
    cleaned = clean_generated_question(content, next_turn_no)
    print(f"[DEBUG] Cleaned next question: {cleaned!r}")

    return cleaned
