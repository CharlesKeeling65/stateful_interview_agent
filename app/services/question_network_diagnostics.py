from __future__ import annotations

from typing import Any


def count_recent_repeated_openings(question_history: list[dict[str, Any]]) -> int:
    code_detail_questions = [
        entry.get("question_text", "")
        for entry in question_history
        if entry.get("stage") == "Code Detail Completion"
    ][-6:]
    opening_counts: dict[str, int] = {}
    for question_text in code_detail_questions:
        normalized = " ".join((question_text or "").split())
        if not normalized:
            continue
        opening = " ".join(normalized.split(" ", 4)[:4]).lower()
        opening_counts[opening] = opening_counts.get(opening, 0) + 1
    return sum(1 for count in opening_counts.values() if count >= 2)


def diagnose_question_network_health(coverage_state: dict[str, Any]) -> dict[str, Any]:
    question_network_stats = coverage_state.get("question_network_stats", {}) or {}
    intent_coverage = coverage_state.get("developer_intent_coverage", {}) or {}
    frontier_items = ((coverage_state.get("investigation_frontier") or {}).get("items", [])) or []

    node_count = int(question_network_stats.get("node_count", 0) or 0)
    isolated_node_count = int(question_network_stats.get("isolated_node_count", 0) or 0)
    connected_ratio = (node_count - isolated_node_count) / node_count if node_count else 0.0
    repeat_opening_clusters = count_recent_repeated_openings(coverage_state.get("question_history", []) or [])

    positive_counts = [count for count in intent_coverage.values() if count > 0]
    total_positive = sum(positive_counts)
    top_intent_share = (max(positive_counts) / total_positive) if total_positive else 0.0

    diagnostic_flags: list[str] = []
    degradation_reasons: list[str] = []

    if node_count >= 4 and connected_ratio < 0.75:
        diagnostic_flags.append("isolated_questions")
        degradation_reasons.append(
            "Too many recent questions are disconnected from the active investigation thread."
        )
    if repeat_opening_clusters > 0:
        diagnostic_flags.append("template_repetition")
        degradation_reasons.append(
            "Recent code-detail turns are reusing the same opening pattern too often."
        )
    if top_intent_share >= 0.7:
        diagnostic_flags.append("intent_collapse")
        degradation_reasons.append(
            "One developer intent dominates the thread, so neighboring investigation angles are being ignored."
        )
    if node_count >= 3 and len(frontier_items) == 0:
        diagnostic_flags.append("frontier_starvation")
        degradation_reasons.append(
            "The active thread has stopped producing meaningful frontier items, which usually means breadth or depth expansion has stalled."
        )

    if "isolated_questions" in diagnostic_flags or "intent_collapse" in diagnostic_flags:
        health_status = "degraded"
    elif diagnostic_flags:
        health_status = "watch"
    else:
        health_status = "healthy"

    return {
        "health_status": health_status,
        "diagnostic_flags": diagnostic_flags,
        "degradation_reasons": degradation_reasons,
        "connected_ratio": round(connected_ratio, 3),
        "repeat_opening_clusters": repeat_opening_clusters,
        "top_intent_share": round(top_intent_share, 3),
    }
