import json

from sqlalchemy.orm import Session

from app.models.question_version import InterviewQuestionVersion
from app.models.turn import InterviewTurn


def summarize_usage_metrics(usage_metrics_list: list[dict]) -> dict:
    return {
        "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in usage_metrics_list),
        "completion_tokens": sum(item.get("completion_tokens", 0) for item in usage_metrics_list),
        "total_tokens": sum(item.get("total_tokens", 0) for item in usage_metrics_list),
        "is_estimated": any(item.get("is_estimated", False) for item in usage_metrics_list),
    }


def ensure_initial_question_version(db: Session, turn: InterviewTurn) -> InterviewQuestionVersion:
    existing_versions = list(turn.question_versions)
    if existing_versions:
        return existing_versions[0]

    initial_question_usages = [
        usage for usage in turn.llm_usages if usage.operation_type == "question_generation"
    ]
    usage_summary = {
        "prompt_tokens": sum(usage.prompt_tokens for usage in initial_question_usages),
        "completion_tokens": sum(usage.completion_tokens for usage in initial_question_usages),
        "total_tokens": sum(usage.total_tokens for usage in initial_question_usages),
        "is_estimated": any(usage.is_estimated for usage in initial_question_usages),
    }
    version = InterviewQuestionVersion(
        turn_id=turn.id,
        version_no=1,
        generation_kind="initial",
        question_text=turn.question_text,
        question_plan_json=turn.question_plan_json,
        human_review_json=None,
        prompt_tokens=usage_summary["prompt_tokens"],
        completion_tokens=usage_summary["completion_tokens"],
        total_tokens=usage_summary["total_tokens"],
        is_estimated=usage_summary["is_estimated"],
    )
    db.add(version)
    db.flush()
    return version


def append_question_version(
    *,
    db: Session,
    turn: InterviewTurn,
    generation_kind: str,
    human_review_signal: dict | None,
    question_plan_json: str | None,
    question_text: str,
    usage_metrics_list: list[dict],
) -> InterviewQuestionVersion:
    ensure_initial_question_version(db, turn)
    summary = summarize_usage_metrics(usage_metrics_list)
    version = InterviewQuestionVersion(
        turn_id=turn.id,
        version_no=(turn.question_versions[-1].version_no + 1) if turn.question_versions else 1,
        generation_kind=generation_kind,
        question_text=question_text,
        question_plan_json=question_plan_json,
        human_review_json=(
            json.dumps(human_review_signal, ensure_ascii=True, sort_keys=True)
            if human_review_signal
            else None
        ),
        prompt_tokens=summary["prompt_tokens"],
        completion_tokens=summary["completion_tokens"],
        total_tokens=summary["total_tokens"],
        is_estimated=summary["is_estimated"],
    )
    db.add(version)
    db.flush()
    return version
