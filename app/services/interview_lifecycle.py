from app.core.config import settings


def can_continue_interview(current_turn_count: int) -> bool:
    return current_turn_count < settings.interview_max_turns


def is_minimum_goal_reached(current_turn_count: int) -> bool:
    return current_turn_count >= settings.interview_min_turns
