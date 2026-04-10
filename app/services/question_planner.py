import re
from typing import Any

from app.models.turn import InterviewTurn
from app.services.coverage_service import (
    default_framework_coverage,
    detect_topic_drift,
    framework_gaps_for_stage,
    normalize_framework_coverage,
)
from app.services.mode_service import (
    AgentMode,
    get_mode_constraints,
    is_understanding_mode,
)
from app.services.repetition_guard import build_question_signature, normalize_target_label
from app.services.rubric_task_service import (
    RubricTaskBoard,
    get_next_priority_task,
    phase_name_to_key,
    initialize_task_board,
    deserialize_task_board,
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
    excluded_branch_ids: set[str] | None = None,
    excluded_target_signatures: set[str] | None = None,
    agent_mode: str = "understand_current_code",
    task_board_json: str | None = None,
) -> dict[str, Any]:
    # Parse mode and get constraints
    mode = AgentMode(agent_mode) if isinstance(agent_mode, str) else agent_mode
    mode_constraints = get_mode_constraints(mode)

    # Parse task board
    task_board = deserialize_task_board(task_board_json) if task_board_json else initialize_task_board()

    framework = normalize_framework_coverage(
        coverage_state.get("framework", default_framework_coverage())
    )
    branches = coverage_state.get("branches", [])
    question_history = coverage_state.get("question_history", [])
    recent_question_history = question_history[-8:]
    excluded_branch_ids = excluded_branch_ids or set()
    excluded_target_signatures = excluded_target_signatures or set()

    # Get next priority rubric task if applicable
    phase_key = phase_name_to_key(current_stage)
    next_rubric_task = get_next_priority_task(task_board, phase_key)

    branch = choose_branch_for_stage(
        branches=branches,
        current_stage=current_stage,
        recent_question_history=recent_question_history,
        excluded_branch_ids=excluded_branch_ids,
    )
    stage_gaps = prioritized_stage_gaps(current_stage, framework_gaps_for_stage(coverage_state, current_stage))
    selected_framework_gap = stage_gaps[0] if stage_gaps else None
    collaboration = framework.get("human_collaboration", {})
    collaboration_gap_count = sum(
        1 for count in collaboration.values() if isinstance(count, (int, float)) and count <= 0
    )
    drift = detect_topic_drift(coverage_state, current_stage)
    review = human_review_signal or {}
    preferred_focus = (review.get("preferred_next_focus") or "").strip().lower()
    review_note = (review.get("note") or "").strip()
    intent_mode = agent_mode  # Use the passed mode

    # Build base constraints based on mode
    base_constraints = []
    if is_understanding_mode(mode):
        base_constraints = [
            "Stay in understand-current-code mode",
            "Focus on HOW the code currently works, not what should change",
            "Avoid 'should', 'could we', 'better way' framing",
            "Write in plain natural English, not AI-assistant phrasing",
        ]
    else:
        base_constraints = [
            f"Stay in {mode.value} mode",
            mode_constraints.get("description", ""),
        ]

    if review and (
        review.get("direction") == "redirect"
        or review.get("verdict") in {"insufficient", "drifted"}
        or preferred_focus
        or review_note
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
            "phase": current_stage,
            "intent_mode": intent_mode,
            "mode": agent_mode,
            "target_type": "human_selected_focus",
            "target_label": target_label,
            "target_identifier": target_label,
            "target_branch_id": branch.get("branch_id") if branch else None,
            "selected_framework_gap": selected_framework_gap,
            "selected_branch_ids": [branch.get("branch_id")] if branch and branch.get("branch_id") else [],
            "selected_turn_ids": branch.get("evidence_turn_ids", []) if branch else [],
            "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
            "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
            "confidence": 0.7,
            "retrieval_focus": "human redirection first, then stage gaps and strongest branch evidence",
            "constraints": base_constraints + [
                "Follow the human redirection signal explicitly",
            ],
            "prompt_id": prompt_id_for_stage(current_stage),
            "reasoning": review_note or "The human redirected the next question toward a missing understanding target.",
            "drift_detected": review.get("verdict") == "drifted",
            "human_collaboration_gate": False,
            "human_review_applied": True,
            "human_review_signal": review,
            "validation_constraints": [
                f"must stay in {agent_mode}",
                "must reflect explicit human redirection",
            ],
            "why_this_question": f"The human redirected the interview toward {target_label} to keep the conversation on understanding the current code.",
        }

    panorama_repeated_drift = (
        current_stage == PANORAMA_STAGE
        and drift["detected"]
        and branch is not None
        and len(branch.get("evidence_turn_nos", [])) >= 2
    )
    if drift["detected"] and (current_stage != PANORAMA_STAGE or panorama_repeated_drift):
        target_label = stage_gaps[0] if stage_gaps else "the most important missing framework target"
        return {
            "question_intent": "drift_repair",
            "phase": current_stage,
            "intent_mode": intent_mode,
            "mode": agent_mode,
            "target_type": "framework_gap",
            "target_label": target_label,
            "target_identifier": target_label,
            "target_branch_id": drift["branch_id"],
            "selected_framework_gap": selected_framework_gap,
            "selected_branch_ids": [drift["branch_id"]] if drift["branch_id"] else [],
            "selected_turn_ids": [],
            "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
            "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
            "confidence": 0.65,
            "retrieval_focus": "framework gaps first, then earlier broad branches",
            "constraints": base_constraints + [
                "Repair drift and return to the highest-priority framework gap",
                "Do not continue the narrow branch unless the human explicitly chooses it",
                "Stay at the current phase-appropriate level of abstraction",
            ],
            "prompt_id": "drift_repair_question",
            "reasoning": drift["reason"],
            "drift_detected": True,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "validation_constraints": [
                "must repair drift toward a framework gap",
                "must avoid branch-local rabbit holes",
            ],
            "why_this_question": f"Repair drift by returning to the missing {target_label} coverage.",
        }

    if current_stage == PANORAMA_STAGE:
        return {
            "question_intent": "overview_gap_fill",
            "phase": current_stage,
            "intent_mode": intent_mode,
            "mode": agent_mode,
            "target_type": "framework_gap",
            "target_label": selected_framework_gap or "overall project understanding",
            "target_identifier": selected_framework_gap or "overall_project_understanding",
            "target_branch_id": branch.get("branch_id") if branch else None,
            "selected_framework_gap": selected_framework_gap,
            "selected_branch_ids": [branch.get("branch_id")] if branch and branch.get("branch_id") else [],
            "selected_turn_ids": branch.get("evidence_turn_ids", []) if branch else [],
            "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
            "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
            "confidence": 0.75 if selected_framework_gap else 0.6,
            "retrieval_focus": "panorama gaps and broad branch clues",
            "constraints": base_constraints + [
                "Stay at macro level",
                "Avoid file/class/method detail",
                "Prioritize purpose, users, boundaries, modules, or workflow",
            ],
            "prompt_id": "next_question_panorama",
            "reasoning": f"Panorama gaps remaining: {', '.join(stage_gaps) or 'none detected'}",
            "drift_detected": drift["detected"],
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "validation_constraints": [
                "must stay macro-level",
                "must not mention files/classes/methods",
            ],
            "why_this_question": f"Panorama is still incomplete, so the next question should fill {selected_framework_gap if selected_framework_gap else 'the broadest remaining macro gap'}.",
        }

    if current_stage == ARCHITECTURE_STAGE:
        return {
            "question_intent": "architecture_clarification",
            "phase": current_stage,
            "intent_mode": intent_mode,
            "mode": agent_mode,
            "target_type": "module_or_call_chain",
            "target_label": branch["label"] if branch else "module responsibilities and call chains",
            "target_identifier": branch["label"] if branch else "module responsibilities and call chains",
            "target_branch_id": branch.get("branch_id") if branch else None,
            "selected_framework_gap": selected_framework_gap,
            "selected_branch_ids": [branch.get("branch_id")] if branch and branch.get("branch_id") else [],
            "selected_turn_ids": branch.get("evidence_turn_ids", []) if branch else [],
            "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
            "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
            "confidence": 0.7,
            "retrieval_focus": "architecture gaps, collaboration mechanisms, and key branch evidence",
            "constraints": base_constraints + [
                "Ask about collaboration or call chains",
                "Avoid shallow overview repetition",
                "Stay focused on how the current structure is organized",
            ],
            "prompt_id": "next_question_architecture",
            "reasoning": f"Architecture gaps remaining: {', '.join(stage_gaps) or 'none detected'}",
            "drift_detected": False,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "validation_constraints": [
                "must stay architecture-oriented",
                "must emphasize module interaction or call chains",
            ],
            "why_this_question": "Architecture still needs clearer module responsibilities or call-chain evidence.",
        }

    if current_stage == CODE_DETAIL_STAGE:
        code_detail_turns = framework.get("stage_turn_counts", {}).get(CODE_DETAIL_STAGE, 0)
        branch_requests_human_choice = bool(
            branch and any(
                marker in " ".join(branch.get("unresolved_points", [])).lower()
                for marker in ("human should choose", "choose whether", "prioritize", "deepen first")
            )
        )
        if (
            collaboration_gap_count >= 3
            and framework_gaps_for_stage(coverage_state, CODE_DETAIL_STAGE)
            and (code_detail_turns >= 4 or branch_requests_human_choice)
        ):
            return {
                "question_intent": "human_review",
                "phase": current_stage,
                "intent_mode": intent_mode,
                "mode": agent_mode,
                "target_type": "prioritization",
                "target_label": branch["label"] if branch else "which implementation branch to deepen next",
                "target_identifier": branch["label"] if branch else "which implementation branch to deepen next",
                "target_branch_id": branch.get("branch_id") if branch else None,
                "selected_framework_gap": selected_framework_gap,
                "selected_branch_ids": [branch.get("branch_id")] if branch and branch.get("branch_id") else [],
                "selected_turn_ids": branch.get("evidence_turn_ids", []) if branch else [],
                "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
                "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
                "confidence": 0.6,
                "retrieval_focus": "highest-priority branch plus code-detail gaps",
                "constraints": base_constraints + [
                    "Ask the human to choose which module, file, path, or branch should be deepened next",
                    "Make human prioritization explicit",
                    "Keep the question concise and direct",
                    "Ask exactly one sentence with exactly one question mark",
                ],
                "prompt_id": "human_review_question",
                "reasoning": "Code-detail work is about to deepen, but explicit human judgment and prioritization evidence is still thin.",
                "drift_detected": False,
                "human_collaboration_gate": True,
                "human_review_applied": False,
                "validation_constraints": [
                    "must ask for human prioritization explicitly",
                    f"must stay in {agent_mode}",
                ],
                "why_this_question": "Before going deeper into implementation, the interview should record the human's prioritization choice.",
            }

        target_type, target_label = choose_code_detail_target(branch)
        if branch:
            branch, target_type, target_label = choose_non_redundant_code_detail_target(
                branches=branches,
                current_stage=current_stage,
                recent_question_history=recent_question_history,
                default_branch=branch,
                excluded_branch_ids=excluded_branch_ids,
                excluded_target_signatures=excluded_target_signatures,
            )
        return {
            "question_intent": "code_detail_deep_dive",
            "phase": current_stage,
            "intent_mode": intent_mode,
            "mode": agent_mode,
            "target_type": target_type,
            "target_label": target_label,
            "target_identifier": target_label,
            "target_branch_id": branch.get("branch_id") if branch else None,
            "selected_framework_gap": selected_framework_gap,
            "selected_branch_ids": [branch.get("branch_id")] if branch and branch.get("branch_id") else [],
            "selected_turn_ids": branch.get("evidence_turn_ids", []) if branch else [],
            "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
            "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
            "confidence": 0.7,
            "retrieval_focus": "code-detail counts, unresolved implementation gaps, and the most evidence-backed branch",
            "constraints": base_constraints + [
                "Must reference a specific file, class, method, execution path, library usage, or error path",
                "Reject broad implementation questions without a concrete target",
                "Prefer actual code artifact names when available",
                "Keep the question concise and direct",
                "Ask exactly one sentence with exactly one question mark",
            ],
            "prompt_id": "next_question_code_detail",
            "reasoning": f"Code-detail gaps remaining: {', '.join(stage_gaps) or 'need more concrete implementation evidence'}",
            "drift_detected": False,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "validation_constraints": [
                "must be implementation-specific",
                f"must stay in {agent_mode}",
                "must reference a concrete artifact or execution path",
            ],
            "why_this_question": build_code_detail_why_text(
                target_type=target_type,
                target_label=target_label,
                recent_question_history=recent_question_history,
            ),
        }

    if current_stage == USE_CASE_STAGE:
        scenario_target = pick_use_case_target(stage_gaps, branch)
        return {
            "question_intent": "scenario_completion",
            "phase": current_stage,
            "intent_mode": intent_mode,
            "mode": agent_mode,
            "target_type": "scenario",
            "target_label": scenario_target,
            "target_identifier": scenario_target,
            "target_branch_id": branch.get("branch_id") if branch else None,
            "selected_framework_gap": selected_framework_gap,
            "selected_branch_ids": [branch.get("branch_id")] if branch and branch.get("branch_id") else [],
            "selected_turn_ids": branch.get("evidence_turn_ids", []) if branch else [],
            "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
            "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
            "confidence": 0.65,
            "retrieval_focus": "scenario gaps, earlier actor/module evidence, and boundary conditions",
            "constraints": base_constraints + [
                "Collect trigger, actors, inputs, process, outputs, and boundary conditions",
                "Tie the scenario back to real actors and inputs/outputs",
                "Aim to complete one of the representative scenarios",
            ],
            "prompt_id": "next_question_use_cases",
            "reasoning": f"Use-case gaps remaining: {', '.join(stage_gaps) or 'complete one concrete scenario cleanly'}",
            "drift_detected": False,
            "human_collaboration_gate": False,
            "human_review_applied": False,
            "validation_constraints": [
                "must collect scenario contract evidence",
                "must mention actor/process/input/output/boundary framing",
            ],
            "why_this_question": "The interview now needs a complete representative scenario rather than more isolated code details.",
        }

    return {
        "question_intent": "wrap_up_readiness",
        "phase": current_stage,
        "intent_mode": intent_mode,
        "mode": agent_mode,
        "target_type": "coverage_gap",
        "target_label": "remaining evidence needed before delivery",
        "target_identifier": "remaining evidence needed before delivery",
        "target_branch_id": branch.get("branch_id") if branch else None,
        "selected_framework_gap": selected_framework_gap,
        "selected_branch_ids": [branch.get("branch_id")] if branch and branch.get("branch_id") else [],
        "selected_turn_ids": branch.get("evidence_turn_ids", []) if branch else [],
        "rubric_task_id": next_rubric_task.task_id if next_rubric_task else None,
        "rubric_task_label": next_rubric_task.label if next_rubric_task else None,
        "confidence": 0.8,
        "retrieval_focus": "small remaining gaps and handoff readiness",
        "constraints": base_constraints + [
            "Do not reopen large new topics",
            "Ask one final readiness or remaining-gap question",
        ],
        "prompt_id": "next_question_wrap_up",
        "reasoning": "The interview is in final wrap-up mode.",
        "drift_detected": False,
        "human_collaboration_gate": False,
        "human_review_applied": False,
        "validation_constraints": [
            "must stay concise and close remaining evidence gaps only",
        ],
        "why_this_question": "Coverage is mostly complete, so the next question should only close the final remaining gap.",
    }


def prioritized_stage_gaps(stage: str, stage_gaps: list[str]) -> list[str]:
    priority_order = {
        PANORAMA_STAGE: [
            "purpose",
            "target_users",
            "boundaries",
            "major_modules",
            "high_level_workflow",
            "initial_module_relationships",
        ],
        ARCHITECTURE_STAGE: [
            "module_responsibilities",
            "collaboration_mechanisms",
            "key_call_chains",
            "system_structure",
            "architecture_style_or_organization",
            "design_rationale_or_quality_attributes",
        ],
        CODE_DETAIL_STAGE: [
            "specific_files_count",
            "specific_methods_count",
            "execution_paths_count",
            "error_handling_points_count",
            "library_usage_points_count",
            "protocol_implementation_points_count",
            "state_management_points_count",
            "specific_classes_count",
        ],
        USE_CASE_STAGE: [
            "representative_scenarios_count",
            "actors_roles_count",
            "input_output_patterns_count",
            "boundary_conditions_count",
            "extension_points_count",
        ],
    }
    order = priority_order.get(stage, [])
    return sorted(stage_gaps, key=lambda gap: (order.index(gap) if gap in order else len(order), gap))


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
    if "representative_scenarios_count" in stage_gaps or "scenario_count" in stage_gaps:
        return "the next representative scenario"
    if "actors_roles_count" in stage_gaps or "user_roles_count" in stage_gaps:
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


def choose_branch_for_stage(
    *,
    branches: list[dict[str, Any]],
    current_stage: str,
    recent_question_history: list[dict[str, Any]],
    excluded_branch_ids: set[str],
) -> dict[str, Any] | None:
    if not branches:
        return None

    recent_branch_ids = {
        str(item.get("branch_id"))
        for item in recent_question_history[-4:]
        if item.get("branch_id")
    }
    for branch in branches:
        if branch.get("branch_id") in excluded_branch_ids:
            continue
        if current_stage == CODE_DETAIL_STAGE and branch.get("branch_id") in recent_branch_ids:
            continue
        return branch
    for branch in branches:
        if branch.get("branch_id") not in excluded_branch_ids:
            return branch
    return branches[0]


def choose_non_redundant_code_detail_target(
    *,
    branches: list[dict[str, Any]],
    current_stage: str,
    recent_question_history: list[dict[str, Any]],
    default_branch: dict[str, Any],
    excluded_branch_ids: set[str],
    excluded_target_signatures: set[str],
) -> tuple[dict[str, Any], str, str]:
    recent_signatures = {
        str(item.get("signature", ""))
        for item in recent_question_history
    }
    recent_signatures |= excluded_target_signatures

    for branch in [default_branch, *[item for item in branches if item is not default_branch]]:
        if branch.get("branch_id") in excluded_branch_ids:
            continue
        target_type, target_label = choose_code_detail_target(branch)
        signature = build_question_signature(
            stage=current_stage,
            intent="code_detail_deep_dive",
            branch_id=branch.get("branch_id"),
            target_type=target_type,
            target_label=target_label,
        )
        if signature not in recent_signatures:
            return branch, target_type, target_label

    fallback_branch = branches[0] if branches else default_branch
    fallback_target_type, fallback_target_label = choose_code_detail_target(fallback_branch)
    return fallback_branch, fallback_target_type, fallback_target_label


def build_code_detail_why_text(
    *,
    target_type: str,
    target_label: str,
    recent_question_history: list[dict[str, Any]],
) -> str:
    recent_targets = {
        normalize_target_label(str(item.get("target_label", "")))
        for item in recent_question_history[-4:]
    }
    normalized_target = normalize_target_label(target_label)
    if normalized_target and normalized_target not in recent_targets:
        return (
            f"Code-detail should dominate now, and this target avoids recently repeated questions by focusing on the concrete "
            f"{target_type} '{target_label}'."
        )
    return f"Code-detail should dominate now, so the next question targets the concrete {target_type} '{target_label}'."
