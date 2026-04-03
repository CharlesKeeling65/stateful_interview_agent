from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project_sessions.id"), nullable=False, index=True
    )
    turn_no: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_llm_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_llm_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project = relationship("ProjectSession", back_populates="agent_runs")
    steps = relationship(
        "AgentRunStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunStep.step_index",
    )

