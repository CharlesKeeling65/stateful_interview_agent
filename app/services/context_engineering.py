from typing import Any

from app.logging import emit_event, preview_payload
from app.models.turn import InterviewTurn
from app.services.coverage_service import default_coverage_state, extract_keywords
from app.services.stage_manager import get_stage_instruction

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
    project_id: int | None = None,
    latest_answer_override: str | None = None,
) -> dict[str, Any]:
    coverage = coverage_state or default_coverage_state()
    recent_context = build_recent_context(turns, latest_answer_override=latest_answer_override)
    selected_branches = select_relevant_branches(
        turns=turns,
        current_stage=current_stage,
        latest_answer_override=latest_answer_override,
        coverage_state=coverage,
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
    coverage_priorities = build_coverage_priorities(selected_branches, current_stage)
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
                branch["branch_id"]: branch["_score"] for branch in selected_branches
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
        },
    )

    return {
        "current_stage": current_stage,
        "next_turn_no": next_turn_no,
        "stage_objective": get_stage_instruction(current_stage),
        "recent_context": recent_context,
        "retrieved_context": retrieved_context,
        "coverage_priorities": coverage_priorities,
        "selected_turn_ids": selected_turn_ids,
        "selected_branch_ids": selected_branch_ids,
        "context_text": "\n\n".join(
            [
                f"Recent context:\n{recent_context}",
                f"Retrieved branch context:\n{retrieved_context}",
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

    prior_completed_turns = [turn for turn in turns[:-1] if turn.answer_text]
    if prior_completed_turns:
        previous_turn = prior_completed_turns[-1]
        lines.append(f"Previous question: {previous_turn.question_text}")
        if previous_turn.answer_summary:
            lines.append(f"Previous summary: {previous_turn.answer_summary}")
        else:
            lines.append(f"Previous answer: {previous_turn.answer_text}")
    return "\n".join(lines)


def select_relevant_branches(
    *,
    turns: list[InterviewTurn],
    current_stage: str,
    latest_answer_override: str | None,
    coverage_state: dict[str, Any],
) -> list[dict[str, Any]]:
    latest_text = latest_answer_override or turns[-1].answer_text or ""
    latest_keywords = set(extract_keywords(latest_text, turns[-1].question_text if turns else ""))
    stage_weight = STAGE_WEIGHTS.get(current_stage, 1.0)
    branches = []

    for branch in coverage_state.get("branches", []):
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
        elif current_stage == "Architecture Understanding" and branch.get("stage") == "Panorama Mapping":
            score += 0.18
        elif current_stage == "Use Cases & Scenarios" and branch.get("stage") in {
            "Panorama Mapping",
            "Architecture Understanding",
        }:
            score += 0.22
        elif current_stage == "Code Detail Completion" and branch.get("stage") == "Architecture Understanding":
            score += 0.25

        if status == "needs_follow_up":
            score += 0.35
        elif status == "partial":
            score += 0.18

        if unresolved_points:
            score += 0.18

        if keyword_overlap:
            score += min(keyword_overlap * 0.18, 0.54)

        branch_copy = dict(branch)
        branch_copy["_score"] = round(score, 3)
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
        unresolved_points = branch.get("unresolved_points", [])
        if unresolved_points:
            lines.append(f"  Unresolved: {' | '.join(unresolved_points)}")
    return "\n".join(lines)


def build_coverage_priorities(branches: list[dict[str, Any]], current_stage: str) -> str:
    if not branches:
        return f"No high-priority branches found for {current_stage}. Stay aligned with the current stage objective."

    lines = [f"Focus on the strongest uncovered branches for {current_stage}:"]
    for branch in branches:
        lines.append(
            f"- {branch['label']} [{branch['status']}] via turns {', '.join(str(turn_no) for turn_no in branch.get('evidence_turn_nos', []))}"
        )
    return "\n".join(lines)
