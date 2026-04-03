from contextvars import ContextVar, Token
from typing import Any

_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


def get_log_context() -> dict[str, Any]:
    return dict(_LOG_CONTEXT.get())


def set_log_context(**values: Any) -> Token:
    next_context = get_log_context()
    next_context.update({key: value for key, value in values.items() if value is not None})
    return _LOG_CONTEXT.set(next_context)


def bind_log_context(**values: Any) -> dict[str, Any]:
    next_context = get_log_context()
    next_context.update({key: value for key, value in values.items() if value is not None})
    _LOG_CONTEXT.set(next_context)
    return next_context


def clear_log_context(token: Token | None = None) -> None:
    if token is not None:
        _LOG_CONTEXT.reset(token)
        return
    _LOG_CONTEXT.set({})
