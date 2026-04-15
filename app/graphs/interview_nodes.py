import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.logging import bind_log_context, emit_event, preview_payload
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.context_engineering import build_generation_context
from app.services.coverage_service import rebuild_coverage_state, save_coverage_state
from app.services.human_gate_service import (
    HumanGate,
    deserialize_gate,
    gate_resolution_to_human_review_signal,
    resolve_gate,
    serialize_gate,
)
from app.services.interview_lifecycle import can_continue_interview, is_minimum_goal_reached
from app.services.mode_service import AgentMode
from app.services.question_planner import plan_next_question
from app.services.question_generator import generate_next_question_from_history
from app.services.question_reviewer import review_question_plan, review_question_text
from app.services.question_version_service import append_question_version
from app.services.question_validator import (
    validate_question_against_repository,
    validate_question_for_stage,
)
from app.services.repetition_guard import build_question_signature, is_question_too_similar
from app.services.repo_grounding_service import build_repo_grounding_context
from app.services.rubric_task_service import (
    deserialize_task_board,
    serialize_task_board,
    sync_task_board,
)
from app.services.run_trace_service import traced_run_step
from app.services.scenario_service import check_scenario_completion
from app.services.summarization_service import ensure_turn_summaries
from app.services.stage_manager import decide_next_stage
from app.services.transcript_event_service import (
    add_event_to_log,
    deserialize_event_log,
    emit_ai_question_event,
    emit_drift_repair_event,
    emit_human_answer_event,
    emit_human_gate_event,
    emit_human_review_event,
    serialize_event_log,
)
from app.services.transcript_service import build_compact_interview_context
from app.services.usage_service import create_usage_record


def build_question_plan_payload(state: dict) -> dict:
    return {
        "mode": state.get("agent_mode") or state.get("planner_decision", {}).get("mode"),
        "phase": state.get("planner_decision", {}).get("phase"),
        "question_intent": state.get("planner_decision", {}).get("question_intent"),
        "intent_mode": state.get("planner_decision", {}).get("intent_mode"),
        "target_branch_id": state.get("planner_decision", {}).get("target_branch_id"),
        "target_type": state.get("planner_decision", {}).get("target_type"),
        "target_label": state.get("planner_decision", {}).get("target_label"),
        "selected_framework_gap": state.get("planner_decision", {}).get("selected_framework_gap"),
        "selected_branch_ids": state.get("planner_decision", {}).get("selected_branch_ids", []),
        "selected_turn_ids": state.get("planner_decision", {}).get("selected_turn_ids", []),
        "human_review_applied": state.get("planner_decision", {}).get("human_review_applied"),
        "drift_detected": state.get("planner_decision", {}).get("drift_detected"),
        "why_this_question": state.get("planner_decision", {}).get("why_this_question"),
        "rubric_task_id": state.get("planner_decision", {}).get("rubric_task_id"),
        "rubric_task_label": state.get("planner_decision", {}).get("rubric_task_label"),
        "confidence_score": state.get("review_result", {}).get("confidence_score")
        or state.get("planner_decision", {}).get("confidence"),
        "human_gate_triggered": state.get("review_result", {}).get("human_gate_triggered"),
        "reviewer_reason": state.get("review_result", {}).get("review_reason"),
        "reviewer_modifications": state.get("review_result", {}).get("suggested_modifications", []),
        "scenario_complete": state.get("scenario_status", {}).get("is_complete"),
        "scenario_missing_aspects": state.get("scenario_status", {}).get("missing_aspects", []),
        "repo_queries": state.get("repo_grounding_meta", {}).get("queries", []),
        "repo_selected_paths": state.get("repo_grounding_meta", {}).get("selected_paths", []),
        "repo_selected_symbols": state.get("repo_grounding_meta", {}).get("selected_symbols", []),
        "repo_commit_sha": state.get("repo_grounding_meta", {}).get("commit_sha"),
        "repo_tool_calls": state.get("repo_grounding_meta", {}).get("tool_calls", []),
    }


def build_question_plan_json(state: dict) -> str:
    return json.dumps(
        build_question_plan_payload(state),
        ensure_ascii=True,
        sort_keys=True,
    )


def _merge_human_review_signal(*signals: dict | None) -> dict | None:
    merged: dict = {}
    for signal in signals:
        if not signal:
            continue
        for key, value in signal.items():
            if value is not None:
                merged[key] = value
    return merged or None


def generate_question_for_state(
    *,
    current_stage: str,
    db: Session,
    human_review_signal: dict | None,
    latest_answer_override: str | None,
    project: ProjectSession,
    run_id: int | None,
    turn_no: int,
    turns: list[InterviewTurn],
    planner_decision_override: dict | None = None,
    review_result: dict | None = None,
    force_llm_generation: bool = False,
) -> dict:
    coverage_state = rebuild_coverage_state(turns, project)
    task_board = sync_task_board(
        deserialize_task_board(project.rubric_task_board),
        coverage_state=coverage_state,
        current_stage=current_stage,
    )
    scenario_status = check_scenario_completion(coverage_state, turns)
    context_payload = build_generation_context(
        turns=turns,
        current_stage=current_stage,
        next_turn_no=turn_no,
        coverage_state=coverage_state,
        project=project,
        project_id=project.id,
        latest_answer_override=latest_answer_override,
    )
    planner_decision = planner_decision_override or plan_next_question(
        turns=turns,
        current_stage=current_stage,
        next_turn_no=turn_no,
        coverage_state=coverage_state,
        human_review_signal=human_review_signal,
        agent_mode=project.agent_mode or AgentMode.UNDERSTAND_CURRENT_CODE.value,
        task_board_json=serialize_task_board(task_board),
    )
    repo_grounding_payload = build_repo_grounding_context(
        project=project,
        turns=turns,
        current_stage=current_stage,
        next_turn_no=turn_no,
        planner_decision=planner_decision,
        latest_answer_override=latest_answer_override,
        project_id=project.id,
        run_id=run_id,
    )
    context_payload["repo_grounding_context"] = repo_grounding_payload["repo_grounding_context"]
    context_payload["repo_grounding_meta"] = repo_grounding_payload["repo_grounding_meta"]

    question_queue = coverage_state.get("question_queue", {"status": "empty", "items": []})
    should_use_queue = (
        current_stage == "Code Detail Completion"
        and question_queue.get("status") == "active"
        and question_queue.get("items")
        and not human_review_signal
        and not force_llm_generation
    )

    if should_use_queue:
        next_item = question_queue["items"].pop(0)
        from app.services.question_queue_service import renumber_sub_question_queue
        question_queue["items"] = renumber_sub_question_queue(question_queue["items"], turn_no + 1)
        if not question_queue["items"]:
            question_queue["status"] = "empty"

        planner_decision["question_intent"] = next_item.get("intent", planner_decision.get("question_intent"))
        planner_decision["target_branch_id"] = next_item.get("target_branch_id", planner_decision.get("target_branch_id"))
        planner_decision["target_type"] = next_item.get("target_type", planner_decision.get("target_type"))
        planner_decision["target_label"] = next_item.get("target_label", planner_decision.get("target_label"))
        
        planner_decision["generated_queue"] = question_queue
        next_question = next_item.get("question_text", "")
        question_usage_metrics = []
        next_question_result = {"prompt_id": "queue_pop", "prompt_version": "1.0"}

    else:
        planner_decision["generated_queue"] = {"status": "empty", "items": []}
        next_question_result = generate_next_question_from_history(
            system_prompt=project.system_prompt,
            recent_context=context_payload["recent_context"],
            retrieved_context=context_payload["retrieved_context"],
            repo_grounding_context=context_payload["repo_grounding_context"],
            coverage_priorities=context_payload["coverage_priorities"],
            next_turn_no=turn_no,
            current_stage=current_stage,
            planner_decision=planner_decision,
            project_id=project.id,
            run_id=run_id,
        )
        next_question = next_question_result["question_text"]
        question_usage_metrics = [next_question_result["usage_metrics"]]

        from app.services.question_queue_service import detect_compound_question_candidate, decompose_code_detail_question_group
        if current_stage == "Code Detail Completion" and detect_compound_question_candidate(next_question):
            new_items = decompose_code_detail_question_group(
                next_question,
                base_turn_no=turn_no,
                intent=planner_decision.get("question_intent", "code_detail_deep_dive"),
                target_branch_id=planner_decision.get("target_branch_id"),
                target_type=planner_decision.get("target_type"),
                target_label=planner_decision.get("target_label"),
            )
            if new_items:
                next_question = new_items[0].question_text
                question_queue["status"] = "active"
                question_queue["parent_turn_no"] = turn_no
                question_queue["parent_group_intent"] = planner_decision.get("question_intent")
                question_queue["items"] = [{"question_text": i.question_text, "turn_offset": i.turn_offset, "intent": i.intent, "target_branch_id": i.target_branch_id, "target_type": i.target_type, "target_label": i.target_label} for i in new_items[1:]]
                planner_decision["generated_queue"] = question_queue

    old_questions = [turn.question_text for turn in turns[:-1]]
    recent_question_signatures = coverage_state.get("question_history", [])[-8:]

    if is_question_too_similar(next_question, old_questions):
        blocked_branch_ids = {planner_decision.get("target_branch_id")} - {None}
        blocked_target_signatures = {
            build_question_signature(
                stage=current_stage,
                intent=planner_decision.get("question_intent"),
                branch_id=planner_decision.get("target_branch_id"),
                target_type=planner_decision.get("target_type"),
                target_label=planner_decision.get("target_label"),
            )
        }
        context_payload = build_generation_context(
            turns=turns,
            current_stage=current_stage,
            next_turn_no=turn_no,
            coverage_state=coverage_state,
            project_id=project.id,
            latest_answer_override=latest_answer_override,
            excluded_branch_ids=blocked_branch_ids,
        )
        planner_decision = plan_next_question(
            turns=turns,
            current_stage=current_stage,
            next_turn_no=turn_no,
            coverage_state=coverage_state,
            human_review_signal=human_review_signal,
            excluded_branch_ids=blocked_branch_ids,
            excluded_target_signatures=blocked_target_signatures,
        )
        repo_grounding_payload = build_repo_grounding_context(
            project=project,
            turns=turns,
            current_stage=current_stage,
            next_turn_no=turn_no,
            planner_decision=planner_decision,
            latest_answer_override=latest_answer_override,
            project_id=project.id,
            run_id=run_id,
        )
        context_payload["repo_grounding_context"] = repo_grounding_payload["repo_grounding_context"]
        context_payload["repo_grounding_meta"] = repo_grounding_payload["repo_grounding_meta"]
        retried_question_result = generate_next_question_from_history(
            system_prompt=project.system_prompt,
            recent_context=context_payload["recent_context"],
            retrieved_context=context_payload["retrieved_context"],
            coverage_priorities=context_payload["coverage_priorities"],
            next_turn_no=turn_no,
            current_stage=current_stage,
            planner_decision=planner_decision,
            repo_grounding_context=context_payload["repo_grounding_context"],
            project_id=project.id,
            run_id=run_id,
        )
        next_question = retried_question_result["question_text"]
        question_usage_metrics.append(retried_question_result["usage_metrics"])

    validation = validate_question_for_stage(
        text=next_question,
        expected_turn_no=turn_no,
        current_stage=current_stage,
        intent_mode=planner_decision.get("intent_mode", "understand_current_code"),
        recent_question_signatures=recent_question_signatures,
        branch_id=planner_decision.get("target_branch_id"),
        agent_mode=project.agent_mode,
    )
    repo_validation = validate_question_against_repository(
        text=next_question,
        current_stage=current_stage,
        repo_grounding_meta=context_payload.get("repo_grounding_meta"),
        repo_manifest=project.repo_manifest_data,
    )
    if not repo_validation["is_valid"]:
        validation["is_valid"] = False
        validation["reasons"].extend(repo_validation["reasons"])

    if not validation["is_valid"]:
        retry_prompt = (
            project.system_prompt
            + "\n\nThe previous draft did not satisfy the stage-specific validator. "
            + "Fix these issues and regenerate one better question: "
            + "; ".join(validation["reasons"])
        )
        retried_question_result = generate_next_question_from_history(
            system_prompt=retry_prompt,
            recent_context=context_payload["recent_context"],
            retrieved_context=context_payload["retrieved_context"],
            coverage_priorities=context_payload["coverage_priorities"],
            next_turn_no=turn_no,
            current_stage=current_stage,
            planner_decision=planner_decision,
            repo_grounding_context=context_payload["repo_grounding_context"],
            project_id=project.id,
            run_id=run_id,
        )
        next_question = retried_question_result["question_text"]
        question_usage_metrics.append(retried_question_result["usage_metrics"])
        validation = validate_question_for_stage(
            text=next_question,
            expected_turn_no=turn_no,
            current_stage=current_stage,
            intent_mode=planner_decision.get("intent_mode", "understand_current_code"),
            recent_question_signatures=recent_question_signatures,
            branch_id=planner_decision.get("target_branch_id"),
            agent_mode=project.agent_mode,
        )
        repo_validation = validate_question_against_repository(
            text=next_question,
            current_stage=current_stage,
            repo_grounding_meta=context_payload.get("repo_grounding_meta"),
            repo_manifest=project.repo_manifest_data,
        )
        if not repo_validation["is_valid"]:
            validation["is_valid"] = False
            validation["reasons"].extend(repo_validation["reasons"])
        if not validation["is_valid"]:
            raise ValueError(
                "Generated question failed stage-specific validation: "
                + "; ".join(validation["reasons"])
            )

    text_review = review_question_text(
        next_question,
        project.agent_mode,
        current_stage=current_stage,
    )
    if not text_review["is_valid"]:
        raise ValueError(
            "Generated question failed reviewer text checks: "
            + "; ".join(text_review["reasons"])
        )

    return {
        "generated_question": next_question,
        "coverage_state": coverage_state,
        "retrieved_context": context_payload["retrieved_context"],
        "coverage_priorities": context_payload["coverage_priorities"],
        "repo_grounding_context": context_payload["repo_grounding_context"],
        "repo_grounding_meta": context_payload["repo_grounding_meta"],
        "selected_turn_ids": context_payload["selected_turn_ids"],
        "selected_branch_ids": context_payload["selected_branch_ids"],
        "planner_decision": planner_decision,
        "validation_result": validation,
        "review_result": review_result or {},
        "scenario_status": scenario_status,
        "prompt_metadata": {
            "prompt_id": next_question_result.get("prompt_id"),
            "prompt_version": next_question_result.get("prompt_version"),
        },
        "question_usage_metrics": question_usage_metrics,
    }


def draft_question_from_answered_history(
    *,
    db: Session,
    project: ProjectSession,
    turns: list[InterviewTurn],
    latest_answer_text: str,
    next_turn_no: int,
    next_stage: str,
    human_review_signal: dict | None,
    run_id: int | None,
    include_latest_answer_in_coverage: bool = False,
    planner_decision_override: dict | None = None,
    review_result: dict | None = None,
    force_llm_generation: bool = False,
) -> dict:
    answered_turns = [turn for turn in turns if turn.answer_text]
    with traced_run_step(
        run_id=run_id,
        project_id=project.id,
        turn_no=next_turn_no,
        step_key="refresh_summaries",
        description="Ensure older answered turns have compact summaries available.",
        next_step_hint="Build compact context",
    ) as summary_step:
        summarized_count = ensure_turn_summaries(
            db=db,
            project_id=project.id,
            system_prompt=project.system_prompt,
            turns_to_summarize=answered_turns,
        )
        if summarized_count:
            db.commit()
            turns = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.project_id == project.id)
                .filter(InterviewTurn.turn_no <= turns[-1].turn_no)
                .order_by(InterviewTurn.turn_no.asc())
                .all()
            )
            answered_turns = [turn for turn in turns if turn.answer_text]
        if summary_step:
            summary_step.set_meta(summarized_count=summarized_count)

    with traced_run_step(
        run_id=run_id,
        project_id=project.id,
        turn_no=next_turn_no,
        step_key="build_compact_context",
        description="Build compact recent-history context for the next question.",
        next_step_hint="Refresh coverage",
    ):
        history_text = build_compact_interview_context(
            turns,
            latest_answer_override=latest_answer_text,
        )
    emit_event(
        "workflow",
        "context.compaction.complete",
        "Built compact interview history",
        operation="build_compact_interview_context",
        project_id=project.id,
        turn_no=next_turn_no,
        stage=next_stage,
        output=preview_payload(
            history_text,
            artifact_category="workflow",
            artifact_name=f"project-{project.id}-compact-history",
        ),
    )

    with traced_run_step(
        run_id=run_id,
        project_id=project.id,
        turn_no=next_turn_no,
        step_key="refresh_coverage",
        description="Refresh framework coverage and branch state from answered turns.",
        next_step_hint="Retrieve relevant context",
    ) as coverage_step:
        original_answer_text = None
        if include_latest_answer_in_coverage and turns and not turns[-1].answer_text:
            original_answer_text = turns[-1].answer_text
            turns[-1].answer_text = latest_answer_text
        coverage_state = rebuild_coverage_state(turns, project)
        if include_latest_answer_in_coverage and turns and not original_answer_text:
            turns[-1].answer_text = original_answer_text
        if coverage_step:
            coverage_step.set_meta(branch_count=coverage_state.get("branch_count", 0))
    emit_event(
        "workflow",
        "coverage.refresh.complete",
        "Rebuilt coverage state before next question generation",
        operation="rebuild_coverage_state",
        project_id=project.id,
        turn_no=next_turn_no,
        stage=next_stage,
        output={
            "branch_count": coverage_state.get("branch_count", 0),
            "updated_through_turn_no": coverage_state.get("updated_through_turn_no", 0),
        },
    )

    generation_payload = generate_question_for_state(
        current_stage=next_stage,
        db=db,
        human_review_signal=human_review_signal,
        latest_answer_override=latest_answer_text,
        project=project,
        run_id=run_id,
        turn_no=next_turn_no,
        turns=turns,
        planner_decision_override=planner_decision_override,
        review_result=review_result,
        force_llm_generation=force_llm_generation,
    )

    return {
        "generated_question": generation_payload["generated_question"],
        "history_text": history_text,
        "coverage_state": coverage_state,
        "retrieved_context": generation_payload["retrieved_context"],
        "coverage_priorities": generation_payload["coverage_priorities"],
        "selected_turn_ids": generation_payload["selected_turn_ids"],
        "selected_branch_ids": generation_payload["selected_branch_ids"],
        "planner_decision": generation_payload["planner_decision"],
        "validation_result": generation_payload["validation_result"],
        "review_result": generation_payload["review_result"],
        "scenario_status": generation_payload["scenario_status"],
        "prompt_metadata": generation_payload["prompt_metadata"],
        "question_usage_metrics": generation_payload["question_usage_metrics"],
    }


def load_project_context(state, db: Session):
    bind_log_context(project_id=state.get("project_id"))
    with traced_run_step(
        run_id=state.get("run_id"),
        project_id=state["project_id"],
        turn_no=None,
        step_key="load_project_context",
        description="Load the active project, latest turn, and compact history baseline.",
        next_step_hint="Refresh summaries",
    ):
        project = (
            db.query(ProjectSession)
            .filter(ProjectSession.id == state["project_id"])
            .first()
        )
        if not project:
            raise ValueError("Project not found")

        latest_turn = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.project_id == state["project_id"])
            .order_by(InterviewTurn.turn_no.desc())
            .first()
        )
        if not latest_turn:
            raise ValueError("Project interview has not started")

        if project.status == "finished":
            raise ValueError("Project interview is already finished")

        if latest_turn.answer_text is None and not state.get("answer_text"):
            raise ValueError("Latest turn does not have a saved answer yet")

        turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.project_id == state["project_id"])
            .order_by(InterviewTurn.turn_no.asc())
            .all()
        )
        task_board = sync_task_board(
            deserialize_task_board(project.rubric_task_board),
            coverage_state=project.coverage_state_data,
            current_stage=project.current_stage,
        )
        pending_gate = deserialize_gate(project.pending_gate_json)
        latest_event_log = deserialize_event_log(latest_turn.event_log_json)
        human_gate_resolution = state.get("human_gate_resolution")
        human_review_signal = _merge_human_review_signal(
            state.get("human_review_signal"),
            gate_resolution_to_human_review_signal(
                pending_gate,
                human_gate_resolution.get("action"),
                preferred_next_focus=human_gate_resolution.get("preferred_next_focus"),
                note=human_gate_resolution.get("note"),
                phase_ready=human_gate_resolution.get("phase_ready"),
            )
            if pending_gate and human_gate_resolution
            else None,
        )

        return {
            "project_status": project.status,
            "agent_mode": project.agent_mode or AgentMode.UNDERSTAND_CURRENT_CODE.value,
            "current_turn_no": latest_turn.turn_no,
            "current_stage": latest_turn.stage,
            "history_text": build_compact_interview_context(turns),
            "coverage_state": project.coverage_state_data,
            "task_board": task_board.model_dump(mode="json"),
            "pending_gate": pending_gate.model_dump(mode="json") if pending_gate else None,
            "scenario_status": check_scenario_completion(project.coverage_state_data, turns),
            "event_log": latest_event_log,
            "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
            "pending_turn_id": latest_turn.id,
            "answer_text": latest_turn.answer_text,
            "human_review_signal": human_review_signal,
            "human_gate_resolution": human_gate_resolution,
            "next_turn_no": None,
            "next_stage": None,
            "generated_question": None,
            "retrieved_context": None,
            "coverage_priorities": None,
            "selected_turn_ids": [],
            "selected_branch_ids": [],
            "stage_decision": {},
            "planner_decision": {},
            "review_result": {},
            "validation_result": {},
            "prompt_metadata": {},
            "question_usage_metrics": [],
            "message": None,
            "interview_finished": None,
        }


def decide_progress(state):
    bind_log_context(project_id=state.get("project_id"))
    current_turn_no = state["current_turn_no"]

    if not can_continue_interview(current_turn_no):
        return {
            "interview_finished": True,
            "minimum_goal_reached": is_minimum_goal_reached(current_turn_no),
            "message": "Interview finished. Maximum turn limit reached.",
        }

    next_turn_no = current_turn_no + 1
    stage_decision = decide_next_stage(
        next_turn_no=next_turn_no,
        coverage_state=state.get("coverage_state", {}),
        current_stage=state.get("current_stage", ""),
        max_turns=settings.interview_max_turns,
        human_review_signal=state.get("human_review_signal"),
    )
    next_stage = stage_decision["next_stage"]

    return {
        "interview_finished": False,
        "next_turn_no": next_turn_no,
        "next_stage": next_stage,
        "stage_decision": stage_decision,
    }


def plan_question(state, db: Session):
    bind_log_context(project_id=state.get("project_id"))
    project = (
        db.query(ProjectSession)
        .filter(ProjectSession.id == state["project_id"])
        .first()
    )
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == state["project_id"])
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    with traced_run_step(
        run_id=state.get("run_id"),
        project_id=state["project_id"],
        turn_no=state["next_turn_no"],
        step_key="plan_question",
        description="Plan the next question from mode, rubric, stage, and human input.",
        next_step_hint="Review question plan",
    ):
        planner_decision = plan_next_question(
            turns=turns,
            current_stage=state["next_stage"],
            next_turn_no=state["next_turn_no"],
            coverage_state=state.get("coverage_state", {}),
            human_review_signal=state.get("human_review_signal"),
            agent_mode=project.agent_mode or AgentMode.UNDERSTAND_CURRENT_CODE.value,
            task_board_json=serialize_task_board(deserialize_task_board(project.rubric_task_board)),
        )
    return {"planner_decision": planner_decision}


def review_question_plan_node(state, db: Session):
    bind_log_context(project_id=state.get("project_id"))
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == state["project_id"])
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    coverage_state = state.get("coverage_state", {})
    task_board = deserialize_task_board(json.dumps(state.get("task_board", {})))
    drift_detection_result = None
    if state.get("planner_decision", {}).get("drift_detected"):
        drift_detection_result = {
            "detected": True,
            "reason": state["planner_decision"].get("reasoning"),
            "branch_id": state["planner_decision"].get("target_branch_id"),
        }
    with traced_run_step(
        run_id=state.get("run_id"),
        project_id=state["project_id"],
        turn_no=state["next_turn_no"],
        step_key="review_question_plan",
        description="Review the planned question for mode compliance, priority, drift, and human gates.",
        next_step_hint="Draft question",
    ):
        review_result = review_question_plan(
            planner_decision=state.get("planner_decision", {}),
            mode=state.get("agent_mode", AgentMode.UNDERSTAND_CURRENT_CODE.value),
            task_board=task_board,
            coverage_state=coverage_state,
            current_stage=state.get("next_stage"),
            drift_detection_result=drift_detection_result,
        ).model_dump(mode="json")

    planner_decision = dict(state.get("planner_decision", {}))
    if review_result.get("alternative_plan"):
        planner_decision.update(review_result["alternative_plan"])
        planner_decision["why_this_question"] = (
            planner_decision.get("why_this_question")
            or review_result.get("review_reason")
            or planner_decision.get("reasoning")
        )
    pending_gate = None
    message = None
    if review_result.get("human_gate_triggered") and review_result.get("human_gate"):
        pending_gate = review_result["human_gate"]
        message = review_result.get("review_reason") or "Human decision required before the next question."

    return {
        "planner_decision": planner_decision,
        "review_result": review_result,
        "pending_gate": pending_gate,
        "message": message,
    }


def draft_next_question(state, db: Session):
    bind_log_context(project_id=state.get("project_id"))
    project = (
        db.query(ProjectSession)
        .filter(ProjectSession.id == state["project_id"])
        .first()
    )
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == state["project_id"])
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )

    generation_payload = draft_question_from_answered_history(
        db=db,
        project=project,
        turns=turns,
        latest_answer_text=state["answer_text"],
        next_turn_no=state["next_turn_no"],
        next_stage=state["next_stage"],
        human_review_signal=state.get("human_review_signal"),
        run_id=state.get("run_id"),
        include_latest_answer_in_coverage=True,
        planner_decision_override=state.get("planner_decision"),
        review_result=state.get("review_result"),
    )

    return {
        "generated_question": generation_payload["generated_question"],
        "history_text": generation_payload["history_text"],
        "coverage_state": generation_payload["coverage_state"],
        "retrieved_context": generation_payload["retrieved_context"],
        "coverage_priorities": generation_payload["coverage_priorities"],
        "selected_turn_ids": generation_payload["selected_turn_ids"],
        "selected_branch_ids": generation_payload["selected_branch_ids"],
        "planner_decision": generation_payload["planner_decision"],
        "validation_result": generation_payload["validation_result"],
        "review_result": generation_payload["review_result"],
        "scenario_status": generation_payload["scenario_status"],
        "prompt_metadata": generation_payload["prompt_metadata"],
        "question_usage_metrics": generation_payload["question_usage_metrics"],
        "pending_gate": None,
    }

def persist_next_step(state, db: Session):
    bind_log_context(project_id=state.get("project_id"))
    with traced_run_step(
        run_id=state.get("run_id"),
        project_id=state["project_id"],
        turn_no=state.get("next_turn_no"),
        step_key="persist_result",
        description="Persist the answered turn, generated question, and refreshed project state.",
        next_step_hint=None,
    ):
        project = (
            db.query(ProjectSession)
            .filter(ProjectSession.id == state["project_id"])
            .first()
        )

        pending_turn = (
            db.query(InterviewTurn)
            .filter(
                InterviewTurn.project_id == state["project_id"],
                InterviewTurn.id == state["pending_turn_id"],
            )
            .first()
        )
        if not pending_turn:
            raise ValueError("Pending turn no longer exists")
        existing_next_turn = (
            db.query(InterviewTurn)
            .filter(
                InterviewTurn.project_id == state["project_id"],
                InterviewTurn.turn_no == state.get("next_turn_no"),
            )
            .first()
        )
        if existing_next_turn is not None:
            raise ValueError("Next turn was already generated for this pending turn.")
        if not pending_turn.answer_text:
            pending_turn.answer_text = state["answer_text"]
        current_event_log = deserialize_event_log(pending_turn.event_log_json)
        answer_event = emit_human_answer_event(
            turn_no=pending_turn.turn_no,
            answer_text=state["answer_text"],
            answer_summary=pending_turn.answer_summary,
            project_id=state["project_id"],
        )
        current_event_log = add_event_to_log(current_event_log, answer_event)
        if state.get("human_review_signal"):
            pending_turn.human_review_json = json.dumps(
                state["human_review_signal"],
                ensure_ascii=True,
                sort_keys=True,
            )
            review_event = emit_human_review_event(
                turn_no=pending_turn.turn_no,
                verdict=state["human_review_signal"].get("verdict"),
                direction=state["human_review_signal"].get("direction"),
                preferred_next_focus=state["human_review_signal"].get("preferred_next_focus"),
                note=state["human_review_signal"].get("note"),
                project_id=state["project_id"],
            )
            current_event_log = add_event_to_log(current_event_log, review_event)
        all_turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.project_id == state["project_id"])
            .order_by(InterviewTurn.turn_no.asc())
            .all()
        )
        refreshed_coverage_state = rebuild_coverage_state(all_turns, project)
        save_coverage_state(project, refreshed_coverage_state)
        task_board = sync_task_board(
            deserialize_task_board(project.rubric_task_board),
            coverage_state=refreshed_coverage_state,
            current_stage=state.get("next_stage") or state.get("current_stage") or project.current_stage,
        )
        project.rubric_task_board = serialize_task_board(task_board)
        emit_event(
            "persistence",
            "coverage.persist.complete",
            "Persisted refreshed coverage state",
            operation="save_coverage_state",
            project_id=project.id,
            turn_no=pending_turn.turn_no,
            stage=pending_turn.stage,
            output={
                "branch_count": refreshed_coverage_state.get("branch_count", 0),
                "updated_through_turn_no": refreshed_coverage_state.get("updated_through_turn_no", 0),
            },
        )

        if state.get("pending_gate"):
            gate = HumanGate.model_validate(state["pending_gate"])
            project.pending_gate_json = serialize_gate(gate)
            gate_event = emit_human_gate_event(
                gate_type=gate.gate_type.value,
                reason=gate.reason,
                resolution=None,
                turn_no=pending_turn.turn_no,
                project_id=state["project_id"],
            )
            current_event_log = add_event_to_log(current_event_log, gate_event)
            pending_turn.event_log_json = serialize_event_log(current_event_log)
            db.commit()
            db.refresh(project)
            db.refresh(pending_turn)
            return {
                "message": state.get("message") or "Human input is required before the next question can be generated.",
                "minimum_goal_reached": is_minimum_goal_reached(pending_turn.turn_no),
                "pending_gate_active": True,
            }

        if state.get("interview_finished"):
            project.status = "finished"
            project.pending_gate_json = "null"
            pending_turn.event_log_json = serialize_event_log(current_event_log)
            db.commit()
            db.refresh(project)
            db.refresh(pending_turn)
            emit_event(
                "persistence",
                "workflow.persist.complete",
                "Persisted final answered turn and finished project",
                operation="persist_next_step",
                project_id=project.id,
                turn_no=pending_turn.turn_no,
                stage=pending_turn.stage,
                status="success",
            )
            return {
                "message": "Interview finished. Maximum turn limit reached.",
                "minimum_goal_reached": is_minimum_goal_reached(pending_turn.turn_no),
            }

        current_max_turn_no = max((turn.turn_no for turn in all_turns), default=0)
        safe_next_turn_no = max(state["next_turn_no"], current_max_turn_no + 1)
        existing_pending_gate = deserialize_gate(project.pending_gate_json)
        next_turn = InterviewTurn(
            project_id=project.id,
            turn_no=safe_next_turn_no,
            stage=state["next_stage"],
            question_text=state["generated_question"],
            question_plan_json=build_question_plan_json(state),
            answer_text=None,
        )
        db.add(next_turn)
        db.flush()

        for usage_metrics in state.get("question_usage_metrics", []):
            db.add(
                create_usage_record(
                    project_id=project.id,
                    turn_id=next_turn.id,
                    operation_type="question_generation",
                    usage_metrics=usage_metrics,
                )
            )
        append_question_version(
            db=db,
            turn=next_turn,
            generation_kind="initial",
            human_review_signal=None,
            question_plan_json=next_turn.question_plan_json,
            question_text=next_turn.question_text,
            usage_metrics_list=state.get("question_usage_metrics", []),
        )

        project.turn_count = next_turn.turn_no
        project.current_stage = state["next_stage"]
        project.agent_mode = state.get("agent_mode", project.agent_mode)
        project.pending_gate_json = "null"
        refreshed_coverage_state = rebuild_coverage_state([*all_turns, next_turn], project)
        save_coverage_state(project, refreshed_coverage_state)
        project.rubric_task_board = serialize_task_board(
            sync_task_board(
                deserialize_task_board(project.rubric_task_board),
                coverage_state=refreshed_coverage_state,
                current_stage=state["next_stage"],
            )
        )

        if state.get("review_result", {}).get("drift_detected"):
            drift_event = emit_drift_repair_event(
                drift_reason=state["review_result"].get("review_reason") or state["planner_decision"].get("reasoning", ""),
                repair_action=state["planner_decision"].get("question_intent", "drift_repair"),
                turn_no=pending_turn.turn_no,
                project_id=state["project_id"],
            )
            current_event_log = add_event_to_log(current_event_log, drift_event)

        if state.get("human_gate_resolution"):
            if existing_pending_gate:
                resolved_gate = resolve_gate(
                    existing_pending_gate, state["human_gate_resolution"].get("action")
                )
                gate_event = emit_human_gate_event(
                    gate_type=resolved_gate.gate_type.value,
                    reason=resolved_gate.reason,
                    resolution=resolved_gate.resolution,
                    turn_no=pending_turn.turn_no,
                    project_id=state["project_id"],
                )
                current_event_log = add_event_to_log(current_event_log, gate_event)

        pending_turn.event_log_json = serialize_event_log(current_event_log)
        next_event_log = deserialize_event_log(next_turn.event_log_json)
        question_event = emit_ai_question_event(
            turn_no=next_turn.turn_no,
            question_text=next_turn.question_text,
            question_plan=next_turn.question_plan or {},
            mode=project.agent_mode,
            phase=next_turn.stage,
            project_id=state["project_id"],
        )
        next_turn.event_log_json = serialize_event_log(add_event_to_log(next_event_log, question_event))

        db.commit()
        db.refresh(project)
        db.refresh(pending_turn)
        db.refresh(next_turn)
        emit_event(
            "persistence",
            "workflow.persist.complete",
            "Persisted answered turn and next question",
            operation="persist_next_step",
            project_id=project.id,
            turn_no=next_turn.turn_no,
            stage=next_turn.stage,
            status="success",
            output={
                "latest_answer_turn": pending_turn.turn_no,
                "next_turn_id": next_turn.id,
                "selected_branch_ids": state.get("selected_branch_ids", []),
            },
        )

        return {
            "message": "Answer submitted and next question generated successfully.",
            "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
        }
