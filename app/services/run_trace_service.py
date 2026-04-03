import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any, Iterator

from app.core.database import SessionLocal
from app.logging import emit_event
from app.logging.context import get_log_context
from app.models.agent_run import AgentRun
from app.models.agent_run_step import AgentRunStep


STEP_DEFINITIONS = {
    "load_project_context": {
        "label": "Load project context",
        "method": "database lookup",
    },
    "refresh_summaries": {
        "label": "Refresh summaries",
        "method": "summary maintenance",
    },
    "refresh_coverage": {
        "label": "Refresh coverage",
        "method": "rule-based coverage map",
    },
    "build_compact_context": {
        "label": "Build compact context",
        "method": "history compaction",
    },
    "retrieve_relevant_branches": {
        "label": "Retrieve relevant context",
        "method": "rule-based retrieval",
    },
    "render_prompt": {
        "label": "Render prompt",
        "method": "prompt asset renderer",
    },
    "call_llm": {
        "label": "Call model",
        "method": "OpenAI-compatible chat.completions",
    },
    "validate_question": {
        "label": "Validate question",
        "method": "rule-based validator",
    },
    "persist_result": {
        "label": "Persist result",
        "method": "database write",
    },
}


def utcnow() -> datetime:
    return datetime.utcnow()


def _emit_trace_write_error(
    *,
    operation: str,
    exc: Exception,
    run_id: int | None = None,
    step_key: str | None = None,
) -> None:
    emit_event(
        "errors",
        "run_trace.write_error",
        "Run trace bookkeeping failed",
        level=40,
        operation=operation,
        run_id=run_id,
        step_key=step_key,
        exc_info=exc,
    )


def create_run(*, project_id: int, turn_no: int | None) -> AgentRun:
    context = get_log_context()
    db = SessionLocal()
    try:
        run = AgentRun(
            project_id=project_id,
            turn_no=turn_no,
            request_id=context.get("request_id"),
            trace_id=context.get("trace_id"),
            status="running",
            started_at=utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def finalize_run(*, run_id: int, status: str, turn_no: int | None = None) -> None:
    try:
        db = SessionLocal()
        try:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if not run:
                return
            run.status = status
            run.turn_no = turn_no if turn_no is not None else run.turn_no
            run.ended_at = utcnow()
            run.duration_ms = max(0, int((run.ended_at - run.started_at).total_seconds() * 1000))
            run.total_llm_calls = sum(1 for step in run.steps if step.step_key == "call_llm" and step.status == "completed")
            run.total_llm_tokens = sum(step.total_tokens for step in run.steps)
            run.step_count = len(run.steps)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        _emit_trace_write_error(operation="finalize_run", exc=exc, run_id=run_id)


@dataclass
class StepSpan:
    run_id: int
    step_id: int
    step_key: str
    meta: dict[str, Any] = field(default_factory=dict)
    next_step_hint: str | None = None
    description: str | None = None
    usage: dict[str, int] | None = None
    started_at_monotonic: float = field(default_factory=perf_counter)

    def set_meta(self, **values: Any) -> None:
        self.meta.update(values)

    def set_usage(self, usage: dict[str, int] | None) -> None:
        self.usage = usage

    def set_next_step_hint(self, hint: str | None) -> None:
        self.next_step_hint = hint

    def set_description(self, description: str | None) -> None:
        self.description = description


def _start_step(
    *,
    run_id: int,
    project_id: int,
    turn_no: int | None,
    step_key: str,
    description: str | None,
    next_step_hint: str | None,
) -> StepSpan:
    definition = STEP_DEFINITIONS.get(step_key, {})
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            raise ValueError(f"Unknown run id: {run_id}")
        step_index = len(run.steps) + 1
        step = AgentRunStep(
            run_id=run_id,
            project_id=project_id,
            turn_no=turn_no,
            step_index=step_index,
            step_key=step_key,
            label=definition.get("label", step_key.replace("_", " ").title()),
            status="running",
            description=description,
            method=definition.get("method"),
            started_at=utcnow(),
            next_step_hint=next_step_hint,
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        return StepSpan(
            run_id=run_id,
            step_id=step.id,
            step_key=step_key,
            description=description,
            next_step_hint=next_step_hint,
        )
    finally:
        db.close()


def _finish_step(span: StepSpan, *, status: str, error_message: str | None = None) -> None:
    db = SessionLocal()
    try:
        step = db.query(AgentRunStep).filter(AgentRunStep.id == span.step_id).first()
        if not step:
            return
        step.status = status
        step.ended_at = utcnow()
        step.duration_ms = max(0, int((step.ended_at - step.started_at).total_seconds() * 1000))
        step.next_step_hint = span.next_step_hint
        step.description = span.description or step.description
        if span.usage:
            step.prompt_tokens = int(span.usage.get("prompt_tokens", 0))
            step.completion_tokens = int(span.usage.get("completion_tokens", 0))
            step.total_tokens = int(span.usage.get("total_tokens", 0))
        meta = dict(span.meta)
        if error_message:
            meta["error_message"] = error_message
        step.meta_json = json.dumps(meta, ensure_ascii=True, sort_keys=True)
        db.commit()
    finally:
        db.close()


@contextmanager
def traced_run_step(
    *,
    run_id: int | None,
    project_id: int,
    turn_no: int | None,
    step_key: str,
    description: str | None = None,
    next_step_hint: str | None = None,
) -> Iterator[StepSpan | None]:
    if run_id is None:
        yield None
        return

    try:
        span = _start_step(
            run_id=run_id,
            project_id=project_id,
            turn_no=turn_no,
            step_key=step_key,
            description=description,
            next_step_hint=next_step_hint,
        )
    except Exception as exc:
        _emit_trace_write_error(
            operation="start_step",
            exc=exc,
            run_id=run_id,
            step_key=step_key,
        )
        yield None
        return
    try:
        yield span
    except Exception as exc:
        try:
            _finish_step(span, status="failed", error_message=str(exc))
        except Exception as trace_exc:
            _emit_trace_write_error(
                operation="finish_step_failed",
                exc=trace_exc,
                run_id=run_id,
                step_key=step_key,
            )
        finalize_run(run_id=run_id, status="failed")
        raise
    else:
        try:
            _finish_step(span, status="completed")
        except Exception as exc:
            _emit_trace_write_error(
                operation="finish_step_completed",
                exc=exc,
                run_id=run_id,
                step_key=step_key,
            )


def serialize_run(run: AgentRun) -> dict[str, Any]:
    current_step = next((step for step in reversed(run.steps) if step.status == "running"), None)
    if current_step is None and run.steps:
        current_step = run.steps[-1]
    return {
        "id": run.id,
        "project_id": run.project_id,
        "turn_no": run.turn_no,
        "request_id": run.request_id,
        "trace_id": run.trace_id,
        "status": run.status,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "duration_ms": run.duration_ms,
        "total_llm_tokens": run.total_llm_tokens,
        "total_llm_calls": run.total_llm_calls,
        "step_count": run.step_count or len(run.steps),
        "current_step_key": current_step.step_key if current_step else None,
        "current_step_label": current_step.label if current_step else None,
        "current_step_status": current_step.status if current_step else None,
        "steps": [
            {
                "id": step.id,
                "step_index": step.step_index,
                "step_key": step.step_key,
                "label": step.label,
                "status": step.status,
                "description": step.description,
                "method": step.method,
                "started_at": step.started_at,
                "ended_at": step.ended_at,
                "duration_ms": step.duration_ms,
                "next_step_hint": step.next_step_hint,
                "prompt_tokens": step.prompt_tokens,
                "completion_tokens": step.completion_tokens,
                "total_tokens": step.total_tokens,
                "meta": step.meta,
            }
            for step in run.steps
        ],
    }
