from app.core.config import settings
from app.core.llm_client import get_openai_client
from app.prompts import get_prompt_manager
from app.services.question_postprocessor import clean_generated_question
from app.services.stage_manager import get_stage_instruction
from app.services.usage_service import extract_usage_metrics


def generate_first_question(system_prompt: str) -> str:
    return generate_first_question_result(system_prompt)["question_text"]


def generate_first_question_result(system_prompt: str) -> dict:
    client = get_openai_client()
    prompt = get_prompt_manager().render(
        "first_question",
        {
            "system_prompt": system_prompt,
            "current_stage": "Panorama Mapping",
            "stage_objective": get_stage_instruction("Panorama Mapping"),
        },
    )
    user_instruction = prompt.messages[1]["content"]

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=prompt.messages,
        temperature=0.3,
        stream=False,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty content.")

    print(f"[DEBUG] Generated first question raw output: {content!r}")
    cleaned = clean_generated_question(content, 1)
    print(f"[DEBUG] Cleaned first question: {cleaned!r}")

    return {
        "question_text": cleaned,
        "usage_metrics": extract_usage_metrics(
            response,
            prompt_text="\n\n".join(message["content"] for message in prompt.messages),
            completion_text=cleaned,
        ),
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
    }


def generate_next_question_from_history(
    system_prompt: str,
    recent_context: str,
    retrieved_context: str,
    coverage_priorities: str,
    next_turn_no: int,
    current_stage: str,
) -> dict:
    client = get_openai_client()

    stage_instruction = get_stage_instruction(current_stage)
    is_near_end = next_turn_no >= settings.interview_min_turns
    closing_instruction = (
        "The interview is now in its closing phase. Prefer questions that help complete coverage cleanly "
        "instead of opening entirely new broad topics."
        if is_near_end
        else "The interview still has room to deepen partially explored branches."
    )
    prompt = get_prompt_manager().render(
        "next_question",
        {
            "system_prompt": system_prompt,
            "current_stage": current_stage,
            "stage_objective": stage_instruction,
            "next_turn_no": next_turn_no,
            "closing_guidance": closing_instruction,
            "recent_context": recent_context,
            "retrieved_context": retrieved_context,
            "coverage_priorities": coverage_priorities,
        },
    )

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=prompt.messages,
        temperature=0.4,
        stream=False,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty content.")
    print(f"[DEBUG] Generated next question raw output: {content!r}")
    cleaned = clean_generated_question(content, next_turn_no)
    print(f"[DEBUG] Cleaned next question: {cleaned!r}")

    return {
        "question_text": cleaned,
        "usage_metrics": extract_usage_metrics(
            response,
            prompt_text="\n\n".join(message["content"] for message in prompt.messages),
            completion_text=cleaned,
        ),
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
    }
