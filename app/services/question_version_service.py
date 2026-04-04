import json

from sqlalchemy.orm import Session

from app.models.question_version import InterviewQuestionVersion
from app.models.turn import InterviewTurn
from app.services.question_postprocessor import clean_generated_question


def summarize_usage_metrics(usage_metrics_list: list[dict]) -> dict:
    return {
        "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in usage_metrics_list),
        "completion_tokens": sum(item.get("completion_tokens", 0) for item in usage_metrics_list),
        "total_tokens": sum(item.get("total_tokens", 0) for item in usage_metrics_list),
        "is_estimated": any(item.get("is_estimated", False) for item in usage_metrics_list),
    }


def normalize_question_versions(db: Session, turn: InterviewTurn) -> list[InterviewQuestionVersion]:
    versions = (
        db.query(InterviewQuestionVersion)
        .filter(InterviewQuestionVersion.turn_id == turn.id)
        .order_by(InterviewQuestionVersion.created_at.asc(), InterviewQuestionVersion.id.asc())
        .all()
    )
    if not versions:
        return []

    deduplicated_versions: list[InterviewQuestionVersion] = []
    for version in versions:
        previous = deduplicated_versions[-1] if deduplicated_versions else None
        is_duplicate_artifact = (
            previous is not None
            and version.question_text == previous.question_text
            and not version.human_review
            and not previous.human_review
        )
        if is_duplicate_artifact:
            db.delete(version)
            continue
        deduplicated_versions.append(version)

    versions = deduplicated_versions

    saw_initial = False
    for index, version in enumerate(versions, start=1):
        if version.version_no != index:
            version.version_no = index
        if index == 1 and version.generation_kind != "initial":
            version.generation_kind = "initial"
        elif index > 1 and version.generation_kind == "initial":
            version.generation_kind = "human_regeneration"
        if version.question_text:
            cleaned_question = clean_generated_question(version.question_text, turn.turn_no)
            if cleaned_question != version.question_text:
                version.question_text = cleaned_question
        saw_initial = saw_initial or version.generation_kind == "initial"

    if not saw_initial:
        versions[0].generation_kind = "initial"

    if turn.question_text:
        cleaned_turn_question = clean_generated_question(turn.question_text, turn.turn_no)
        if cleaned_turn_question != turn.question_text:
            turn.question_text = cleaned_turn_question

    db.flush()
    return versions


def ensure_initial_question_version(db: Session, turn: InterviewTurn) -> InterviewQuestionVersion:
    existing_versions = normalize_question_versions(db, turn)
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
    existing_versions = normalize_question_versions(db, turn)
    if not existing_versions:
        initial_version = ensure_initial_question_version(db, turn)
        if generation_kind == "initial":
            return initial_version
        existing_versions = [initial_version]
    summary = summarize_usage_metrics(usage_metrics_list)
    version = InterviewQuestionVersion(
        turn_id=turn.id,
        version_no=existing_versions[-1].version_no + 1,
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
