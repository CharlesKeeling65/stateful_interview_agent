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
    DebugInfoResponse,
)
from app.services.mode_service import (
    AgentMode,
    can_mode_propose_changes,
    get_mode_constraints,
    validate_mode_transition,
)
from app.services.context_engineering import build_generation_context
from app.services.coverage_service import rebuild_coverage_state, save_coverage_state
from app.services.llm_test import test_llm_call
from app.services.question_generator import get_prompt_id_for_plan
from app.services.question_planner import plan_next_question
from app.services.question_validator import validate_question_for_stage
from app.services.rubric_task_service import deserialize_task_board, get_next_priority_task
from app.services.scenario_service import check_scenario_completion
from app.services.stage_manager import decide_next_stage
from app.services.summarization_service import ensure_turn_summaries
from app.services.transcript_event_service import deserialize_event_log

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm")
def debug_llm():
    return test_llm_call()


@router.get("/projects/{project_id}/coverage", response_model=CoverageDebugResponse)
def debug_project_coverage(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    coverage_state = rebuild_coverage_state(turns, project)
    return coverage_state


@router.get("/projects/{project_id}/queue-summary")
def debug_project_queue_summary(project_id: int, db: Session = Depends(get_db)):
    """Return active sub-question queue summary for the project."""
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    coverage_state = rebuild_coverage_state(turns, project)
    queue = coverage_state.get("question_queue", {"status": "empty", "items": []})
    return {
        "status": queue.get("status", "empty"),
        "item_count": len(queue.get("items", [])),
        "parent_turn_no": queue.get("parent_turn_no"),
        "parent_group_intent": queue.get("parent_group_intent"),
        "pending_questions": [
            {
                "turn_offset": item.get("turn_offset"),
                "question_text": item.get("question_text", ""),
                "intent": item.get("intent", ""),
                "target_label": item.get("target_label"),
            }
            for item in queue.get("items", [])
        ],
    }


@router.get("/projects/{project_id}/file-coverage-summary")
def debug_project_file_coverage_summary(project_id: int, db: Session = Depends(get_db)):
    """Return file importance/exploration metrics and tree summary for the project."""
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    coverage_state = rebuild_coverage_state(turns, project)
    repo_coverage = coverage_state.get("repo_file_coverage", {})
    tree_summary = coverage_state.get("repo_tree_summary", {})

    # Compute summary analytics
    all_files = [v for v in repo_coverage.values() if isinstance(v, dict)]
    important_files = [f for f in all_files if f.get("importance_score", 0.0) >= 0.5]
    underexplored = [
        f for f in important_files
        if f.get("coverage_gap_score", 0.0) > 0.2
    ]
    exploration_scores = [f.get("exploration_score", 0.0) for f in all_files]
    median_exploration = sorted(exploration_scores)[len(exploration_scores) // 2] if exploration_scores else 0.0

    # Top files by gap: Sort by importance (desc) then gap (desc), filtering for those with non-zero gap
    underexplored_files = [f for f in all_files if f.get("coverage_gap_score", 0.0) > 0.05]
    top_gap_files = sorted(
        underexplored_files,
        key=lambda f: (f.get("importance_score", 0.0), f.get("coverage_gap_score", 0.0)),
        reverse=True,
    )[:14]

    # Concentration ratio: what fraction of total asks are on top 1 / top 3 files?
    files_by_asks = sorted(all_files, key=lambda f: f.get("times_asked", 0), reverse=True)
    total_asks = sum(f.get("times_asked", 0) for f in all_files)
    top1_asks = files_by_asks[0].get("times_asked", 0) if files_by_asks else 0
    top3_asks = sum(f.get("times_asked", 0) for f in files_by_asks[:3])

    return {
        "total_tracked_files": len(all_files),
        "important_files_count": len(important_files),
        "underexplored_important_count": len(underexplored),
        "median_exploration_score": round(median_exploration, 3),
        "concentration_ratio_top1": round(top1_asks / total_asks, 3) if total_asks > 0 else 0.0,
        "concentration_ratio_top3": round(top3_asks / total_asks, 3) if total_asks > 0 else 0.0,
        "top_gap_files": [
            {
                "path": f["path"],
                "importance_score": round(f.get("importance_score", 0.0), 3),
                "exploration_score": round(f.get("exploration_score", 0.0), 3),
                "coverage_gap_score": round(f.get("coverage_gap_score", 0.0), 3),
                "times_asked": f.get("times_asked", 0),
                "times_answered": f.get("times_answered", 0),
                "last_turn_no": f.get("last_turn_no"),
            }
            for f in top_gap_files
        ],
        "tree_summary": tree_summary,
    }


@router.get("/projects/{project_id}/state", response_model=DebugInfoResponse)
def debug_project_state(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    latest_turn = turns[-1] if turns else None
    task_board = deserialize_task_board(project.rubric_task_board)
    next_task = get_next_priority_task(task_board)
    scenario_status = check_scenario_completion(project.coverage_state_data, turns)
    current_mode = project.agent_mode or AgentMode.UNDERSTAND_CURRENT_CODE.value

    return {
        "question_plan": {
            "mode": current_mode,
            "phase": latest_turn.stage if latest_turn else project.current_stage,
            "rubric_task_id": (latest_turn.question_plan or {}).get("rubric_task_id") if latest_turn else None,
            "rubric_task_label": (latest_turn.question_plan or {}).get("rubric_task_label") if latest_turn else None,
            "target_branch_ids": (latest_turn.question_plan or {}).get("selected_branch_ids", []) if latest_turn else [],
            "target_artifact": (latest_turn.question_plan or {}).get("target_label") if latest_turn else None,
            "framework_gap": (latest_turn.question_plan or {}).get("selected_framework_gap") if latest_turn else None,
            "confidence_score": (
                ((latest_turn.question_plan or {}).get("confidence_score") or 0.5)
                if latest_turn
                else 0.5
            ),
            "human_gate_triggered": bool(project.pending_gate),
            "human_gate_reason": (project.pending_gate or {}).get("reason"),
            "why_this_question": (latest_turn.question_plan or {}).get("why_this_question", "") if latest_turn else "",
            "planning_steps": ["load_context", "decide_progress", "plan_question", "review_question_plan", "draft_question"],
            "reviewer_modifications": (latest_turn.question_plan or {}).get("reviewer_modifications", []) if latest_turn else [],
            "evidence_turn_ids": (latest_turn.question_plan or {}).get("selected_turn_ids", []) if latest_turn else [],
            "question_intent": (latest_turn.question_plan or {}).get("question_intent") if latest_turn else None,
            "intent_mode": (latest_turn.question_plan or {}).get("intent_mode") if latest_turn else current_mode,
            "drift_detected": bool((latest_turn.question_plan or {}).get("drift_detected")) if latest_turn else False,
            "human_review_applied": bool((latest_turn.question_plan or {}).get("human_review_applied")) if latest_turn else False,
        },
        "task_board": {
            "current_phase": task_board.current_phase,
            "phase_status": {key: value.value for key, value in task_board.phase_status.items()},
            "incomplete_tasks": [
                task.model_dump()
                for tasks in task_board.phases.values()
                for task in tasks
                if task.status.value != "completed"
            ][:10],
            "next_priority_task": next_task.model_dump() if next_task else None,
            "human_gate_pending": bool(project.pending_gate),
        },
        "mode": {
            "current_mode": current_mode,
            "mode_constraints": get_mode_constraints(current_mode),
            "can_propose_changes": can_mode_propose_changes(current_mode),
            "valid_transitions": [
                mode.value
                for mode in AgentMode
                if validate_mode_transition(current_mode, mode.value) and mode.value != current_mode
            ],
        },
        "scenario": scenario_status,
        "coverage_summary": {
            "branch_count": project.coverage_state_data.get("branch_count", 0),
            "updated_through_turn_no": project.coverage_state_data.get("updated_through_turn_no", 0),
        },
        "recent_events": deserialize_event_log(latest_turn.event_log_json if latest_turn else "[]")[-10:],
    }


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
    coverage_state = rebuild_coverage_state(turns, project)
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
        human_review_signal=payload.human_review.model_dump() if payload.human_review else None,
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
        human_review_signal=payload.human_review.model_dump() if payload.human_review else None,
    )

    prompt = get_prompt_manager().render(
        get_prompt_id_for_plan(next_stage, planner_decision),
        {
            "system_prompt": project.system_prompt,
            "current_stage": next_stage,
            "stage_objective": context_payload["stage_objective"],
            "question_intent": planner_decision["question_intent"],
            "intent_mode": planner_decision.get("intent_mode", "understand_current_code"),
            "target_type": planner_decision["target_type"],
            "target_label": planner_decision["target_label"],
            "planner_reasoning": planner_decision["reasoning"],
            "human_review_context": (
                payload.human_review.model_dump_json() if payload.human_review else "No explicit human review signal was provided for this turn."
            ),
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
        intent_mode=planner_decision.get("intent_mode", "understand_current_code"),
    )

    return {
        **context_payload,
        "question_history": coverage_state.get("question_history", []),
        "stage_decision": stage_decision,
        "planner_decision": planner_decision,
        "validation_preview": validation_preview,
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
        "prompt_messages": prompt.messages,
    }
