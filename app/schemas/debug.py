from pydantic import BaseModel


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


class CoverageDebugResponse(BaseModel):
    version: int
    branch_count: int
    updated_through_turn_no: int
    branches: list[CoverageBranchDebug]


class ContextPreviewRequest(BaseModel):
    answer_text: str


class ContextPreviewResponse(BaseModel):
    current_stage: str
    next_turn_no: int
    stage_objective: str
    recent_context: str
    retrieved_context: str
    coverage_priorities: str
    selected_turn_ids: list[int]
    selected_branch_ids: list[str]
    prompt_id: str
    prompt_version: str
    prompt_messages: list[dict[str, str]]
