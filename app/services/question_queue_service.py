import re
from typing import Any
import uuid

from app.schemas.debug import QueuedQuestionDebug
from app.services.repetition_guard import infer_question_target

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

def renumber_sub_question_queue(queue_items: list[QueuedQuestionDebug | dict], next_turn_no: int) -> list[QueuedQuestionDebug | dict]:
    renumbered = []
    for idx, item in enumerate(queue_items):
        is_dict = isinstance(item, dict)
        q_text = item.get("question_text", "") if is_dict else item.question_text
        raw_text = re.sub(r"^Q\d+[:.\-\s]*", "", q_text).strip()
        new_text = f"Q{next_turn_no + idx}: {raw_text}"
        if is_dict:
            item["turn_offset"] = idx
            item["question_text"] = new_text
            renumbered.append(item)
        else:
            item.turn_offset = idx
            item.question_text = new_text
            renumbered.append(item)
    return renumbered

def prune_question_queue(
    queue_state: dict[str, Any], 
    answer_text: str, 
    summary: str,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    if not queue_state.get("items"):
        queue_state["status"] = "empty"
        return queue_state

    corpus = (answer_text + " " + summary + " " + " ".join(analysis.get("key_points", []))).lower()
    
    remaining = []
    for item in queue_state["items"]:
        q_text = item.get("question_text", "") if isinstance(item, dict) else item.question_text
        
        target_type, target_label = infer_question_target(q_text)
        
        if len(target_label) > 4 and target_label.lower() in corpus and "?" not in corpus:
            # A bit dangerous heuristic, checking if the question's target was heavily discussed
            # Let's just look for strong overlap
            overlap = sum(1 for word in target_label.lower().split() if word in corpus)
            if overlap >= len(target_label.split()) and len(target_label) > 3:
                continue # Question target was explored
        
        remaining.append(item)

    queue_state["items"] = remaining
    if not remaining:
        queue_state["status"] = "empty"
    return queue_state
