import json
import re
from typing import Any

from app.models.project import ProjectSession
from app.models.turn import InterviewTurn

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "about",
    "there",
    "their",
    "them",
    "they",
    "have",
    "has",
    "had",
    "what",
    "which",
    "where",
    "when",
    "why",
    "how",
    "does",
    "doing",
    "main",
    "more",
    "very",
    "only",
    "used",
    "use",
    "using",
    "through",
    "within",
    "across",
    "project",
    "system",
    "service",
    "services",
    "module",
    "modules",
    "code",
    "detail",
    "details",
    "completion",
    "mapping",
    "architecture",
    "understanding",
    "scenarios",
    "question",
    "answer",
    "interview",
}

UNRESOLVED_MARKERS = (
    "unclear",
    "unknown",
    "unresolved",
    "not yet",
    "still",
    "missing",
    "tbd",
    "later",
    "needs follow-up",
    "ambigu",
)


def default_coverage_state() -> dict[str, Any]:
    return {
        "version": 1,
        "branch_count": 0,
        "updated_through_turn_no": 0,
        "branches": [],
    }


def load_coverage_state(project: ProjectSession) -> dict[str, Any]:
    raw_value = getattr(project, "coverage_state", None)
    if not raw_value:
        return default_coverage_state()

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return default_coverage_state()

    if not isinstance(parsed, dict):
        return default_coverage_state()
    parsed.setdefault("version", 1)
    parsed.setdefault("branches", [])
    parsed.setdefault("branch_count", len(parsed["branches"]))
    parsed.setdefault("updated_through_turn_no", 0)
    return parsed


def save_coverage_state(project: ProjectSession, coverage_state: dict[str, Any]) -> None:
    project.coverage_state = json.dumps(coverage_state, ensure_ascii=True, sort_keys=True)


def rebuild_coverage_state(turns: list[InterviewTurn]) -> dict[str, Any]:
    branches: list[dict[str, Any]] = []

    for turn in turns:
        if not turn.answer_text:
            continue

        summary = turn.answer_summary or turn.answer_text
        candidate_keywords = extract_keywords(
            turn.question_text,
            summary,
            turn.answer_text,
        )
        if not candidate_keywords:
            candidate_keywords = [f"turn-{turn.turn_no}"]

        unresolved_points = extract_unresolved_points(summary)
        label = build_branch_label(turn, candidate_keywords)
        branch_id = build_branch_id(turn, candidate_keywords)

        matching_branch = find_matching_branch(branches, candidate_keywords)
        if matching_branch is None:
            branches.append(
                {
                    "branch_id": branch_id,
                    "label": label,
                    "stage": turn.stage,
                    "status": "needs_follow_up" if unresolved_points else "partial",
                    "priority": 0.0,
                    "keywords": candidate_keywords[:8],
                    "evidence_turn_ids": [turn.id],
                    "evidence_turn_nos": [turn.turn_no],
                    "summary": summary,
                    "unresolved_points": unresolved_points,
                    "last_turn_no": turn.turn_no,
                }
            )
            continue

        matching_branch["keywords"] = merge_unique(
            matching_branch["keywords"], candidate_keywords, limit=10
        )
        matching_branch["evidence_turn_ids"] = merge_unique(
            matching_branch["evidence_turn_ids"], [turn.id]
        )
        matching_branch["evidence_turn_nos"] = merge_unique(
            matching_branch["evidence_turn_nos"], [turn.turn_no]
        )
        matching_branch["summary"] = summary
        matching_branch["unresolved_points"] = merge_unique(
            matching_branch["unresolved_points"], unresolved_points, limit=5
        )
        matching_branch["last_turn_no"] = turn.turn_no
        if matching_branch["unresolved_points"]:
            matching_branch["status"] = "needs_follow_up"
        elif len(matching_branch["evidence_turn_ids"]) >= 2:
            matching_branch["status"] = "covered"
        else:
            matching_branch["status"] = "partial"

    for branch in branches:
        branch["priority"] = compute_branch_priority(branch)

    updated_through_turn_no = max(
        (turn.turn_no for turn in turns if turn.answer_text),
        default=0,
    )
    return {
        "version": 1,
        "branch_count": len(branches),
        "updated_through_turn_no": updated_through_turn_no,
        "branches": sorted(branches, key=lambda item: item["priority"], reverse=True),
    }


def build_branch_label(turn: InterviewTurn, keywords: list[str]) -> str:
    prompt_label = re.sub(r"^Q\d+[:.\-\s]*", "", turn.question_text).strip()
    prompt_label = prompt_label.rstrip("?").strip()
    if prompt_label:
        return prompt_label[:120]
    return " / ".join(keywords[:3])


def build_branch_id(turn: InterviewTurn, keywords: list[str]) -> str:
    base = "-".join(keywords[:3]) or f"turn-{turn.turn_no}"
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or f"turn-{turn.turn_no}"


def extract_keywords(*texts: str) -> list[str]:
    tokens = []
    for text in texts:
        lowered = text.lower()
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", lowered):
            if token in STOPWORDS or token.isdigit():
                continue
            tokens.append(token)

    scored: dict[str, int] = {}
    for token in tokens:
        scored[token] = scored.get(token, 0) + 1

    return [
        token
        for token, _ in sorted(scored.items(), key=lambda item: (-item[1], item[0]))
    ][:8]


def extract_unresolved_points(summary: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", summary.strip())
    unresolved = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(marker in lowered for marker in UNRESOLVED_MARKERS):
            unresolved.append(sentence.strip())
    return unresolved[:4]


def find_matching_branch(
    branches: list[dict[str, Any]], candidate_keywords: list[str]
) -> dict[str, Any] | None:
    candidate_set = set(candidate_keywords)
    best_match = None
    best_score = 0.0
    for branch in branches:
        existing_set = set(branch["keywords"])
        if not existing_set:
            continue
        overlap = len(candidate_set & existing_set)
        union = len(candidate_set | existing_set)
        score = overlap / union if union else 0.0
        if overlap >= 2 and score > best_score:
            best_match = branch
            best_score = score
    return best_match


def compute_branch_priority(branch: dict[str, Any]) -> float:
    priority = 0.4
    if branch["status"] == "needs_follow_up":
        priority += 0.35
    elif branch["status"] == "partial":
        priority += 0.2
    if branch["unresolved_points"]:
        priority += 0.15
    priority += min(len(branch["keywords"]), 6) * 0.03
    return round(priority, 3)


def merge_unique(existing: list[Any], incoming: list[Any], *, limit: int | None = None) -> list[Any]:
    merged = list(existing)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    if limit is not None:
        return merged[:limit]
    return merged
