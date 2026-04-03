import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project_sessions.id"), nullable=False, index=True
    )
    turn_no: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_step_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    run = relationship("AgentRun", back_populates="steps")
    project = relationship("ProjectSession")

    @property
    def meta(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.meta_json) if self.meta_json else {}
        except json.JSONDecodeError:
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}
