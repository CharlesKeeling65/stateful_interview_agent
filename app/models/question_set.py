import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuestionSet(Base):
    """A generated question set for repository code understanding."""
    
    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # pending -> analyzing -> generating -> validating -> completed | failed
    
    # Configuration
    total_questions: Mapped[int] = mapped_column(Integer, default=40)
    code_detail_ratio: Mapped[float] = mapped_column(Float, default=0.85)
    min_core_file_coverage: Mapped[float] = mapped_column(Float, default=0.90)
    
    # Repository analysis results (JSON)
    repository_analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    
    # Validation report (JSON)
    validation_report_json: Mapped[str] = mapped_column(Text, default="{}")
    
    # Coverage report (JSON)
    coverage_report_json: Mapped[str] = mapped_column(Text, default="{}")
    
    # Error message if failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    questions = relationship(
        "GeneratedQuestion", back_populates="question_set", cascade="all, delete-orphan"
    )
    revisions = relationship(
        "QuestionRevision", back_populates="question_set", cascade="all, delete-orphan"
    )

    @property
    def repository_analysis(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.repository_analysis_json) if self.repository_analysis_json else {}
        except json.JSONDecodeError:
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    @property
    def validation_report(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.validation_report_json) if self.validation_report_json else {}
        except json.JSONDecodeError:
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    @property
    def coverage_report(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.coverage_report_json) if self.coverage_report_json else {}
        except json.JSONDecodeError:
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def code_detail_count(self) -> int:
        return sum(1 for q in self.questions if q.phase == "Code Detail Completion")

    @property
    def code_detail_ratio_actual(self) -> float:
        if not self.questions:
            return 0.0
        return self.code_detail_count / len(self.questions)

    @property
    def covered_core_files(self) -> set[str]:
        files = set()
        for q in self.questions:
            if q.target_files:
                files.update(q.target_files)
        return files

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "repository_url": self.repository_url,
            "status": self.status,
            "total_questions": self.total_questions,
            "code_detail_ratio": self.code_detail_ratio,
            "min_core_file_coverage": self.min_core_file_coverage,
            "question_count": self.question_count,
            "code_detail_count": self.code_detail_count,
            "code_detail_ratio_actual": self.code_detail_ratio_actual,
            "repository_analysis": self.repository_analysis,
            "validation_report": self.validation_report,
            "coverage_report": self.coverage_report,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "questions": [q.to_dict() for q in self.questions],
        }


class GeneratedQuestion(Base):
    """A single generated question in a question set."""
    
    __tablename__ = "generated_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_set_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_sets.id"), nullable=False)
    question_no: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(100), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Target files mentioned in the question (JSON array)
    target_files_json: Mapped[str] = mapped_column(Text, default="[]")
    
    # Target symbols (classes, functions, methods) mentioned (JSON array)
    target_symbols_json: Mapped[str] = mapped_column(Text, default="[]")
    
    # Quality score (0.0 - 1.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Warnings/issues found during validation (JSON array)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    question_set = relationship("QuestionSet", back_populates="questions")
    revisions = relationship(
        "QuestionRevision", back_populates="question", cascade="all, delete-orphan"
    )
    versions = relationship(
        "QuestionVersion", back_populates="question", cascade="all, delete-orphan"
    )

    @property
    def target_files(self) -> list[str]:
        try:
            parsed = json.loads(self.target_files_json) if self.target_files_json else []
        except json.JSONDecodeError:
            parsed = []
        return parsed if isinstance(parsed, list) else []

    @property
    def target_symbols(self) -> list[str]:
        try:
            parsed = json.loads(self.target_symbols_json) if self.target_symbols_json else []
        except json.JSONDecodeError:
            parsed = []
        return parsed if isinstance(parsed, list) else []

    @property
    def warnings(self) -> list[str]:
        try:
            parsed = json.loads(self.warnings_json) if self.warnings_json else []
        except json.JSONDecodeError:
            parsed = []
        return parsed if isinstance(parsed, list) else []

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question_set_id": self.question_set_id,
            "question_no": self.question_no,
            "phase": self.phase,
            "question_text": self.question_text,
            "target_files": self.target_files,
            "target_symbols": self.target_symbols,
            "quality_score": self.quality_score,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "revision_count": len(self.revisions),
            "version_count": len(self.versions),
            "current_version_no": max([v.version_no for v in self.versions]) if self.versions else 0,
        }


class QuestionRevision(Base):
    """A revision of a generated question based on Chinese instructions."""
    
    __tablename__ = "question_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_set_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_sets.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("generated_questions.id"), nullable=False)
    
    # Chinese instruction from user
    chinese_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Original question text before revision
    original_question_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Revised question text (English)
    revised_question_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Validation result after revision (JSON)
    validation_result_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    question_set = relationship("QuestionSet", back_populates="revisions")
    question = relationship("GeneratedQuestion", back_populates="revisions")

    @property
    def validation_result(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.validation_result_json) if self.validation_result_json else {}
        except json.JSONDecodeError:
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question_set_id": self.question_set_id,
            "question_id": self.question_id,
            "chinese_instruction": self.chinese_instruction,
            "original_question_text": self.original_question_text,
            "revised_question_text": self.revised_question_text,
            "validation_result": self.validation_result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class QuestionVersion(Base):
    """Version history for a generated question."""
    
    __tablename__ = "question_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("generated_questions.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3, ...
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'generated', 'revised', 'rollback'
    change_summary: Mapped[str] = mapped_column(Text, default="")  # 中文指令或回滚原因
    parent_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("question_versions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    question = relationship("GeneratedQuestion", back_populates="versions")
    parent_version = relationship("QuestionVersion", remote_side=[id])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question_id": self.question_id,
            "version_no": self.version_no,
            "question_text": self.question_text,
            "change_type": self.change_type,
            "change_summary": self.change_summary,
            "parent_version_id": self.parent_version_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
