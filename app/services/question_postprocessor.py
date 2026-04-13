import re

# Parenthetical asides that signal AI-generated padding; these start with known filler words
# and are safe to remove without breaking code references like func() or .py paths.
_EXPLANATORY_PAREN_RE = re.compile(
    r"\s*\((?:which|that\s+(?:is|are|was)|i\.?e\.?\,?|e\.?g\.?\,?|such as|also known as|also called|the|this is|these are|including|and|or)[^()]{0,80}\)",
    re.IGNORECASE,
)
import unicodedata

CODE_DETAIL_STAGE = "Code Detail Completion"
WINDOWS_SAFE_REPLACEMENTS = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "—": "-",
    "–": "-",
    "―": "-",
    "…": "...",
    "→": "->",
    "←": "<-",
    "↔": "<->",
    "：": ":",
    "？": "?",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
}


def _remove_ai_lead_in(text: str) -> str:
    text = re.sub(
        r"^\s*(?:specifically|more specifically|more concretely|concretely|in particular)\s*,\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(
        r"^\s*(?:in\s+q(?:uestion)?\s*\d+|from\s+q(?:uestion)?\s*\d+|based\s+on\s+q(?:uestion)?\s*\d+|as\s+(?:mentioned|noted|discussed)\s+(?:above|earlier|before)|as\s+you\s+mentioned|as\s+noted\s+above|from\s+the\s+previous\s+answer)\s*,\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
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


def _remove_explanatory_parens(text: str) -> str:
    """Remove AI-style parenthetical asides while preserving code-syntax parens.

    Targets only parentheses whose content begins with known filler words such as
    'which', 'i.e.', 'e.g.', 'such as', etc.  Parentheses that immediately follow
    a word character (function calls like func()) or contain file-extension dots are
    left untouched, so code artifact references are never corrupted.
    """
    cleaned = _EXPLANATORY_PAREN_RE.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _keep_only_first_question(text: str) -> str:
    first_question_mark = text.find("?")
    if first_question_mark >= 0:
        return text[: first_question_mark + 1].strip()
    return text


def _capitalize_question_start(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _should_enforce_code_detail_tightening(current_stage: str | None) -> bool:
    return current_stage == CODE_DETAIL_STAGE


def _normalize_windows_safe_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    for source, target in WINDOWS_SAFE_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)

    safe_chars: list[str] = []
    for char in normalized:
        if ord(char) < 128:
            safe_chars.append(char)
            continue
        if unicodedata.category(char).startswith("Z"):
            safe_chars.append(" ")

    normalized = "".join(safe_chars)
    return re.sub(r"\s+", " ", normalized).strip()


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
    body = _remove_explanatory_parens(body)
    body = _normalize_windows_safe_text(body)
    body = _capitalize_question_start(body)
    if _should_enforce_code_detail_tightening(current_stage):
        body = _keep_only_first_question(body)
        if "?" not in body:
            body = body.rstrip(".") + "?"
    text = prefix + body

    # 保证是问句
    if "?" not in text:
        text = text.rstrip(".") + "?"

    return text
