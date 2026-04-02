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
    ProjectStatusResponse,
    ProjectUpdate,
    TranscriptResponse,
)
from app.schemas.turn import AnswerSubmitRequest, AnswerSubmitResponse, TurnRead
from app.services.interview_lifecycle import is_minimum_goal_reached
from app.services.question_generator import generate_first_question_result
from app.services.transcript_service import build_project_transcript
from app.services.usage_service import aggregate_project_usage, create_usage_record

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


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    return (
        db.query(ProjectSession)
        .order_by(ProjectSession.updated_at.desc(), ProjectSession.id.desc())
        .all()
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(project, field_name, value)

    db.commit()
    db.refresh(project)
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

    first_question_result = generate_first_question_result(project.system_prompt)

    first_turn = InterviewTurn(
        project_id=project.id,
        turn_no=1,
        stage="Panorama Mapping",
        question_text=first_question_result["question_text"],
        answer_text=None,
    )
    db.add(first_turn)
    db.flush()
    db.add(
        create_usage_record(
            project_id=project.id,
            turn_id=first_turn.id,
            operation_type="question_generation",
            usage_metrics=first_question_result["usage_metrics"],
        )
    )

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

    try:
        result = interview_graph.invoke(
            {
                "project_id": project_id,
                "answer_text": payload.answer_text,
            },
            config={"configurable": {"thread_id": f"project-{project_id}"}},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    updated_project = (
        db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    )

    previous_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.desc())
        .offset(1 if not result.get("interview_finished") else 0)
        .first()
    )

    latest_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.desc())
        .first()
    )

    if result.get("interview_finished"):
        previous_turn = latest_turn
        next_turn = None
    else:
        next_turn = latest_turn
        previous_turn = (
            db.query(InterviewTurn)
            .filter(
                InterviewTurn.project_id == project_id,
                InterviewTurn.turn_no == next_turn.turn_no - 1,
            )
            .first()
        )

    return {
        "project": updated_project,
        "previous_turn": previous_turn,
        "next_turn": next_turn,
        "interview_finished": result.get("interview_finished", False),
        "minimum_goal_reached": result.get("minimum_goal_reached", False),
        "usage_summary": aggregate_project_usage(updated_project.llm_usages),
        "message": result.get("message", ""),
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


@router.get("/{project_id}/transcript", response_model=TranscriptResponse)
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
        "usage_summary": aggregate_project_usage(project.llm_usages),
        "transcript": build_project_transcript(turns),
    }


@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
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
        "latest_question_text": latest_turn.question_text if latest_turn else None,
        "latest_question_text_for_copy": (
            latest_turn.question_text_for_copy if latest_turn else None
        ),
        "usage_summary": aggregate_project_usage(project.llm_usages),
    }
