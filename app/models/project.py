import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectSession(Base):
    __tablename__ = "project_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(100), default="Panorama Mapping")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    coverage_state: Mapped[str] = mapped_column(
        Text,
        default='{"version": 1, "branch_count": 0, "updated_through_turn_no": 0, "branches": []}',
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    turns = relationship(
        "InterviewTurn", back_populates="project", cascade="all, delete-orphan"
    )
    llm_usages = relationship(
        "LLMUsage", back_populates="project", cascade="all, delete-orphan"
    )

    @property
    def total_prompt_tokens(self) -> int:
        return sum(usage.prompt_tokens for usage in self.llm_usages)

    @property
    def total_completion_tokens(self) -> int:
        return sum(usage.completion_tokens for usage in self.llm_usages)

    @property
    def total_tokens(self) -> int:
        return sum(usage.total_tokens for usage in self.llm_usages)

    @property
    def estimated_total_tokens(self) -> int:
        return sum(usage.total_tokens for usage in self.llm_usages if usage.is_estimated)

    @property
    def coverage_state_data(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.coverage_state) if self.coverage_state else {}
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed.setdefault("version", 1)
        parsed.setdefault("branch_count", len(parsed.get("branches", [])))
        parsed.setdefault("updated_through_turn_no", 0)
        parsed.setdefault("branches", [])
        return parsed
