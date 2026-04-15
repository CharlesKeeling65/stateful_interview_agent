import re
from typing import Any
import uuid

from app.schemas.debug import QueuedQuestionDebug

def detect_compound_question_candidate(question_text: str) -> bool:
    question_text = question_text.strip()
    return question_text.count("?") >= 2

def normalize_sub_question_text(text: str, turn_number: int) -> str:
    text = text.strip()
    text = re.sub(r"^Q\d+[:.\-\s]*", "", text).strip()
    text = text.capitalize()
    if not text.endswith("?"):
        text += "?"
    return f"Q{turn_number}: {text}"

def decompose_code_detail_question_group(
    question_text: str,
    base_turn_no: int,
    intent: str = "code_detail_deep_dive",
    target_branch_id: str | None = None,
    target_type: str | None = None,
    target_label: str | None = None
) -> list[QueuedQuestionDebug]:
    # Heuristic split by "?"
    parts = [p.strip() for p in question_text.split("?") if p.strip()]
    
    queued = []
    # Limit to 3 items
    parts = parts[:3]
    for idx, part in enumerate(parts):
        turn_offset = idx  # First is offset 0 (asked immediately), second is 1, etc.
        item_text = normalize_sub_question_text(part, base_turn_no + turn_offset)
        queued.append(
            QueuedQuestionDebug(
                id=str(uuid.uuid4()),
                turn_offset=turn_offset,
                question_text=item_text,
                intent=intent,
                target_branch_id=target_branch_id,
                target_type=target_type,
                target_label=target_label,
            )
        )
    return queued

def renumber_sub_question_queue(queue_items: list[QueuedQuestionDebug], next_turn_no: int) -> list[QueuedQuestionDebug]:
    for idx, item in enumerate(queue_items):
        item.turn_offset = idx
        raw_text = re.sub(r"^Q\d+[:.\-\s]*", "", item.question_text).strip()
        item.question_text = f"Q{next_turn_no + idx}: {raw_text}"
    return queue_items
