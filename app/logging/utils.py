import logging
import traceback as traceback_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.logging.context import get_log_context
from app.logging.event import StructuredLogEvent


def get_logger(category: str) -> logging.Logger:
    return logging.getLogger(f"app.{category}")


def preview_text(
    value: str | None,
    *,
    artifact_category: str | None = None,
    artifact_name: str | None = None,
    force_artifact: bool = False,
) -> dict[str, Any] | None:
    if value is None:
        return None

    preview_limit = max(32, settings.log_text_preview_chars)
    normalized = value.strip()
    payload: dict[str, Any] = {
        "preview": (
            normalized[:preview_limit] + ("..." if len(normalized) > preview_limit else "")
        ),
        "length": len(value),
    }

    if settings.log_artifacts_enabled and (
        force_artifact or len(normalized) > preview_limit
    ):
        payload["artifact_path"] = write_artifact(
            artifact_category or "generic",
            artifact_name or "payload",
            value,
        )
    return payload


def preview_payload(
    value: Any,
    *,
    artifact_category: str | None = None,
    artifact_name: str | None = None,
) -> Any:
    if isinstance(value, str):
        return preview_text(
            value,
            artifact_category=artifact_category,
            artifact_name=artifact_name,
        )
    if isinstance(value, dict):
        return {
            key: preview_payload(
                nested_value,
                artifact_category=artifact_category,
                artifact_name=f"{artifact_name or 'payload'}-{key}",
            )
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [
            preview_payload(
                item,
                artifact_category=artifact_category,
                artifact_name=f"{artifact_name or 'payload'}-{index}",
            )
            for index, item in enumerate(value[:10])
        ]
    return value


def emit_event(
    category: str,
    event: str,
    message: str,
    *,
    level: int = logging.INFO,
    exc_info: BaseException | None = None,
    **fields: Any,
) -> None:
    logger = get_logger(category)
    payload = {
        **get_log_context(),
        **fields,
        "level": logging.getLevelName(level),
        "logger": logger.name,
        "event": event,
        "message": message,
    }
    if exc_info is not None:
        payload.setdefault("error_type", type(exc_info).__name__)
        payload.setdefault("error_message", str(exc_info))
        payload.setdefault(
            "traceback",
            "".join(
                traceback_lib.format_exception(
                    type(exc_info), exc_info, exc_info.__traceback__
                )
            ),
        )

    event_record = StructuredLogEvent.model_validate(payload)
    logger.log(
        level,
        message,
        extra={"event_payload": event_record.model_dump(mode="json", exclude_none=True)},
    )


def write_artifact(category: str, name: str, content: str) -> str:
    root = Path(settings.log_dir) / "artifacts"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_name = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in name
    ).strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%H%M%S%f")
    file_path = root / day / category / f"{timestamp}-{safe_name or 'artifact'}.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)
