"""
Mode service for the Code Understand Agent.

Provides mode-aware constraints and validation for different agent operating modes.
"""

from enum import Enum
from typing import Any


class AgentMode(str, Enum):
    """Agent operating modes."""

    UNDERSTAND_CURRENT_CODE = "understand_current_code"
    REVIEW_CURRENT_CODE = "review_current_code"
    PROPOSE_CHANGES = "propose_changes"


class TaskStatus(str, Enum):
    """Status for rubric tasks."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class GateType(str, Enum):
    """Types of human decision gates."""

    PHASE_COMPLETION = "phase_completion"
    DRIFT_REDIRECTION = "drift_redirection"
    BRANCH_PRIORITIZATION = "branch_prioritization"
    LOW_CONFIDENCE = "low_confidence"
    MODE_TRANSITION = "mode_transition"
    SCENARIO_COMPLETION = "scenario_completion"


# Change proposal patterns that should be rejected in understand mode
CHANGE_PROPOSAL_PATTERNS = [
    r"should\s+be\s+(changed|modified|updated|refactored)",
    r"(?:how|what)\s+(?:should|could|would)\s+we\s+(change|modify|fix)",
    r"suggest\s+(?:changes?|improvements?|refactoring)",
    r"recommended\s+(?:changes?|approach\s+for\s+changing)",
    r"better\s+(?:way|approach)\s+to\s+(implement|handle)",
    r"redesign\s+the",
    r"update\s+(?:the\s+)?tests?",
    r"modify\s+(?:this|the)",
    r"what\s+changes\s+(?:should|could|would)",
    r"improve\s+(?:this|the)\s+(?:code|implementation)",
]

# Understanding-focused patterns that are allowed in understand mode
UNDERSTANDING_PATTERNS = [
    r"how\s+does\s+(?:this|the)",
    r"what\s+does\s+(?:this|the)",
    r"why\s+does\s+(?:this|the)",
    r"explain\s+(?:how|what|why)",
    r"describe\s+(?:the|this)",
    r"current\s+(?:implementation|behavior|flow)",
    r"what\s+is\s+the\s+(?:current|existing)",
    r"walk\s+through\s+(?:the|this)",
    r"trace\s+(?:the|this)",
]


def get_mode_constraints(mode: AgentMode | str) -> dict[str, Any]:
    """
    Return constraints for each mode.

    Args:
        mode: The agent operating mode

    Returns:
        Dictionary with constraint settings for the mode
    """
    mode = AgentMode(mode) if isinstance(mode, str) else mode

    constraints = {
        AgentMode.UNDERSTAND_CURRENT_CODE: {
            "allow_change_proposals": False,
            "allow_review_questions": False,
            "focus_on_current_behavior": True,
            "reject_markers": [
                "should change",
                "should be changed",
                "should be modified",
                "should be refactored",
                "could we change",
                "how should we",
                "what should we",
                "suggest improvements",
                "recommended changes",
                "better way to",
                "redesign",
                "modify this",
                "update tests",
            ],
            "encouraged_patterns": UNDERSTANDING_PATTERNS,
            "question_intent_whitelist": [
                "explore",
                "deepen",
                "clarify",
                "trace_execution_path",
                "understand_current_code",
                "map_structure",
            ],
            "description": "Focus on understanding CURRENT behavior, not proposed changes.",
        },
        AgentMode.REVIEW_CURRENT_CODE: {
            "allow_change_proposals": False,
            "allow_review_questions": True,
            "focus_on_quality_assessment": True,
            "reject_markers": [
                "implement this",
                "change this now",
                "fix by doing",
            ],
            "encouraged_patterns": [
                r"quality\s+(?:of|in)",
                r"issues?\s+(?:in|with)",
                r"problems?\s+(?:in|with)",
                r"risks?",
                r"concerns?",
                r"technical\s+debt",
                r"code\s+smell",
            ],
            "question_intent_whitelist": [
                "review",
                "assess_quality",
                "identify_risks",
                "find_issues",
                "deepen",
                "clarify",
            ],
            "description": "Focus on reviewing and assessing code quality, not proposing implementation details.",
        },
        AgentMode.PROPOSE_CHANGES: {
            "allow_change_proposals": True,
            "allow_review_questions": True,
            "focus_on_improvement": True,
            "reject_markers": [],
            "encouraged_patterns": [
                r"improve",
                r"refactor",
                r"change",
                r"implement",
                r"fix",
                r"update",
            ],
            "question_intent_whitelist": None,  # All intents allowed
            "description": "Focus on proposing concrete changes to improve the codebase.",
        },
    }

    return constraints.get(mode, constraints[AgentMode.UNDERSTAND_CURRENT_CODE])


def validate_mode_transition(current_mode: AgentMode | str, target_mode: AgentMode | str) -> bool:
    """
    Validate if mode transition is allowed.

    Mode transitions follow a forward progression:
    understand_current_code -> review_current_code -> propose_changes

    Args:
        current_mode: Current mode
        target_mode: Target mode to transition to

    Returns:
        True if transition is allowed, False otherwise
    """
    current = AgentMode(current_mode) if isinstance(current_mode, str) else current_mode
    target = AgentMode(target_mode) if isinstance(target_mode, str) else target_mode

    # Same mode is always valid
    if current == target:
        return True

    valid_transitions = {
        AgentMode.UNDERSTAND_CURRENT_CODE: [
            AgentMode.REVIEW_CURRENT_CODE,
            AgentMode.PROPOSE_CHANGES,
        ],
        AgentMode.REVIEW_CURRENT_CODE: [
            AgentMode.PROPOSE_CHANGES,
        ],
        AgentMode.PROPOSE_CHANGES: [],  # Terminal mode, can't go back
    }

    return target in valid_transitions.get(current, [])


def get_mode_description(mode: AgentMode | str) -> str:
    """Get human-readable description for a mode."""
    mode = AgentMode(mode) if isinstance(mode, str) else mode
    descriptions = {
        AgentMode.UNDERSTAND_CURRENT_CODE: "Understanding current code behavior",
        AgentMode.REVIEW_CURRENT_CODE: "Reviewing code quality and identifying issues",
        AgentMode.PROPOSE_CHANGES: "Proposing changes and improvements",
    }
    return descriptions.get(mode, "Unknown mode")


def is_understanding_mode(mode: AgentMode | str) -> bool:
    """Check if the mode is focused on understanding (default mode)."""
    mode = AgentMode(mode) if isinstance(mode, str) else mode
    return mode == AgentMode.UNDERSTAND_CURRENT_CODE


def can_mode_propose_changes(mode: AgentMode | str) -> bool:
    """Check if the mode allows proposing changes."""
    mode = AgentMode(mode) if isinstance(mode, str) else mode
    constraints = get_mode_constraints(mode)
    return constraints.get("allow_change_proposals", False) is True
