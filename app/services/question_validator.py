import re

CODE_DETAIL_MARKERS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    "class ",
    "method ",
    "function ",
    "execution path",
    "request path",
    "call chain",
    "library",
    "error handling",
    "exception",
)

PANORAMA_DEEP_DETAIL_MARKERS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    "class ",
    "method ",
    "function ",
    "implementation",
    "error handling",
)

ARCHITECTURE_MARKERS = (
    "module",
    "service",
    "collabor",
    "call chain",
    "request path",
    "communicat",
    "responsibil",
    "layer",
)

USE_CASE_MARKERS = (
    "scenario",
    "user",
    "role",
    "input",
    "output",
    "boundary",
    "extension",
    "workflow",
)


def looks_like_valid_question(text: str, expected_turn_no: int) -> bool:
    return validate_question_for_stage(
        text=text,
        expected_turn_no=expected_turn_no,
        current_stage=None,
    )["is_valid"]


def validate_question_for_stage(
    *,
    text: str,
    expected_turn_no: int,
    current_stage: str | None,
) -> dict:
    text = text.strip()
    normalized = text.lower()
    reasons: list[str] = []

    if not text:
        reasons.append("Question text is empty.")

    if not re.match(rf"^Q{expected_turn_no}[:.]\s+", text):
        reasons.append("Question prefix does not match the expected turn number.")

    if "?" not in text:
        reasons.append("Question must contain a question mark.")

    if len(text) < 15:
        reasons.append("Question is too short.")

    if current_stage == "Panorama Mapping":
        if any(marker in normalized for marker in PANORAMA_DEEP_DETAIL_MARKERS):
            reasons.append("Panorama questions must avoid deep implementation detail.")

    elif current_stage == "Architecture Understanding":
        if not any(marker in normalized for marker in ARCHITECTURE_MARKERS):
            reasons.append("Architecture questions should focus on modules, collaboration, or call chains.")
        if any(marker in normalized for marker in (".py", ".ts", ".tsx", ".js")):
            reasons.append("Architecture questions should not already zoom into file-level detail.")

    elif current_stage == "Code Detail Completion":
        if not any(marker in normalized for marker in CODE_DETAIL_MARKERS):
            reasons.append("Code-detail questions must target a concrete implementation artifact or path.")

    elif current_stage == "Use Cases & Scenarios":
        if not any(marker in normalized for marker in USE_CASE_MARKERS):
            reasons.append("Use-case questions must stay tied to actors, scenarios, inputs/outputs, or boundaries.")
        if any(marker in normalized for marker in (".py", ".ts", ".tsx", ".js", "class ", "method ", "function ")):
            reasons.append("Use-case questions should not be purely code-level.")

    elif current_stage == "Final Wrap-up":
        if any(marker in normalized for marker in ("class ", "method ", ".py", ".ts")):
            reasons.append("Wrap-up questions should not reopen deep implementation topics.")

    return {
        "is_valid": len(reasons) == 0,
        "reasons": reasons,
    }
