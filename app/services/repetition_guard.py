import re
from difflib import SequenceMatcher

from app.core.config import settings
from app.services.embedding_similarity import get_embedding_similarity

FILE_PATTERN = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|java|go|rb|yaml|yml|json)\b")
CLASS_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]{2,}\b")
METHOD_PATTERN = re.compile(r"\b([a-z_][a-z0-9_]{2,})\s*\(")


STAGE_TO_INTENT = {
    "Panorama Mapping": "overview_gap_fill",
    "Architecture Understanding": "architecture_clarification",
    "Code Detail Completion": "code_detail_deep_dive",
    "Use Cases & Scenarios": "scenario_completion",
    "Final Wrap-up": "wrap_up_readiness",
}


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^q\d+[:.]\s*", "", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_target_label(label: str | None) -> str:
    if not label:
        return ""
    normalized = normalize_text(label)
    normalized = re.sub(r"[`\"']", "", normalized)
    return normalized.strip(" .:-")


def infer_question_target(question_text: str) -> tuple[str, str]:
    normalized_text = normalize_text(question_text)

    file_match = FILE_PATTERN.search(question_text)
    if file_match:
        return "file", normalize_target_label(file_match.group(0))

    method_match = METHOD_PATTERN.search(question_text)
    if method_match:
        return "method", normalize_target_label(method_match.group(1))

    class_match = CLASS_PATTERN.search(question_text)
    if class_match:
        return "class", normalize_target_label(class_match.group(0))

    if "error handling" in normalized_text or "exception" in normalized_text:
        return "error_path", "error handling"
    if "library" in normalized_text or "openai" in normalized_text or "fastapi" in normalized_text:
        return "library_usage", "library usage"
    if "execution path" in normalized_text or "request path" in normalized_text or "call chain" in normalized_text:
        return "execution_path", "execution path"
    if "scenario" in normalized_text:
        return "scenario", "scenario"

    compact = normalized_text[:80].strip()
    return "topic", compact or "topic"


def build_question_signature(
    *,
    stage: str | None,
    intent: str | None,
    branch_id: str | None,
    target_type: str | None,
    target_label: str | None,
) -> str:
    return "|".join(
        [
            stage or "",
            intent or "",
            branch_id or "",
            target_type or "",
            normalize_target_label(target_label),
        ]
    )


def build_question_history_entry(
    *,
    turn_no: int,
    stage: str,
    question_text: str,
    intent: str | None = None,
    branch_id: str | None = None,
    target_type: str | None = None,
    target_label: str | None = None,
) -> dict[str, str | int]:
    resolved_target_type, resolved_target_label = (
        (target_type, target_label)
        if target_type and target_label
        else infer_question_target(question_text)
    )
    resolved_intent = intent or STAGE_TO_INTENT.get(stage, "question")
    signature = build_question_signature(
        stage=stage,
        intent=resolved_intent,
        branch_id=branch_id,
        target_type=resolved_target_type,
        target_label=resolved_target_label,
    )
    return {
        "turn_no": turn_no,
        "stage": stage,
        "intent": resolved_intent,
        "branch_id": branch_id or "",
        "target_type": resolved_target_type,
        "target_label": normalize_target_label(resolved_target_label),
        "signature": signature,
        "question_text": question_text,
    }


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def is_question_too_similar(
    new_question: str, old_questions: list[str], threshold: float = 0.82
) -> bool:
    for old in old_questions:
        if similarity(new_question, old) >= threshold:
            return True
    return False


def is_question_semantically_redundant(
    *,
    text: str,
    stage: str | None,
    intent: str | None,
    branch_id: str | None = None,
    recent_question_signatures: list[dict] | None = None,
    threshold: float = 0.76,
) -> bool:
    if not recent_question_signatures:
        return False

    candidate = build_question_history_entry(
        turn_no=0,
        stage=stage or "",
        question_text=text,
        intent=intent,
        branch_id=branch_id,
    )
    candidate_signature = str(candidate["signature"])
    candidate_target = str(candidate["target_label"])

    for previous in recent_question_signatures:
        previous_signature = str(previous.get("signature", ""))
        previous_target = normalize_target_label(str(previous.get("target_label", "")))
        previous_question = str(previous.get("question_text", ""))
        if previous_signature and previous_signature == candidate_signature:
            return True
        if candidate_target and previous_target and candidate_target == previous_target:
            if similarity(text, previous_question) >= threshold:
                return True
        if settings.duplicate_guard_use_embeddings and previous_question:
            lexical_score = similarity(text, previous_question)
            same_intent = str(previous.get("intent", "")) == str(candidate.get("intent", ""))
            if same_intent and 0.45 <= lexical_score < threshold:
                embedding_score = get_embedding_similarity(text, previous_question)
                if (
                    embedding_score is not None
                    and embedding_score >= settings.duplicate_guard_embedding_threshold
                ):
                    return True
    return False
