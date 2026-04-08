import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.graphs.interview_graph import interview_graph
from app.graphs.interview_nodes import build_question_plan_json, generate_question_for_state
from app.graphs.interview_nodes import draft_question_from_answered_history
from app.logging import bind_log_context, emit_event, preview_payload
from app.models.agent_run import AgentRun
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
from app.schemas.run_trace import RunRead
from app.schemas.turn import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    AnswerWithdrawResponse,
    CurrentQuestionRegenerateRequest,
    CurrentQuestionRegenerateResponse,
    NextQuestionRequest,
    TurnRead,
)
from app.services.opencode_execution_service import auto_answer_turn
from app.services.question_generator import generate_first_question_result
from app.services.question_version_service import (
    append_question_version,
    ensure_initial_question_version,
    normalize_question_versions,
    summarize_usage_metrics,
)
from app.services.repository_service import (
    RepositoryConfigurationError,
    apply_repository_configuration,
    format_repository_manifest,
    resolve_project_repository,
)
from app.services.rubric_task_service import initialize_task_board, serialize_task_board
from app.services.run_trace_service import create_run, finalize_run, serialize_run
from app.services.stage_manager import decide_next_stage, normalize_stage_name
from app.services.coverage_service import rebuild_coverage_state, save_coverage_state
from app.services.summarization_service import refresh_turn_answer_memory
from app.services.transcript_service import build_project_transcript
from app.services.usage_service import aggregate_project_usage, create_usage_record

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    emit_event(
        "persistence",
        "project.create.start",
        "Creating project session",
        operation="create_project",
        input=preview_payload(payload.model_dump(), artifact_category="requests", artifact_name="create-project"),
    )
    project = ProjectSession(
        project_name=payload.project_name,
        system_prompt=payload.system_prompt,
        agent_mode=payload.agent_mode,
        answer_provider_type=payload.answer_provider_type,
        answer_automation_enabled=payload.answer_automation_enabled,
        rubric_task_board=serialize_task_board(initialize_task_board()),
    )
    db.add(project)
    db.flush()
    try:
        apply_repository_configuration(
            project,
            payload.repository.model_dump() if payload.repository else None,
        )
        if project.repo_source_type != "none":
            resolve_project_repository(project)
    except RepositoryConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(project)
    bind_log_context(project_id=project.id)
    emit_event(
        "persistence",
        "project.create.complete",
        "Created project session",
        operation="create_project",
        status="success",
        project_id=project.id,
        output={"project_name": project.project_name},
    )
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
    bind_log_context(project_id=project_id)
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
    bind_log_context(project_id=project_id)
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = payload.model_dump(exclude_unset=True)
    repository_update = updates.pop("repository", None)
    for field_name, value in updates.items():
        setattr(project, field_name, value)
    if "repository" in payload.model_fields_set:
        try:
            apply_repository_configuration(project, repository_update)
            if project.repo_source_type != "none":
                resolve_project_repository(project)
        except RepositoryConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(project)
    emit_event(
        "persistence",
        "project.update.complete",
        "Updated project session",
        operation="update_project",
        status="success",
        project_id=project.id,
        input=preview_payload(updates, artifact_category="requests", artifact_name="update-project"),
    )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    bind_log_context(project_id=project_id)
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    emit_event(
        "persistence",
        "project.delete.complete",
        "Deleted project session",
        operation="delete_project",
        status="success",
        project_id=project_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/start", response_model=ProjectStartResponse)
def start_project_interview(project_id: int, db: Session = Depends(get_db)):
    bind_log_context(project_id=project_id)
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.turn_count > 0:
        raise HTTPException(
            status_code=400, detail="Project interview has already started"
        )

    repository_context = "No repository source configured for this project."
    if project.repo_source_type != "none":
        try:
            workspace = resolve_project_repository(project)
            if workspace:
                repository_context = format_repository_manifest(
                    workspace.manifest,
                    source_label=workspace.source_label,
                    commit_sha=workspace.commit_sha,
                )
        except RepositoryConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    first_question_result = generate_first_question_result(
        project.system_prompt,
        repository_context=repository_context,
    )

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
    db.flush()
    ensure_initial_question_version(db, first_turn)

    project.current_stage = "Panorama Mapping"
    project.turn_count = 1

    db.commit()
    db.refresh(project)
    if project.answer_provider_type == "opencode" and project.answer_automation_enabled:
        auto_answer_turn(db=db, project=project, turn=first_turn)
        db.commit()
        db.refresh(project)
        db.refresh(first_turn)
    emit_event(
        "persistence",
        "project.start.complete",
        "Started interview and persisted first turn",
        operation="start_project_interview",
        status="success",
        project_id=project.id,
        turn_no=first_turn.turn_no,
        stage=first_turn.stage,
        output={"question_text": preview_payload(first_turn.question_text, artifact_category="llm", artifact_name="first-question")},
    )

    return {
        "project": project,
        "first_turn": first_turn,
    }


@router.post("/{project_id}/answer", response_model=AnswerSubmitResponse)
def submit_answer(
    project_id: int, payload: AnswerSubmitRequest, db: Session = Depends(get_db)
):
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
    previous_answer = latest_turn.answer_text
    latest_turn.answer_text = payload.answer_text
    refresh_turn_answer_memory(
        db=db,
        project_id=project_id,
        system_prompt=project.system_prompt,
        turn=latest_turn,
    )
    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    refreshed_coverage_state = rebuild_coverage_state(turns)
    save_coverage_state(project, refreshed_coverage_state)
    db.commit()
    db.refresh(latest_turn)
    emit_event(
        "persistence",
        "turn.answer.persisted",
        "Persisted answer to latest turn",
        operation="submit_answer",
        status="success",
        project_id=project_id,
        turn_no=latest_turn.turn_no,
        stage=latest_turn.stage,
        output={"answer_updated": previous_answer is not None},
        input=preview_payload(payload.answer_text, artifact_category="answers", artifact_name=f"project-{project_id}-turn-{latest_turn.turn_no}"),
    )

    return {
        "project_id": project_id,
        "updated_turn": latest_turn,
        "can_generate_next": True,
        "message": "Answer saved. You can now generate the next question separately.",
    }


@router.post("/{project_id}/withdraw-answer", response_model=AnswerWithdrawResponse)
def withdraw_answer(project_id: int, db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=400, detail="Latest turn has no answer to withdraw")

    next_turn = (
        db.query(InterviewTurn)
        .filter(
            InterviewTurn.project_id == project_id,
            InterviewTurn.turn_no > latest_turn.turn_no,
        )
        .order_by(InterviewTurn.turn_no.asc())
        .first()
    )
    if next_turn is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot withdraw answer: next question already generated. Delete the next turn first.",
        )

    latest_turn.answer_text = None
    latest_turn.answer_summary = None
    latest_turn.answer_analysis_json = None

    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.project_id == project_id)
        .order_by(InterviewTurn.turn_no.asc())
        .all()
    )
    refreshed_coverage_state = rebuild_coverage_state(turns)
    save_coverage_state(project, refreshed_coverage_state)

    db.commit()
    db.refresh(latest_turn)

    emit_event(
        "persistence",
        "turn.answer.withdrawn",
        "Withdrawn answer from latest turn",
        operation="withdraw_answer",
        status="success",
        project_id=project_id,
        turn_no=latest_turn.turn_no,
        stage=latest_turn.stage,
    )

    return {
        "project_id": project_id,
        "withdrawn_turn": latest_turn,
        "message": "Answer withdrawn. The turn is now ready for a new answer.",
    }


@router.post("/{project_id}/auto-answer-latest", response_model=AnswerSubmitResponse)
def auto_answer_latest_turn(project_id: int, db: Session = Depends(get_db)):
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
    if latest_turn.answer_text is not None:
        raise HTTPException(status_code=400, detail="Latest turn already has an answer")

    auto_answer_turn(db=db, project=project, turn=latest_turn)
    db.commit()
    db.refresh(latest_turn)
    db.refresh(project)
    return {
        "project_id": project_id,
        "updated_turn": latest_turn,
        "can_generate_next": True,
        "message": "OpenCode answer saved for the latest turn.",
    }


@router.post("/{project_id}/auto-step", response_model=ProjectNextResponse)
def auto_step_project(project_id: int, payload: NextQuestionRequest, db: Session = Depends(get_db)):
    result = submit_answer_and_generate_next(project_id=project_id, payload=payload, db=db)
    if result["next_turn"] is not None and result["project"].answer_provider_type == "opencode" and result["project"].answer_automation_enabled:
        auto_answer_turn(db=db, project=result["project"], turn=result["next_turn"])
        db.commit()
        db.refresh(result["project"])
        db.refresh(result["next_turn"])
        result["previous_turn"] = result["next_turn"]
        result["next_turn"] = None
        result["message"] = f"{result['message']} OpenCode auto-answered the generated turn.".strip()
    return result


@router.post(
    "/{project_id}/turns/{turn_id}/regenerate-question",
    response_model=CurrentQuestionRegenerateResponse,
)
def regenerate_current_question(
    project_id: int,
    turn_id: int,
    payload: CurrentQuestionRegenerateRequest,
    db: Session = Depends(get_db),
):
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
    if latest_turn.id != turn_id:
        raise HTTPException(status_code=400, detail="Only the latest turn can be regenerated")
    if latest_turn.answer_text is not None:
        raise HTTPException(status_code=400, detail="Cannot regenerate a turn that already has an answer")

    run = create_run(project_id=project_id, turn_no=latest_turn.turn_no)
    bind_log_context(run_id=run.id)

    try:
        human_review_signal = payload.human_review.model_dump() if payload.human_review else None
        previous_stage = latest_turn.stage
        previous_question_text = latest_turn.question_text
        previous_version_no = latest_turn.current_question_version_no
        previous_regeneration_count = latest_turn.question_regeneration_count
        corrected_stage = normalize_stage_name((human_review_signal or {}).get("phase")) if human_review_signal else None
        if human_review_signal and human_review_signal.get("phase") and not corrected_stage:
            raise HTTPException(status_code=400, detail="Invalid stage correction for current question regeneration")

        turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.project_id == project_id)
            .order_by(InterviewTurn.turn_no.asc())
            .all()
        )
        if latest_turn.turn_no == 1:
            effective_stage = corrected_stage or latest_turn.stage
            generation_payload = generate_question_for_state(
                current_stage=effective_stage,
                db=db,
                human_review_signal=human_review_signal,
                latest_answer_override=None,
                project=project,
                run_id=run.id,
                turn_no=latest_turn.turn_no,
                turns=turns,
            )
        else:
            source_turns = turns[:-1]
            if not source_turns or source_turns[-1].answer_text is None:
                raise HTTPException(
                    status_code=400,
                    detail="Current question can only be regenerated from the previous answered turn.",
                )
            source_turn = source_turns[-1]
            source_coverage_state = rebuild_coverage_state(source_turns)
            stage_decision = decide_next_stage(
                next_turn_no=latest_turn.turn_no,
                coverage_state=source_coverage_state,
                current_stage=source_turn.stage,
                max_turns=settings.interview_max_turns,
                human_review_signal=human_review_signal,
            )
            effective_stage = corrected_stage or stage_decision["next_stage"]
            generation_payload = draft_question_from_answered_history(
                db=db,
                project=project,
                turns=source_turns,
                latest_answer_text=source_turn.answer_text,
                next_turn_no=latest_turn.turn_no,
                next_stage=effective_stage,
                human_review_signal=human_review_signal,
                run_id=run.id,
                include_latest_answer_in_coverage=False,
            )

        ensure_initial_question_version(db, latest_turn)
        latest_turn.stage = effective_stage
        latest_turn.question_text = generation_payload["generated_question"]
        latest_turn.question_plan_json = build_question_plan_json(generation_payload)
        latest_turn.human_review_json = (
            json.dumps(human_review_signal, ensure_ascii=True, sort_keys=True)
            if human_review_signal
            else None
        )
        project.current_stage = effective_stage

        for usage_metrics in generation_payload["question_usage_metrics"]:
            db.add(
                create_usage_record(
                    project_id=project.id,
                    turn_id=latest_turn.id,
                    operation_type="question_regeneration",
                    usage_metrics=usage_metrics,
                )
            )

        usage_summary = summarize_usage_metrics(generation_payload["question_usage_metrics"])
        append_question_version(
            db=db,
            turn=latest_turn,
            generation_kind="human_regeneration",
            human_review_signal=human_review_signal,
            question_plan_json=latest_turn.question_plan_json,
            question_text=latest_turn.question_text,
            usage_metrics_list=generation_payload["question_usage_metrics"],
        )

        db.commit()
        db.refresh(latest_turn)
    except HTTPException:
        finalize_run(run_id=run.id, status="failed")
        raise
    except ValueError as exc:
        finalize_run(run_id=run.id, status="failed")
        emit_event(
            "workflow",
            "turn.regenerate.error",
            "Current question regeneration failed validation",
            level=40,
            operation="regenerate_current_question",
            project_id=project_id,
            turn_no=latest_turn.turn_no,
            exc_info=exc,
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except ImportError as exc:
        finalize_run(run_id=run.id, status="failed")
        emit_event(
            "workflow",
            "turn.regenerate.error",
            "Current question regeneration failed due to LLM client configuration",
            level=40,
            operation="regenerate_current_question",
            project_id=project_id,
            turn_no=latest_turn.turn_no,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Question regeneration is temporarily unavailable because the LLM client "
                "could not be initialized. Check proxy settings or install the optional "
                "SOCKS dependency for httpx."
            ),
        )
    except Exception as exc:
        finalize_run(run_id=run.id, status="failed")
        emit_event(
            "workflow",
            "turn.regenerate.error",
            "Current question regeneration failed",
            level=40,
            operation="regenerate_current_question",
            project_id=project_id,
            turn_no=latest_turn.turn_no,
            exc_info=exc,
        )
        raise

    finalize_run(run_id=run.id, status="completed", turn_no=latest_turn.turn_no)

    return {
        "project_id": project_id,
        "turn": latest_turn,
        "run_id": run.id,
        "usage_summary": {
            "prompt_tokens": usage_summary["prompt_tokens"],
            "completion_tokens": usage_summary["completion_tokens"],
            "total_tokens": usage_summary["total_tokens"],
            "estimated_total_tokens": usage_summary["total_tokens"] if usage_summary["is_estimated"] else 0,
        },
        "applied_changes": {
            "review_persisted": bool(latest_turn.human_review),
            "planner_followed_review": bool((latest_turn.question_plan or {}).get("human_review_applied")),
            "question_changed": latest_turn.question_text != previous_question_text,
            "previous_stage": previous_stage,
            "current_stage": latest_turn.stage,
            "stage_changed": latest_turn.stage != previous_stage,
            "requested_focus": (human_review_signal or {}).get("preferred_next_focus"),
            "requested_verdict": (human_review_signal or {}).get("verdict"),
            "requested_direction": (human_review_signal or {}).get("direction"),
            "note_applied": bool((human_review_signal or {}).get("note")),
            "phase_ready_applied": bool((human_review_signal or {}).get("phase_ready")),
            "question_version_before": previous_version_no,
            "question_version_after": latest_turn.current_question_version_no,
            "regeneration_count_before": previous_regeneration_count,
            "regeneration_count_after": latest_turn.question_regeneration_count,
        },
        "message": "Current question refreshed from the previous answer successfully.",
    }


@router.post("/{project_id}/next", response_model=ProjectNextResponse)
def submit_answer_and_generate_next(
    project_id: int,
    payload: NextQuestionRequest,
    db: Session = Depends(get_db),
):
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
    if project.pending_gate and not payload.human_gate:
        raise HTTPException(
            status_code=409,
            detail="Resolve the pending human gate before generating the next question.",
        )
    if payload.human_gate and project.pending_gate:
        if payload.human_gate.gate_id != project.pending_gate.get("gate_id"):
            raise HTTPException(status_code=400, detail="Human gate resolution does not match the active gate.")
    run = create_run(
        project_id=project_id,
        turn_no=(latest_turn.turn_no + 1) if latest_turn else None,
    )
    bind_log_context(run_id=run.id)

    try:
        emit_event(
            "workflow",
            "workflow.invoke.start",
            "Invoking interview workflow",
            operation="submit_answer_and_generate_next",
            project_id=project_id,
            input=preview_payload(latest_turn.answer_text, artifact_category="answers", artifact_name=f"workflow-input-project-{project_id}"),
        )
        result = interview_graph.invoke(
            {
                "run_id": run.id,
                "project_id": project_id,
                "answer_text": latest_turn.answer_text,
                "human_review_signal": payload.human_review.model_dump() if payload.human_review else None,
                "human_gate_resolution": payload.human_gate.model_dump() if payload.human_gate else None,
            },
            config={"configurable": {"thread_id": f"project-{project_id}"}},
        )
    except ValueError as e:
        finalize_run(run_id=run.id, status="failed")
        emit_event(
            "workflow",
            "workflow.invoke.error",
            "Interview workflow failed",
            level=40,
            operation="submit_answer_and_generate_next",
            project_id=project_id,
            exc_info=e,
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        finalize_run(run_id=run.id, status="failed")
        emit_event(
            "workflow",
            "workflow.invoke.error",
            "Interview workflow failed",
            level=40,
            operation="submit_answer_and_generate_next",
            project_id=project_id,
            exc_info=e,
        )
        raise

    db.expire_all()
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
    elif (
        result.get("pending_gate_active")
        or updated_project.pending_gate
        or (latest_turn and latest_turn.answer_text is not None)
    ):
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
    if previous_turn is None:
        previous_turn = latest_turn

    emit_event(
        "workflow",
        "workflow.invoke.complete",
        "Interview workflow completed",
        operation="submit_answer_and_generate_next",
        status="success",
        project_id=project_id,
        turn_no=latest_turn.turn_no if latest_turn else None,
        stage=latest_turn.stage if latest_turn else None,
        output={
            "interview_finished": result.get("interview_finished", False),
            "selected_branch_ids": result.get("selected_branch_ids", []),
        },
    )
    finalize_run(
        run_id=run.id,
        status="completed",
        turn_no=(next_turn.turn_no if next_turn else previous_turn.turn_no if previous_turn else None),
    )

    return {
        "project": updated_project,
        "previous_turn": previous_turn,
        "next_turn": next_turn,
        "run_id": run.id,
        "interview_finished": result.get("interview_finished", False),
        "minimum_goal_reached": result.get("minimum_goal_reached", False),
        "usage_summary": aggregate_project_usage(updated_project.llm_usages),
        "message": result.get("message", ""),
    }


@router.get("/{project_id}/runs", response_model=list[RunRead])
def list_project_runs(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    runs = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id)
        .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
        .all()
    )
    return [serialize_run(run) for run in runs]


@router.get("/{project_id}/runs/latest", response_model=RunRead)
def get_latest_project_run(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    run = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id)
        .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize_run(run)


@router.get("/{project_id}/runs/{run_id}", response_model=RunRead)
def get_project_run(project_id: int, run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id, AgentRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize_run(run)


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
    mutated = False
    for turn in turns:
        before_text = turn.question_text
        before_version_snapshot = [
            (version.id, version.version_no, version.generation_kind, version.question_text)
            for version in turn.question_versions
        ]
        normalized_versions = normalize_question_versions(db, turn)
        after_version_snapshot = [
            (version.id, version.version_no, version.generation_kind, version.question_text)
            for version in normalized_versions
        ]
        if turn.question_text != before_text or after_version_snapshot != before_version_snapshot:
            mutated = True
    if mutated:
        db.commit()
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
    if latest_turn:
        normalize_question_versions(db, latest_turn)
        db.commit()
        db.refresh(latest_turn)

    return {
        "project_id": project.id,
        "project_name": project.project_name,
        "status": project.status,
        "current_stage": project.current_stage,
        "turn_count": project.turn_count,
        "answer_provider_type": project.answer_provider_type,
        "answer_automation_enabled": project.answer_automation_enabled,
        "minimum_goal_reached": is_minimum_goal_reached(project.turn_count),
        "max_turn_limit": settings.interview_max_turns,
        "latest_turn_no": latest_turn.turn_no if latest_turn else None,
        "latest_turn_answered": (
            (latest_turn.answer_text is not None) if latest_turn else None
        ),
        "latest_turn_ready_for_next_generation": (
            bool(latest_turn and latest_turn.answer_text is not None and project.status != "finished")
        ),
        "latest_question_text": latest_turn.question_text if latest_turn else None,
        "latest_question_text_for_copy": (
            latest_turn.question_text_for_copy if latest_turn else None
        ),
        "latest_turn_regeneration_count": (
            latest_turn.question_regeneration_count if latest_turn else 0
        ),
        "latest_human_intervention_regeneration_usage_summary": (
            latest_turn.human_intervention_regeneration_usage_summary
            if latest_turn
            else aggregate_project_usage([])
        ),
        "cumulative_generation_time_ms": project.cumulative_generation_time_ms,
        "run_count": project.run_count,
        "average_run_duration_ms": project.average_run_duration_ms,
        "repository": project.repository,
        "repository_manifest": project.repository_manifest,
        "usage_summary": aggregate_project_usage(project.llm_usages),
    }
