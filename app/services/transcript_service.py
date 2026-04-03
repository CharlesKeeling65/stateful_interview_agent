from app.models.turn import InterviewTurn


def format_turn_history(turns: list[InterviewTurn]) -> str:
    lines = []
    for turn in turns:
        lines.append(f"Turn {turn.turn_no}")
        lines.append(f"Question: {turn.question_text}")
        lines.append(f"Answer: {turn.answer_text or '[No answer yet]'}")
        lines.append("")
    return "\n".join(lines).strip()


def build_project_transcript(turns: list[InterviewTurn]) -> str:
    if not turns:
        return "No turns yet."
    return format_turn_history(turns)


def build_compact_interview_context(
    turns: list[InterviewTurn],
    *,
    latest_answer_override: str | None = None,
) -> str:
    if not turns:
        return "No turns yet."

    latest_completed_turn_no = None
    for turn in turns:
        if turn.answer_text or (
            latest_answer_override is not None and turn is turns[-1] and not turn.answer_text
        ):
            latest_completed_turn_no = turn.turn_no

    lines = []
    for turn in turns:
        lines.append(f"Turn {turn.turn_no}")
        lines.append(f"Question: {turn.question_text}")

        answer_text = turn.answer_text
        if latest_answer_override is not None and turn is turns[-1] and not turn.answer_text:
            answer_text = latest_answer_override

        if answer_text:
            if turn.turn_no == latest_completed_turn_no:
                lines.append(f"Answer: {answer_text}")
            elif turn.answer_summary:
                lines.append(f"Summary: {turn.answer_summary}")
            else:
                lines.append(f"Answer: {answer_text}")
        else:
            lines.append("Answer: [No answer yet]")

        lines.append("")

    return "\n".join(lines).strip()
