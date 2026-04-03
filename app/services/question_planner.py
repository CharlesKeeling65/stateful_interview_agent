import re
from typing import Any

from app.models.turn import InterviewTurn
from app.services.coverage_service import default_framework_coverage, framework_gaps_for_stage
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
) -> dict[str, Any]:
    framework = coverage_state.get("framework", default_framework_coverage())
    branches = coverage_state.get("branches", [])
    branch = branches[0] if branches else None
    stage_gaps = framework_gaps_for_stage(coverage_state, current_stage)

    if current_stage == PANORAMA_STAGE:
        return {
            "question_intent": "overview_gap_fill",
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
        }

    if current_stage == ARCHITECTURE_STAGE:
        return {
            "question_intent": "architecture_clarification",
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
        }

    if current_stage == CODE_DETAIL_STAGE:
        target_type, target_label = choose_code_detail_target(branch)
        return {
            "question_intent": "code_detail_deep_dive",
            "target_type": target_type,
            "target_label": target_label,
            "target_branch_id": branch.get("branch_id") if branch else None,
            "retrieval_focus": "code-detail counts, unresolved implementation gaps, and the most evidence-backed branch",
            "constraints": [
                "Must reference a specific file, class, method, execution path, library usage, or error path",
                "Reject broad implementation questions without a concrete target",
                "Prefer actual code artifact names when available",
            ],
            "prompt_id": "next_question_code_detail",
            "reasoning": f"Code-detail gaps remaining: {', '.join(stage_gaps) or 'need more concrete implementation evidence'}",
        }

    if current_stage == USE_CASE_STAGE:
        return {
            "question_intent": "scenario_completion",
            "target_type": "scenario",
            "target_label": branch["label"] if branch else (stage_gaps[0] if stage_gaps else "typical scenario"),
            "target_branch_id": branch.get("branch_id") if branch else None,
            "retrieval_focus": "scenario gaps, earlier actor/module evidence, and boundary conditions",
            "constraints": [
                "Tie the scenario back to real actors and inputs/outputs",
                "Avoid returning to broad overview",
                "Avoid purely internal code questions without scenario relevance",
            ],
            "prompt_id": "next_question_use_cases",
            "reasoning": f"Use-case gaps remaining: {', '.join(stage_gaps) or 'complete one concrete scenario cleanly'}",
        }

    return {
        "question_intent": "wrap_up_readiness",
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
    }


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
