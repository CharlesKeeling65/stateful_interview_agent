from datetime import datetime

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
