from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graphs.interview_state import InterviewGraphState
from app.core.database import SessionLocal
from app.graphs.interview_nodes import (
    decide_progress,
    draft_next_question,
    load_project_context,
    persist_next_step,
)


def load_context_node(state: InterviewGraphState):
    db = SessionLocal()
    try:
        return load_project_context(state, db)
    finally:
        db.close()


def decide_progress_node(state: InterviewGraphState):
    return decide_progress(state)


def draft_question_node(state: InterviewGraphState):
    db = SessionLocal()
    try:
        return draft_next_question(state, db)
    finally:
        db.close()


def persist_node(state: InterviewGraphState):
    db = SessionLocal()
    try:
        return persist_next_step(state, db)
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
