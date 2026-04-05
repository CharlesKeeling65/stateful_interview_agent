"""
Scenario service for the Code Understand Agent.

Provides scenario contract creation, validation, and follow-up question generation.
"""

import json
import re
from typing import Any

from app.models.turn import InterviewTurn
from app.schemas.scenario import (
    ScenarioContract,
    ScenarioValidationResult,
    REQUIRED_SCENARIO_FIELDS,
    SCENARIO_FIELD_LABELS,
    SCENARIO_FOLLOW_UP_QUESTIONS,
)


def validate_scenario_contract(scenario: ScenarioContract) -> ScenarioValidationResult:
    """
    Validate completeness of scenario contract.

    Args:
        scenario: The scenario contract to validate

    Returns:
        ScenarioValidationResult with completeness status
    """
    missing = []

    if not scenario.trigger:
        missing.append("trigger")
    if not scenario.actor:
        missing.append("actor")
    if len(scenario.inputs) == 0:
        missing.append("inputs")
    if len(scenario.outputs) == 0:
        missing.append("outputs")
    if len(scenario.boundary_conditions) == 0:
        missing.append("boundary_conditions")

    # Process steps are not strictly required but good to have
    if len(scenario.process_steps) == 0:
        missing.append("process_steps")

    # Calculate confidence based on completeness
    total_fields = len(REQUIRED_SCENARIO_FIELDS) + 1  # +1 for process_steps
    filled_fields = total_fields - len(missing)
    confidence = filled_fields / total_fields

    return ScenarioValidationResult(
        is_complete=len(missing) == 0,
        missing_fields=missing,
        confidence=confidence,
        needs_follow_up=len(missing) > 0,
        follow_up_questions=generate_follow_up_questions(missing, scenario),
        current_scenario=scenario,
    )


def generate_follow_up_questions(
    missing_fields: list[str],
    scenario: ScenarioContract,
) -> list[str]:
    """
    Generate specific follow-up questions for missing scenario fields.

    Args:
        missing_fields: List of missing field names
        scenario: The current scenario contract

    Returns:
        List of follow-up questions
    """
    questions = []
    name = scenario.name or "this scenario"

    for field in missing_fields:
        if field in SCENARIO_FOLLOW_UP_QUESTIONS:
            questions.append(SCENARIO_FOLLOW_UP_QUESTIONS[field].format(name=name))

    return questions


def extract_scenario_from_turn(turn: InterviewTurn) -> ScenarioContract | None:
    """
    Extract scenario contract from turn answer.

    This is a heuristic extraction based on patterns in the answer text.
    For more robust extraction, consider using an LLM.

    Args:
        turn: The interview turn to extract from

    Returns:
        ScenarioContract if scenario elements detected, None otherwise
    """
    if not turn.answer_text:
        return None

    text = turn.answer_text

    # Check if this turn is about a scenario/use case
    scenario_keywords = ["scenario", "use case", "workflow", "when", "user journey", "process"]
    if not any(kw in text.lower() for kw in scenario_keywords):
        return None

    scenario = ScenarioContract(
        scenario_id=f"scenario_turn_{turn.turn_no}",
        name=f"Scenario from Q{turn.turn_no}",
        evidence_turn_ids=[turn.id] if turn.id else [],
        evidence_turn_nos=[turn.turn_no],
    )

    # Try to extract trigger
    trigger_patterns = [
        r"(?:when|trigger|initiates?|starts?|begins?)[\s:]+([^.]+)",
        r"(?:entry\s+point)[\s:]+([^.]+)",
    ]
    for pattern in trigger_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            scenario.trigger = match.group(1).strip()[:200]
            break

    # Try to extract actor
    actor_patterns = [
        r"(?:actor|user|role|who)[\s:]+([^.]+)",
        r"(?:performed\s+by)[\s:]+([^.]+)",
    ]
    for pattern in actor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            scenario.actor = match.group(1).strip()[:200]
            break

    # Try to extract inputs
    input_patterns = [
        r"(?:input|requires?|needs?)[\s:]+([^.]+)",
        r"(?:provided|given)[\s:]+([^.]+)",
    ]
    for pattern in input_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            inputs = [inp.strip() for inp in match.group(1).split(",") if inp.strip()]
            scenario.inputs = inputs[:5]
            break

    # Try to extract outputs
    output_patterns = [
        r"(?:output|result|produces?|returns?)[\s:]+([^.]+)",
        r"(?:response)[\s:]+([^.]+)",
    ]
    for pattern in output_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            outputs = [out.strip() for out in match.group(1).split(",") if out.strip()]
            scenario.outputs = outputs[:5]
            break

    # Try to extract boundary conditions
    boundary_patterns = [
        r"(?:boundary|edge\s+case|error|limit|failure)[\s:]+([^.]+)",
        r"(?:if\s+\w+\s+fails?)[,:\s]+([^.]+)",
    ]
    for pattern in boundary_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            conditions = [c.strip() for c in match.group(1).split(",") if c.strip()]
            scenario.boundary_conditions = conditions[:5]
            break

    return scenario


def check_scenario_completion(
    coverage_state: dict[str, Any],
    turns: list[InterviewTurn] | None = None,
) -> dict[str, Any]:
    """
    Check scenario completion status from coverage state.

    Args:
        coverage_state: The current coverage state
        turns: Optional list of turns to extract scenarios from

    Returns:
        Dict with completion status, missing fields, and scenarios
    """
    framework = coverage_state.get("framework", {})
    use_cases = framework.get("use_cases", {})

    # Get existing scenario contracts if any
    existing_scenarios = []
    if turns:
        for turn in turns:
            if turn.stage == "Use Cases & Scenarios" and turn.answer_text:
                scenario = extract_scenario_from_turn(turn)
                if scenario:
                    existing_scenarios.append(scenario)

    # Count based completion
    scenario_count = use_cases.get("representative_scenarios_count", 0)
    actors_count = use_cases.get("actors_roles_count", 0)
    io_patterns_count = use_cases.get("input_output_patterns_count", 0)
    boundary_count = use_cases.get("boundary_conditions_count", 0)

    # Overall scenario completion status
    has_minimum_scenarios = scenario_count >= 1
    has_actors = actors_count >= 1
    has_io = io_patterns_count >= 1
    has_boundaries = boundary_count >= 1

    missing_aspects = []
    if not has_minimum_scenarios:
        missing_aspects.append("representative_scenarios")
    if not has_actors:
        missing_aspects.append("actors_roles")
    if not has_io:
        missing_aspects.append("input_output_patterns")
    if not has_boundaries:
        missing_aspects.append("boundary_conditions")

    # Validate individual scenarios if we have them
    scenario_validations = []
    for scenario in existing_scenarios:
        validation = validate_scenario_contract(scenario)
        scenario_validations.append(validation.model_dump())

    # Overall completion
    is_complete = (
        has_minimum_scenarios
        and has_actors
        and has_io
        and has_boundaries
        and all(v["is_complete"] for v in scenario_validations)
    )

    # Calculate confidence
    confidence = sum([
        0.25 if has_minimum_scenarios else 0,
        0.25 if has_actors else 0,
        0.25 if has_io else 0,
        0.25 if has_boundaries else 0,
    ])
    if scenario_validations:
        avg_scenario_conf = sum(v["confidence"] for v in scenario_validations) / len(scenario_validations)
        confidence = (confidence + avg_scenario_conf) / 2

    # Generate follow-up questions
    follow_ups = []
    if not has_minimum_scenarios:
        follow_ups.append("Can you describe a main user scenario or workflow?")
    if not has_actors:
        follow_ups.append("Who are the main actors or users involved in this system?")
    if not has_io:
        follow_ups.append("What are the typical inputs and outputs for this workflow?")
    if not has_boundaries:
        follow_ups.append("What edge cases or error conditions should be considered?")

    # Add scenario-specific follow-ups
    for validation in scenario_validations:
        follow_ups.extend(validation.get("follow_up_questions", []))

    return {
        "is_complete": is_complete,
        "confidence": confidence,
        "missing_aspects": missing_aspects,
        "scenario_count": scenario_count,
        "existing_scenarios": [s.model_dump() for s in existing_scenarios],
        "scenario_validations": scenario_validations,
        "follow_up_questions": follow_ups[:5],  # Limit to 5 questions
    }


def create_default_scenario_contract(name: str = "Primary Scenario") -> ScenarioContract:
    """Create a default empty scenario contract for initialization."""
    return ScenarioContract(
        scenario_id=f"scenario_{name.lower().replace(' ', '_')}",
        name=name,
    )


def update_scenario_from_answer(
    scenario: ScenarioContract,
    answer_text: str,
    turn_id: int | None = None,
    turn_no: int | None = None,
) -> ScenarioContract:
    """
    Update scenario contract with additional information from an answer.

    Args:
        scenario: Existing scenario contract
        answer_text: New answer text to extract from
        turn_id: Turn ID for evidence
        turn_no: Turn number for evidence

    Returns:
        Updated scenario contract
    """
    # Extract any missing fields
    temp_scenario = extract_scenario_from_turn(
        type("Turn", (), {"answer_text": answer_text, "turn_no": turn_no or 0, "id": turn_id})()
    )

    if not temp_scenario:
        return scenario

    # Update empty fields with extracted data
    updates = {}
    if not scenario.trigger and temp_scenario.trigger:
        updates["trigger"] = temp_scenario.trigger
    if not scenario.actor and temp_scenario.actor:
        updates["actor"] = temp_scenario.actor
    if not scenario.inputs and temp_scenario.inputs:
        updates["inputs"] = temp_scenario.inputs
    if not scenario.outputs and temp_scenario.outputs:
        updates["outputs"] = temp_scenario.outputs
    if not scenario.boundary_conditions and temp_scenario.boundary_conditions:
        updates["boundary_conditions"] = temp_scenario.boundary_conditions

    # Add evidence
    evidence_turn_ids = list(scenario.evidence_turn_ids)
    evidence_turn_nos = list(scenario.evidence_turn_nos)
    if turn_id and turn_id not in evidence_turn_ids:
        evidence_turn_ids.append(turn_id)
    if turn_no and turn_no not in evidence_turn_nos:
        evidence_turn_nos.append(turn_no)

    return ScenarioContract(
        scenario_id=scenario.scenario_id,
        name=scenario.name,
        trigger=updates.get("trigger", scenario.trigger),
        actor=updates.get("actor", scenario.actor),
        inputs=updates.get("inputs", scenario.inputs),
        process_steps=scenario.process_steps,
        outputs=updates.get("outputs", scenario.outputs),
        boundary_conditions=updates.get("boundary_conditions", scenario.boundary_conditions),
        extension_points=scenario.extension_points,
        confidence=min(1.0, scenario.confidence + (0.2 if updates else 0)),
        evidence_turn_ids=evidence_turn_ids,
        evidence_turn_nos=evidence_turn_nos,
    )


def serialize_scenario(scenario: ScenarioContract) -> str:
    """Serialize scenario to JSON string."""
    return scenario.model_dump_json()


def deserialize_scenario(json_str: str | None) -> ScenarioContract | None:
    """Deserialize scenario from JSON string."""
    if not json_str:
        return None
    try:
        return ScenarioContract.model_validate_json(json_str)
    except Exception:
        return None
