from typing import TypedDict


class InterviewGraphState(TypedDict, total=False):
    run_id: int
    project_id: int
    answer_text: str

    current_turn_no: int
    next_turn_no: int
    current_stage: str
    next_stage: str

    project_status: str

    history_text: str
    coverage_state: dict
    retrieved_context: str
    coverage_priorities: str
    selected_turn_ids: list[int]
    selected_branch_ids: list[str]
    stage_decision: dict
    planner_decision: dict
    validation_result: dict
    prompt_metadata: dict
    latest_question: str
    generated_question: str
    question_usage_metrics: list[dict]
    pending_turn_id: int

    interview_finished: bool
    minimum_goal_reached: bool
    message: str
