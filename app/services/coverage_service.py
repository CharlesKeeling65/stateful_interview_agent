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

FILE_PATTERN = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|java|go|rb|yaml|yml|json)\b")
CLASS_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]{2,}\b")
METHOD_PATTERN = re.compile(r"\b[a-z_][a-z0-9_]{2,}\s*\(")
LIBRARY_PATTERN = re.compile(
    r"\b(?:openai|fastapi|sqlalchemy|langgraph|langchain|pydantic|react|tailwind|vite)\b",
    re.IGNORECASE,
)

PANORAMA_KEYWORDS = {
    "purpose": {"purpose", "goal", "achieve", "problem", "supports", "helps"},
    "target_users": {"user", "users", "customer", "customers", "operator", "operators", "admin", "admins", "analyst"},
    "boundaries": {"boundary", "boundaries", "scope", "limit", "outside", "inside"},
    "major_modules": {"module", "modules", "service", "services", "component", "components", "gateway"},
    "high_level_workflow": {"workflow", "flow", "routing", "pipeline", "intake", "handoff", "request"},
}

ARCHITECTURE_KEYWORDS = {
    "architecture_style": {"layered", "pipeline", "monolith", "microservice", "architecture", "tier"},
    "module_responsibilities": {"responsibility", "responsibilities", "owns", "split", "organize", "module"},
    "communication_mechanisms": {"http", "rpc", "event", "queue", "message", "async", "synchronous"},
    "key_call_chains": {"call chain", "path", "handoff", "request path", "execution path", "routes to", "->"},
    "design_rationale": {"rationale", "tradeoff", "reliability", "performance", "maintainability", "why"},
}

USE_CASE_KEYWORDS = {
    "scenario_count": {"scenario", "workflow", "journey", "request", "case"},
    "user_roles_count": {"role", "operator", "customer", "admin", "analyst", "actor"},
    "input_output_patterns_count": {"input", "output", "payload", "response", "request", "result"},
    "boundary_conditions_count": {"edge", "boundary", "limit", "invalid", "failure", "condition"},
    "extension_points_count": {"extension", "plugin", "customize", "hook", "configuration"},
}

COLLABORATION_MARKERS = {
    "judgment_turn_count": ("i think", "i believe", "my judgment", "my read is", "my view"),
    "correction_turn_count": ("correct", "actually", "instead", "not that", "misread", "fix the earlier"),
    "redirection_turn_count": ("redirect", "back to", "return to", "focus back", "instead of that branch"),
    "prioritization_turn_count": ("prioritize", "worth continuing", "deepen next", "first before", "more central"),
}

DRIFT_NARROW_TOPIC_MARKERS = {
    "safety",
    "audit",
    "edge",
    "exception",
    "failure",
    "retry",
    "fallback",
    "boundary",
    "subprocess",
}


def default_coverage_state() -> dict[str, Any]:
    return {
        "version": 1,
        "branch_count": 0,
        "updated_through_turn_no": 0,
        "branches": [],
        "framework": default_framework_coverage(),
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
    parsed.setdefault("framework", default_framework_coverage())
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
    framework = rebuild_framework_coverage(turns)
    return {
        "version": 1,
        "branch_count": len(branches),
        "updated_through_turn_no": updated_through_turn_no,
        "branches": sorted(branches, key=lambda item: item["priority"], reverse=True),
        "framework": framework,
    }


def default_framework_coverage() -> dict[str, Any]:
    return {
        "panorama": {
            "purpose": False,
            "target_users": False,
            "boundaries": False,
            "major_modules": False,
            "high_level_workflow": False,
        },
        "architecture": {
            "architecture_style": False,
            "module_responsibilities": False,
            "communication_mechanisms": False,
            "key_call_chains": False,
            "design_rationale": False,
        },
        "code_detail": {
            "key_files_count": 0,
            "key_classes_count": 0,
            "key_methods_count": 0,
            "execution_paths_count": 0,
            "third_party_library_usage_count": 0,
            "error_handling_count": 0,
        },
        "use_cases": {
            "scenario_count": 0,
            "user_roles_count": 0,
            "input_output_patterns_count": 0,
            "boundary_conditions_count": 0,
            "extension_points_count": 0,
        },
        "human_collaboration": {
            "judgment_turn_count": 0,
            "correction_turn_count": 0,
            "redirection_turn_count": 0,
            "prioritization_turn_count": 0,
        },
        "stage_turn_counts": {
            "Panorama Mapping": 0,
            "Architecture Understanding": 0,
            "Code Detail Completion": 0,
            "Use Cases & Scenarios": 0,
            "Final Wrap-up": 0,
        },
        "gaps": {},
        "wrap_up_ready": False,
    }


def rebuild_framework_coverage(turns: list[InterviewTurn]) -> dict[str, Any]:
    framework = default_framework_coverage()
    panorama = framework["panorama"]
    architecture = framework["architecture"]
    code_detail = framework["code_detail"]
    use_cases = framework["use_cases"]
    collaboration = framework["human_collaboration"]
    stage_turn_counts = framework["stage_turn_counts"]

    for turn in turns:
        if not turn.answer_text:
            continue

        stage_turn_counts[turn.stage] = stage_turn_counts.get(turn.stage, 0) + 1
        text = " ".join(
            filter(
                None,
                [turn.question_text, turn.answer_text, turn.answer_summary],
            )
        ).lower()

        for key, keywords in PANORAMA_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                panorama[key] = True

        for key, keywords in ARCHITECTURE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                architecture[key] = True

        code_detail["key_files_count"] += len(set(FILE_PATTERN.findall(turn.answer_text)))
        code_detail["key_classes_count"] += len(set(CLASS_PATTERN.findall(turn.answer_text)))
        code_detail["key_methods_count"] += len(set(method.strip(" (") for method in METHOD_PATTERN.findall(turn.answer_text)))
        if any(marker in text for marker in {"execution path", "request path", "call chain", "->"}):
            code_detail["execution_paths_count"] += 1
        code_detail["third_party_library_usage_count"] += len(
            set(token.lower() for token in LIBRARY_PATTERN.findall(turn.answer_text))
        )
        if any(marker in text for marker in {"error", "exception", "retry", "fallback", "http exception", "log"}):
            code_detail["error_handling_count"] += 1

        for key, keywords in USE_CASE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                use_cases[key] += 1

        for key, markers in COLLABORATION_MARKERS.items():
            if any(marker in text for marker in markers):
                collaboration[key] += 1

        human_review = turn.human_review or {}
        verdict = human_review.get("verdict")
        direction = human_review.get("direction")
        if verdict in {"sufficient", "insufficient", "drifted"}:
            collaboration["judgment_turn_count"] += 1
        if verdict == "drifted" or direction == "redirect":
            collaboration["redirection_turn_count"] += 1
            collaboration["correction_turn_count"] += 1
        if human_review.get("preferred_next_focus"):
            collaboration["prioritization_turn_count"] += 1

    framework["gaps"] = {
        "panorama": [
            key for key, covered in panorama.items() if not covered
        ],
        "architecture": [
            key for key, covered in architecture.items() if not covered
        ],
        "code_detail": [
            key
            for key, count in code_detail.items()
            if count <= 0
        ],
        "use_cases": [
            key
            for key, count in use_cases.items()
            if count <= 0
        ],
        "human_collaboration": [
            key
            for key, count in collaboration.items()
            if count <= 0
        ],
    }
    framework["wrap_up_ready"] = (
        len(framework["gaps"]["panorama"]) <= 1
        and len(framework["gaps"]["architecture"]) <= 1
        and code_detail["key_files_count"] >= 2
        and code_detail["key_methods_count"] >= 2
        and use_cases["scenario_count"] >= 1
        and use_cases["input_output_patterns_count"] >= 1
        and use_cases["boundary_conditions_count"] >= 1
    )
    return framework


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


def framework_gaps_for_stage(coverage_state: dict[str, Any], stage: str) -> list[str]:
    framework = coverage_state.get("framework", default_framework_coverage())
    gap_map = framework.get("gaps", {})
    if not gap_map:
        gap_map = {
            "panorama": [
                key
                for key, covered in framework.get("panorama", {}).items()
                if not covered
            ],
            "architecture": [
                key
                for key, covered in framework.get("architecture", {}).items()
                if not covered
            ],
            "code_detail": [
                key
                for key, count in framework.get("code_detail", {}).items()
                if isinstance(count, (int, float)) and count <= 0
            ],
            "use_cases": [
                key
                for key, count in framework.get("use_cases", {}).items()
                if isinstance(count, (int, float)) and count <= 0
            ],
            "human_collaboration": [
                key
                for key, count in framework.get("human_collaboration", {}).items()
                if isinstance(count, (int, float)) and count <= 0
            ],
        }
    if stage == "Panorama Mapping":
        return gap_map.get("panorama", [])
    if stage == "Architecture Understanding":
        return gap_map.get("architecture", [])
    if stage == "Code Detail Completion":
        return gap_map.get("code_detail", [])
    if stage == "Use Cases & Scenarios":
        return gap_map.get("use_cases", [])
    return []


def detect_topic_drift(coverage_state: dict[str, Any], stage: str) -> dict[str, Any]:
    framework = coverage_state.get("framework", default_framework_coverage())
    panorama_gaps = framework_gaps_for_stage(coverage_state, "Panorama Mapping")
    architecture_gaps = framework_gaps_for_stage(coverage_state, "Architecture Understanding")
    branches = coverage_state.get("branches", [])
    if not branches:
        return {"detected": False, "reason": "", "branch_id": None}

    top_branch = branches[0]
    branch_text = " ".join(
        str(top_branch.get(key, "")) for key in ("label", "summary", "keywords")
    ).lower()
    narrow_topic_hits = sum(1 for marker in DRIFT_NARROW_TOPIC_MARKERS if marker in branch_text)

    if stage == "Panorama Mapping" and panorama_gaps and narrow_topic_hits >= 2:
        return {
            "detected": True,
            "reason": "Panorama still has macro gaps, but the active branch is drifting into a narrow safety or edge-case audit.",
            "branch_id": top_branch.get("branch_id"),
        }

    if stage == "Architecture Understanding" and architecture_gaps and narrow_topic_hits >= 2:
        return {
            "detected": True,
            "reason": "Architecture still has structural gaps, but the active branch is drifting into a narrow local mechanism.",
            "branch_id": top_branch.get("branch_id"),
        }

    if stage in {"Architecture Understanding", "Code Detail Completion"} and any(
        marker in branch_text
        for marker in {
            "should change",
            "should be changed",
            "redesign",
            "refactor",
            "modify",
            "update tests",
        }
    ):
        return {
            "detected": True,
            "reason": "The active branch is drifting from understanding the current code into change-planning or redesign discussion.",
            "branch_id": top_branch.get("branch_id"),
        }

    return {"detected": False, "reason": "", "branch_id": None}
