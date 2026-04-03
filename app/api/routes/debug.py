from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.prompts import get_prompt_manager
from app.schemas.debug import (
    ContextPreviewRequest,
    ContextPreviewResponse,
    CoverageDebugResponse,
)
from app.services.context_engineering import build_generation_context
from app.services.coverage_service import rebuild_coverage_state, save_coverage_state
from app.services.llm_test import test_llm_call
from app.services.question_generator import get_prompt_id_for_plan
from app.services.question_planner import plan_next_question
from app.services.question_validator import validate_question_for_stage
from app.services.stage_manager import decide_next_stage
from app.services.summarization_service import ensure_turn_summaries

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm")
def debug_llm():
    return test_llm_call()


@router.get("/projects/{project_id}/coverage", response_model=CoverageDebugResponse)
def debug_project_coverage(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.coverage_state_data


@router.post(
    "/projects/{project_id}/next-context",
    response_model=ContextPreviewResponse,
)
def debug_next_context_preview(
    project_id: int,
    payload: ContextPreviewRequest,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    if not turns:
        raise HTTPException(status_code=400, detail="Project interview has not started")

    answered_turns = [turn for turn in turns if turn.answer_text]
    summarized_count = ensure_turn_summaries(
        db=db,
        project_id=project.id,
        system_prompt=project.system_prompt,
        turns_to_summarize=answered_turns,
    )
    if summarized_count:
        db.flush()

    pending_turn = turns[-1]
    original_answer_text = pending_turn.answer_text
    pending_turn.answer_text = payload.answer_text
    coverage_state = rebuild_coverage_state(turns)
    pending_turn.answer_text = original_answer_text
    save_coverage_state(project, coverage_state)
    db.commit()
    db.refresh(project)

    next_turn_no = pending_turn.turn_no + 1
    stage_decision = decide_next_stage(
        next_turn_no=next_turn_no,
        coverage_state=coverage_state,
        current_stage=project.current_stage,
        max_turns=settings.interview_max_turns,
    )
    next_stage = stage_decision["next_stage"]
    context_payload = build_generation_context(
        turns=turns,
        current_stage=next_stage,
        next_turn_no=next_turn_no,
        coverage_state=coverage_state,
        project_id=project.id,
        latest_answer_override=payload.answer_text,
    )

    planner_decision = plan_next_question(
        turns=turns,
        current_stage=next_stage,
        next_turn_no=next_turn_no,
        coverage_state=coverage_state,
    )

    prompt = get_prompt_manager().render(
        get_prompt_id_for_plan(next_stage, planner_decision),
        {
            "system_prompt": project.system_prompt,
            "current_stage": next_stage,
            "stage_objective": context_payload["stage_objective"],
            "question_intent": planner_decision["question_intent"],
            "target_type": planner_decision["target_type"],
            "target_label": planner_decision["target_label"],
            "planner_reasoning": planner_decision["reasoning"],
            "next_turn_no": next_turn_no,
            "recent_context": context_payload["recent_context"],
            "retrieved_context": context_payload["retrieved_context"],
            "coverage_priorities": context_payload["coverage_priorities"],
            "style_constraints": "\n".join(planner_decision.get("constraints", [])),
        },
    )

    validation_preview = validate_question_for_stage(
        text=f"Q{next_turn_no}: Placeholder validation preview?",
        expected_turn_no=next_turn_no,
        current_stage=next_stage,
    )

    return {
        **context_payload,
        "stage_decision": stage_decision,
        "planner_decision": planner_decision,
        "validation_preview": validation_preview,
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
        "prompt_messages": prompt.messages,
    }
