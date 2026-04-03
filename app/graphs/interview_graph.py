import time

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graphs.interview_state import InterviewGraphState
from app.core.database import SessionLocal
from app.logging import emit_event, preview_payload
from app.graphs.interview_nodes import (
    decide_progress,
    draft_next_question,
    load_project_context,
    persist_next_step,
)


def _run_logged_node(node_name: str, state: InterviewGraphState, fn):
    start_time = time.perf_counter()
    emit_event(
        "workflow",
        "workflow.node.start",
        f"Workflow node {node_name} started",
        node=node_name,
        project_id=state.get("project_id"),
        turn_no=state.get("current_turn_no"),
        stage=state.get("current_stage") or state.get("next_stage"),
        input={"state_keys": sorted(state.keys())},
    )
    try:
        result = fn()
    except Exception as exc:
        emit_event(
            "workflow",
            "workflow.node.error",
            f"Workflow node {node_name} failed",
            level=40,
            node=node_name,
            project_id=state.get("project_id"),
            turn_no=state.get("current_turn_no"),
            stage=state.get("current_stage") or state.get("next_stage"),
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            exc_info=exc,
        )
        raise

    emit_event(
        "workflow",
        "workflow.node.complete",
        f"Workflow node {node_name} completed",
        node=node_name,
        project_id=state.get("project_id"),
        turn_no=result.get("next_turn_no") or state.get("current_turn_no"),
        stage=result.get("next_stage") or state.get("current_stage") or state.get("next_stage"),
        status="success",
        duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
        output=preview_payload(result, artifact_category="workflow", artifact_name=f"{node_name}-result"),
    )
    return result


def load_context_node(state: InterviewGraphState):
    db = SessionLocal()
    try:
        return _run_logged_node("load_context", state, lambda: load_project_context(state, db))
    finally:
        db.close()


def decide_progress_node(state: InterviewGraphState):
    return _run_logged_node("decide_progress", state, lambda: decide_progress(state))


def draft_question_node(state: InterviewGraphState):
    db = SessionLocal()
    try:
        return _run_logged_node("draft_question", state, lambda: draft_next_question(state, db))
    finally:
        db.close()


def persist_node(state: InterviewGraphState):
    db = SessionLocal()
    try:
        return _run_logged_node("persist", state, lambda: persist_next_step(state, db))
    finally:
        db.close()


def route_after_decision(state: InterviewGraphState):
    if state.get("interview_finished"):
        return "persist"
    return "draft_question"


builder = StateGraph(InterviewGraphState)

builder.add_node("load_context", load_context_node)
builder.add_node("decide_progress", decide_progress_node)
builder.add_node("draft_question", draft_question_node)
builder.add_node("persist", persist_node)

builder.set_entry_point("load_context")
builder.add_edge("load_context", "decide_progress")
builder.add_conditional_edges(
    "decide_progress",
    route_after_decision,
    {
        "draft_question": "draft_question",
        "persist": "persist",
    },
)
builder.add_edge("draft_question", "persist")
builder.add_edge("persist", END)

checkpointer = MemorySaver()
interview_graph = builder.compile(checkpointer=checkpointer)
