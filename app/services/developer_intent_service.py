from __future__ import annotations

from typing import Any


DEVELOPER_INTENT_KEYS = (
    "trace_execution",
    "understand_responsibility",
    "inspect_inputs_outputs",
    "investigate_failure",
    "follow_state_change",
    "check_dependency_usage",
    "understand_data_contract",
    "review_boundary_case",
    "evaluate_optimization_tradeoff",
    "connect_related_module",
)


def normalize_developer_intent_coverage(raw: dict[str, Any] | None) -> dict[str, int]:
    normalized = {key: 0 for key in DEVELOPER_INTENT_KEYS}
    for key, value in (raw or {}).items():
        if key in normalized:
            normalized[key] = int(value or 0)
    return normalized


def developer_intent_undercoverage_bonus(
    intent: str | None,
    coverage: dict[str, Any] | None,
) -> float:
    normalized = normalize_developer_intent_coverage(coverage)
    if not intent or intent not in normalized:
        return 0.0

    intent_count = normalized[intent]
    lowest_count = min(normalized.values()) if normalized else 0
    highest_count = max(normalized.values()) if normalized else 0
    if intent_count == lowest_count and highest_count > lowest_count:
        return 0.35
    if intent_count <= 1:
        return 0.15
    return 0.0
