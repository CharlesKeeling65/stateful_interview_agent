from typing import TypedDict


class InterviewGraphState(TypedDict, total=False):
    project_id: int
    answer_text: str

    current_turn_no: int
    next_turn_no: int
    current_stage: str
    next_stage: str

    project_status: str

    history_text: str
    latest_question: str
    generated_question: str

    interview_finished: bool
    minimum_goal_reached: bool
    message: str
