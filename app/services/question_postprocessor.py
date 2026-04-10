import re

CODE_DETAIL_STAGE = "Code Detail Completion"


def _remove_ai_lead_in(text: str) -> str:
    text = re.sub(
        r"^\s*(?:to better understand|to help me understand|to understand)\s+(?:the\s+)?(?:current\s+)?(?:implementation|system|codebase)\s*,\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    what_and_who_match = re.match(
        r"^(?:could you|can you|would you)\s+walk me through\s+what\s+(.+?)\s+does\s+and\s+who\s+it\s+serves\??$",
        text,
        flags=re.IGNORECASE,
    )
    if what_and_who_match:
        subject = what_and_who_match.group(1).strip()
        return f"What does {subject} do and who does it serve?"

    what_match = re.match(
        r"^(?:could you|can you|would you)\s+walk me through\s+what\s+(.+?)\s+does\??$",
        text,
        flags=re.IGNORECASE,
    )
    if what_match:
        subject = what_match.group(1).strip()
        return f"What does {subject} do?"

    walk_through_match = re.match(
        r"^(?:could you|can you|would you)\s+walk me through\s+how\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if walk_through_match:
        subject = walk_through_match.group(1).strip()
        subject = re.sub(r"\bbuilds\b", "build", subject, flags=re.IGNORECASE)
        return f"How does {subject}"

    return re.sub(
        r"^\s*(?:could you|can you|would you)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _keep_only_first_question(text: str) -> str:
    first_question_mark = text.find("?")
    if first_question_mark >= 0:
        return text[: first_question_mark + 1].strip()
    return text


def _should_enforce_code_detail_tightening(current_stage: str | None) -> bool:
    return current_stage == CODE_DETAIL_STAGE


def strip_question_prefix(text: str) -> str:
    return re.sub(
        r"^\s*(?:\*\*\s*)?(?:Q|Question)\s*\d+\s*[:：]\s*(?:\*\*\s*)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def clean_generated_question(
    text: str,
    expected_turn_no: int,
    current_stage: str | None = None,
) -> str:
    text = text.strip()

    # 只保留第一行，避免附带解释
    text = text.splitlines()[0].strip()

    # 去掉常见引导语
    text = re.sub(
        r"^(Sure|Certainly|Of course|Here is the next question)[:\-\s]*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 去掉开头或整体包裹的 markdown 粗体标记，例如 **Q2:** ...
    text = text.replace("**", "").strip()
    text = re.sub(r"^\s*#+\s*", "", text).strip()

    # 去掉任意已有的题号前缀，避免重生成时出现 "Q19: Q20: ..."
    text = re.sub(
        r"^(?:(?:Q|Question)\s*\d+[:.\-\s]*)+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(r"^\s*#+\s*", "", text).strip()

    # 统一把 "Question 2", "Q 2", "Q2." 等标准化成 "Q2: "
    text = re.sub(
        rf"^(Q\s*{expected_turn_no}|Question\s*{expected_turn_no})[:.\-\s]*",
        f"Q{expected_turn_no}: ",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 如果前面出现了重复前缀，例如 "Q2: Q2: xxx"
    text = re.sub(
        rf"^(Q{expected_turn_no}:\s*)+",
        f"Q{expected_turn_no}: ",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 如果还没有标准前缀，则补上
    if not re.match(rf"^Q{expected_turn_no}:\s+", text):
        text = f"Q{expected_turn_no}: {text}"

    # 再次清理可能出现的重复前缀
    text = re.sub(
        rf"^Q{expected_turn_no}:\s*Q{expected_turn_no}:\s*",
        f"Q{expected_turn_no}: ",
        text,
        flags=re.IGNORECASE,
    ).strip()

    prefix = f"Q{expected_turn_no}: "
    body = text[len(prefix):].strip() if text.startswith(prefix) else text
    body = _remove_ai_lead_in(body)
    if _should_enforce_code_detail_tightening(current_stage):
        body = _keep_only_first_question(body)
        if "?" not in body:
            body = body.rstrip(".") + "?"
    text = prefix + body

    # 保证是问句
    if "?" not in text:
        text = text.rstrip(".") + "?"

    return text
