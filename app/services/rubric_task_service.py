"""
Rubric task board service for the Code Understand Agent.

Provides task-board style orchestration with structured tasks per phase.
"""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.turn import InterviewTurn
from app.services.mode_service import TaskStatus


class RubricTask(BaseModel):
    """A single task in the rubric task board."""

    task_id: str
    phase: str
    label: str
    description: str
    status: TaskStatus = TaskStatus.NOT_STARTED
    priority: float = 0.5
    confidence: float = 0.0
    evidence_turn_ids: list[int] = Field(default_factory=list)
    evidence_turn_nos: list[int] = Field(default_factory=list)
    human_confirmed: bool = False
    required_for_phase_completion: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str | None = None


class RubricTaskBoard(BaseModel):
    """The complete task board for a project."""

    version: int = 1
    phases: dict[str, list[RubricTask]] = Field(default_factory=dict)
    phase_status: dict[str, TaskStatus] = Field(default_factory=dict)
    human_gate_triggered: bool = False
    human_gate_reason: str | None = None
    current_phase: str = "panorama_mapping"
    scenario_contracts: list[dict[str, Any]] = Field(default_factory=list)


# Default task definitions per phase
DEFAULT_RUBRIC_TASKS = {
    "panorama_mapping": [
        {
            "task_id": "pan_purpose",
            "label": "Purpose & Goals",
            "description": "What problem does the system solve? What are its core goals?",
            "priority": 1.0,
        },
        {
            "task_id": "pan_users",
            "label": "Target Users",
            "description": "Who uses the system? What roles do they have?",
            "priority": 0.9,
        },
        {
            "task_id": "pan_boundaries",
            "label": "Boundaries & Scope",
            "description": "What is in scope? What is explicitly out of scope?",
            "priority": 0.85,
        },
        {
            "task_id": "pan_modules",
            "label": "Major Modules",
            "description": "What are the main components or modules?",
            "priority": 0.95,
        },
        {
            "task_id": "pan_workflow",
            "label": "High-Level Workflow",
            "description": "How does work flow through the system at a high level?",
            "priority": 0.9,
        },
        {
            "task_id": "pan_relationships",
            "label": "Module Relationships",
            "description": "How do the major modules interact with each other?",
            "priority": 0.85,
        },
    ],
    "architecture_understanding": [
        {
            "task_id": "arch_style",
            "label": "Architecture Style",
            "description": "What architectural pattern or style is the system built on?",
            "priority": 1.0,
        },
        {
            "task_id": "arch_responsibilities",
            "label": "Module Responsibilities",
            "description": "What specific responsibilities does each module own?",
            "priority": 0.95,
        },
        {
            "task_id": "arch_collaboration",
            "label": "Collaboration Mechanisms",
            "description": "How do modules communicate? HTTP, events, queues?",
            "priority": 0.9,
        },
        {
            "task_id": "arch_call_chains",
            "label": "Key Call Chains",
            "description": "What are the main request paths through the system?",
            "priority": 0.9,
        },
        {
            "task_id": "arch_structure",
            "label": "System Structure",
            "description": "How is the codebase organized? Layers, tiers, boundaries?",
            "priority": 0.85,
        },
        {
            "task_id": "arch_rationale",
            "label": "Design Rationale",
            "description": "Why were key architectural decisions made? Tradeoffs?",
            "priority": 0.8,
        },
    ],
    "code_detail_completion": [],  # Dynamic, based on branches
    "use_cases_scenarios": [
        {
            "task_id": "use_scenario_1",
            "label": "Primary Scenario",
            "description": "Main user workflow - trigger, actors, inputs, process, outputs",
            "priority": 1.0,
            "required_for_phase_completion": True,
        },
        {
            "task_id": "use_scenario_2",
            "label": "Secondary Scenario",
            "description": "Alternative workflow or edge case scenario",
            "priority": 0.9,
            "required_for_phase_completion": True,
        },
        {
            "task_id": "use_actors",
            "label": "Actors & Roles",
            "description": "Complete mapping of actors and their roles in the system",
            "priority": 0.85,
        },
        {
            "task_id": "use_io_patterns",
            "label": "Input/Output Patterns",
            "description": "Common input and output patterns across scenarios",
            "priority": 0.8,
        },
        {
            "task_id": "use_boundaries",
            "label": "Boundary Conditions",
            "description": "Edge cases, error conditions, and boundary scenarios",
            "priority": 0.75,
        },
    ],
}


def initialize_task_board() -> RubricTaskBoard:
    """Initialize a new task board with default tasks."""
    phases: dict[str, list[RubricTask]] = {}
    phase_status: dict[str, TaskStatus] = {}

    for phase_key, tasks in DEFAULT_RUBRIC_TASKS.items():
        phases[phase_key] = [
            RubricTask(
                task_id=task["task_id"],
                phase=phase_key,
                label=task["label"],
                description=task["description"],
                priority=task.get("priority", 0.5),
                required_for_phase_completion=task.get("required_for_phase_completion", True),
            )
            for task in tasks
        ]
        phase_status[phase_key] = TaskStatus.NOT_STARTED

    return RubricTaskBoard(
        version=1,
        phases=phases,
        phase_status=phase_status,
        current_phase="panorama_mapping",
    )


def phase_name_to_key(stage_name: str) -> str:
    """Convert stage name to task board phase key."""
    mapping = {
        "Panorama Mapping": "panorama_mapping",
        "Architecture Understanding": "architecture_understanding",
        "Code Detail Completion": "code_detail_completion",
        "Use Cases & Scenarios": "use_cases_scenarios",
        "Final Wrap-up": "final_wrap_up",
    }
    return mapping.get(stage_name, stage_name.lower().replace(" ", "_").replace("&", "and"))


def key_to_phase_name(key: str) -> str:
    """Convert task board phase key to stage name."""
    mapping = {
        "panorama_mapping": "Panorama Mapping",
        "architecture_understanding": "Architecture Understanding",
        "code_detail_completion": "Code Detail Completion",
        "use_cases_scenarios": "Use Cases & Scenarios",
        "final_wrap_up": "Final Wrap-up",
    }
    return mapping.get(key, key)


def update_task_from_turn(
    task_board: RubricTaskBoard,
    turn: InterviewTurn,
    framework_key: str | None = None,
) -> RubricTaskBoard:
    """
    Update task board based on turn evidence.

    Args:
        task_board: Current task board
        turn: The interview turn to process
        framework_key: Optional specific framework key to update

    Returns:
        Updated task board
    """
    if not turn.answer_text:
        return task_board

    phase_key = phase_name_to_key(turn.stage)
    tasks = task_board.phases.get(phase_key, [])

    # Map framework keys to task IDs
    key_to_task = {
        # Panorama
        "purpose": "pan_purpose",
        "target_users": "pan_users",
        "boundaries": "pan_boundaries",
        "major_modules": "pan_modules",
        "high_level_workflow": "pan_workflow",
        "initial_module_relationships": "pan_relationships",
        # Architecture
        "architecture_style_or_organization": "arch_style",
        "module_responsibilities": "arch_responsibilities",
        "collaboration_mechanisms": "arch_collaboration",
        "key_call_chains": "arch_call_chains",
        "system_structure": "arch_structure",
        "design_rationale_or_quality_attributes": "arch_rationale",
        # Use Cases
        "representative_scenarios_count": "use_scenario_1",
        "actors_roles_count": "use_actors",
        "input_output_patterns_count": "use_io_patterns",
        "boundary_conditions_count": "use_boundaries",
    }

    if framework_key and framework_key in key_to_task:
        task_id = key_to_task[framework_key]
        for i, task in enumerate(tasks):
            if task.task_id == task_id:
                tasks[i] = RubricTask(
                    task_id=task.task_id,
                    phase=task.phase,
                    label=task.label,
                    description=task.description,
                    status=TaskStatus.IN_PROGRESS if task.status == TaskStatus.NOT_STARTED else task.status,
                    priority=task.priority,
                    confidence=min(1.0, task.confidence + 0.3),
                    evidence_turn_ids=list(set(task.evidence_turn_ids + [turn.id])),
                    evidence_turn_nos=list(set(task.evidence_turn_nos + [turn.turn_no])),
                    human_confirmed=task.human_confirmed,
                    required_for_phase_completion=task.required_for_phase_completion,
                    updated_at=datetime.utcnow().isoformat(),
                )
                break

    task_board.phases[phase_key] = tasks
    return _update_phase_status(task_board, phase_key)


def _update_phase_status(task_board: RubricTaskBoard, phase_key: str) -> RubricTaskBoard:
    """Update phase status based on task completion."""
    tasks = task_board.phases.get(phase_key, [])

    if not tasks:
        task_board.phase_status[phase_key] = TaskStatus.NOT_STARTED
        return task_board

    required_tasks = [t for t in tasks if t.required_for_phase_completion]
    completed_required = [t for t in required_tasks if t.status == TaskStatus.COMPLETED]

    if len(required_tasks) == 0:
        # No required tasks, treat as completed when all are done
        if all(t.status == TaskStatus.COMPLETED for t in tasks):
            task_board.phase_status[phase_key] = TaskStatus.COMPLETED
        elif any(t.status == TaskStatus.IN_PROGRESS for t in tasks):
            task_board.phase_status[phase_key] = TaskStatus.IN_PROGRESS
    else:
        completion_ratio = len(completed_required) / len(required_tasks)

        if completion_ratio >= 1.0:
            task_board.phase_status[phase_key] = TaskStatus.COMPLETED
        elif completion_ratio > 0 or any(t.status == TaskStatus.IN_PROGRESS for t in tasks):
            task_board.phase_status[phase_key] = TaskStatus.IN_PROGRESS
        else:
            task_board.phase_status[phase_key] = TaskStatus.NOT_STARTED

    return task_board


def get_next_priority_task(
    task_board: RubricTaskBoard,
    phase_key: str | None = None,
) -> RubricTask | None:
    """
    Get the highest priority incomplete task for a phase.

    Args:
        task_board: The task board
        phase_key: Optional phase key, defaults to current phase

    Returns:
        The highest priority incomplete task, or None
    """
    if phase_key is None:
        phase_key = task_board.current_phase

    tasks = task_board.phases.get(phase_key, [])
    incomplete = [
        t
        for t in tasks
        if t.status in (TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS)
    ]

    if not incomplete:
        return None

    return max(incomplete, key=lambda t: t.priority)


def get_phase_gaps(task_board: RubricTaskBoard, phase_key: str) -> list[str]:
    """Get list of incomplete task IDs for a phase."""
    tasks = task_board.phases.get(phase_key, [])
    return [
        t.task_id
        for t in tasks
        if t.status != TaskStatus.COMPLETED and t.required_for_phase_completion
    ]


def is_phase_complete(task_board: RubricTaskBoard, phase_key: str) -> bool:
    """Check if a phase has all required tasks completed."""
    return task_board.phase_status.get(phase_key) == TaskStatus.COMPLETED


def should_trigger_phase_gate(task_board: RubricTaskBoard) -> tuple[bool, str | None]:
    """
    Check if human gate should be triggered for phase completion.

    Returns:
        Tuple of (should_trigger, reason)
    """
    current_phase = task_board.current_phase
    phase_status = task_board.phase_status.get(current_phase)

    if phase_status == TaskStatus.COMPLETED:
        # Check if there's a next phase
        phases = [
            "panorama_mapping",
            "architecture_understanding",
            "code_detail_completion",
            "use_cases_scenarios",
        ]
        try:
            current_idx = phases.index(current_phase)
            if current_idx < len(phases) - 1:
                next_phase = phases[current_idx + 1]
                return (
                    True,
                    f"Phase '{key_to_phase_name(current_phase)}' completed. "
                    f"Ready to advance to '{key_to_phase_name(next_phase)}'?",
                )
        except ValueError:
            pass

    return False, None


def mark_task_completed(
    task_board: RubricTaskBoard,
    task_id: str,
    confidence: float = 1.0,
    human_confirmed: bool = False,
) -> RubricTaskBoard:
    """Mark a specific task as completed."""
    for phase_key, tasks in task_board.phases.items():
        for i, task in enumerate(tasks):
            if task.task_id == task_id:
                tasks[i] = RubricTask(
                    task_id=task.task_id,
                    phase=task.phase,
                    label=task.label,
                    description=task.description,
                    status=TaskStatus.COMPLETED,
                    priority=task.priority,
                    confidence=confidence,
                    evidence_turn_ids=task.evidence_turn_ids,
                    evidence_turn_nos=task.evidence_turn_nos,
                    human_confirmed=human_confirmed,
                    required_for_phase_completion=task.required_for_phase_completion,
                    updated_at=datetime.utcnow().isoformat(),
                )
                task_board.phases[phase_key] = tasks
                return _update_phase_status(task_board, phase_key)

    return task_board


def add_dynamic_code_detail_task(
    task_board: RubricTaskBoard,
    task_id: str,
    label: str,
    description: str,
    priority: float = 0.5,
    turn_id: int | None = None,
    turn_no: int | None = None,
) -> RubricTaskBoard:
    """Add a dynamic task for code detail phase (based on branches)."""
    if "code_detail_completion" not in task_board.phases:
        task_board.phases["code_detail_completion"] = []

    task = RubricTask(
        task_id=task_id,
        phase="code_detail_completion",
        label=label,
        description=description,
        status=TaskStatus.IN_PROGRESS,
        priority=priority,
        confidence=0.3,
        evidence_turn_ids=[turn_id] if turn_id else [],
        evidence_turn_nos=[turn_no] if turn_no else [],
        required_for_phase_completion=False,  # Code detail tasks are optional
    )

    task_board.phases["code_detail_completion"].append(task)
    return task_board


def serialize_task_board(task_board: RubricTaskBoard) -> str:
    """Serialize task board to JSON string."""
    return task_board.model_dump_json()


def deserialize_task_board(json_str: str | None) -> RubricTaskBoard:
    """Deserialize task board from JSON string."""
    if not json_str:
        return initialize_task_board()

    try:
        data = json.loads(json_str)
        return RubricTaskBoard.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return initialize_task_board()


def migrate_coverage_to_task_board(coverage_state: dict[str, Any]) -> dict[str, Any]:
    """
    Migrate legacy coverage state to task board format.

    This preserves backward compatibility while converting to the new schema.
    """
    task_board = initialize_task_board()

    if not coverage_state:
        return json.loads(serialize_task_board(task_board))

    framework = coverage_state.get("framework", {})

    # Migrate panorama tasks
    panorama = framework.get("panorama", {})
    for key, task_id in [
        ("purpose", "pan_purpose"),
        ("target_users", "pan_users"),
        ("boundaries", "pan_boundaries"),
        ("major_modules", "pan_modules"),
        ("high_level_workflow", "pan_workflow"),
        ("initial_module_relationships", "pan_relationships"),
    ]:
        if panorama.get(key):
            task_board = mark_task_completed(task_board, task_id)

    # Migrate architecture tasks
    architecture = framework.get("architecture", {})
    for key, task_id in [
        ("architecture_style_or_organization", "arch_style"),
        ("module_responsibilities", "arch_responsibilities"),
        ("collaboration_mechanisms", "arch_collaboration"),
        ("key_call_chains", "arch_call_chains"),
        ("system_structure", "arch_structure"),
        ("design_rationale_or_quality_attributes", "arch_rationale"),
    ]:
        if architecture.get(key):
            task_board = mark_task_completed(task_board, task_id)

    # Migrate use cases tasks (count-based)
    use_cases = framework.get("use_cases", {})
    for key, task_id in [
        ("representative_scenarios_count", "use_scenario_1"),
        ("actors_roles_count", "use_actors"),
        ("input_output_patterns_count", "use_io_patterns"),
        ("boundary_conditions_count", "use_boundaries"),
    ]:
        count = use_cases.get(key, 0)
        if isinstance(count, (int, float)) and count > 0:
            task_board = mark_task_completed(task_board, task_id, confidence=min(1.0, count / 2))

    return json.loads(serialize_task_board(task_board))


def sync_task_board(
    task_board: RubricTaskBoard | None,
    *,
    coverage_state: dict[str, Any],
    current_stage: str,
) -> RubricTaskBoard:
    """Refresh task-board completion state from coverage while preserving the structure."""
    board = task_board or initialize_task_board()
    migrated = RubricTaskBoard.model_validate(migrate_coverage_to_task_board(coverage_state))

    for phase_key, tasks in migrated.phases.items():
        existing_by_id = {task.task_id: task for task in board.phases.get(phase_key, [])}
        merged_tasks: list[RubricTask] = []
        for migrated_task in tasks:
            existing = existing_by_id.get(migrated_task.task_id)
            if existing is None:
                merged_tasks.append(migrated_task)
                continue
            merged_tasks.append(
                RubricTask(
                    task_id=existing.task_id,
                    phase=existing.phase,
                    label=existing.label,
                    description=existing.description,
                    status=(
                        TaskStatus.COMPLETED
                        if migrated_task.status == TaskStatus.COMPLETED
                        else existing.status
                    ),
                    priority=existing.priority,
                    confidence=max(existing.confidence, migrated_task.confidence),
                    evidence_turn_ids=list(set(existing.evidence_turn_ids + migrated_task.evidence_turn_ids)),
                    evidence_turn_nos=list(set(existing.evidence_turn_nos + migrated_task.evidence_turn_nos)),
                    human_confirmed=existing.human_confirmed,
                    required_for_phase_completion=existing.required_for_phase_completion,
                    created_at=existing.created_at,
                    updated_at=datetime.utcnow().isoformat(),
                    notes=existing.notes,
                )
            )
        board.phases[phase_key] = merged_tasks
        _update_phase_status(board, phase_key)

    board.current_phase = phase_name_to_key(current_stage)
    return board
