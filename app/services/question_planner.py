import re
from typing import Any

from app.models.turn import InterviewTurn
from app.services.coverage_service import (
    default_framework_coverage,
    detect_topic_drift,
    framework_gaps_for_stage,
)
from app.services.stage_manager import (
    ARCHITECTURE_STAGE,
    CODE_DETAIL_STAGE,
    PANORAMA_STAGE,
    USE_CASE_STAGE,
    WRAP_UP_STAGE,
)

FILE_PATTERN = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|java|go|rb|yaml|yml|json)\b")
CLASS_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]{2,}\b")
METHOD_PATTERN = re.compile(r"\b[a-z_][a-z0-9_]{2,}\s*\(")


def plan_next_question(
    *,
    turns: list[InterviewTurn],
    current_stage: str,
    next_turn_no: int,
    coverage_state: dict[str, Any],
    human_review_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    framework = coverage_state.get("framework", default_framework_coverage())
    branches = coverage_state.get("branches", [])
    branch = branches[0] if branches else None
    stage_gaps = framework_gaps_for_stage(coverage_state, current_stage)
    collaboration = framework.get("human_collaboration", {})
    collaboration_gap_count = sum(
        1 for count in collaboration.values() if isinstance(count, (int, float)) and count <= 0
    )
    drift = detect_topic_drift(coverage_state, current_stage)
    review = human_review_signal or {}
    preferred_focus = (review.get("preferred_next_focus") or "").strip().lower()
    review_note = (review.get("note") or "").strip()
    intent_mode = "understand_current_code"

    if review and (
        review.get("direction") == "redirect" or review.get("verdict") in {"insufficient", "drifted"}
    ):
        target_label = resolve_human_review_target(
            current_stage=current_stage,
            stage_gaps=stage_gaps,
            preferred_focus=preferred_focus,
            review_note=review_note,
            branch=branch,
        )
        return {
            "question_intent": "human_guided_redirect",
            "intent_mode": intent_mode,
            "target_type": "human_selected_focus",
            "target_label": target_label,
            "target_branch_id": branch.get("branch_id") if branch else None,
            "retrieval_focus": "human redirection first, then stage gaps and strongest branch evidence",
            "constraints": [
                "Stay in understand-current-code mode",
                "Follow the human redirection signal explicitly",
                "Do not ask what should change or how the code should be redesigned",
            ],
            "prompt_id": prompt_id_for_stage(current_stage),
            "reasoning": review_note or "The human redirected the next question toward a missing understanding target.",
            "drift_detected": review.get("verdict") == "drifted",
            "human_collaboration_gate": False,
            "human_review_applied": True,
            "human_review_signal": review,
            "why_this_question": f"The human redirected the interview toward {target_label} to keep the conversation on understanding the current code.",
        }

    if drift["detected"]:
        target_label = stage_gaps[0] if stage_gaps else "the most important missing framework target"
        return {
            "question_intent": "drift_repair",
            "intent_mode": intent_mode,
            "target_type": "framework_gap",
            "target_label": target_label,
            "target_branch_id": drift["branch_id"],
            "retrieval_focus": "framework gaps first, then earlier broad branches",
            "constraints": [
                "Repair drift and return to the highest-priority framework gap",
                "Do not continue the narrow branch unless the human explicitly chooses it",
                "Stay at the current phase-appropriate level of abstraction",
            ],
            "prompt_id": "drift_repair_question",
            "reasoning": drift["reason"],
            "drift_detected": True,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "why_this_question": f"Repair drift by returning to the missing {target_label} coverage.",
        }

    if current_stage == PANORAMA_STAGE:
        return {
            "question_intent": "overview_gap_fill",
            "intent_mode": intent_mode,
            "target_type": "framework_gap",
            "target_label": stage_gaps[0] if stage_gaps else "overall project understanding",
            "target_branch_id": branch.get("branch_id") if branch else None,
            "retrieval_focus": "panorama gaps and broad branch clues",
            "constraints": [
                "Stay at macro level",
                "Avoid file/class/method detail",
                "Prioritize purpose, users, boundaries, modules, or workflow",
            ],
            "prompt_id": "next_question_panorama",
            "reasoning": f"Panorama gaps remaining: {', '.join(stage_gaps) or 'none detected'}",
            "drift_detected": False,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "why_this_question": f"Panorama is still incomplete, so the next question should fill {stage_gaps[0] if stage_gaps else 'the broadest remaining macro gap'}.",
        }

    if current_stage == ARCHITECTURE_STAGE:
        return {
            "question_intent": "architecture_clarification",
            "intent_mode": intent_mode,
            "target_type": "module_or_call_chain",
            "target_label": branch["label"] if branch else "module responsibilities and call chains",
            "target_branch_id": branch.get("branch_id") if branch else None,
            "retrieval_focus": "architecture gaps, collaboration mechanisms, and key branch evidence",
            "constraints": [
                "Ask about collaboration or call chains",
                "Avoid shallow overview repetition",
                "Avoid jumping to file-level implementation detail unless naming a path is necessary",
            ],
            "prompt_id": "next_question_architecture",
            "reasoning": f"Architecture gaps remaining: {', '.join(stage_gaps) or 'none detected'}",
            "drift_detected": False,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "why_this_question": "Architecture still needs clearer module responsibilities or call-chain evidence.",
        }

    if current_stage == CODE_DETAIL_STAGE:
        if collaboration_gap_count >= 3 and framework_gaps_for_stage(coverage_state, CODE_DETAIL_STAGE):
            return {
                "question_intent": "human_review",
                "intent_mode": intent_mode,
                "target_type": "prioritization",
                "target_label": branch["label"] if branch else "which implementation branch to deepen next",
                "target_branch_id": branch.get("branch_id") if branch else None,
                "retrieval_focus": "highest-priority branch plus code-detail gaps",
                "constraints": [
                    "Ask the human to choose which module, file, path, or branch should be deepened next",
                    "Make human prioritization explicit",
                    "Keep the collaboration visible before deeper code detail begins",
                ],
                "prompt_id": "human_review_question",
                "reasoning": "Code-detail work is about to deepen, but explicit human judgment and prioritization evidence is still thin.",
                "drift_detected": False,
                "human_collaboration_gate": True,
                "human_review_applied": False,
                "why_this_question": "Before going deeper into implementation, the interview should record the human's prioritization choice.",
            }

        target_type, target_label = choose_code_detail_target(branch)
        return {
            "question_intent": "code_detail_deep_dive",
            "intent_mode": intent_mode,
            "target_type": target_type,
            "target_label": target_label,
            "target_branch_id": branch.get("branch_id") if branch else None,
            "retrieval_focus": "code-detail counts, unresolved implementation gaps, and the most evidence-backed branch",
            "constraints": [
                "Must reference a specific file, class, method, execution path, library usage, or error path",
                "Reject broad implementation questions without a concrete target",
                "Prefer actual code artifact names when available",
                "Ask how the current implementation works, not what should be changed",
            ],
            "prompt_id": "next_question_code_detail",
            "reasoning": f"Code-detail gaps remaining: {', '.join(stage_gaps) or 'need more concrete implementation evidence'}",
            "drift_detected": False,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "why_this_question": f"Code-detail should dominate now, so the next question targets the concrete {target_type} '{target_label}'.",
        }

    if current_stage == USE_CASE_STAGE:
        scenario_target = pick_use_case_target(stage_gaps, branch)
        return {
            "question_intent": "scenario_completion",
            "intent_mode": intent_mode,
            "target_type": "scenario",
            "target_label": scenario_target,
            "target_branch_id": branch.get("branch_id") if branch else None,
            "retrieval_focus": "scenario gaps, earlier actor/module evidence, and boundary conditions",
            "constraints": [
                "Collect trigger, actors, inputs, process, result, and boundary conditions",
                "Tie the scenario back to real actors and inputs/outputs",
                "Avoid returning to broad overview",
                "Avoid purely internal code questions without scenario relevance",
                "Aim to complete one of the representative scenarios rather than opening a brand-new topic",
            ],
            "prompt_id": "next_question_use_cases",
            "reasoning": f"Use-case gaps remaining: {', '.join(stage_gaps) or 'complete one concrete scenario cleanly'}",
            "drift_detected": False,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "why_this_question": "The interview now needs a complete representative scenario rather than more isolated code details.",
        }

    return {
        "question_intent": "wrap_up_readiness",
        "intent_mode": intent_mode,
        "target_type": "coverage_gap",
        "target_label": "remaining evidence needed before delivery",
        "target_branch_id": branch.get("branch_id") if branch else None,
        "retrieval_focus": "small remaining gaps and handoff readiness",
        "constraints": [
            "Do not reopen large new topics",
            "Ask one final readiness or remaining-gap question",
        ],
        "prompt_id": "next_question_wrap_up",
        "reasoning": "The interview is in final wrap-up mode.",
        "drift_detected": False,
        "human_collaboration_gate": False,
        "human_review_applied": False,
        "why_this_question": "Coverage is mostly complete, so the next question should only close the final remaining gap.",
    }


def prompt_id_for_stage(stage: str) -> str:
    if stage == PANORAMA_STAGE:
        return "next_question_panorama"
    if stage == ARCHITECTURE_STAGE:
        return "next_question_architecture"
    if stage == CODE_DETAIL_STAGE:
        return "next_question_code_detail"
    if stage == USE_CASE_STAGE:
        return "next_question_use_cases"
    return "next_question_wrap_up"


def resolve_human_review_target(
    *,
    current_stage: str,
    stage_gaps: list[str],
    preferred_focus: str,
    review_note: str,
    branch: dict[str, Any] | None,
) -> str:
    focus_targets = {
        "panorama": "the remaining panorama understanding gaps",
        "architecture": "the main module responsibilities and call chain",
        "code path": "the main current execution path",
        "code_detail": "the most important current implementation path",
        "scenario": "a representative current usage scenario",
        "use_case": "a representative current usage scenario",
        "use cases": "a representative current usage scenario",
    }
    if preferred_focus in focus_targets:
        return focus_targets[preferred_focus]
    if review_note:
        return review_note
    if stage_gaps:
        return stage_gaps[0].replace("_", " ")
    if branch:
        return branch.get("label", f"the current {current_stage.lower()} target")
    return f"the current {current_stage.lower()} target"


def pick_use_case_target(stage_gaps: list[str], branch: dict[str, Any] | None) -> str:
    if "scenario_count" in stage_gaps:
        return "the next representative scenario"
    if "user_roles_count" in stage_gaps:
        return "the actor or user role in the current scenario"
    if "input_output_patterns_count" in stage_gaps:
        return "the inputs and outputs of the current scenario"
    if "boundary_conditions_count" in stage_gaps:
        return "the boundary conditions of the current scenario"
    if branch:
        return branch["label"]
    return "the representative scenario"


def choose_code_detail_target(branch: dict[str, Any] | None) -> tuple[str, str]:
    if not branch:
        return "execution_path", "the most important concrete request path"

    text = " ".join(
        str(branch.get(key, "")) for key in ("label", "summary")
    )

    file_match = FILE_PATTERN.search(text)
    if file_match:
        return "file", file_match.group(0)

    class_match = CLASS_PATTERN.search(text)
    if class_match:
        return "class", class_match.group(0)

    method_match = METHOD_PATTERN.search(text)
    if method_match:
        return "method", method_match.group(0).strip(" (")

    if "path" in text.lower() or "chain" in text.lower():
        return "execution_path", branch.get("label", "the key execution path")

    keywords = branch.get("keywords", [])
    if keywords:
        return "execution_path", keywords[0]

    return "execution_path", branch.get("label", "the key execution path")
