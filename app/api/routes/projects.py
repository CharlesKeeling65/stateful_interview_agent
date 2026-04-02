from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.graphs.interview_graph import interview_graph
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.schemas.project import (
    ProjectCreate,
    ProjectNextResponse,
    ProjectRead,
    ProjectStartResponse,
)
from app.schemas.turn import AnswerSubmitRequest, AnswerSubmitResponse, TurnRead
from app.services.interview_lifecycle import (
    can_continue_interview,
    is_minimum_goal_reached,
)
from app.services.question_generator import (
    generate_first_question,
    generate_next_question,
)
from app.services.question_validator import looks_like_valid_question
from app.services.repetition_guard import is_question_too_similar
from app.services.stage_manager import determine_stage_by_turn
from app.services.transcript_service import build_project_transcript

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = ProjectSession(
        project_name=payload.project_name,
        system_prompt=payload.system_prompt,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/start", response_model=ProjectStartResponse)
def start_project_interview(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.turn_count > 0:
        raise HTTPException(
            status_code=400, detail="Project interview has already started"
        )

    first_question = generate_first_question(project.system_prompt)

    first_turn = InterviewTurn(
        project_id=project.id,
        turn_no=1,
        stage="Panorama Mapping",
        question_text=first_question,
        answer_text=None,
    )
    db.add(first_turn)

    project.current_stage = "Panorama Mapping"
    project.turn_count = 1

    db.commit()
    db.refresh(project)
    db.refresh(first_turn)

    return {
        "project": project,
        "first_turn": first_turn,
    }


@router.post("/{project_id}/answer", response_model=AnswerSubmitResponse)
def submit_answer(
    project_id: int, payload: AnswerSubmitRequest, db: Session = Depends(get_db)
):
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

    if latest_turn.answer_text is not None:
        raise HTTPException(status_code=400, detail="Latest turn already has an answer")

    latest_turn.answer_text = payload.answer_text
    db.commit()
    db.refresh(latest_turn)

    return {
        "project_id": project_id,
        "updated_turn": latest_turn,
    }


@router.post("/{project_id}/next", response_model=ProjectNextResponse)
def submit_answer_and_generate_next(
    project_id: int,
    payload: AnswerSubmitRequest,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status == "finished":
        raise HTTPException(
            status_code=400, detail="Project interview is already finished"
        )

    latest_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.desc())
        .first()
    )
    if not latest_turn:
        raise HTTPException(status_code=400, detail="Project interview has not started")

    if latest_turn.answer_text is not None:
        raise HTTPException(status_code=400, detail="Latest turn already has an answer")

    latest_turn.answer_text = payload.answer_text

    current_turn_count = latest_turn.turn_no

    if not can_continue_interview(current_turn_count):
        project.status = "finished"
        db.commit()
        db.refresh(project)
        db.refresh(latest_turn)

        return {
            "project": project,
            "previous_turn": latest_turn,
            "next_turn": None,
            "interview_finished": True,
            "minimum_goal_reached": is_minimum_goal_reached(current_turn_count),
            "message": "Interview finished. Maximum turn limit reached.",
        }

    all_turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )

    next_turn_no = latest_turn.turn_no + 1
    next_stage = determine_stage_by_turn(next_turn_no)

    next_question = generate_next_question(
        system_prompt=project.system_prompt,
        turns=all_turns,
        next_turn_no=next_turn_no,
        current_stage=next_stage,
    )

    if not looks_like_valid_question(next_question, next_turn_no):
        raise HTTPException(
            status_code=500, detail="Generated question format is invalid"
        )

    old_questions = [turn.question_text for turn in all_turns]

    if is_question_too_similar(next_question, old_questions):
        retry_prompt = (
            project.system_prompt
            + "\n\nThe next question draft was too similar to an earlier question. "
            "Generate a more specific and substantially different follow-up question."
        )

        next_question = generate_next_question(
            system_prompt=retry_prompt,
            turns=all_turns,
            next_turn_no=next_turn_no,
            current_stage=next_stage,
        )

        if not looks_like_valid_question(next_question, next_turn_no):
            raise HTTPException(
                status_code=500, detail="Regenerated question format is invalid"
            )

    next_turn = InterviewTurn(
        project_id=project.id,
        turn_no=next_turn_no,
        stage=next_stage,
        question_text=next_question,
        answer_text=None,
    )
    db.add(next_turn)

    project.turn_count = next_turn_no
    project.current_stage = next_stage

    db.commit()
    db.refresh(project)
    db.refresh(latest_turn)
    db.refresh(next_turn)

    return {
        "project": project,
        "previous_turn": latest_turn,
        "next_turn": next_turn,
        "interview_finished": project.status == "finished",
        "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
        "message": "Answer submitted and next question generated successfully.",
    }


@router.get("/{project_id}/turns", response_model=list[TurnRead])
def get_project_turns(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    return turns


@router.get("/{project_id}/transcript")
def get_project_transcript(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )

    return {
        "project_id": project_id,
        "project_name": project.project_name,
        "turn_count": len(turns),
        "transcript": build_project_transcript(turns),
    }


@router.get("/{project_id}/status")
def get_project_status(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    latest_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.desc())
        .first()
    )

    return {
        "project_id": project.id,
        "project_name": project.project_name,
        "status": project.status,
        "current_stage": project.current_stage,
        "turn_count": project.turn_count,
        "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
        "max_turn_limit": settings.interview_max_turns,
        "latest_turn_no": latest_turn.turn_no if latest_turn else None,
        "latest_turn_answered": (
            (latest_turn.answer_text is not None) if latest_turn else None
        ),
    }
