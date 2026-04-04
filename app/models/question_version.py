from datetime import datetime
import json

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InterviewQuestionVersion(Base):
    __tablename__ = "interview_question_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    turn_id: Mapped[int] = mapped_column(
        ForeignKey("interview_turns.id"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="initial")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_review_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    turn = relationship("InterviewTurn", back_populates="question_versions")

    @property
    def human_review(self) -> dict | None:
        if not self.human_review_json:
            return None
        try:
            parsed = json.loads(self.human_review_json)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @property
    def question_plan(self) -> dict | None:
        if not self.question_plan_json:
            return None
        try:
            parsed = json.loads(self.question_plan_json)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
