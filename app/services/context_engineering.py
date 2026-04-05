from typing import Any

from app.logging import emit_event, preview_payload
from app.models.turn import InterviewTurn
from app.services.coverage_service import (
    default_coverage_state,
    extract_keywords,
    framework_gaps_for_stage,
    normalize_framework_coverage,
)
from app.services.stage_manager import (
    ARCHITECTURE_STAGE,
    CODE_DETAIL_STAGE,
    PANORAMA_STAGE,
    USE_CASE_STAGE,
    WRAP_UP_STAGE,
    get_stage_instruction,
)

STAGE_WEIGHTS = {
    "Panorama Mapping": 0.9,
    "Architecture Understanding": 1.0,
    "Code Detail Completion": 1.1,
    "Use Cases & Scenarios": 1.0,
}


def build_generation_context(
    *,
    turns: list[InterviewTurn],
    current_stage: str,
    next_turn_no: int,
    coverage_state: dict[str, Any] | None,
    project=None,
    project_id: int | None = None,
    latest_answer_override: str | None = None,
    excluded_branch_ids: set[str] | None = None,
) -> dict[str, Any]:
    coverage = coverage_state or default_coverage_state()
    stage_gaps = framework_gaps_for_stage(coverage, current_stage)
    recent_context = build_recent_context(turns, latest_answer_override=latest_answer_override)
    selected_branches = select_relevant_branches(
        turns=turns,
        current_stage=current_stage,
        latest_answer_override=latest_answer_override,
        coverage_state=coverage,
        stage_gaps=stage_gaps,
        excluded_branch_ids=excluded_branch_ids or set(),
    )
    selected_turn_ids = sorted(
        {
            evidence_turn_id
            for branch in selected_branches
            for evidence_turn_id in branch.get("evidence_turn_ids", [])
        }
    )
    selected_branch_ids = [branch["branch_id"] for branch in selected_branches]
    retrieved_context = build_retrieved_branch_context(selected_branches)
    coverage_priorities = build_coverage_priorities(selected_branches, current_stage, stage_gaps)
    repo_grounding_payload = {
        "repo_grounding_context": "No repository source configured for this project.",
        "repo_grounding_meta": {
            "enabled": False,
            "source_type": "none",
            "queries": [],
            "selected_paths": [],
            "selected_symbols": [],
            "tool_calls": [],
            "commit_sha": None,
        },
    }
    emit_event(
        "retrieval",
        "retrieval.context.complete",
        "Built selective generation context",
        operation="build_generation_context",
        project_id=project_id,
        stage=current_stage,
        turn_no=next_turn_no,
        status="success",
        output={
            "selected_branch_ids": selected_branch_ids,
            "selected_turn_ids": selected_turn_ids,
            "branch_scores": {
                branch["branch_id"]: {
                    "score": branch["_score"],
                    "novelty_penalty": branch.get("_novelty_penalty", 0.0),
                }
                for branch in selected_branches
            },
            "context_preview": preview_payload(
                "\n\n".join(
                    [
                        recent_context,
                        retrieved_context,
                        coverage_priorities,
                    ]
                ),
                artifact_category="retrieval",
                artifact_name=f"project-{project_id or 'unknown'}-q{next_turn_no}-context",
            ),
            "repo_selected_paths": repo_grounding_payload["repo_grounding_meta"].get("selected_paths", []),
        },
    )

    return {
        "current_stage": current_stage,
        "next_turn_no": next_turn_no,
        "stage_objective": get_stage_instruction(current_stage),
        "framework_gaps": stage_gaps,
        "recent_context": recent_context,
        "retrieved_context": retrieved_context,
        "repo_grounding_context": repo_grounding_payload["repo_grounding_context"],
        "repo_grounding_meta": repo_grounding_payload["repo_grounding_meta"],
        "coverage_priorities": coverage_priorities,
        "selected_turn_ids": selected_turn_ids,
        "selected_branch_ids": selected_branch_ids,
        "branch_selection_meta": {
            branch["branch_id"]: {
                "score": branch["_score"],
                "novelty_penalty": branch.get("_novelty_penalty", 0.0),
            }
            for branch in selected_branches
        },
        "context_text": "\n\n".join(
            [
                f"Recent context:\n{recent_context}",
                f"Retrieved branch context:\n{retrieved_context}",
                f"Repository evidence:\n{repo_grounding_payload['repo_grounding_context']}",
                f"Coverage priorities:\n{coverage_priorities}",
            ]
        ).strip(),
    }


def build_recent_context(
    turns: list[InterviewTurn],
    *,
    latest_answer_override: str | None = None,
) -> str:
    if not turns:
        return "No recent context available."

    latest_turn = turns[-1]
    latest_question = latest_turn.question_text
    latest_answer = latest_answer_override or latest_turn.answer_text or "[No answer yet]"
    lines = [
        f"Latest turn question: {latest_question}",
        f"Latest turn answer: {latest_answer}",
    ]
    latest_analysis = latest_turn.answer_analysis or {}
    if latest_analysis.get("key_points"):
        lines.append(
            "Latest answer key points: "
            + " | ".join(latest_analysis.get("key_points", [])[:4])
        )
    if latest_analysis.get("follow_up_anchors"):
        lines.append(
            "Latest answer follow-up anchors: "
            + " | ".join(latest_analysis.get("follow_up_anchors", [])[:3])
        )

    prior_completed_turns = [turn for turn in turns[:-1] if turn.answer_text]
    if prior_completed_turns:
        previous_turn = prior_completed_turns[-1]
        lines.append(f"Previous question: {previous_turn.question_text}")
        if previous_turn.answer_summary:
            lines.append(f"Previous summary: {previous_turn.answer_summary}")
        else:
            lines.append(f"Previous answer: {previous_turn.answer_text}")
        previous_analysis = previous_turn.answer_analysis or {}
        if previous_analysis.get("key_points"):
            lines.append(
                "Previous key points: "
                + " | ".join(previous_analysis.get("key_points", [])[:3])
            )
    return "\n".join(lines)


def select_relevant_branches(
    *,
    turns: list[InterviewTurn],
    current_stage: str,
    latest_answer_override: str | None,
    coverage_state: dict[str, Any],
    stage_gaps: list[str],
    excluded_branch_ids: set[str],
) -> list[dict[str, Any]]:
    framework = normalize_framework_coverage(
        coverage_state.get("framework", {})
    )
    latest_text = latest_answer_override or turns[-1].answer_text or ""
    latest_keywords = set(extract_keywords(latest_text, turns[-1].question_text if turns else ""))
    stage_weight = STAGE_WEIGHTS.get(current_stage, 1.0)
    recent_question_history = coverage_state.get("question_history", [])[-6:]
    recent_branch_counts: dict[str, int] = {}
    for item in recent_question_history:
        branch_id = str(item.get("branch_id") or "")
        if branch_id:
            recent_branch_counts[branch_id] = recent_branch_counts.get(branch_id, 0) + 1
    branches = []

    for branch in coverage_state.get("branches", []):
        if branch.get("branch_id") in excluded_branch_ids:
            continue
        branch_keywords = set(branch.get("keywords", []))
        keyword_overlap = len(branch_keywords & latest_keywords)
        unresolved_points = branch.get("unresolved_points", [])
        status = branch.get("status", "partial")
        score = float(branch.get("priority", 0.0))

        if (
            status == "covered"
            and not unresolved_points
            and keyword_overlap == 0
            and branch.get("stage") != current_stage
        ):
            continue

        if branch.get("stage") == current_stage:
            score += 0.4 * stage_weight
        elif current_stage == ARCHITECTURE_STAGE and branch.get("stage") == PANORAMA_STAGE:
            score += 0.18
        elif current_stage == USE_CASE_STAGE and branch.get("stage") in {
            PANORAMA_STAGE,
            ARCHITECTURE_STAGE,
        }:
            score += 0.22
        elif current_stage == CODE_DETAIL_STAGE and branch.get("stage") == ARCHITECTURE_STAGE:
            score += 0.25
        elif current_stage == WRAP_UP_STAGE:
            score += 0.1

        if status == "needs_follow_up":
            score += 0.35
        elif status == "partial":
            score += 0.18

        if unresolved_points:
            score += 0.18

        if keyword_overlap:
            score += min(keyword_overlap * 0.18, 0.54)

        label_and_summary = " ".join(
            str(branch.get(field, "")) for field in ("label", "summary")
        ).lower()
        gap_hits = sum(1 for gap in stage_gaps if gap.replace("_", " ") in label_and_summary)
        if gap_hits:
            score += gap_hits * 0.35

        score += stage_relevance_bonus(current_stage=current_stage, branch=branch, framework=framework)

        branch_id = str(branch.get("branch_id") or "")
        novelty_penalty = 0.0
        if branch_id:
            novelty_penalty += recent_branch_counts.get(branch_id, 0) * 0.34
            recent_top_branch_id = str(recent_question_history[-1].get("branch_id") or "") if recent_question_history else ""
            if recent_top_branch_id and recent_top_branch_id == branch_id:
                novelty_penalty += 0.28
        novelty_penalty += stage_misalignment_penalty(current_stage=current_stage, branch_text=label_and_summary)
        score -= novelty_penalty

        branch_copy = dict(branch)
        branch_copy["_score"] = round(score, 3)
        branch_copy["_novelty_penalty"] = round(novelty_penalty, 3)
        branches.append(branch_copy)

    branches.sort(key=lambda branch: branch["_score"], reverse=True)
    return branches[:3]


def build_retrieved_branch_context(branches: list[dict[str, Any]]) -> str:
    if not branches:
        return "No historical branches were selected."

    lines = []
    for branch in branches:
        lines.append(
            f"- [{branch['branch_id']}] {branch['label']} (stage: {branch['stage']}, status: {branch['status']}, score: {branch['_score']})"
        )
        lines.append(f"  Keywords: {', '.join(branch.get('keywords', [])) or 'None'}")
        lines.append(
            f"  Evidence turns: {', '.join(str(turn_no) for turn_no in branch.get('evidence_turn_nos', [])) or 'None'}"
        )
        lines.append(f"  Latest summary: {branch.get('summary', 'None')}")
        key_points = branch.get("key_points", [])
        if key_points:
            lines.append(f"  Key points: {' | '.join(key_points[:4])}")
        unresolved_points = branch.get("unresolved_points", [])
        if unresolved_points:
            lines.append(f"  Unresolved: {' | '.join(unresolved_points)}")
    return "\n".join(lines)


def stage_relevance_bonus(*, current_stage: str, branch: dict[str, Any], framework: dict[str, Any]) -> float:
    text = " ".join(str(branch.get(field, "")) for field in ("label", "summary")).lower()
    if current_stage == PANORAMA_STAGE:
        if any(marker in text for marker in ("purpose", "user", "workflow", "module", "boundary")):
            return 0.22
        return 0.0
    if current_stage == ARCHITECTURE_STAGE:
        if any(marker in text for marker in ("call chain", "path", "collabor", "module", "layer")):
            return 0.24
        return 0.0
    if current_stage == CODE_DETAIL_STAGE:
        if any(marker in text for marker in (".py", ".ts", ".tsx", ".js", "class", "method", "function", "execution path")):
            return 0.28
        return -0.1
    if current_stage == USE_CASE_STAGE:
        if any(marker in text for marker in ("scenario", "actor", "input", "output", "boundary", "extension")):
            return 0.26
        if framework.get("use_cases", {}).get("representative_scenarios_count", 0) <= 0:
            return -0.12
    return 0.0


def stage_misalignment_penalty(*, current_stage: str, branch_text: str) -> float:
    if current_stage == PANORAMA_STAGE and any(marker in branch_text for marker in (".py", ".ts", ".tsx", ".js", "class ", "method ", "error handling")):
        return 0.45
    if current_stage == ARCHITECTURE_STAGE and any(marker in branch_text for marker in ("refactor", "redesign", "modify", "update tests")):
        return 0.42
    if current_stage == USE_CASE_STAGE and any(marker in branch_text for marker in (".py", ".ts", ".tsx", ".js", "class ", "method ")):
        return 0.35
    return 0.0


def build_coverage_priorities(
    branches: list[dict[str, Any]], current_stage: str, stage_gaps: list[str]
) -> str:
    if not branches:
        base = f"No high-priority branches found for {current_stage}. Stay aligned with the current stage objective."
        if stage_gaps:
            base += f" Framework gaps: {', '.join(stage_gaps)}."
        return base

    lines = [f"Focus on the strongest uncovered branches for {current_stage}:"]
    if stage_gaps:
        lines.append(f"- Required framework gaps: {', '.join(stage_gaps)}")
    for branch in branches:
        lines.append(
            f"- {branch['label']} [{branch['status']}] via turns {', '.join(str(turn_no) for turn_no in branch.get('evidence_turn_nos', []))}"
        )
    return "\n".join(lines)
