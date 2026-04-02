from app.models.turn import InterviewTurn
from app.services.question_generator import format_turn_history


def build_project_transcript(turns: list[InterviewTurn]) -> str:
    if not turns:
        return "No turns yet."
    return format_turn_history(turns)
