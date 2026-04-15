from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ManifestRow:
    run_id: str
    repo_id: str
    task_id: str
    system_id: str
    system_config_id: str
    db_snapshot_path: str
    logs_root: str
    task_file: str


@dataclass
class RepoRow:
    repo_id: str
    repo_label: str
    repo_path_or_url: str
    repo_snapshot_ref: str


SUPPORTED_SYSTEMS = {"full_system", "stateless_qa", "no_human_review"}
AUTO_GATE_LOOP_LIMIT = 8


def load_manifest_row(run_manifest: Path, run_id: str) -> ManifestRow:
    with run_manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("run_id") or "").strip() != run_id:
                continue
            return ManifestRow(
                run_id=run_id,
                repo_id=(row.get("repo_id") or "").strip(),
                task_id=(row.get("task_id") or "").strip(),
                system_id=(row.get("system_id") or "").strip(),
                system_config_id=(row.get("system_config_id") or "").strip(),
                db_snapshot_path=(row.get("db_snapshot_path") or "").strip(),
                logs_root=(row.get("logs_root") or "").strip(),
                task_file=(row.get("task_file") or "").strip(),
            )
    raise ValueError(f"Run id not found in manifest: {run_id}")


def resolve_condition_id(row: ManifestRow) -> str:
    candidate = row.system_config_id or row.system_id
    if candidate in SUPPORTED_SYSTEMS:
        return candidate
    raise ValueError(
        f"Unsupported system condition for run {row.run_id}: system_id={row.system_id!r}, "
        f"system_config_id={row.system_config_id!r}"
    )


def configure_runtime_from_manifest(row: ManifestRow, run_manifest: Path) -> None:
    workspace_root = _workspace_root_from_manifest(run_manifest)
    if row.db_snapshot_path:
        db_path = (workspace_root / Path(row.db_snapshot_path)).expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    if row.logs_root:
        logs_root = (workspace_root / Path(row.logs_root)).expanduser().resolve()
        logs_root.mkdir(parents=True, exist_ok=True)
        os.environ["LOG_DIR"] = str(logs_root)


def infer_project_id_from_sqlite(db_snapshot_path: str) -> int:
    db_path = Path(db_snapshot_path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30)
    try:
        rows = connection.execute(
            "select id from project_sessions order by updated_at desc, id desc"
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        raise ValueError(f"No project_sessions rows found in {db_path}")
    if len(rows) > 1:
        raise ValueError(
            f"Multiple projects found in {db_path}; rerun with --project-id to disambiguate"
        )
    return int(rows[0][0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment runner dispatch for interview-generation conditions."
    )
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--system-id", default=None, choices=sorted(SUPPORTED_SYSTEMS))
    parser.add_argument("--run-manifest", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def _workspace_root_from_manifest(run_manifest: Path) -> Path:
    return run_manifest.expanduser().resolve().parent.parent


def _resolve_manifest_relative_path(run_manifest: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    workspace_root = _workspace_root_from_manifest(run_manifest)
    workspace_candidate = (workspace_root / path).resolve()
    if workspace_candidate.exists():
        return workspace_candidate
    return (run_manifest.parent / path).resolve()


def _load_repo_row(run_manifest: Path, repo_id: str) -> RepoRow:
    repos_path = (run_manifest.parent / "repos.csv").resolve()
    with repos_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("repo_id") or "").strip() != repo_id:
                continue
            return RepoRow(
                repo_id=repo_id,
                repo_label=(row.get("repo_label") or repo_id).strip(),
                repo_path_or_url=(row.get("repo_path_or_url") or "").strip(),
                repo_snapshot_ref=(row.get("repo_snapshot_ref") or "").strip(),
            )
    raise ValueError(f"repo_id not found in repos.csv: {repo_id}")


def _extract_yaml_scalar(text: str, key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip().strip('"')


def _extract_yaml_block(text: str, key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}:\s*>\s*$\n((?:^[ \t].*$\n?)*)", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    lines = [line.strip() for line in match.group(1).splitlines()]
    return " ".join(line for line in lines if line).strip() or None


def _load_task_metadata(run_manifest: Path, task_file: str) -> dict[str, str]:
    task_path = _resolve_manifest_relative_path(run_manifest, task_file)
    raw = task_path.read_text(encoding="utf-8")
    task_label = _extract_yaml_scalar(raw, "task_label") or Path(task_file).stem
    objective = _extract_yaml_block(raw, "objective") or "Understand the repository implementation in a structured interview."
    operator_role = _extract_yaml_scalar(raw, "operator_role") or "Technical reviewer"
    return {
        "task_label": task_label,
        "objective": objective,
        "operator_role": operator_role,
    }


def _build_system_prompt(*, repo: RepoRow, task_meta: dict[str, str]) -> str:
    return (
        f"You are {task_meta['operator_role']}. "
        f"Repository under review: {repo.repo_label}. "
        f"Task: {task_meta['task_label']}. "
        f"Objective: {task_meta['objective']}"
    )


def _make_mock_answer(*, task_meta: dict[str, str], question_text: str, repo: RepoRow) -> str:
    return (
        f"Mock execution answer for task {task_meta['task_label']} on repo {repo.repo_label}. "
        f"Current question: {question_text} "
        f"Primary objective reminder: {task_meta['objective']}"
    )


def ensure_project_initialized(*, run_manifest: Path, row: ManifestRow) -> int:
    from app.api.routes.projects import start_project_interview
    from app.core.database import SessionLocal, ensure_database_schema
    from app.logging import bind_log_context, emit_event
    from app.models.project import ProjectSession
    from app.models.turn import InterviewTurn
    from app.schemas.project import ProjectCreate
    from app.services.opencode_execution_service import persist_turn_answer
    from app.services.repository_service import apply_repository_configuration, resolve_project_repository
    from app.services.rubric_task_service import initialize_task_board, serialize_task_board

    ensure_database_schema()
    repo = _load_repo_row(run_manifest, row.repo_id)
    task_meta = _load_task_metadata(run_manifest, row.task_file)

    db = SessionLocal()
    try:
        project = db.query(ProjectSession).order_by(ProjectSession.id.asc()).first()
        if project is None:
            project = ProjectSession(
                project_name=f"{row.task_id}:{row.system_config_id or row.system_id}",
                system_prompt=_build_system_prompt(repo=repo, task_meta=task_meta),
                agent_mode="understand_current_code",
                answer_provider_type="manual",
                answer_automation_enabled=False,
                rubric_task_board=serialize_task_board(initialize_task_board()),
            )
            db.add(project)
            db.flush()
            apply_repository_configuration(
                project,
                {
                    "source_type": "local_path",
                    "local_path": repo.repo_path_or_url,
                    "git_ref": repo.repo_snapshot_ref,
                },
            )
            resolve_project_repository(project)
            db.commit()
            db.refresh(project)
            bind_log_context(project_id=project.id)
            emit_event(
                "persistence",
                "experiment.runner.project_initialized",
                "Initialized project automatically from run manifest",
                operation="ensure_project_initialized",
                project_id=project.id,
                output={"repo_id": row.repo_id, "task_id": row.task_id},
            )

        latest_turn = None
        if project.turn_count == 0:
            started = start_project_interview(project_id=project.id, db=db)
            project = started["project"]
            latest_turn = started["first_turn"]
        else:
            latest_turn = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.project_id == project.id)
                .order_by(InterviewTurn.turn_no.desc())
                .first()
            )

        if latest_turn is not None and latest_turn.answer_text is None:
            persist_turn_answer(
                db=db,
                project=project,
                turn=latest_turn,
                answer_text=_make_mock_answer(
                    task_meta=task_meta,
                    question_text=latest_turn.question_text,
                    repo=repo,
                ),
            )
            db.commit()
            db.refresh(project)
        return int(project.id)
    finally:
        db.close()


def _auto_gate_payload(project: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    pending_gate = project.pending_gate
    if not pending_gate:
        return None, None
    default_action = pending_gate.get("default_action") or "continue"
    review_signal = {
        "verdict": "sufficient",
        "direction": "continue",
        "note": "Review Approved",
    }
    gate_resolution = {
        "gate_id": pending_gate["gate_id"],
        "action": default_action,
        "note": "Review Approved",
    }
    return review_signal, gate_resolution


def run_next_turn(*, project_id: int, system_id: str) -> dict:
    from app.api.routes.projects import submit_answer_and_generate_next
    from app.baselines.stateless_qa import submit_answer_and_generate_next_stateless
    from app.core.database import SessionLocal, ensure_database_schema
    from app.logging import bind_log_context, emit_event
    from app.models.project import ProjectSession
    from app.models.turn import InterviewTurn
    from app.schemas.turn import HumanGateResolutionInput, HumanReviewInput, NextQuestionRequest

    ensure_database_schema()
    db = SessionLocal()
    try:
        bind_log_context(project_id=project_id)
        emit_event(
            "workflow",
            "experiment.runner.dispatch",
            "Dispatching experiment runner condition",
            operation="run_next_turn",
            project_id=project_id,
            output={"system_id": system_id},
        )
        if system_id == "stateless_qa":
            # Get project first
            project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            
            # Ensure latest turn has an answer before generating next question
            latest_turn = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.project_id == project_id)
                .order_by(InterviewTurn.turn_no.desc())
                .first()
            )
            if latest_turn and latest_turn.answer_text is None:
                # Save a mock answer
                from app.services.opencode_execution_service import persist_turn_answer
                persist_turn_answer(
                    db=db,
                    project=project,
                    turn=latest_turn,
                    answer_text="Mock answer for stateless_qa run",
                )
                db.commit()
            
            return submit_answer_and_generate_next_stateless(project_id=project_id, db=db)
        if system_id == "full_system":
            # Get project first
            project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            
            # Ensure latest turn has an answer before generating next question
            latest_turn = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.project_id == project_id)
                .order_by(InterviewTurn.turn_no.desc())
                .first()
            )
            if latest_turn and latest_turn.answer_text is None:
                # Save a mock answer
                from app.services.opencode_execution_service import persist_turn_answer
                persist_turn_answer(
                    db=db,
                    project=project,
                    turn=latest_turn,
                    answer_text="Mock answer for full_system run",
                )
                db.commit()
            
            return submit_answer_and_generate_next(
                project_id=project_id,
                payload=NextQuestionRequest(),
                db=db,
            )
        if system_id == "no_human_review":
            payload = NextQuestionRequest()
            for _ in range(AUTO_GATE_LOOP_LIMIT):
                # First save a mock answer, then generate next question
                from app.services.opencode_execution_service import persist_turn_answer
                from app.models.turn import InterviewTurn
                
                db.expire_all()
                project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
                if not project:
                    raise RuntimeError("Project not found")
                
                # Get the latest turn that needs an answer
                latest_turn = (
                    db.query(InterviewTurn)
                    .filter(InterviewTurn.project_id == project_id)
                    .order_by(InterviewTurn.turn_no.desc())
                    .first()
                )
                
                if latest_turn and latest_turn.answer_text is None:
                    # Save a mock answer
                    persist_turn_answer(
                        db=db,
                        project=project,
                        turn=latest_turn,
                        answer_text="Mock answer for automatic gate resolution",
                    )
                    db.commit()
                
                # Now generate the next question
                result = submit_answer_and_generate_next(project_id=project_id, payload=payload, db=db)
                db.expire_all()
                project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
                
                if result.get("interview_finished") or not project or not project.pending_gate:
                    return result
                
                review_signal, gate_resolution = _auto_gate_payload(project)
                payload = NextQuestionRequest(
                    human_review=HumanReviewInput(**review_signal) if review_signal else None,
                    human_gate=HumanGateResolutionInput(**gate_resolution) if gate_resolution else None,
                )
            raise RuntimeError("no_human_review exceeded automatic gate resolution limit")
        raise ValueError(f"Unsupported system_id: {system_id}")
    finally:
        db.close()


def main() -> int:
    args = parse_args()

    if args.run_manifest and args.run_id:
        manifest_row = load_manifest_row(args.run_manifest, args.run_id)
        configure_runtime_from_manifest(manifest_row, args.run_manifest)
        system_id = resolve_condition_id(manifest_row)
        project_id = args.project_id
        if project_id is None:
            try:
                project_id = infer_project_id_from_sqlite(manifest_row.db_snapshot_path)
            except ValueError:
                project_id = ensure_project_initialized(run_manifest=args.run_manifest, row=manifest_row)
    else:
        if args.project_id is None or args.system_id is None:
            raise ValueError(
                "Either pass --project-id with --system-id, or pass --run-manifest with --run-id"
            )
        project_id = args.project_id
        system_id = args.system_id

    result = run_next_turn(project_id=project_id, system_id=system_id)
    print(
        json.dumps(
            {
                "run_id": result.get("run_id"),
                "message": result.get("message"),
                "system_id": system_id,
                "project_id": project_id,
            },
            ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
