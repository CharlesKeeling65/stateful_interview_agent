import re


def looks_like_valid_question(text: str, expected_turn_no: int) -> bool:
    text = text.strip()

    if not text:
        return False

    if not re.match(rf"^Q{expected_turn_no}[:.]\s+", text):
        return False

    if "?" not in text:
        return False

    if len(text) < 15:
        return False

    return True
