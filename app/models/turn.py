from datetime import datetime
import json

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.services.question_postprocessor import strip_question_prefix


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project_sessions.id"), nullable=False, index=True
    )

    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_review_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project = relationship("ProjectSession", back_populates="turns")
    llm_usages = relationship(
        "LLMUsage", back_populates="turn", cascade="all, delete-orphan"
    )
    question_versions = relationship(
        "InterviewQuestionVersion",
        back_populates="turn",
        cascade="all, delete-orphan",
        order_by="InterviewQuestionVersion.version_no",
    )

    @property
    def prompt_tokens(self) -> int:
        return sum(usage.prompt_tokens for usage in self.llm_usages)

    @property
    def completion_tokens(self) -> int:
        return sum(usage.completion_tokens for usage in self.llm_usages)

    @property
    def total_tokens(self) -> int:
        return sum(usage.total_tokens for usage in self.llm_usages)

    @property
    def question_text_for_copy(self) -> str:
        return strip_question_prefix(self.question_text)

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

    @property
    def answer_analysis(self) -> dict | None:
        if not self.answer_analysis_json:
            return None
        try:
            parsed = json.loads(self.answer_analysis_json)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @property
    def current_question_version_no(self) -> int:
        if self.question_versions:
            return self.question_versions[-1].version_no
        return 1

    @property
    def question_regeneration_count(self) -> int:
        return max(0, self.current_question_version_no - 1)

    @property
    def human_intervention_regeneration_usage_summary(self) -> dict[str, int]:
        versions = [
            version
            for version in self.question_versions
            if version.generation_kind == "human_regeneration"
        ]
        return {
            "prompt_tokens": sum(version.prompt_tokens for version in versions),
            "completion_tokens": sum(version.completion_tokens for version in versions),
            "total_tokens": sum(version.total_tokens for version in versions),
            "estimated_total_tokens": sum(
                version.total_tokens for version in versions if getattr(version, "is_estimated", False)
            ),
        }
