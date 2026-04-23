from __future__ import annotations

from typing import Any

from app.logging import emit_event
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.coverage_service import extract_keywords
from app.services.repository_service import (
    RepositoryWorkspace,
    format_repository_manifest,
    read_repository_snippet,
    resolve_project_repository,
    search_repository_code,
    trace_repository_symbol,
)
from app.services.run_trace_service import traced_run_step


def build_repo_grounding_context(
    *,
    project: ProjectSession,
    turns: list[InterviewTurn],
    current_stage: str,
    next_turn_no: int,
    planner_decision: dict[str, Any],
    latest_answer_override: str | None,
    project_id: int,
    run_id: int | None,
) -> dict[str, Any]:
    workspace = resolve_project_repository(project)
    if not workspace:
        return {
            "repo_grounding_context": "No repository source configured for this project.",
            "repo_grounding_meta": {
                "enabled": False,
                "source_type": "none",
                "queries": [],
                "selected_paths": [],
                "selected_symbols": [],
                "tool_calls": [],
                "commit_sha": None,
            },
        }

    with traced_run_step(
        run_id=run_id,
        project_id=project_id,
        turn_no=next_turn_no,
        step_key="repo_manifest",
        description="Read repository manifest and key entry points.",
        next_step_hint="Search relevant code regions",
    ):
        manifest_text = format_repository_manifest(
            workspace.manifest,
            source_label=workspace.source_label,
            commit_sha=workspace.commit_sha,
        )

    queries = derive_repository_queries(
        planner_decision=planner_decision,
        turns=turns,
        latest_answer_override=latest_answer_override,
        workspace=workspace,
    )
    tool_calls = [{"tool": "repo_manifest"}]
    search_hits: list[dict[str, Any]] = []

    with traced_run_step(
        run_id=run_id,
        project_id=project_id,
        turn_no=next_turn_no,
        step_key="repo_search",
        description="Search the repository for paths, symbols, and keywords related to the next question target.",
        next_step_hint="Read focused snippets",
    ) as search_step:
        for query in queries[:4]:
            hits = search_repository_code(workspace.root_path, query, limit=5)
            if hits:
                tool_calls.append({"tool": "search_code", "query": query, "hit_count": len(hits)})
                search_hits.extend(hits)
        if search_step:
            search_step.set_meta(query_count=len(queries), hit_count=len(search_hits))

    deduplicated_hits: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for hit in search_hits:
        path = str(hit.get("path") or "")
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        deduplicated_hits.append(hit)
        if len(deduplicated_hits) >= 4:
            break

    snippets: list[dict[str, Any]] = []
    with traced_run_step(
        run_id=run_id,
        project_id=project_id,
        turn_no=next_turn_no,
        step_key="repo_read",
        description="Open only the most relevant files and line ranges for grounded question writing.",
        next_step_hint="Trace a likely symbol if available",
    ) as read_step:
        for hit in deduplicated_hits:
            snippet = read_repository_snippet(
                workspace.root_path,
                str(hit["path"]),
                center_line=int(hit.get("line_no") or 1),
            )
            if snippet:
                snippets.append(snippet)
                tool_calls.append(
                    {
                        "tool": "read_file",
                        "path": snippet["path"],
                        "start_line": snippet["start_line"],
                        "end_line": snippet["end_line"],
                    }
                )
        if read_step:
            read_step.set_meta(snippet_count=len(snippets))

    symbols = collect_candidate_symbols(snippets, planner_decision)
    trace = None
    if symbols:
        with traced_run_step(
            run_id=run_id,
            project_id=project_id,
            turn_no=next_turn_no,
            step_key="repo_trace",
            description="Trace one likely symbol to reduce technical errors in the drafted question.",
            next_step_hint="Render grounded prompt",
        ):
            trace = trace_repository_symbol(workspace.root_path, symbols[0], limit=5)
            tool_calls.append({"tool": "trace_call_path", "symbol": symbols[0]})

    context = format_repo_grounding_context(
        manifest_text=manifest_text,
        queries=queries,
        hits=deduplicated_hits,
        snippets=snippets,
        trace=trace,
        stage=current_stage,
    )
    meta = {
        "enabled": True,
        "source_type": workspace.source_type,
        "source_label": workspace.source_label,
        "root_path": str(workspace.root_path),
        "queries": queries,
        "selected_paths": [snippet["path"] for snippet in snippets],
        "selected_symbols": symbols[:4],
        "tool_calls": tool_calls,
        "commit_sha": workspace.commit_sha,
    }
    emit_event(
        "retrieval",
        "retrieval.repo_grounding.complete",
        "Built repository-grounded evidence bundle",
        operation="build_repo_grounding_context",
        project_id=project_id,
        stage=current_stage,
        turn_no=next_turn_no,
        status="success",
        output={
            "queries": queries,
            "selected_paths": meta["selected_paths"],
            "selected_symbols": meta["selected_symbols"],
            "commit_sha": workspace.commit_sha,
        },
    )
    return {
        "repo_grounding_context": context,
        "repo_grounding_meta": meta,
    }


def derive_repository_queries(
    *,
    planner_decision: dict[str, Any],
    turns: list[InterviewTurn],
    latest_answer_override: str | None,
    workspace: RepositoryWorkspace,
) -> list[str]:
    raw_candidates: list[str] = []
    for key in ("target_label", "selected_framework_gap", "question_intent", "retrieval_focus"):
        value = str(planner_decision.get(key) or "").strip()
        if value:
            raw_candidates.append(value)

    for key in ("source_node_id", "parent_node_id"):
        value = str(planner_decision.get(key) or "").strip()
        if value:
            raw_candidates.append(value)

    for list_key in ("neighbor_targets", "frontier_labels", "artifact_keys"):
        values = planner_decision.get(list_key) or []
        if isinstance(values, list):
            raw_candidates.extend(str(value).strip() for value in values if str(value).strip())

    human_review = planner_decision.get("human_review_signal") or {}
    for key in ("preferred_next_focus", "note"):
        value = str(human_review.get(key) or "").strip()
        if value:
            raw_candidates.append(value)

    latest_text = latest_answer_override or (turns[-1].answer_text if turns else None) or ""
    raw_candidates.extend(extract_keywords(latest_text, ""))
    raw_candidates.extend(workspace.manifest.get("key_files", [])[:4])

    queries: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        cleaned = " ".join(str(candidate).split())
        if len(cleaned) < 3:
            continue
        if cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        queries.append(cleaned)
        if len(queries) >= 8:
            break
    return queries


def collect_candidate_symbols(
    snippets: list[dict[str, Any]],
    planner_decision: dict[str, Any],
) -> list[str]:
    symbols: list[str] = []
    target_label = str(planner_decision.get("target_label") or "")
    if target_label:
        for token in target_label.replace("/", " ").replace(".", " ").split():
            if token[:1].isalpha() and any(character.isupper() for character in token[1:]):
                symbols.append(token)
    for snippet in snippets:
        symbols.extend(snippet.get("symbols", []))
    deduplicated: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        if symbol not in seen:
            seen.add(symbol)
            deduplicated.append(symbol)
    return deduplicated


def format_repo_grounding_context(
    *,
    manifest_text: str,
    queries: list[str],
    hits: list[dict[str, Any]],
    snippets: list[dict[str, Any]],
    trace: dict[str, Any] | None,
    stage: str,
) -> str:
    lines = [
        "Repository evidence bundle:",
        manifest_text,
        "",
        "Progressive disclosure:",
        "1. Repo manifest and key files",
        "2. Search hits narrowed by planner target and recent answer",
        "3. Focused file reads only for the top matching paths",
        "4. A single symbol trace when a likely symbol is available",
        "",
        f"Stage alignment: {stage}",
        f"Queries: {', '.join(queries[:6]) or 'None'}",
        "",
        "Top search hits:",
    ]
    if hits:
        for hit in hits[:4]:
            lines.append(f"- {hit['path']}:{hit['line_no']} -> {hit['line_text']}")
    else:
        lines.append("- No targeted code hits were found.")

    lines.append("")
    lines.append("Focused snippets:")
    if snippets:
        for snippet in snippets[:3]:
            lines.append(f"[{snippet['path']}:{snippet['start_line']}-{snippet['end_line']}]")
            lines.append(snippet["content"])
            lines.append("")
    else:
        lines.append("- No snippets were opened.")

    lines.append("Symbol trace:")
    if trace and trace.get("symbol"):
        lines.append(f"- Symbol: {trace['symbol']}")
        definitions = trace.get("definitions") or []
        calls = trace.get("calls") or []
        if definitions:
            lines.append(
                "- Definitions: "
                + "; ".join(f"{item['path']}:{item['line_no']}" for item in definitions[:2])
            )
        if calls:
            lines.append(
                "- Call sites: "
                + "; ".join(f"{item['path']}:{item['line_no']}" for item in calls[:4])
            )
    else:
        lines.append("- No reliable symbol trace was available.")
    return "\n".join(lines).strip()
