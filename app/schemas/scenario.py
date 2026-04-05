"""
Scenario contract schemas for the Code Understand Agent.

Defines structured scenario contracts for use case coverage.
"""

from pydantic import BaseModel, Field
from typing import Any


class ScenarioContract(BaseModel):
    """Structured scenario contract for use cases."""

    scenario_id: str
    name: str = "Untitled Scenario"
    trigger: str = Field(default="", description="What initiates this scenario")
    actor: str = Field(default="", description="Who/what triggers and participates")
    inputs: list[str] = Field(default_factory=list, description="Required inputs")
    process_steps: list[str] = Field(default_factory=list, description="Step-by-step flow")
    outputs: list[str] = Field(default_factory=list, description="Resulting outputs")
    boundary_conditions: list[str] = Field(default_factory=list, description="Edge cases, errors, limits")
    extension_points: list[str] = Field(default_factory=list, description="Customization hooks")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_turn_ids: list[int] = Field(default_factory=list)
    evidence_turn_nos: list[int] = Field(default_factory=list)


class ScenarioValidationResult(BaseModel):
    """Result of validating a scenario contract."""

    is_complete: bool
    missing_fields: list[str]
    confidence: float
    needs_follow_up: bool
    follow_up_questions: list[str]
    current_scenario: ScenarioContract | None = None


# Required fields for a complete scenario
REQUIRED_SCENARIO_FIELDS = [
    "trigger",
    "actor",
    "inputs",
    "outputs",
    "boundary_conditions",
]

# Human-readable names for fields
SCENARIO_FIELD_LABELS = {
    "trigger": "Trigger/Entry Point",
    "actor": "Actors/Roles",
    "inputs": "Inputs Required",
    "process_steps": "Process Steps",
    "outputs": "Outputs/Results",
    "boundary_conditions": "Boundary Conditions",
    "extension_points": "Extension Points",
}

# Question templates for missing fields
SCENARIO_FOLLOW_UP_QUESTIONS = {
    "trigger": "What triggers or initiates the {name} scenario?",
    "actor": "Who are the actors or roles involved in {name}?",
    "inputs": "What inputs are required for {name} to execute?",
    "process_steps": "What are the step-by-step stages in {name}?",
    "outputs": "What outputs or results does {name} produce?",
    "boundary_conditions": "What edge cases, error conditions, or limits exist in {name}?",
    "extension_points": "What customization or extension points exist in {name}?",
}
