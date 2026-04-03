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
from app.services.stage_manager import determine_stage_by_turn
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
    next_stage = determine_stage_by_turn(next_turn_no)
    context_payload = build_generation_context(
        turns=turns,
        current_stage=next_stage,
        next_turn_no=next_turn_no,
        coverage_state=coverage_state,
        latest_answer_override=payload.answer_text,
    )

    prompt = get_prompt_manager().render(
        "next_question",
        {
            "system_prompt": project.system_prompt,
            "current_stage": next_stage,
            "stage_objective": context_payload["stage_objective"],
            "next_turn_no": next_turn_no,
            "closing_guidance": (
                "The interview is now in its closing phase. Prefer questions that help complete coverage cleanly instead of opening entirely new broad topics."
                if next_turn_no >= settings.interview_min_turns
                else "The interview still has room to deepen partially explored branches."
            ),
            "recent_context": context_payload["recent_context"],
            "retrieved_context": context_payload["retrieved_context"],
            "coverage_priorities": context_payload["coverage_priorities"],
        },
    )

    return {
        **context_payload,
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
        "prompt_messages": prompt.messages,
    }
