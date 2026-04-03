from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StructuredLogEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    level: str
    logger: str
    event: str
    message: str

    request_id: str | None = None
    trace_id: str | None = None
    project_id: int | None = None
    turn_no: int | None = None
    stage: str | None = None
    node: str | None = None
    operation: str | None = None
    status: str | None = None
    duration_ms: float | None = None
    request_method: str | None = None
    request_path: str | None = None
    status_code: int | None = None
    input: Any | None = None
    output: Any | None = None
    usage: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    traceback: str | None = None
