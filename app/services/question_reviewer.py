"""
Question reviewer service for the Code Understand Agent.

Provides the Reviewer phase in the Planner → Reviewer → Writer pipeline.
Reviews planner decisions before question generation.
"""

import re
from typing import Any

from pydantic import BaseModel, Field

from app.services.mode_service import (
    AgentMode,
    GateType,
    get_mode_constraints,
)
from app.services.human_gate_service import (
    HumanGate,
    create_low_confidence_gate,
    create_phase_completion_gate,
    create_drift_redirection_gate,
    create_branch_prioritization_gate,
)
from app.services.rubric_task_service import (
    RubricTaskBoard,
    get_next_priority_task,
    get_phase_gaps,
    is_phase_complete,
    should_trigger_phase_gate,
)


class ReviewResult(BaseModel):
    """Result of reviewing a planner decision."""

    approved: bool = True
    review_reason: str = "Plan approved"
    mode_violation: bool = False
    priority_override: bool = False
    human_gate_triggered: bool = False
    human_gate: HumanGate | None = None
    human_gate_reason: str | None = None
    suggested_modifications: list[str] = Field(default_factory=list)
    confidence_score: float = 0.5
    drift_detected: bool = False
    drift_info: dict[str, Any] = Field(default_factory=dict)
    alternative_plan: dict[str, Any] | None = None


# Patterns that indicate change-planning questions (for mode enforcement)
CHANGE_PROPOSAL_PATTERNS = [
    r"should\s+be\s+(changed|modified|updated|refactored)",
    r"(?:how|what)\s+(?:should|could|would)\s+we\s+(change|modify|fix|implement)",
    r"suggest\s+(?:changes?|improvements?|refactoring)",
    r"recommended\s+(?:changes?|approach\s+for)",
    r"better\s+(?:way|approach)\s+to\s+(implement|handle)",
    r"redesign\s+the",
    r"update\s+(?:the\s+)?tests?",
    r"modify\s+(?:this|the)",
    r"what\s+changes\s+(?:should|could)",
    r"improve\s+(?:this|the)\s+(?:code|implementation)",
]

# Patterns that indicate genuine understanding questions
UNDERSTANDING_PATTERNS = [
    r"how\s+does\s+(?:this|the)",
    r"what\s+does\s+(?:this|the)",
    r"why\s+does\s+(?:this|the)",
    r"explain\s+(?:how|what|why)",
    r"describe\s+(?:the|this)",
    r"current\s+(?:implementation|behavior|flow)",
    r"what\s+is\s+(?:the\s+)?(?:current|existing)",
]

MAX_QUESTION_LENGTH = 160


def review_question_plan(
    planner_decision: dict[str, Any],
    mode: AgentMode | str,
    task_board: RubricTaskBoard,
    coverage_state: dict[str, Any],
    current_stage: str,
    drift_detection_result: dict[str, Any] | None = None,
    confidence_threshold: float = 0.4,
) -> ReviewResult:
    """
    Review the planner's decision before question generation.

    Checks:
    1. Mode constraint compliance
    2. Phase/task alignment
    3. Priority correctness
    4. Human gate requirements
    5. Drift detection
    6. Confidence level

    Args:
        planner_decision: The planner's output decision
        mode: Current agent mode
        task_board: Current task board state
        coverage_state: Current coverage state
        current_stage: Current interview stage
        drift_detection_result: Optional drift detection result
        confidence_threshold: Minimum confidence threshold

    Returns:
        ReviewResult with approval status and any gate triggers
    """
    mode = AgentMode(mode) if isinstance(mode, str) else mode
    result = ReviewResult(approved=True, review_reason="Plan approved")

    # Extract key fields from planner decision
    target_label = planner_decision.get("target_label", "")
    question_intent = planner_decision.get("question_intent", "")
    selected_gap = planner_decision.get("selected_framework_gap")
    confidence = planner_decision.get("confidence", 0.5)

    # 1. Mode constraint check
    mode_result = _check_mode_constraints(planner_decision, mode)
    if not mode_result.approved:
        return mode_result

    # 2. Drift detection check
    if drift_detection_result and drift_detection_result.get("detected"):
        result.drift_detected = True
        result.drift_info = drift_detection_result

        # Trigger drift gate
        result.human_gate_triggered = True
        result.human_gate = create_drift_redirection_gate(drift_detection_result)
        result.human_gate_reason = drift_detection_result.get("reason", "Topic drift detected")
        result.approved = False
        result.review_reason = f"Drift detected: {result.human_gate_reason}"
        return result

    # 3. Phase completion gate check
    should_gate, gate_reason = should_trigger_phase_gate(task_board)
    if should_gate and task_board.human_gate_triggered:
        result.human_gate_triggered = True
        result.human_gate = create_phase_completion_gate(
            current_stage,
            {"completed_tasks": get_phase_gaps(task_board, task_board.current_phase)},
        )
        result.human_gate_reason = gate_reason
        result.approved = False
        result.review_reason = gate_reason or "Phase completion requires confirmation"
        return result

    # 4. Confidence check
    result.confidence_score = _compute_plan_confidence(
        planner_decision, coverage_state, mode
    )
    if result.confidence_score < confidence_threshold:
        result.human_gate_triggered = True
        result.human_gate = create_low_confidence_gate(planner_decision)
        result.human_gate_reason = f"Low confidence: {result.confidence_score:.0%}"
        result.approved = False
        result.review_reason = result.human_gate_reason
        return result

    # 5. Priority override check - is there a higher priority task?
    next_task = get_next_priority_task(task_board)
    if next_task and next_task.priority > 0.8:
        current_priority = planner_decision.get("priority", 0.5)
        if next_task.priority > current_priority + 0.2:
            result.priority_override = True
            result.suggested_modifications.append(
                f"Consider higher priority task: {next_task.label}"
            )
            # Include in alternative plan
            result.alternative_plan = {
                "rubric_task_id": next_task.task_id,
                "rubric_task_label": next_task.label,
                "question_intent": "address_rubric_task",
                "target_label": next_task.label,
                "priority": next_task.priority,
            }

    # Approved with any modifications noted
    result.review_reason = "Plan approved"
    if result.suggested_modifications:
        result.review_reason += f" (with suggestions: {', '.join(result.suggested_modifications)})"

    return result


def _check_mode_constraints(
    planner_decision: dict[str, Any],
    mode: AgentMode,
) -> ReviewResult:
    """Check if planner decision violates mode constraints."""
    constraints = get_mode_constraints(mode)
    result = ReviewResult(approved=True, review_reason="Mode constraints satisfied")

    target_label = planner_decision.get("target_label", "").lower()
    question_text = planner_decision.get("question_text", "")
    question_intent = planner_decision.get("question_intent", "")

    # Check reject markers
    reject_markers = constraints.get("reject_markers", [])
    for marker in reject_markers:
        if marker.lower() in target_label or marker.lower() in question_text.lower():
            result.approved = False
            result.mode_violation = True
            result.review_reason = f"Mode violation: '{marker}' not allowed in {mode.value} mode"
            result.suggested_modifications.append(
                f"Rephrase to focus on current behavior, not proposed changes"
            )
            return result

    # Check regex patterns for change proposals
    if not constraints.get("allow_change_proposals", False):
        combined_text = f"{target_label} {question_text}".lower()
        for pattern in CHANGE_PROPOSAL_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                result.approved = False
                result.mode_violation = True
                result.review_reason = (
                    f"Question seeks change proposals, but mode is '{mode.value}'. "
                    "Focus on understanding current behavior."
                )
                result.suggested_modifications.append(
                    "Use phrasing like 'How does X currently...' instead of 'How should we...'"
                )
                return result

    # Check intent whitelist
    whitelist = constraints.get("question_intent_whitelist")
    if whitelist and question_intent and question_intent not in whitelist:
        result.suggested_modifications.append(
            f"Question intent '{question_intent}' is unusual for {mode.value} mode"
        )

    return result


def _compute_plan_confidence(
    planner_decision: dict[str, Any],
    coverage_state: dict[str, Any],
    mode: AgentMode,
) -> float:
    """Compute confidence score for the plan."""
    score = 0.5  # Base confidence

    # Boost for framework gap alignment
    if planner_decision.get("selected_framework_gap"):
        score += 0.15

    # Boost for branch evidence
    if planner_decision.get("target_branch_id"):
        score += 0.1

    # Boost for rubric task alignment
    if planner_decision.get("rubric_task_id"):
        score += 0.15

    # Boost for evidence turn selection
    if planner_decision.get("selected_turn_ids"):
        score += 0.05

    # Reduce for novelty (new topic without strong connection)
    if planner_decision.get("is_novel_topic"):
        score -= 0.1

    # Reduce for drift
    if planner_decision.get("drift_detected"):
        score -= 0.2

    # Mode alignment bonus
    if mode == AgentMode.UNDERSTAND_CURRENT_CODE:
        if planner_decision.get("intent_mode") == "understand_current_code":
            score += 0.1

    # Coverage state consideration
    framework = coverage_state.get("framework", {})
    if framework.get("wrap_up_ready"):
        score += 0.1  # Good time to wrap up

    return min(1.0, max(0.0, score))


def review_question_text(
    question_text: str,
    mode: AgentMode | str,
    expected_intent: str | None = None,
) -> dict[str, Any]:
    """
    Review generated question text for mode compliance.

    This is a lightweight check on the final question text.

    Args:
        question_text: The generated question
        mode: Current agent mode
        expected_intent: Expected question intent

    Returns:
        Dict with is_valid, reasons, and suggestions
    """
    mode = AgentMode(mode) if isinstance(mode, str) else mode
    constraints = get_mode_constraints(mode)
    result = {
        "is_valid": True,
        "reasons": [],
        "suggestions": [],
    }

    # Check reject markers
    reject_markers = constraints.get("reject_markers", [])
    text_lower = question_text.lower()
    for marker in reject_markers:
        if marker.lower() in text_lower:
            result["is_valid"] = False
            result["reasons"].append(
                f"Contains '{marker}' which is not allowed in {mode.value} mode"
            )

    if question_text.count("?") != 1:
        result["is_valid"] = False
        result["reasons"].append("Question must contain exactly one question mark.")

    if len(question_text.strip()) > MAX_QUESTION_LENGTH:
        result["is_valid"] = False
        result["reasons"].append("Question is too long; keep it concise and direct.")

    # Check patterns
    if not constraints.get("allow_change_proposals", False):
        for pattern in CHANGE_PROPOSAL_PATTERNS:
            if re.search(pattern, question_text, re.IGNORECASE):
                result["is_valid"] = False
                result["reasons"].append(
                    "Question phrasing suggests change proposals, not understanding"
                )
                result["suggestions"].append(
                    "Rephrase to ask about current behavior (e.g., 'How does X currently...')"
                )
                break

    # Check for understanding patterns (good sign)
    has_understanding_pattern = any(
        re.search(pattern, question_text, re.IGNORECASE)
        for pattern in UNDERSTANDING_PATTERNS
    )
    if has_understanding_pattern:
        result["understanding_focus"] = True

    return result


def should_regenerate_question(
    review_result: ReviewResult,
    question_text: str,
    mode: AgentMode | str,
) -> tuple[bool, str]:
    """
    Determine if a question should be regenerated after review.

    Args:
        review_result: Result of plan review
        question_text: The generated question
        mode: Current agent mode

    Returns:
        Tuple of (should_regenerate, reason)
    """
    if not review_result.approved:
        return True, review_result.review_reason

    # Also check the question text itself
    text_review = review_question_text(question_text, mode)
    if not text_review["is_valid"]:
        return True, "; ".join(text_review["reasons"])

    return False, ""
