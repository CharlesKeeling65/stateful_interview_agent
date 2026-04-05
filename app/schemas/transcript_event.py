"""
Transcript event schemas for the Code Understand Agent.

Defines event types for structured transcript modeling.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of transcript events."""

    AI_QUESTION = "ai_question"
    AI_ANSDER_SUMMARY = "ai_answer_summary"
    HUMAN_ANSWER = "human_answer"
    HUMAN_REVIEW = "human_review"
    HUMAN_REDIRECT = "human_redirect"
    PHASE_TRANSITION = "phase_transition"
    MODE_CHANGE = "mode_change"
    HUMAN_GATE = "human_gate"
    BRANCH_CREATED = "branch_created"
    DRIFT_REPAIR = "drift_repair"
    RUN_SUMMARY = "run_summary"


class TranscriptEvent(BaseModel):
    """Base class for transcript events."""

    event_id: str
    event_type: EventType
    turn_no: int | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIQuestionEvent(TranscriptEvent):
    """Event for AI question generation."""

    event_type: EventType = EventType.AI_QUESTION

    @classmethod
    def create(
        cls,
        turn_no: int,
        question_text: str,
        question_plan: dict[str, Any],
        mode: str,
        phase: str,
    ) -> "AIQuestionEvent":
        return cls(
            event_id=f"q_{turn_no}_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "question_text": question_text,
                "question_plan": question_plan,
                "mode": mode,
                "phase": phase,
            },
            metadata={
                "branch_id": question_plan.get("target_branch_id"),
                "target_type": question_plan.get("target_type"),
                "rubric_task_id": question_plan.get("rubric_task_id"),
            },
        )


class HumanAnswerEvent(TranscriptEvent):
    """Event for human answer submission."""

    event_type: EventType = EventType.HUMAN_ANSWER

    @classmethod
    def create(
        cls,
        turn_no: int,
        answer_text: str,
        answer_summary: str | None = None,
    ) -> "HumanAnswerEvent":
        return cls(
            event_id=f"ha_{turn_no}_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "answer_length": len(answer_text),
                "has_summary": answer_summary is not None,
            },
        )


class HumanReviewEvent(TranscriptEvent):
    """Event for human review input."""

    event_type: EventType = EventType.HUMAN_REVIEW

    @classmethod
    def create(
        cls,
        turn_no: int,
        verdict: str | None,
        direction: str | None,
        preferred_next_focus: str | None = None,
        note: str | None = None,
    ) -> "HumanReviewEvent":
        return cls(
            event_id=f"hr_{turn_no}_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "verdict": verdict,
                "direction": direction,
                "preferred_next_focus": preferred_next_focus,
                "note": note,
            },
        )


class PhaseTransitionEvent(TranscriptEvent):
    """Event for phase transitions."""

    event_type: EventType = EventType.PHASE_TRANSITION

    @classmethod
    def create(
        cls,
        from_phase: str,
        to_phase: str,
        trigger: str,
        confidence: float = 1.0,
        turn_no: int | None = None,
    ) -> "PhaseTransitionEvent":
        return cls(
            event_id=f"pt_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "from_phase": from_phase,
                "to_phase": to_phase,
                "trigger": trigger,
                "confidence": confidence,
            },
        )


class ModeChangeEvent(TranscriptEvent):
    """Event for mode changes."""

    event_type: EventType = EventType.MODE_CHANGE

    @classmethod
    def create(
        cls,
        from_mode: str,
        to_mode: str,
        reason: str,
        turn_no: int | None = None,
    ) -> "ModeChangeEvent":
        return cls(
            event_id=f"mc_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "from_mode": from_mode,
                "to_mode": to_mode,
                "reason": reason,
            },
        )


class HumanGateEvent(TranscriptEvent):
    """Event for human decision gates."""

    event_type: EventType = EventType.HUMAN_GATE

    @classmethod
    def create(
        cls,
        gate_type: str,
        reason: str,
        resolution: str | None,
        turn_no: int | None = None,
    ) -> "HumanGateEvent":
        return cls(
            event_id=f"hg_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "gate_type": gate_type,
                "reason": reason,
                "resolution": resolution,
            },
        )


class DriftRepairEvent(TranscriptEvent):
    """Event for drift detection and repair."""

    event_type: EventType = EventType.DRIFT_REPAIR

    @classmethod
    def create(
        cls,
        drift_reason: str,
        repair_action: str,
        turn_no: int | None = None,
    ) -> "DriftRepairEvent":
        return cls(
            event_id=f"dr_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "drift_reason": drift_reason,
                "repair_action": repair_action,
            },
        )


class BranchCreatedEvent(TranscriptEvent):
    """Event for topic branch creation."""

    event_type: EventType = EventType.BRANCH_CREATED

    @classmethod
    def create(
        cls,
        branch_id: str,
        branch_label: str,
        stage: str,
        turn_no: int,
    ) -> "BranchCreatedEvent":
        return cls(
            event_id=f"bc_{turn_no}_{datetime.utcnow().timestamp():.0f}",
            turn_no=turn_no,
            payload={
                "branch_id": branch_id,
                "branch_label": branch_label,
                "stage": stage,
            },
        )


def event_to_dict(event: TranscriptEvent) -> dict[str, Any]:
    """Convert event to dictionary for JSON serialization."""
    return event.model_dump()


def events_to_json(events: list[TranscriptEvent]) -> str:
    """Convert list of events to JSON string."""
    import json
    return json.dumps([event_to_dict(e) for e in events], ensure_ascii=True)


def json_to_events(json_str: str) -> list[dict[str, Any]]:
    """Parse events from JSON string."""
    import json
    if not json_str:
        return []
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return []
