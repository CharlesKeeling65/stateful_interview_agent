"""
Human gate service for the Code Understand Agent.

Provides decision gate creation and resolution for human-in-the-loop orchestration.
"""

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.mode_service import GateType


class GateOption(BaseModel):
    """A single option for a human decision gate."""

    action: str
    label: str
    description: str | None = None


class HumanGate(BaseModel):
    """A human decision gate requiring user input."""

    gate_id: str = Field(default_factory=lambda: f"gate_{uuid4().hex[:8]}")
    gate_type: GateType
    phase: str | None = None
    reason: str
    options: list[GateOption] = Field(default_factory=list)
    default_action: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved: bool = False
    resolution: str | None = None
    resolved_at: str | None = None
    additional_context: dict[str, Any] = Field(default_factory=dict)

    def resolve(self, action: str) -> "HumanGate":
        """Mark this gate as resolved with the given action."""
        return HumanGate(
            gate_id=self.gate_id,
            gate_type=self.gate_type,
            phase=self.phase,
            reason=self.reason,
            options=self.options,
            default_action=self.default_action,
            created_at=self.created_at,
            resolved=True,
            resolution=action,
            resolved_at=datetime.utcnow().isoformat(),
            additional_context=self.additional_context,
        )


def create_phase_completion_gate(
    phase: str,
    task_summary: dict[str, Any] | None = None,
) -> HumanGate:
    """
    Create a gate for phase completion confirmation.

    Args:
        phase: The phase that is completing
        task_summary: Optional summary of completed tasks

    Returns:
        HumanGate for user confirmation
    """
    return HumanGate(
        gate_type=GateType.PHASE_COMPLETION,
        phase=phase,
        reason=f"Phase '{phase}' has completed required tasks. Confirm to proceed to the next phase?",
        options=[
            GateOption(
                action="confirm",
                label="Proceed",
                description="Advance to the next phase",
            ),
            GateOption(
                action="extend",
                label="Continue Phase",
                description="Stay in current phase for more exploration",
            ),
            GateOption(
                action="review",
                label="Review Gaps",
                description="Address remaining gaps first",
            ),
        ],
        default_action="confirm",
        additional_context=task_summary or {},
    )


def create_drift_redirection_gate(
    drift_info: dict[str, Any],
) -> HumanGate:
    """
    Create a gate for drift redirection.

    Args:
        drift_info: Information about detected drift

    Returns:
        HumanGate for drift handling
    """
    drift_reason = drift_info.get("reason", "Conversation topic has drifted")
    branch_id = drift_info.get("branch_id")

    return HumanGate(
        gate_type=GateType.DRIFT_REDIRECTION,
        reason=f"Detected drift: {drift_reason}",
        options=[
            GateOption(
                action="redirect",
                label="Redirect",
                description="Return to main topic alignment",
            ),
            GateOption(
                action="continue",
                label="Continue",
                description="Accept current direction",
            ),
            GateOption(
                action="new_branch",
                label="New Branch",
                description="Start a new topic branch",
            ),
        ],
        default_action="redirect",
        additional_context={
            "branch_id": branch_id,
            "drift_details": drift_info,
        },
    )


def create_branch_prioritization_gate(
    branches: list[dict[str, Any]],
) -> HumanGate:
    """
    Create a gate for branch prioritization.

    Args:
        branches: List of candidate branches with their priority scores

    Returns:
        HumanGate for branch selection
    """
    options = [
        GateOption(
            action=f"branch_{i}",
            label=branch.get("label", f"Branch {i + 1}")[:40],
            description=f"Priority: {branch.get('priority', 0):.2f}",
        )
        for i, branch in enumerate(branches[:4])  # Limit to 4 options
    ]

    # Add custom option
    options.append(
        GateOption(
            action="auto",
            label="Auto Select",
            description="Let the system choose the best branch",
        )
    )

    return HumanGate(
        gate_type=GateType.BRANCH_PRIORITIZATION,
        reason="Multiple topic branches are candidates for the next question. Which should be prioritized?",
        options=options,
        default_action="auto",
        additional_context={
            "branches": branches,
        },
    )


def create_low_confidence_gate(
    planner_decision: dict[str, Any],
) -> HumanGate:
    """
    Create a gate for low confidence scenarios.

    Args:
        planner_decision: The planner's decision with low confidence

    Returns:
        HumanGate for confidence handling
    """
    confidence = planner_decision.get("confidence", 0)
    question_intent = planner_decision.get("question_intent", "unknown")
    target = planner_decision.get("target_label", "unknown target")

    return HumanGate(
        gate_type=GateType.LOW_CONFIDENCE,
        reason=f"Low confidence ({confidence:.0%}) in planned question about '{target}'. Please confirm or adjust.",
        options=[
            GateOption(
                action="proceed",
                label="Proceed",
                description="Accept the suggested question",
            ),
            GateOption(
                action="alternative",
                label="Find Alternative",
                description="Look for a better question match",
            ),
            GateOption(
                action="human_input",
                label="Provide Guidance",
                description="Give specific direction for the next question",
            ),
        ],
        default_action="alternative",
        additional_context={
            "confidence": confidence,
            "question_intent": question_intent,
            "planner_decision": planner_decision,
        },
    )


def create_mode_transition_gate(
    current_mode: str,
    suggested_mode: str,
    reason: str,
) -> HumanGate:
    """
    Create a gate for mode transition approval.

    Args:
        current_mode: Current agent mode
        suggested_mode: Proposed new mode
        reason: Why the transition is suggested

    Returns:
        HumanGate for mode transition
    """
    return HumanGate(
        gate_type=GateType.MODE_TRANSITION,
        reason=f"Suggested mode change from '{current_mode}' to '{suggested_mode}': {reason}",
        options=[
            GateOption(
                action="accept",
                label="Accept",
                description=f"Switch to {suggested_mode} mode",
            ),
            GateOption(
                action="decline",
                label="Stay Current",
                description=f"Remain in {current_mode} mode",
            ),
        ],
        default_action="accept",
        additional_context={
            "current_mode": current_mode,
            "suggested_mode": suggested_mode,
        },
    )


def create_scenario_completion_gate(
    scenario_validation: dict[str, Any],
) -> HumanGate:
    """
    Create a gate for scenario contract completion.

    Args:
        scenario_validation: Validation result for scenario contracts

    Returns:
        HumanGate for scenario completion
    """
    missing_fields = scenario_validation.get("missing_fields", [])
    current_confidence = scenario_validation.get("confidence", 0)

    return HumanGate(
        gate_type=GateType.SCENARIO_COMPLETION,
        reason=f"Scenario contracts need completion. Missing: {', '.join(missing_fields)} (confidence: {current_confidence:.0%})",
        options=[
            GateOption(
                action="continue",
                label="Continue Collecting",
                description="Ask questions to fill gaps",
            ),
            GateOption(
                action="accept",
                label="Accept Current",
                description="Proceed with current detail level",
            ),
            GateOption(
                action="skip",
                label="Skip Scenarios",
                description="Move to wrap-up without full scenarios",
            ),
        ],
        default_action="continue",
        additional_context=scenario_validation,
    )


def serialize_gate(gate: HumanGate | None) -> str:
    """Serialize gate to JSON string."""
    if gate is None:
        return "null"
    return gate.model_dump_json()


def deserialize_gate(json_str: str | None) -> HumanGate | None:
    """Deserialize gate from JSON string."""
    if not json_str or json_str == "null":
        return None

    try:
        data = json.loads(json_str)
        if not data:
            return None
        return HumanGate.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None


def is_gate_active(gate: HumanGate | None) -> bool:
    """Check if a gate is currently active (exists and unresolved)."""
    return gate is not None and not gate.resolved


def resolve_gate(gate: HumanGate, action: str) -> HumanGate:
    """Resolve a gate with the given action."""
    return gate.resolve(action)


def get_gate_resolution_instruction(gate: HumanGate) -> str:
    """Get instruction text for what to do after gate resolution."""
    resolution_instructions = {
        GateType.PHASE_COMPLETION: {
            "confirm": "Proceeding to next phase.",
            "extend": "Continuing in current phase for further exploration.",
            "review": "Focusing on remaining gaps in current phase.",
        },
        GateType.DRIFT_REDIRECTION: {
            "redirect": "Redirecting to main topic alignment.",
            "continue": "Continuing with current direction.",
            "new_branch": "Starting a new topic branch.",
        },
        GateType.BRANCH_PRIORITIZATION: {
            "auto": "System will select the best branch automatically.",
        },
        GateType.LOW_CONFIDENCE: {
            "proceed": "Proceeding with suggested question.",
            "alternative": "Searching for alternative question.",
            "human_input": "Waiting for specific guidance.",
        },
        GateType.MODE_TRANSITION: {
            "accept": "Mode transition accepted.",
            "decline": "Staying in current mode.",
        },
        GateType.SCENARIO_COMPLETION: {
            "continue": "Will ask questions to complete scenarios.",
            "accept": "Proceeding with current scenario detail.",
            "skip": "Skipping to wrap-up.",
        },
    }

    action_map = resolution_instructions.get(gate.gate_type, {})
    return action_map.get(gate.resolution, f"Gate resolved with action: {gate.resolution}")


def gate_resolution_to_human_review_signal(
    gate: HumanGate,
    action: str,
    *,
    preferred_next_focus: str | None = None,
    note: str | None = None,
    phase_ready: bool | None = None,
) -> dict[str, Any]:
    """Translate a resolved human gate into planner/stage-consumable review input."""
    signal: dict[str, Any] = {
        "direction": "continue",
        "gate_type": gate.gate_type.value,
        "gate_action": action,
        "gate_id": gate.gate_id,
    }

    if preferred_next_focus:
        signal["preferred_next_focus"] = preferred_next_focus
    if note:
        signal["note"] = note
    if phase_ready is not None:
        signal["phase_ready"] = phase_ready

    if gate.gate_type == GateType.DRIFT_REDIRECTION:
        signal["direction"] = "redirect" if action == "redirect" else "continue"
        signal["verdict"] = "drifted"
    elif gate.gate_type == GateType.PHASE_COMPLETION:
        signal["phase_ready"] = action == "confirm"
        if action == "review":
            signal["direction"] = "redirect"
            signal.setdefault("verdict", "insufficient")
    elif gate.gate_type == GateType.LOW_CONFIDENCE:
        if action in {"alternative", "human_input"}:
            signal["direction"] = "redirect"
            signal.setdefault("verdict", "insufficient")
    elif gate.gate_type == GateType.BRANCH_PRIORITIZATION:
        if action != "auto":
            signal["direction"] = "redirect"
            signal["preferred_next_focus"] = preferred_next_focus or action.replace("branch_", "branch ")
    elif gate.gate_type == GateType.SCENARIO_COMPLETION:
        if action == "continue":
            signal["direction"] = "redirect"
            signal.setdefault("preferred_next_focus", "scenario")
        elif action == "skip":
            signal["phase_ready"] = True

    return signal
