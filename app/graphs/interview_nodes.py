from sqlalchemy.orm import Session

from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.interview_lifecycle import can_continue_interview, is_minimum_goal_reached
from app.services.question_generator import generate_next_question_from_history
from app.services.question_validator import looks_like_valid_question
from app.services.repetition_guard import is_question_too_similar
from app.services.summarization_service import ensure_turn_summaries
from app.services.stage_manager import determine_stage_by_turn
from app.services.transcript_service import build_compact_interview_context
from app.services.usage_service import create_usage_record


def load_project_context(state, db: Session):
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
        "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
        "pending_turn_id": latest_turn.id,
    }


def decide_progress(state):
    current_turn_no = state["current_turn_no"]

    if not can_continue_interview(current_turn_no):
        return {
            "interview_finished": True,
            "minimum_goal_reached": is_minimum_goal_reached(current_turn_no),
            "message": "Interview finished. Maximum turn limit reached.",
        }

    next_turn_no = current_turn_no + 1
    next_stage = determine_stage_by_turn(next_turn_no)

    return {
        "interview_finished": False,
        "next_turn_no": next_turn_no,
        "next_stage": next_stage,
    }


def draft_next_question(state, db: Session):
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

    answered_turns = [turn for turn in turns if turn.answer_text]
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
            .filter(InterviewTurn.project_id == state["project_id"])
            .order_by(InterviewTurn.turn_no.asc())
            .all()
        )

    history_text = build_compact_interview_context(
        turns,
        latest_answer_override=state["answer_text"],
    )

    next_question_result = generate_next_question_from_history(
        system_prompt=project.system_prompt,
        history_text=history_text,
        next_turn_no=state["next_turn_no"],
        current_stage=state["next_stage"],
    )
    next_question = next_question_result["question_text"]
    question_usage_metrics = [next_question_result["usage_metrics"]]

    old_questions = [turn.question_text for turn in turns]

    if is_question_too_similar(next_question, old_questions):
        retry_prompt = (
            project.system_prompt
            + "\n\nThe next question draft was too similar to an earlier question. "
            "Generate a more specific and substantially different follow-up question."
        )

        retried_question_result = generate_next_question_from_history(
            system_prompt=retry_prompt,
            history_text=history_text,
            next_turn_no=state["next_turn_no"],
            current_stage=state["next_stage"],
        )
        next_question = retried_question_result["question_text"]
        question_usage_metrics.append(retried_question_result["usage_metrics"])

    if not looks_like_valid_question(next_question, state["next_turn_no"]):
        raise ValueError("Generated question format is invalid")

    return {
        "generated_question": next_question,
        "history_text": history_text,
        "question_usage_metrics": question_usage_metrics,
    }

def persist_next_step(state, db: Session):
    project = (
        db.query(ProjectSession)
        .filter(ProjectSession.id == state["project_id"])
        .first()
    )

    latest_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == state["project_id"])
        .order_by(InterviewTurn.turn_no.desc())
        .first()
    )

    latest_turn.answer_text = state["answer_text"]

    if state.get("interview_finished"):
        project.status = "finished"
        db.commit()
        db.refresh(project)
        db.refresh(latest_turn)
        return {
            "message": "Interview finished. Maximum turn limit reached.",
            "minimum_goal_reached": is_minimum_goal_reached(latest_turn.turn_no),
        }

    next_turn = InterviewTurn(
        project_id=project.id,
        turn_no=state["next_turn_no"],
        stage=state["next_stage"],
        question_text=state["generated_question"],
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

    project.turn_count = state["next_turn_no"]
    project.current_stage = state["next_stage"]

    db.commit()
    db.refresh(project)
    db.refresh(latest_turn)
    db.refresh(next_turn)

    return {
        "message": "Answer submitted and next question generated successfully.",
        "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
    }
