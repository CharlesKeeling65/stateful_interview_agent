import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.logging import bind_log_context, emit_event, preview_payload
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.context_engineering import build_generation_context
from app.services.coverage_service import rebuild_coverage_state, save_coverage_state
from app.services.interview_lifecycle import can_continue_interview, is_minimum_goal_reached
from app.services.question_planner import plan_next_question
from app.services.question_generator import generate_next_question_from_history
from app.services.question_version_service import append_question_version
from app.services.question_validator import validate_question_for_stage
from app.services.repetition_guard import build_question_signature, is_question_too_similar
from app.services.run_trace_service import traced_run_step
from app.services.summarization_service import ensure_turn_summaries
from app.services.stage_manager import decide_next_stage
from app.services.transcript_service import build_compact_interview_context
from app.services.usage_service import create_usage_record


def build_question_plan_payload(state: dict) -> dict:
    return {
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
    }


def build_question_plan_json(state: dict) -> str:
    return json.dumps(
        build_question_plan_payload(state),
        ensure_ascii=True,
        sort_keys=True,
    )


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
) -> dict:
    coverage_state = rebuild_coverage_state(turns)
    context_payload = build_generation_context(
        turns=turns,
        current_stage=current_stage,
        next_turn_no=turn_no,
        coverage_state=coverage_state,
        project_id=project.id,
        latest_answer_override=latest_answer_override,
    )
    planner_decision = plan_next_question(
        turns=turns,
        current_stage=current_stage,
        next_turn_no=turn_no,
        coverage_state=coverage_state,
        human_review_signal=human_review_signal,
    )
    next_question_result = generate_next_question_from_history(
        system_prompt=project.system_prompt,
        recent_context=context_payload["recent_context"],
        retrieved_context=context_payload["retrieved_context"],
        coverage_priorities=context_payload["coverage_priorities"],
        next_turn_no=turn_no,
        current_stage=current_stage,
        planner_decision=planner_decision,
        project_id=project.id,
        run_id=run_id,
    )
    next_question = next_question_result["question_text"]
    question_usage_metrics = [next_question_result["usage_metrics"]]

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
        retried_question_result = generate_next_question_from_history(
            system_prompt=project.system_prompt,
            recent_context=context_payload["recent_context"],
            retrieved_context=context_payload["retrieved_context"],
            coverage_priorities=context_payload["coverage_priorities"],
            next_turn_no=turn_no,
            current_stage=current_stage,
            planner_decision=planner_decision,
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
    )

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
        )
        if not validation["is_valid"]:
            raise ValueError(
                "Generated question failed stage-specific validation: "
                + "; ".join(validation["reasons"])
            )

    return {
        "generated_question": next_question,
        "coverage_state": coverage_state,
        "retrieved_context": context_payload["retrieved_context"],
        "coverage_priorities": context_payload["coverage_priorities"],
        "selected_turn_ids": context_payload["selected_turn_ids"],
        "selected_branch_ids": context_payload["selected_branch_ids"],
        "planner_decision": planner_decision,
        "validation_result": validation,
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
        coverage_state = rebuild_coverage_state(turns)
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

        if latest_turn.answer_text is not None:
            raise ValueError("Latest turn already has an answer")

        turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.project_id == state["project_id"])
            .order_by(InterviewTurn.turn_no.asc())
            .all()
        )

        return {
            "project_status": project.status,
            "current_turn_no": latest_turn.turn_no,
            "current_stage": latest_turn.stage,
            "history_text": build_compact_interview_context(turns),
            "coverage_state": project.coverage_state_data,
            "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
            "pending_turn_id": latest_turn.id,
            "human_review_signal": state.get("human_review_signal"),
            "next_turn_no": None,
            "next_stage": None,
            "generated_question": None,
            "retrieved_context": None,
            "coverage_priorities": None,
            "selected_turn_ids": [],
            "selected_branch_ids": [],
            "stage_decision": {},
            "planner_decision": {},
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
        "prompt_metadata": generation_payload["prompt_metadata"],
        "question_usage_metrics": generation_payload["question_usage_metrics"],
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
        if pending_turn.answer_text is not None:
            raise ValueError("Pending turn was already answered by another request")

        pending_turn.answer_text = state["answer_text"]
        if state.get("human_review_signal"):
            pending_turn.human_review_json = json.dumps(
                state["human_review_signal"],
                ensure_ascii=True,
                sort_keys=True,
            )
        all_turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.project_id == state["project_id"])
            .order_by(InterviewTurn.turn_no.asc())
            .all()
        )
        refreshed_coverage_state = rebuild_coverage_state(all_turns)
        save_coverage_state(project, refreshed_coverage_state)
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

        if state.get("interview_finished"):
            project.status = "finished"
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
        refreshed_coverage_state = rebuild_coverage_state([*all_turns, next_turn])
        save_coverage_state(project, refreshed_coverage_state)

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
