#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sqlite3
import statistics
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable


DEFAULT_PROJECT_ROOT = Path("/Users/wyb/File/Programming/Git_Code/stateful_interview_agent")
DEFAULT_DB_PATH = DEFAULT_PROJECT_ROOT / "data" / "app.db"
DEFAULT_LOGS_ROOT = DEFAULT_PROJECT_ROOT / "logs"
DEFAULT_OUTPUT_DIR = Path("/Users/wyb/File/Study/agent_article/paper_agent_workspace/results")
DEFAULT_RUN_MANIFEST = Path(
    "/Users/wyb/File/Study/agent_article/paper_agent_workspace/experiment_assets/run_manifest_template.csv"
)

CORE_HEADERS = [
    "run_id",
    "project_id",
    "system_config",
    "total_turns",
    "framework_coverage_pct",
    "panorama_coverage_pct",
    "architecture_coverage_pct",
    "detail_coverage_pct",
    "use_cases_coverage_pct",
    "redundancy_rate",
    "avg_relevance_proxy_rate",
    "avg_coherence_proxy_rate",
    "turns_to_80pct_coverage",
    "total_duration_ms",
    "total_llm_tokens",
    "human_gate_count",
    "human_gate_rate",
]

TURN_HEADERS = [
    "run_id",
    "project_id",
    "turn_no",
    "stage",
    "question_relevance_proxy_rate",
    "redundancy_proxy_rate",
    "progressive_depth_proxy_rate",
    "coverage_delta",
    "repo_grounding_count",
    "human_review_present",
    "regenerated",
    "question_length_tokens",
    "answer_length_tokens",
    "llm_tokens_this_turn",
]

ABLATION_HEADERS = [
    "run_id",
    "project_id",
    "ablation_config",
    "framework_coverage_pct",
    "redundancy_rate",
    "avg_relevance_proxy_rate",
    "turns_to_80pct_coverage",
    "human_gate_rate",
]

REPO_STEP_KEYS = {"repo_manifest", "repo_search", "repo_read", "repo_trace"}

STAGE_ORDER = {
    "Panorama Mapping": 0,
    "Architecture Understanding": 1,
    "Code Detail Completion": 2,
    "Use Cases & Scenarios": 3,
    "Final Wrap-up": 4,
}


@dataclass
class ProjectRow:
    project_id: int
    current_stage: str | None
    turn_count: int | None
    status: str | None
    coverage_state: dict[str, Any]
    rubric_task_board: dict[str, Any]
    pending_gate: dict[str, Any] | None
    agent_mode: str | None


@dataclass
class TurnRow:
    turn_id: int
    project_id: int
    turn_no: int
    stage: str
    question_text: str
    question_plan: dict[str, Any] | None
    answer_text: str | None
    answer_summary: str | None
    answer_analysis: dict[str, Any] | None
    human_review: dict[str, Any] | None
    event_log: list[dict[str, Any]]


@dataclass
class RunRow:
    run_id: int
    project_id: int
    turn_no: int | None
    status: str
    duration_ms: int
    total_llm_tokens: int


@dataclass
class CoverageSnapshot:
    project_id: int
    run_id: int
    turn_no: int
    branch_count: int


@dataclass
class ManifestRow:
    run_id: str
    repo_id: str
    task_id: str
    system_id: str
    system_config_id: str
    replicate_id: str
    db_snapshot_path: str
    logs_root: str
    output_root: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Cycle 003 metrics from SQLite and structured logs.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--logs-root", type=Path, default=DEFAULT_LOGS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN_MANIFEST)
    parser.add_argument("--config", default=None, help="Optional ablation config filter for one-off exports.")
    parser.add_argument("--output", type=Path, default=None, help="Optional single-output CSV path when --config is used.")
    return parser.parse_args()


def warn(message: str) -> None:
    print(f"[extract_metrics] {message}", file=sys.stderr)


def parse_json_object(raw: str | None, *, default: Any) -> Any:
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return default
    return parsed if isinstance(parsed, type(default)) else default


def iter_jsonl_events(logs_root: Path) -> list[dict[str, Any]]:
    if not logs_root.exists():
        return []
    events: list[dict[str, Any]] = []
    for path in sorted(logs_root.rglob("*.jsonl")):
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            warn(f"Skipping unreadable log file {path}: {exc}")
            continue
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                warn(f"Skipping malformed JSON log line in {path}")
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events


def normalize_path_string(raw: str | None) -> str:
    if not raw:
        return ""
    return str(Path(raw).expanduser().resolve(strict=False))


def load_run_manifest(path: Path) -> list[ManifestRow]:
    if not path.exists():
        return []
    rows: list[ManifestRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row:
                continue
            rows.append(
                ManifestRow(
                    run_id=str(row.get("run_id") or "").strip(),
                    repo_id=str(row.get("repo_id") or "").strip(),
                    task_id=str(row.get("task_id") or "").strip(),
                    system_id=str(row.get("system_id") or "").strip(),
                    system_config_id=str(row.get("system_config_id") or "").strip(),
                    replicate_id=str(row.get("replicate_id") or "").strip(),
                    db_snapshot_path=str(row.get("db_snapshot_path") or "").strip(),
                    logs_root=str(row.get("logs_root") or "").strip(),
                    output_root=str(row.get("output_root") or "").strip(),
                )
            )
    return rows


def select_manifest_row(
    rows: list[ManifestRow],
    *,
    db_path: Path,
    logs_root: Path,
    output_dir: Path,
) -> ManifestRow | None:
    if not rows:
        return None
    target_db = normalize_path_string(str(db_path))
    target_logs = normalize_path_string(str(logs_root))
    target_output = normalize_path_string(str(output_dir))
    best: ManifestRow | None = None
    best_score = -1
    for row in rows:
        score = 0
        if normalize_path_string(row.db_snapshot_path) == target_db:
            score += 3
        if normalize_path_string(row.logs_root) == target_logs:
            score += 3
        if normalize_path_string(row.output_root) == target_output:
            score += 2
        if score > best_score:
            best = row
            best_score = score
    if best_score > 0:
        return best
    if len(rows) == 1:
        return rows[0]
    return None


def load_projects(connection: sqlite3.Connection) -> list[ProjectRow]:
    rows = connection.execute(
        """
        select id, current_stage, turn_count, status, coverage_state, rubric_task_board, pending_gate_json, agent_mode
        from project_sessions
        order by id asc
        """
    ).fetchall()
    return [
        ProjectRow(
            project_id=int(row[0]),
            current_stage=row[1],
            turn_count=int(row[2]) if row[2] is not None else None,
            status=row[3],
            coverage_state=parse_json_object(row[4], default={}),
            rubric_task_board=parse_json_object(row[5], default={}),
            pending_gate=parse_json_object(row[6], default={}) if row[6] not in (None, "null", "") else None,
            agent_mode=row[7],
        )
        for row in rows
    ]


def load_turns(connection: sqlite3.Connection) -> list[TurnRow]:
    rows = connection.execute(
        """
        select id, project_id, turn_no, stage, question_text, question_plan_json, answer_text,
               answer_summary, answer_analysis_json, human_review_json, event_log_json
        from interview_turns
        order by project_id asc, turn_no asc, id asc
        """
    ).fetchall()
    return [
        TurnRow(
            turn_id=int(row[0]),
            project_id=int(row[1]),
            turn_no=int(row[2]),
            stage=str(row[3]),
            question_text=str(row[4] or ""),
            question_plan=parse_json_object(row[5], default={}) if row[5] else None,
            answer_text=row[6],
            answer_summary=row[7],
            answer_analysis=parse_json_object(row[8], default={}) if row[8] else None,
            human_review=parse_json_object(row[9], default={}) if row[9] else None,
            event_log=parse_json_object(row[10], default=[]),
        )
        for row in rows
    ]


def load_runs(connection: sqlite3.Connection) -> list[RunRow]:
    rows = connection.execute(
        """
        select id, project_id, turn_no, status, duration_ms, total_llm_tokens
        from agent_runs
        where status = 'completed'
        order by project_id asc, coalesce(turn_no, 0) asc, id asc
        """
    ).fetchall()
    return [
        RunRow(
            run_id=int(row[0]),
            project_id=int(row[1]),
            turn_no=int(row[2]) if row[2] is not None else None,
            status=str(row[3]),
            duration_ms=int(row[4] or 0),
            total_llm_tokens=int(row[5] or 0),
        )
        for row in rows
    ]


def load_repo_grounding_counts(connection: sqlite3.Connection) -> dict[int, int]:
    rows = connection.execute(
        """
        select run_id, count(*)
        from agent_run_steps
        where step_key in ('repo_manifest', 'repo_search', 'repo_read', 'repo_trace')
        group by run_id
        """
    ).fetchall()
    return {int(run_id): int(count) for run_id, count in rows}


def load_regeneration_counts(connection: sqlite3.Connection) -> dict[int, int]:
    rows = connection.execute(
        """
        select turn_id, count(*)
        from interview_question_versions
        group by turn_id
        """
    ).fetchall()
    return {int(turn_id): int(count) for turn_id, count in rows}


def load_llm_tokens_by_turn(connection: sqlite3.Connection) -> dict[int, int]:
    rows = connection.execute(
        """
        select turn_id, sum(total_tokens)
        from llm_usages
        where turn_id is not null
        group by turn_id
        """
    ).fetchall()
    return {int(turn_id): int(total or 0) for turn_id, total in rows}


def normalize_text(text: str) -> str:
    import re

    normalized = text.lower().strip()
    normalized = re.sub(r"^q\d+[:.]\s*", "", normalized)
    normalized = re.sub(r"\*+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def similarity_score(text: str, previous: str) -> float:
    return SequenceMatcher(None, normalize_text(text), normalize_text(previous)).ratio()


def fallback_is_question_too_similar(new_question: str, old_questions: list[str], threshold: float = 0.82) -> bool:
    return any(similarity_score(new_question, old) >= threshold for old in old_questions)


def load_repetition_guard(project_root: Path) -> Callable[[str, list[str]], bool]:
    module_path = project_root / "app" / "services" / "repetition_guard.py"
    if not module_path.exists():
        return fallback_is_question_too_similar
    sys.path.insert(0, str(project_root))
    try:
        spec = importlib.util.spec_from_file_location("cycle003_repetition_guard", module_path)
        if spec is None or spec.loader is None:
            return fallback_is_question_too_similar
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = getattr(module, "is_question_too_similar", None)
        if callable(fn):
            return fn
    except Exception as exc:
        warn(f"Falling back to local redundancy heuristic because repetition_guard import failed: {exc}")
    return fallback_is_question_too_similar


def round_str(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return ""
    return f"{value:.{decimals}f}"


def pct_from_bools(section: dict[str, Any]) -> float:
    if not section:
        return 0.0
    values = [bool(value) for value in section.values()]
    if not values:
        return 0.0
    return 100.0 * sum(values) / len(values)


def pct_from_counts(section: dict[str, Any]) -> float:
    if not section:
        return 0.0
    numeric_values = [value for value in section.values() if isinstance(value, (int, float))]
    if not numeric_values:
        return 0.0
    return 100.0 * sum(1 for value in numeric_values if value > 0) / len(numeric_values)


def framework_coverage_pct(coverage_state: dict[str, Any]) -> float:
    branches = coverage_state.get("branches", [])
    if not branches:
        return 0.0
    counted = sum(
        1
        for branch in branches
        if str(branch.get("status") or "") in {"covered", "needs_follow_up"}
    )
    return 100.0 * counted / len(branches)


def token_count(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


def count_human_gate_events(turn: TurnRow) -> int:
    count = 0
    for event in turn.event_log:
        if str(event.get("event_type") or "") == "human_gate":
            count += 1
    return count


def has_human_review(turn: TurnRow) -> bool:
    if turn.human_review:
        return True
    return any(str(event.get("event_type") or "") == "human_review" for event in turn.event_log)


def progressive_depth_proxy_rate(
    stage: str,
    previous_stage: str | None,
    redundancy_proxy_rate: float,
    coverage_delta: float,
) -> float:
    if previous_stage is None:
        return 4.0 if STAGE_ORDER.get(stage, 0) == 0 else 3.0
    current_rank = STAGE_ORDER.get(stage, 0)
    previous_rank = STAGE_ORDER.get(previous_stage, 0)
    if current_rank < previous_rank:
        return 1.0
    if current_rank - previous_rank > 1:
        return 2.0
    if redundancy_proxy_rate >= 0.82:
        return 2.0
    if coverage_delta > 0:
        return 5.0 if current_rank >= previous_rank else 4.0
    return 3.0


def relevance_proxy_rate(coverage_delta: float, redundancy_proxy_rate: float) -> float:
    if coverage_delta >= 20.0:
        return 5.0
    if coverage_delta >= 10.0:
        return 4.0
    if coverage_delta > 0.0:
        return 3.0
    if redundancy_proxy_rate >= 0.82:
        return 1.0
    return 2.0


def select_branch_snapshots(events: list[dict[str, Any]]) -> tuple[dict[tuple[int, int], CoverageSnapshot], dict[int, int]]:
    by_turn: dict[tuple[int, int], CoverageSnapshot] = {}
    run_to_turn: dict[int, int] = {}
    for event in events:
        event_name = str(event.get("event") or "")
        if event_name not in {"coverage.persist.complete", "coverage.refresh.complete", "workflow.persist.complete"}:
            continue
        run_id = event.get("run_id")
        project_id = event.get("project_id")
        if not isinstance(run_id, int) or not isinstance(project_id, int):
            continue
        output = event.get("output") or {}
        turn_no = event.get("turn_no")
        if not isinstance(turn_no, int):
            latest_answer_turn = output.get("latest_answer_turn")
            turn_no = latest_answer_turn if isinstance(latest_answer_turn, int) else None
        if not isinstance(turn_no, int):
            continue
        run_to_turn[run_id] = turn_no
        branch_count = output.get("branch_count")
        if not isinstance(branch_count, int):
            continue
        key = (project_id, turn_no)
        snapshot = CoverageSnapshot(project_id=project_id, run_id=run_id, turn_no=turn_no, branch_count=branch_count)
        current = by_turn.get(key)
        if current is None or event_name == "coverage.persist.complete":
            by_turn[key] = snapshot
    return by_turn, run_to_turn


def build_turn_rows(
    projects: list[ProjectRow],
    turns: list[TurnRow],
    runs: list[RunRow],
    repo_grounding_by_run: dict[int, int],
    regeneration_counts: dict[int, int],
    llm_tokens_by_turn: dict[int, int],
    coverage_snapshots: dict[tuple[int, int], CoverageSnapshot],
    run_to_answer_turn: dict[int, int],
    similarity_fn: Callable[[str, list[str]], bool],
    extraction_run_id: str,
    system_config: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    project_map = {project.project_id: project for project in projects}
    runs_by_project: dict[int, list[RunRow]] = {}
    for run in runs:
        runs_by_project.setdefault(run.project_id, []).append(run)
    run_by_project_turn: dict[tuple[int, int], RunRow] = {}
    for run in runs:
        answer_turn = run_to_answer_turn.get(run.run_id)
        if answer_turn is not None:
            run_by_project_turn[(run.project_id, answer_turn)] = run

    turns_by_project: dict[int, list[TurnRow]] = {}
    for turn in turns:
        turns_by_project.setdefault(turn.project_id, []).append(turn)

    per_turn_rows: list[dict[str, Any]] = []
    core_rows: list[dict[str, Any]] = []

    for project_id, project_turns in sorted(turns_by_project.items()):
        project = project_map.get(project_id)
        prior_questions: list[str] = []
        previous_stage: str | None = None
        previous_branch_count = 0
        final_branch_count = max(1, len((project.coverage_state or {}).get("branches", []))) if project else 1
        turns_to_80pct: int | None = None
        relevance_values: list[float] = []
        coherence_values: list[float] = []
        redundant_count = 0
        human_gate_count = 0

        for turn in project_turns:
            redundancy_proxy_rate = 0.0
            if prior_questions:
                redundancy_proxy_rate = max(similarity_score(turn.question_text, old) for old in prior_questions)
            if similarity_fn(turn.question_text, prior_questions):
                redundant_count += 1
            prior_questions.append(turn.question_text)

            snapshot = coverage_snapshots.get((project_id, turn.turn_no))
            current_branch_count = snapshot.branch_count if snapshot else previous_branch_count
            coverage_delta = 100.0 * max(0, current_branch_count - previous_branch_count) / final_branch_count
            previous_branch_count = current_branch_count

            if turns_to_80pct is None:
                observed_pct = 100.0 * current_branch_count / final_branch_count if final_branch_count else 0.0
                if observed_pct >= 80.0:
                    turns_to_80pct = turn.turn_no

            review_present = has_human_review(turn)
            human_gate_count += count_human_gate_events(turn)
            regenerated = 1 if regeneration_counts.get(turn.turn_id, 0) > 1 else 0
            llm_tokens_this_turn = llm_tokens_by_turn.get(turn.turn_id, 0)

            run = run_by_project_turn.get((project_id, turn.turn_no))
            repo_grounding_count = repo_grounding_by_run.get(run.run_id, 0) if run else 0

            relevance = relevance_proxy_rate(coverage_delta, redundancy_proxy_rate)
            coherence = progressive_depth_proxy_rate(
                turn.stage,
                previous_stage,
                redundancy_proxy_rate,
                coverage_delta,
            )
            previous_stage = turn.stage

            relevance_values.append(relevance)
            coherence_values.append(coherence)

            per_turn_rows.append(
                {
                    "run_id": extraction_run_id,
                    "project_id": str(project_id),
                    "turn_no": str(turn.turn_no),
                    "stage": turn.stage,
                    "question_relevance_proxy_rate": round_str(relevance),
                    "redundancy_proxy_rate": round_str(redundancy_proxy_rate),
                    "progressive_depth_proxy_rate": round_str(coherence),
                    "coverage_delta": round_str(coverage_delta),
                    "repo_grounding_count": str(repo_grounding_count),
                    "human_review_present": "1" if review_present else "0",
                    "regenerated": str(regenerated),
                    "question_length_tokens": str(token_count(turn.question_text)),
                    "answer_length_tokens": str(token_count(turn.answer_text)),
                    "llm_tokens_this_turn": str(llm_tokens_this_turn),
                }
            )

        project_runs = runs_by_project.get(project_id, [])
        total_turns = len(project_turns)
        total_duration_ms = sum(run.duration_ms for run in project_runs)
        total_llm_tokens = sum(run.total_llm_tokens for run in project_runs)
        coverage_state = project.coverage_state if project else {}
        framework = coverage_state.get("framework", {}) if isinstance(coverage_state, dict) else {}
        redundancy_rate = 100.0 * redundant_count / total_turns if total_turns else 0.0
        human_gate_rate = 100.0 * human_gate_count / total_turns if total_turns else 0.0

        core_rows.append(
            {
                "run_id": extraction_run_id,
                "project_id": str(project_id),
                "system_config": system_config,
                "total_turns": str(total_turns),
                "framework_coverage_pct": round_str(framework_coverage_pct(coverage_state)),
                "panorama_coverage_pct": round_str(pct_from_bools(framework.get("panorama", {}))),
                "architecture_coverage_pct": round_str(pct_from_bools(framework.get("architecture", {}))),
                "detail_coverage_pct": round_str(pct_from_counts(framework.get("code_detail", {}))),
                "use_cases_coverage_pct": round_str(pct_from_counts(framework.get("use_cases", {}))),
                "redundancy_rate": round_str(redundancy_rate),
                "avg_relevance_proxy_rate": round_str(statistics.mean(relevance_values) if relevance_values else 0.0),
                "avg_coherence_proxy_rate": round_str(statistics.mean(coherence_values) if coherence_values else 0.0),
                "turns_to_80pct_coverage": str(turns_to_80pct) if turns_to_80pct is not None else "",
                "total_duration_ms": str(total_duration_ms),
                "total_llm_tokens": str(total_llm_tokens),
                "human_gate_count": str(human_gate_count),
                "human_gate_rate": round_str(human_gate_rate),
            }
        )

    return core_rows, per_turn_rows


def mean_or_blank(rows: list[dict[str, Any]], key: str) -> str:
    values: list[float] = []
    for row in rows:
        raw = row.get(key, "")
        if raw in ("", None):
            continue
        values.append(float(raw))
    return round_str(statistics.mean(values)) if values else ""


def build_ablation_rows(core_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    run_id = core_rows[0]["run_id"] if core_rows else ""
    system_config = core_rows[0]["system_config"] if core_rows else "full_system"
    aggregate_full = {
        "run_id": run_id,
        "project_id": "aggregate",
        "ablation_config": system_config,
        "framework_coverage_pct": mean_or_blank(core_rows, "framework_coverage_pct"),
        "redundancy_rate": mean_or_blank(core_rows, "redundancy_rate"),
        "avg_relevance_proxy_rate": mean_or_blank(core_rows, "avg_relevance_proxy_rate"),
        "turns_to_80pct_coverage": mean_or_blank(core_rows, "turns_to_80pct_coverage"),
        "human_gate_rate": mean_or_blank(core_rows, "human_gate_rate"),
    }
    placeholders = [
        "no_planner",
        "no_coverage_state",
        "no_human_review",
        "no_retrieval",
    ]
    rows = [aggregate_full]
    for config in placeholders:
        rows.append(
            {
                "run_id": run_id,
                "project_id": "aggregate",
                "ablation_config": config,
                "framework_coverage_pct": "",
                "redundancy_rate": "",
                "avg_relevance_proxy_rate": "",
                "turns_to_80pct_coverage": "",
                "human_gate_rate": "",
            }
        )
    return rows


def write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def run_extraction(
    *,
    project_root: Path,
    db_path: Path,
    logs_root: Path,
    output_dir: Path,
    run_manifest: Path,
) -> dict[str, Path]:
    connection = sqlite3.connect(db_path)
    try:
        projects = load_projects(connection)
        turns = load_turns(connection)
        runs = load_runs(connection)
        repo_grounding_by_run = load_repo_grounding_counts(connection)
        regeneration_counts = load_regeneration_counts(connection)
        llm_tokens_by_turn = load_llm_tokens_by_turn(connection)
    finally:
        connection.close()

    similarity_fn = load_repetition_guard(project_root)
    manifest_rows = load_run_manifest(run_manifest)
    manifest_row = select_manifest_row(
        manifest_rows,
        db_path=db_path,
        logs_root=logs_root,
        output_dir=output_dir,
    )
    extraction_run_id = manifest_row.run_id if manifest_row and manifest_row.run_id else f"local-{db_path.stem}"
    system_config = (
        manifest_row.system_config_id
        if manifest_row and manifest_row.system_config_id
        else "full_system"
    )
    events = iter_jsonl_events(logs_root)
    coverage_snapshots, run_to_answer_turn = select_branch_snapshots(events)
    core_rows, turn_rows = build_turn_rows(
        projects=projects,
        turns=turns,
        runs=runs,
        repo_grounding_by_run=repo_grounding_by_run,
        regeneration_counts=regeneration_counts,
        llm_tokens_by_turn=llm_tokens_by_turn,
        coverage_snapshots=coverage_snapshots,
        run_to_answer_turn=run_to_answer_turn,
        similarity_fn=similarity_fn,
        extraction_run_id=extraction_run_id,
        system_config=system_config,
    )
    ablation_rows = build_ablation_rows(core_rows)

    core_path = output_dir / "metrics_core.csv"
    turns_path = output_dir / "metrics_turns.csv"
    ablations_path = output_dir / "metrics_ablations.csv"
    write_csv(core_path, CORE_HEADERS, core_rows)
    write_csv(turns_path, TURN_HEADERS, turn_rows)
    write_csv(ablations_path, ABLATION_HEADERS, ablation_rows)
    return {
        "metrics_core": core_path,
        "metrics_turns": turns_path,
        "metrics_ablations": ablations_path,
    }


def main() -> int:
    args = parse_args()
    outputs = run_extraction(
        project_root=args.project_root,
        db_path=args.db_path,
        logs_root=args.logs_root,
        output_dir=args.output_dir,
        run_manifest=args.run_manifest,
    )
    if args.config and args.output:
        connection = sqlite3.connect(args.db_path)
        connection.close()
        with outputs["metrics_ablations"].open(newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if row["ablation_config"] == args.config]
        write_csv(args.output, ABLATION_HEADERS, rows)
        print(f"Wrote filtered ablation CSV to {args.output}")
    else:
        print(
            "Wrote metrics to "
            f"{outputs['metrics_core']}, {outputs['metrics_turns']}, {outputs['metrics_ablations']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
