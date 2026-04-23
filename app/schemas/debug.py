from typing import Any

from pydantic import BaseModel, Field

from app.schemas.turn import HumanReviewInput


class QuestionPlanDebug(BaseModel):
    """Debug information for why a question was generated."""

    mode: str = "understand_current_code"
    phase: str = "Panorama Mapping"
    rubric_task_id: str | None = None
    rubric_task_label: str | None = None
    target_branch_ids: list[str] = Field(default_factory=list)
    target_artifact: str | None = None
    framework_gap: str | None = None
    confidence_score: float = 0.5
    human_gate_triggered: bool = False
    human_gate_reason: str | None = None
    why_this_question: str = ""
    planning_steps: list[str] = Field(default_factory=list)
    reviewer_modifications: list[str] = Field(default_factory=list)
    evidence_turn_ids: list[int] = Field(default_factory=list)
    question_intent: str | None = None
    intent_mode: str | None = None
    drift_detected: bool = False
    human_review_applied: bool = False


class TaskBoardDebug(BaseModel):
    """Debug information for task board state."""

    current_phase: str = "panorama_mapping"
    phase_status: dict[str, str] = Field(default_factory=dict)
    incomplete_tasks: list[dict[str, Any]] = Field(default_factory=list)
    next_priority_task: dict[str, Any] | None = None
    human_gate_pending: bool = False


class ModeDebug(BaseModel):
    """Debug information for mode state."""

    current_mode: str = "understand_current_code"
    mode_constraints: dict[str, Any] = Field(default_factory=dict)
    can_propose_changes: bool = False
    valid_transitions: list[str] = Field(default_factory=list)


class ScenarioDebug(BaseModel):
    """Debug information for scenario completion."""

    is_complete: bool = False
    confidence: float = 0.0
    scenario_count: int = 0
    missing_aspects: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class DebugInfoResponse(BaseModel):
    """Complete debug information response."""

    question_plan: QuestionPlanDebug | None = None
    task_board: TaskBoardDebug | None = None
    mode: ModeDebug | None = None
    scenario: ScenarioDebug | None = None
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class CoverageBranchDebug(BaseModel):
    branch_id: str
    label: str
    stage: str
    status: str
    priority: float
    keywords: list[str]
    evidence_turn_ids: list[int]
    evidence_turn_nos: list[int]
    summary: str
    unresolved_points: list[str]
    last_turn_no: int


class QuestionHistoryDebug(BaseModel):
    turn_no: int
    stage: str
    intent: str
    branch_id: str
    target_type: str
    target_label: str
    signature: str
    question_text: str


class QueuedQuestionDebug(BaseModel):
    id: str
    turn_offset: int
    question_text: str
    intent: str
    target_branch_id: str | None = None
    target_type: str | None = None
    target_label: str | None = None
    node_id: str | None = None
    parent_node_id: str | None = None
    relation_type: str | None = None
    developer_intent: str | None = None
    priority_score: float | None = None


class QuestionQueueDebug(BaseModel):
    status: str
    items: list[QueuedQuestionDebug] = Field(default_factory=list)
    parent_turn_no: int | None = None
    parent_group_intent: str | None = None


class RepoFileCoverageDebug(BaseModel):
    path: str
    importance_score: float = 0.0
    exploration_score: float = 0.0
    coverage_gap_score: float = 0.0
    times_asked: int = 0
    times_answered: int = 0
    last_turn_no: int | None = None
    linked_branch_ids: list[str] = Field(default_factory=list)
    tree_depth: int = 0


class QuestionGraphNodeDebug(BaseModel):
    node_id: str
    turn_no: int
    stage: str
    question_text: str
    target_label: str = ""
    artifact_keys: list[str] = Field(default_factory=list)
    intent_type: str
    depth_level: str
    status: str
    unresolved_points: list[str] = Field(default_factory=list)


class QuestionGraphEdgeDebug(BaseModel):
    from_node_id: str
    to_node_id: str
    relation_type: str


class QuestionGraphDebug(BaseModel):
    nodes: list[QuestionGraphNodeDebug] = Field(default_factory=list)
    edges: list[QuestionGraphEdgeDebug] = Field(default_factory=list)


class InvestigationFrontierItemDebug(BaseModel):
    source_node_id: str
    label: str
    priority: float = 0.0


class InvestigationFrontierDebug(BaseModel):
    items: list[InvestigationFrontierItemDebug] = Field(default_factory=list)


class QuestionNetworkStatsDebug(BaseModel):
    node_count: int = 0
    connected_edge_count: int = 0
    isolated_node_count: int = 0
    breadth_transition_count: int = 0
    depth_transition_count: int = 0
    developer_intent_count: int = 0
    dominant_intent_ratio: float = 0.0


class RelationCountDebug(BaseModel):
    relation_type: str
    count: int


class IntentCountDebug(BaseModel):
    intent: str
    count: int


class FrontierPreviewDebug(BaseModel):
    source_node_id: str
    label: str
    priority: float = 0.0


class QuestionNetworkSummaryDebug(BaseModel):
    node_count: int = 0
    connected_edge_count: int = 0
    isolated_node_count: int = 0
    connected_ratio: float = 0.0
    frontier_count: int = 0
    repeat_opening_clusters: int = 0
    health_status: str = "healthy"
    diagnostic_flags: list[str] = Field(default_factory=list)
    degradation_reasons: list[str] = Field(default_factory=list)
    top_relation_types: list[RelationCountDebug] = Field(default_factory=list)
    top_intents: list[IntentCountDebug] = Field(default_factory=list)
    undercovered_intents: list[str] = Field(default_factory=list)
    frontier_preview: list[FrontierPreviewDebug] = Field(default_factory=list)


class CoverageDebugResponse(BaseModel):
    version: int
    branch_count: int
    updated_through_turn_no: int
    branches: list[CoverageBranchDebug]
    question_history: list[QuestionHistoryDebug]
    framework: dict
    question_queue: QuestionQueueDebug = Field(default_factory=lambda: QuestionQueueDebug(status="empty"))
    repo_file_coverage: dict[str, RepoFileCoverageDebug] = Field(default_factory=dict)
    repo_tree_summary: dict[str, Any] = Field(default_factory=dict)
    question_graph: QuestionGraphDebug = Field(default_factory=QuestionGraphDebug)
    investigation_frontier: InvestigationFrontierDebug = Field(default_factory=InvestigationFrontierDebug)
    developer_intent_coverage: dict[str, int] = Field(default_factory=dict)
    question_network_stats: QuestionNetworkStatsDebug = Field(default_factory=QuestionNetworkStatsDebug)


class ContextPreviewRequest(BaseModel):
    answer_text: str
    human_review: HumanReviewInput | None = None


class ContextPreviewResponse(BaseModel):
    current_stage: str
    next_turn_no: int
    stage_objective: str
    framework_gaps: list[str]
    recent_context: str
    retrieved_context: str
    coverage_priorities: str
    selected_turn_ids: list[int]
    selected_branch_ids: list[str]
    branch_selection_meta: dict[str, dict]
    question_history: list[QuestionHistoryDebug]
    stage_decision: dict
    planner_decision: dict
    validation_preview: dict
    prompt_id: str
    prompt_version: str
    prompt_messages: list[dict[str, str]]
