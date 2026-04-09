import time

from app.core.config import settings
from app.core.llm_client import get_llm_provider
from app.logging import emit_event, preview_payload
from app.prompts import get_prompt_manager
from app.services.question_postprocessor import clean_generated_question
from app.services.run_trace_service import traced_run_step
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


def response_model_label() -> str:
    if settings.llm_provider == "anthropic":
        return settings.anthropic_model
    if settings.llm_provider == "opencode":
        return "opencode-http"
    return settings.openai_model


def generate_first_question_result(system_prompt: str, repository_context: str = "No repository source configured for this project.") -> dict:
    provider = get_llm_provider()
    prompt = get_prompt_manager().render(
        "first_question",
        {
            "system_prompt": system_prompt,
            "current_stage": "Panorama Mapping",
            "stage_objective": get_stage_instruction("Panorama Mapping"),
            "repo_grounding_context": repository_context,
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
            "model": response_model_label(),
            "messages": preview_payload(
                prompt.messages,
                artifact_category="llm",
                artifact_name="first-question-messages",
            ) if settings.log_llm_payloads else None,
        },
    )

    try:
        response = provider.generate_text(
            model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
            messages=prompt.messages,
            temperature=0.3,
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

    content = response.text
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
    repo_grounding_context: str = "No repository source configured for this project.",
    project_id: int | None = None,
    run_id: int | None = None,
) -> dict:
    provider = get_llm_provider()

    stage_instruction = get_stage_instruction(current_stage)
    is_near_end = next_turn_no >= max(1, settings.interview_max_turns - 1)
    closing_instruction = (
        "The interview is in its final scenario-focused phase. Do not ask a separate wrap-up or convergence question; "
        "use the remaining turns only to complete representative use-case coverage cleanly."
        if is_near_end
        else "The interview still has room to deepen partially explored branches."
    )
    planner = planner_decision or default_planner_decision(current_stage)
    prompt_id = get_prompt_id_for_plan(current_stage, planner)
    with traced_run_step(
        run_id=run_id,
        project_id=project_id or 0,
        turn_no=next_turn_no,
        step_key="render_prompt",
        description=f"Render prompt asset {prompt_id} for the next question.",
        next_step_hint="Call model",
    ) as render_step:
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
                "intent_mode": planner.get("intent_mode", "understand_current_code"),
                "target_type": planner["target_type"],
                "target_label": planner["target_label"],
                "planner_reasoning": planner["reasoning"],
                "human_review_context": format_human_review_context(planner.get("human_review_signal")),
                "repo_grounding_context": repo_grounding_context,
                "style_constraints": "; ".join(planner["constraints"]) + f"; Closing guidance: {closing_instruction}",
            },
        )
        if render_step:
            render_step.set_meta(prompt_id=prompt.prompt_id, prompt_version=prompt.version)
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
            "model": response_model_label(),
            "messages": preview_payload(
                prompt.messages,
                artifact_category="llm",
                artifact_name=f"next-question-q{next_turn_no}-messages",
            ) if settings.log_llm_payloads else None,
        },
    )

    try:
        with traced_run_step(
            run_id=run_id,
            project_id=project_id or 0,
            turn_no=next_turn_no,
            step_key="call_llm",
            description=f"Call {response_model_label()} to draft the next question.",
            next_step_hint="Validate question",
        ) as llm_step:
            response = provider.generate_text(
                model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
                messages=prompt.messages,
                temperature=0.4,
            )
            if llm_step:
                llm_step.set_meta(model=response.model, prompt_id=prompt.prompt_id)
            content = response.text
            if not content:
                raise ValueError("Model returned empty content.")
            cleaned = clean_generated_question(content, next_turn_no)
            usage_metrics = extract_usage_metrics(
                response,
                prompt_text=prompt_text,
                completion_text=cleaned,
            )
            if llm_step:
                llm_step.set_usage(usage_metrics)
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


def get_prompt_id_for_plan(stage: str, planner: dict | None) -> str:
    if planner and planner.get("prompt_id"):
        return planner["prompt_id"]
    return get_stage_prompt_id(stage)


def default_planner_decision(stage: str) -> dict:
    return {
        "question_intent": "stage_follow_up",
        "intent_mode": "understand_current_code",
        "target_type": "framework_gap",
        "target_label": "the next uncovered target",
        "constraints": ["Stay aligned with the current stage"],
        "reasoning": f"Fallback planner decision for {stage}.",
    }


def format_human_review_context(human_review_signal: dict | None) -> str:
    if not human_review_signal:
        return "No explicit human review signal was provided for this turn."

    parts = [
        f"Verdict: {human_review_signal.get('verdict', 'unknown')}",
        f"Direction: {human_review_signal.get('direction', 'continue')}",
    ]
    if human_review_signal.get("preferred_next_focus"):
        parts.append(f"Preferred next focus: {human_review_signal['preferred_next_focus']}")
    if human_review_signal.get("note"):
        parts.append(f"Human note: {human_review_signal['note']}")
    if human_review_signal.get("phase"):
        parts.append(f"Corrected stage: {human_review_signal['phase']}")
    if human_review_signal.get("phase_ready") is not None:
        parts.append(f"Phase ready: {human_review_signal['phase_ready']}")
    return " | ".join(parts)
