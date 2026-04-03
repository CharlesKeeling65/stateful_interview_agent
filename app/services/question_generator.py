import time

from app.core.config import settings
from app.core.llm_client import get_openai_client
from app.logging import emit_event, preview_payload
from app.prompts import get_prompt_manager
from app.services.question_postprocessor import clean_generated_question
from app.services.stage_manager import (
    ARCHITECTURE_STAGE,
    CODE_DETAIL_STAGE,
    PANORAMA_STAGE,
    USE_CASE_STAGE,
    WRAP_UP_STAGE,
    get_stage_instruction,
)
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
    prompt_text = "\n\n".join(message["content"] for message in prompt.messages)
    start_time = time.perf_counter()
    emit_event(
        "llm",
        "llm.call.start",
        "Starting first-question LLM call",
        operation="question_generation",
        status="started",
        input={
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "model": settings.openai_model,
            "messages": preview_payload(
                prompt.messages,
                artifact_category="llm",
                artifact_name="first-question-messages",
            ) if settings.log_llm_payloads else None,
        },
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=prompt.messages,
            temperature=0.3,
            stream=False,
        )
    except Exception as exc:
        emit_event(
            "llm",
            "llm.call.error",
            "First-question LLM call failed",
            level=40,
            operation="question_generation",
            status="error",
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            exc_info=exc,
        )
        raise

    content = response.choices[0].message.content
    if not content:
        error = ValueError("Model returned empty content.")
        emit_event(
            "llm",
            "llm.call.error",
            "First-question LLM call returned empty content",
            level=40,
            operation="question_generation",
            status="error",
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            exc_info=error,
        )
        raise error
    cleaned = clean_generated_question(content, 1)
    usage_metrics = extract_usage_metrics(
        response,
        prompt_text=prompt_text,
        completion_text=cleaned,
    )
    emit_event(
        "llm",
        "llm.call.complete",
        "Completed first-question LLM call",
        operation="question_generation",
        status="success",
        duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
        usage=usage_metrics,
        output={
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "raw_output": preview_payload(
                content,
                artifact_category="llm",
                artifact_name="first-question-raw",
            ) if settings.log_llm_payloads else None,
            "cleaned_output": preview_payload(
                cleaned,
                artifact_category="llm",
                artifact_name="first-question-cleaned",
            ),
            "validation_result": {"cleaned_prefix": cleaned.split(":")[0]},
        },
    )

    return {
        "question_text": cleaned,
        "usage_metrics": usage_metrics,
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
    planner_decision: dict | None = None,
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
    prompt_id = get_stage_prompt_id(current_stage)
    planner = planner_decision or default_planner_decision(current_stage)
    prompt = get_prompt_manager().render(
        prompt_id,
        {
            "system_prompt": system_prompt,
            "current_stage": current_stage,
            "stage_objective": stage_instruction,
            "next_turn_no": next_turn_no,
            "recent_context": recent_context,
            "retrieved_context": retrieved_context,
            "coverage_priorities": coverage_priorities,
            "question_intent": planner["question_intent"],
            "target_type": planner["target_type"],
            "target_label": planner["target_label"],
            "planner_reasoning": planner["reasoning"],
            "style_constraints": "; ".join(planner["constraints"]) + f"; Closing guidance: {closing_instruction}",
        },
    )
    prompt_text = "\n\n".join(message["content"] for message in prompt.messages)
    start_time = time.perf_counter()
    emit_event(
        "llm",
        "llm.call.start",
        "Starting next-question LLM call",
        operation="question_generation",
        stage=current_stage,
        turn_no=next_turn_no,
        status="started",
        input={
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "model": settings.openai_model,
            "messages": preview_payload(
                prompt.messages,
                artifact_category="llm",
                artifact_name=f"next-question-q{next_turn_no}-messages",
            ) if settings.log_llm_payloads else None,
        },
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=prompt.messages,
            temperature=0.4,
            stream=False,
        )
    except Exception as exc:
        emit_event(
            "llm",
            "llm.call.error",
            "Next-question LLM call failed",
            level=40,
            operation="question_generation",
            stage=current_stage,
            turn_no=next_turn_no,
            status="error",
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            exc_info=exc,
        )
        raise

    content = response.choices[0].message.content
    if not content:
        error = ValueError("Model returned empty content.")
        emit_event(
            "llm",
            "llm.call.error",
            "Next-question LLM call returned empty content",
            level=40,
            operation="question_generation",
            stage=current_stage,
            turn_no=next_turn_no,
            status="error",
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            exc_info=error,
        )
        raise error
    cleaned = clean_generated_question(content, next_turn_no)
    usage_metrics = extract_usage_metrics(
        response,
        prompt_text=prompt_text,
        completion_text=cleaned,
    )
    emit_event(
        "llm",
        "llm.call.complete",
        "Completed next-question LLM call",
        operation="question_generation",
        stage=current_stage,
        turn_no=next_turn_no,
        status="success",
        duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
        usage=usage_metrics,
        output={
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "raw_output": preview_payload(
                content,
                artifact_category="llm",
                artifact_name=f"next-question-q{next_turn_no}-raw",
            ) if settings.log_llm_payloads else None,
            "cleaned_output": preview_payload(
                cleaned,
                artifact_category="llm",
                artifact_name=f"next-question-q{next_turn_no}-cleaned",
            ),
            "validation_result": {"question_number": next_turn_no},
        },
    )

    return {
        "question_text": cleaned,
        "usage_metrics": usage_metrics,
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
    }


def get_stage_prompt_id(stage: str) -> str:
    mapping = {
        PANORAMA_STAGE: "next_question_panorama",
        ARCHITECTURE_STAGE: "next_question_architecture",
        CODE_DETAIL_STAGE: "next_question_code_detail",
        USE_CASE_STAGE: "next_question_use_cases",
        WRAP_UP_STAGE: "next_question_wrap_up",
    }
    return mapping.get(stage, "next_question_architecture")


def default_planner_decision(stage: str) -> dict:
    return {
        "question_intent": "stage_follow_up",
        "target_type": "framework_gap",
        "target_label": "the next uncovered target",
        "constraints": ["Stay aligned with the current stage"],
        "reasoning": f"Fallback planner decision for {stage}.",
    }
