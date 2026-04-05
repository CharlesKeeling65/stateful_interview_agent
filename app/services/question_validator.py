import re
from pathlib import Path

from app.services.repetition_guard import is_question_semantically_redundant

# Comprehensive change proposal patterns that should be rejected in understand mode
CHANGE_PROPOSAL_MARKERS = (
    "should be changed",
    "should change",
    "what should be changed",
    "which files should be modified",
    "what code changes",
    "how should we",
    "redesign",
    "refactor",
    "improve",
    "update the tests",
    "modify",
    "changes are required",
    "could we change",
    "would you change",
    "better way to",
    "recommended changes",
    "suggest improvements",
)

# Regex patterns for more sophisticated change proposal detection
CHANGE_PROPOSAL_PATTERNS = [
    r"should\s+be\s+(changed|modified|updated|refactored)",
    r"(?:how|what)\s+(?:should|could|would)\s+we\s+(change|modify|fix|implement)",
    r"suggest\s+(?:changes?|improvements?|refactoring)",
    r"recommended\s+(?:changes?|approach\s+for)",
    r"better\s+(?:way|approach)\s+to\s+(implement|handle)",
    r"redesign\s+the",
    r"update\s+(?:the\s+)?tests?",
    r"modify\s+(?:this|the)",
    r"what\s+changes\s+(?:should|could)",
    r"improve\s+(?:this|the)\s+(?:code|implementation)",
]

# Understanding-focused patterns that are encouraged in understand mode
UNDERSTANDING_PATTERNS = [
    r"how\s+does\s+(?:this|the)",
    r"what\s+does\s+(?:this|the)",
    r"why\s+does\s+(?:this|the)",
    r"explain\s+(?:how|what|why)",
    r"describe\s+(?:the|this)",
    r"current\s+(?:implementation|behavior|flow)",
    r"what\s+is\s+(?:the\s+)?(?:current|existing)",
    r"walk\s+through\s+(?:the|this)",
    r"trace\s+(?:the|this)",
]

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
    "currently",
    "current behavior",
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
QUESTION_FILE_PATTERN = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|java|go|rb|yaml|yml|json|toml|md)\b")
QUESTION_SYMBOL_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]{2,}\b")


def looks_like_valid_question(text: str, expected_turn_no: int) -> bool:
    return validate_question_for_stage(
        text=text,
        expected_turn_no=expected_turn_no,
        current_stage=None,
        intent_mode="understand_current_code",
    )["is_valid"]


def validate_question_for_stage(
    *,
    text: str,
    expected_turn_no: int,
    current_stage: str | None,
    intent_mode: str = "understand_current_code",
    recent_question_signatures: list[dict] | None = None,
    branch_id: str | None = None,
    agent_mode: str | None = None,
) -> dict:
    text = text.strip()
    normalized = text.lower()
    reasons: list[str] = []

    # Use agent_mode if provided, otherwise fall back to intent_mode
    effective_mode = agent_mode or intent_mode

    if not text:
        reasons.append("Question text is empty.")

    if not re.match(rf"^Q{expected_turn_no}[:.]\s+", text):
        reasons.append("Question prefix does not match the expected turn number.")

    if "?" not in text:
        reasons.append("Question must contain a question mark.")

    if len(text) < 15:
        reasons.append("Question is too short.")

    # Mode-specific validation
    if effective_mode == "understand_current_code":
        # Check for change proposal markers
        if any(marker in normalized for marker in CHANGE_PROPOSAL_MARKERS):
            reasons.append(
                "Questions in understand mode must focus on CURRENT code behavior, not proposed changes."
            )

        # Check for change proposal patterns via regex
        for pattern in CHANGE_PROPOSAL_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                reasons.append(
                    f"Question phrasing suggests change proposals, which is not allowed in understand mode. "
                    f"Rephrase to ask about current behavior (e.g., 'How does X currently...')."
                )
                break

        # Check for semantic redundancy
        if is_question_semantically_redundant(
            text=text,
            stage=current_stage,
            intent="code_detail_deep_dive" if current_stage == "Code Detail Completion" else None,
            branch_id=branch_id,
            recent_question_signatures=recent_question_signatures,
        ):
            reasons.append(
                "Question is too similar to a recently asked question and should target a different branch or implementation detail."
            )

    elif effective_mode == "review_current_code":
        # Review mode allows quality assessment but not implementation details
        if any(phrase in normalized for phrase in ("implement this", "change this now", "fix by doing")):
            reasons.append(
                "Review mode focuses on identifying issues, not proposing implementation details."
            )

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
        if any(phrase in normalized for phrase in ("overall", "generally", "in the project overall")) and not any(
            marker in normalized for marker in (".py", ".ts", ".tsx", ".js", "class ", "method ", "function ", "execution path", "request path")
        ):
            reasons.append("Code-detail questions must stay specific; broad overall implementation prompts are not concrete enough.")
        if intent_mode == "understand_current_code" and not any(
            marker in normalized
            for marker in ("how does", "how do", "what does", "trace", "currently", "current", "where does")
        ):
            reasons.append(
                "Code-detail questions in understand mode must ask how the current implementation works."
            )
        if any(marker in normalized for marker in CHANGE_PROPOSAL_MARKERS):
            reasons.append("Code-detail questions in understand mode must not drift into redesign or modification planning.")

    elif current_stage == "Use Cases & Scenarios":
        if not any(marker in normalized for marker in USE_CASE_MARKERS):
            reasons.append("Use-case questions must stay tied to actors, scenarios, inputs/outputs, or boundaries.")
        if any(marker in normalized for marker in (".py", ".ts", ".tsx", ".js", "class ", "method ", "function ")):
            reasons.append("Use-case questions should not be purely code-level.")
        if not any(marker in normalized for marker in ("trigger", "actor", "input", "output", "result", "boundary", "scenario")):
            reasons.append("Use-case questions should explicitly gather scenario contract details such as trigger, actor, input/output, or boundaries.")

    elif current_stage == "Final Wrap-up":
        if any(marker in normalized for marker in ("class ", "method ", ".py", ".ts")):
            reasons.append("Wrap-up questions should not reopen deep implementation topics.")

    return {
        "is_valid": len(reasons) == 0,
        "reasons": reasons,
    }


def validate_question_against_repository(
    *,
    text: str,
    current_stage: str | None,
    repo_grounding_meta: dict | None,
    repo_manifest: dict | None,
) -> dict:
    repo_grounding_meta = repo_grounding_meta or {}
    repo_manifest = repo_manifest or {}
    if not repo_grounding_meta.get("enabled"):
        return {"is_valid": True, "reasons": []}

    normalized = text.strip()
    reasons: list[str] = []
    known_paths = {
        str(path)
        for path in (
            repo_grounding_meta.get("selected_paths", [])
            + repo_manifest.get("key_files", [])
        )
    }
    known_symbols = {str(symbol) for symbol in repo_grounding_meta.get("selected_symbols", [])}
    root_path_text = str(repo_manifest.get("root_path") or "").strip()
    repo_root = Path(root_path_text).expanduser().resolve() if root_path_text else None

    mentioned_paths = QUESTION_FILE_PATTERN.findall(normalized)
    if mentioned_paths:
        missing_paths = [
            path
            for path in mentioned_paths
            if path not in known_paths and not _repository_path_exists(repo_root, path)
        ]
        if missing_paths:
            reasons.append(
                "Question references repository paths that were not found in the current evidence bundle: "
                + ", ".join(sorted(set(missing_paths)))
            )

    if current_stage == "Code Detail Completion":
        if not mentioned_paths:
            mentioned_symbols = set(QUESTION_SYMBOL_PATTERN.findall(normalized))
            if known_symbols and not (mentioned_symbols & known_symbols):
                reasons.append(
                    "Code-detail questions must mention at least one grounded file path or symbol from the repository evidence bundle."
                )

    return {
        "is_valid": len(reasons) == 0,
        "reasons": reasons,
    }


def _repository_path_exists(repo_root: Path | None, relative_path: str) -> bool:
    if repo_root is None or not repo_root.exists():
        return False
    normalized = Path(relative_path)
    if normalized.is_absolute() or ".." in normalized.parts:
        return False
    return (repo_root / normalized).is_file()
