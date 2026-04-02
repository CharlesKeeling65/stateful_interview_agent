import re
from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^q\d+[:.]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def is_question_too_similar(
    new_question: str, old_questions: list[str], threshold: float = 0.82
) -> bool:
    for old in old_questions:
        if similarity(new_question, old) >= threshold:
            return True
    return False
