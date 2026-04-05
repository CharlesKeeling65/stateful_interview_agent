"""
Transcript event service for the Code Understand Agent.

Provides event emission for structured transcript modeling.
"""

import json
from datetime import datetime
from typing import Any

from app.logging import emit_event
from app.schemas.transcript_event import (
    AIQuestionEvent,
    HumanAnswerEvent,
    HumanReviewEvent,
    PhaseTransitionEvent,
    ModeChangeEvent,
    HumanGateEvent,
    DriftRepairEvent,
    BranchCreatedEvent,
    EventType,
    TranscriptEvent,
    event_to_dict,
)


def emit_ai_question_event(
    turn_no: int,
    question_text: str,
    question_plan: dict[str, Any],
    mode: str,
    phase: str,
    project_id: int | None = None,
) -> AIQuestionEvent:
    """
    Emit structured AI question event.

    Args:
        turn_no: Current turn number
        question_text: The generated question
        question_plan: The planner decision
        mode: Current agent mode
        phase: Current phase
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = AIQuestionEvent.create(
        turn_no=turn_no,
        question_text=question_text,
        question_plan=question_plan,
        mode=mode,
        phase=phase,
    )

    emit_event(
        "transcript",
        "ai.question",
        f"AI question generated for turn {turn_no}",
        project_id=project_id,
        turn_no=turn_no,
        **{"event_data": event_to_dict(event)},
    )

    return event


def emit_human_answer_event(
    turn_no: int,
    answer_text: str,
    answer_summary: str | None = None,
    project_id: int | None = None,
) -> HumanAnswerEvent:
    """
    Emit structured human answer event.

    Args:
        turn_no: Current turn number
        answer_text: The answer text
        answer_summary: Optional answer summary
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = HumanAnswerEvent.create(
        turn_no=turn_no,
        answer_text=answer_text,
        answer_summary=answer_summary,
    )

    emit_event(
        "transcript",
        "human.answer",
        f"Human answer submitted for turn {turn_no}",
        project_id=project_id,
        turn_no=turn_no,
        **{"event_data": event_to_dict(event)},
    )

    return event


def emit_human_review_event(
    turn_no: int,
    verdict: str | None,
    direction: str | None,
    preferred_next_focus: str | None = None,
    note: str | None = None,
    project_id: int | None = None,
) -> HumanReviewEvent:
    """
    Emit structured human review event.

    Args:
        turn_no: Current turn number
        verdict: Review verdict (sufficient/insufficient/drifted)
        direction: Direction (continue/redirect)
        preferred_next_focus: Optional preferred focus area
        note: Optional review note
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = HumanReviewEvent.create(
        turn_no=turn_no,
        verdict=verdict,
        direction=direction,
        preferred_next_focus=preferred_next_focus,
        note=note,
    )

    emit_event(
        "transcript",
        "human.review",
        f"Human review submitted for turn {turn_no}",
        project_id=project_id,
        turn_no=turn_no,
        verdict=verdict,
        direction=direction,
    )

    return event


def emit_phase_transition_event(
    from_phase: str,
    to_phase: str,
    trigger: str,
    confidence: float = 1.0,
    turn_no: int | None = None,
    project_id: int | None = None,
) -> PhaseTransitionEvent:
    """
    Emit structured phase transition event.

    Args:
        from_phase: Previous phase
        to_phase: New phase
        trigger: What triggered the transition
        confidence: Confidence in the transition
        turn_no: Turn number when transition occurred
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = PhaseTransitionEvent.create(
        from_phase=from_phase,
        to_phase=to_phase,
        trigger=trigger,
        confidence=confidence,
        turn_no=turn_no,
    )

    emit_event(
        "transcript",
        "phase.transition",
        f"Phase transition: {from_phase} -> {to_phase}",
        project_id=project_id,
        turn_no=turn_no,
        from_phase=from_phase,
        to_phase=to_phase,
        trigger=trigger,
    )

    return event


def emit_mode_change_event(
    from_mode: str,
    to_mode: str,
    reason: str,
    turn_no: int | None = None,
    project_id: int | None = None,
) -> ModeChangeEvent:
    """
    Emit structured mode change event.

    Args:
        from_mode: Previous mode
        to_mode: New mode
        reason: Reason for the change
        turn_no: Turn number when change occurred
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = ModeChangeEvent.create(
        from_mode=from_mode,
        to_mode=to_mode,
        reason=reason,
        turn_no=turn_no,
    )

    emit_event(
        "transcript",
        "mode.change",
        f"Mode changed: {from_mode} -> {to_mode}",
        project_id=project_id,
        turn_no=turn_no,
        from_mode=from_mode,
        to_mode=to_mode,
        reason=reason,
    )

    return event


def emit_human_gate_event(
    gate_type: str,
    reason: str,
    resolution: str | None = None,
    turn_no: int | None = None,
    project_id: int | None = None,
) -> HumanGateEvent:
    """
    Emit structured human gate event.

    Args:
        gate_type: Type of gate
        reason: Why gate was triggered
        resolution: How gate was resolved (if applicable)
        turn_no: Turn number
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = HumanGateEvent.create(
        gate_type=gate_type,
        reason=reason,
        resolution=resolution,
        turn_no=turn_no,
    )

    emit_event(
        "transcript",
        "human.gate",
        f"Human gate triggered: {gate_type}",
        project_id=project_id,
        turn_no=turn_no,
        gate_type=gate_type,
        reason=reason,
        resolution=resolution,
    )

    return event


def emit_drift_repair_event(
    drift_reason: str,
    repair_action: str,
    turn_no: int | None = None,
    project_id: int | None = None,
) -> DriftRepairEvent:
    """
    Emit structured drift repair event.

    Args:
        drift_reason: Why drift was detected
        repair_action: What action was taken to repair
        turn_no: Turn number
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = DriftRepairEvent.create(
        drift_reason=drift_reason,
        repair_action=repair_action,
        turn_no=turn_no,
    )

    emit_event(
        "transcript",
        "drift.repair",
        f"Drift detected and repaired: {drift_reason}",
        project_id=project_id,
        turn_no=turn_no,
        drift_reason=drift_reason,
        repair_action=repair_action,
    )

    return event


def emit_branch_created_event(
    branch_id: str,
    branch_label: str,
    stage: str,
    turn_no: int,
    project_id: int | None = None,
) -> BranchCreatedEvent:
    """
    Emit structured branch created event.

    Args:
        branch_id: New branch ID
        branch_label: Branch label
        stage: Current stage
        turn_no: Turn number when created
        project_id: Optional project ID for logging

    Returns:
        The created event
    """
    event = BranchCreatedEvent.create(
        branch_id=branch_id,
        branch_label=branch_label,
        stage=stage,
        turn_no=turn_no,
    )

    emit_event(
        "transcript",
        "branch.created",
        f"New topic branch created: {branch_id}",
        project_id=project_id,
        turn_no=turn_no,
        branch_id=branch_id,
        branch_label=branch_label,
    )

    return event


def add_event_to_log(
    existing_log: list[dict[str, Any]],
    event: TranscriptEvent,
) -> list[dict[str, Any]]:
    """
    Add an event to an existing event log.

    Args:
        existing_log: Current event log
        event: New event to add

    Returns:
        Updated event log
    """
    log = list(existing_log)
    log.append(event_to_dict(event))
    return log


def serialize_event_log(event_log: list[dict[str, Any]]) -> str:
    """Serialize event log to JSON string."""
    return json.dumps(event_log, ensure_ascii=True)


def deserialize_event_log(json_str: str | None) -> list[dict[str, Any]]:
    """Deserialize event log from JSON string."""
    if not json_str:
        return []
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return []
