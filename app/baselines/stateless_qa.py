from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.logging import bind_log_context, emit_event, preview_payload
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.coverage_service import default_coverage_state, save_coverage_state
from app.services.question_generator import generate_next_question_from_history
from app.services.question_version_service import append_question_version
from app.services.run_trace_service import create_run, finalize_run, traced_run_step
from app.services.transcript_event_service import (
    add_event_to_log,
    deserialize_event_log,
    emit_ai_question_event,
    emit_human_answer_event,
    serialize_event_log,
)
from app.services.usage_service import aggregate_project_usage, create_usage_record

STATELESS_QA_SYSTEM_ID = "stateless_qa"
STATELESS_QA_WINDOW = 3


def _build_recent_context(turns: list[InterviewTurn]) -> str:
    if not turns:
        return "No previous conversation."
    parts: list[str] = []
    for turn in turns[-STATELESS_QA_WINDOW:]:
        parts.append(f"Turn {turn.turn_no}:")
        parts.append(f"Q: {turn.question_text}")
        if turn.answer_text:
            parts.append(f"A: {turn.answer_text}")
        parts.append("")
    return "\n".join(parts).strip()


def _clear_coverage_state(
    *,
    project: ProjectSession,
    turn_no: int,
    stage: str | None,
    emit_persist_event: bool,
) -> None:
    empty_state = default_coverage_state()
    empty_state["updated_through_turn_no"] = turn_no
    save_coverage_state(project, empty_state)
    if not emit_persist_event:
        return
    emit_event(
        "persistence",
        "coverage.persist.complete",
        "Persisted cleared coverage state for stateless baseline",
        operation="save_coverage_state",
        project_id=project.id,
        turn_no=turn_no,
        stage=stage,
        output={
            "branch_count": 0,
            "updated_through_turn_no": turn_no,
            "system_id": STATELESS_QA_SYSTEM_ID,
        },
    )


def submit_answer_and_generate_next_stateless(project_id: int, db: Session) -> dict:
    bind_log_context(project_id=project_id)
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    latest_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.desc())
        .first()
    )
    if not latest_turn:
        raise HTTPException(status_code=400, detail="Project interview has not started")
    if latest_turn.answer_text is None:
        raise HTTPException(
            status_code=400,
            detail="Save an answer for the current question before generating the next one.",
        )

    run = create_run(project_id=project_id, turn_no=latest_turn.turn_no + 1)
    bind_log_context(run_id=run.id)
    stage = project.current_stage or latest_turn.stage

    try:
        emit_event(
            "workflow",
            "workflow.invoke.start",
            "Invoking stateless QA workflow",
            operation="submit_answer_and_generate_next_stateless",
            project_id=project_id,
            run_id=run.id,
            stage=stage,
            input=preview_payload(
                latest_turn.answer_text,
                artifact_category="answers",
                artifact_name=f"stateless-input-project-{project_id}",
            ),
        )

        answered_turns = (
            db.query(InterviewTurn)
            .filter(
                InterviewTurn.project_id == project_id,
                InterviewTurn.answer_text.isnot(None),
            )
            .order_by(InterviewTurn.turn_no.asc())
            .all()
        )

        with traced_run_step(
            run_id=run.id,
            project_id=project_id,
            turn_no=latest_turn.turn_no + 1,
            step_key="build_compact_context",
            description="Build stateless sliding-window context from the last three answered turns.",
            next_step_hint="Render prompt",
        ) as context_step:
            recent_turns = answered_turns[-STATELESS_QA_WINDOW:]
            recent_context = _build_recent_context(recent_turns)
            if context_step:
                context_step.set_meta(
                    system_id=STATELESS_QA_SYSTEM_ID,
                    context_turn_nos=[turn.turn_no for turn in recent_turns],
                    sliding_window_size=STATELESS_QA_WINDOW,
                    coverage_state_cleared=True,
                )

        project.pending_gate_json = "null"
        _clear_coverage_state(
            project=project,
            turn_no=latest_turn.turn_no,
            stage=latest_turn.stage,
            emit_persist_event=True,
        )

        generation_payload = generate_next_question_from_history(
            system_prompt=project.system_prompt,
            recent_context=recent_context,
            retrieved_context="Stateless baseline: repository retrieval disabled.",
            coverage_priorities=(
                "Stateless baseline: ignore persistent coverage state and focus only on the recent three turns."
            ),
            next_turn_no=latest_turn.turn_no + 1,
            current_stage=stage,
            planner_decision={
                "question_intent": "stateless_follow_up",
                "intent_mode": "understand_current_code",
                "target_type": "recent_context",
                "target_label": "the most recent unresolved thread",
                "constraints": [
                    "Use only the last three answered turns as context",
                    "Do not rely on persistent coverage state",
                    "Ask exactly one concrete follow-up question",
                ],
                "reasoning": "Stateless QA baseline using a fixed three-turn sliding window.",
            },
            repo_grounding_context="Stateless baseline: no repo grounding context attached.",
            project_id=project_id,
            run_id=run.id,
        )

        with traced_run_step(
            run_id=run.id,
            project_id=project_id,
            turn_no=latest_turn.turn_no + 1,
            step_key="persist_result",
            description="Persist stateless baseline outputs using the same run/event tables as the full workflow.",
            next_step_hint="Finalize run",
        ) as persist_step:
            current_event_log = deserialize_event_log(latest_turn.event_log_json)
            answer_event = emit_human_answer_event(
                turn_no=latest_turn.turn_no,
                answer_text=latest_turn.answer_text,
                answer_summary=latest_turn.answer_summary,
                project_id=project_id,
            )
            current_event_log = add_event_to_log(current_event_log, answer_event)
            latest_turn.event_log_json = serialize_event_log(current_event_log)

            next_turn = InterviewTurn(
                project_id=project.id,
                turn_no=latest_turn.turn_no + 1,
                stage=stage,
                question_text=generation_payload["question_text"],
                question_plan_json=json.dumps(
                    {
                        "mode": STATELESS_QA_SYSTEM_ID,
                        "phase": stage,
                        "question_intent": "stateless_follow_up",
                        "selected_branch_ids": [],
                        "selected_turn_ids": [turn.id for turn in answered_turns[-STATELESS_QA_WINDOW:]],
                        "repo_queries": [],
                        "repo_selected_paths": [],
                        "repo_selected_symbols": [],
                        "why_this_question": "Generated from the last three answered turns only.",
                        "system_id": STATELESS_QA_SYSTEM_ID,
                        "coverage_state_cleared": True,
                        "sliding_window_size": STATELESS_QA_WINDOW,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                answer_text=None,
            )
            db.add(next_turn)
            db.flush()

            db.add(
                create_usage_record(
                    project_id=project.id,
                    turn_id=next_turn.id,
                    operation_type="question_generation",
                    usage_metrics=generation_payload["usage_metrics"],
                )
            )
            append_question_version(
                db=db,
                turn=next_turn,
                generation_kind="initial",
                human_review_signal=None,
                question_plan_json=next_turn.question_plan_json,
                question_text=next_turn.question_text,
                usage_metrics_list=[generation_payload["usage_metrics"]],
            )

            next_event_log = deserialize_event_log(next_turn.event_log_json)
            question_event = emit_ai_question_event(
                turn_no=next_turn.turn_no,
                question_text=next_turn.question_text,
                question_plan=next_turn.question_plan or {},
                mode=STATELESS_QA_SYSTEM_ID,
                phase=next_turn.stage,
                project_id=project_id,
            )
            next_turn.event_log_json = serialize_event_log(add_event_to_log(next_event_log, question_event))

            project.turn_count = next_turn.turn_no
            project.current_stage = stage
            project.pending_gate_json = "null"
            _clear_coverage_state(
                project=project,
                turn_no=next_turn.turn_no,
                stage=next_turn.stage,
                emit_persist_event=False,
            )

            if persist_step:
                persist_step.set_meta(
                    system_id=STATELESS_QA_SYSTEM_ID,
                    persisted_turn_no=next_turn.turn_no,
                    coverage_state_cleared=True,
                )

            db.commit()
            db.refresh(project)
            db.refresh(next_turn)
            db.refresh(latest_turn)

        emit_event(
            "persistence",
            "workflow.persist.complete",
            "Persisted stateless baseline next turn",
            operation="persist_next_step",
            project_id=project.id,
            run_id=run.id,
            turn_no=next_turn.turn_no,
            stage=next_turn.stage,
            status="success",
            output={
                "interview_finished": False,
                "selected_branch_ids": [],
                "system_id": STATELESS_QA_SYSTEM_ID,
            },
        )
        emit_event(
            "workflow",
            "workflow.invoke.complete",
            "Stateless QA workflow completed",
            operation="submit_answer_and_generate_next_stateless",
            status="success",
            project_id=project_id,
            run_id=run.id,
            turn_no=next_turn.turn_no,
            stage=next_turn.stage,
            output={
                "interview_finished": False,
                "selected_branch_ids": [],
                "system_id": STATELESS_QA_SYSTEM_ID,
            },
        )
        finalize_run(run_id=run.id, status="completed", turn_no=next_turn.turn_no)
        return {
            "project": project,
            "previous_turn": latest_turn,
            "next_turn": next_turn,
            "run_id": run.id,
            "interview_finished": False,
            "minimum_goal_reached": False,
            "usage_summary": aggregate_project_usage(project.llm_usages),
            "message": "Stateless QA baseline generated the next question from a 3-turn sliding window.",
        }
    except HTTPException:
        db.rollback()
        finalize_run(run_id=run.id, status="failed")
        raise
    except Exception as exc:
        db.rollback()
        finalize_run(run_id=run.id, status="failed")
        emit_event(
            "workflow",
            "workflow.invoke.error",
            "Stateless QA workflow failed",
            level=40,
            operation="submit_answer_and_generate_next_stateless",
            project_id=project_id,
            run_id=run.id,
            exc_info=exc,
        )
        raise
