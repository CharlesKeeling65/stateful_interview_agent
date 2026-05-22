from pydantic import BaseModel, Field
from typing import Any


class QuestionSetCreate(BaseModel):
    """Request to create a new question set."""
    repository_url: str = Field(..., description="URL of the repository to analyze")
    total_questions: int = Field(default=40, ge=35, le=100, description="Total number of questions to generate")
    code_detail_ratio: float = Field(default=0.85, ge=0.5, le=1.0, description="Minimum ratio of code detail questions")
    min_core_file_coverage: float = Field(default=0.90, ge=0.5, le=1.0, description="Minimum core file coverage ratio")


class QuestionRevisionRequest(BaseModel):
    """Request to revise a question using Chinese instructions."""
    question_id: int = Field(..., description="ID of the question to revise")
    chinese_instruction: str = Field(..., description="Chinese instruction for revision")


class QuestionRevisionResponse(BaseModel):
    """Response after revising a question."""
    question_id: int
    original_question: str
    revised_question: str
    chinese_instruction: str
    phase_changed: bool
    new_phase: str | None = None
    coverage_changed: bool
    duplicate_check_passed: bool
    validation_result: dict[str, Any]
    warnings: list[str] = []


class ValidationReport(BaseModel):
    """Validation report for a question set."""
    is_valid: bool
    total_questions: int
    code_detail_count: int
    code_detail_ratio: float
    core_files_detected: int
    core_files_covered: int
    core_file_coverage: float
    phase_counts: dict[str, int]
    warnings: list[str] = []
    errors: list[str] = []


class CoverageReport(BaseModel):
    """Coverage report for core files."""
    total_core_files: int
    covered_core_files: int
    coverage_percentage: float
    uncovered_files: list[str] = []
    file_importance: dict[str, float] = {}


class QuestionSetResponse(BaseModel):
    """Response containing a question set."""
    id: int
    repository_url: str
    status: str
    total_questions: int
    code_detail_ratio: float
    min_core_file_coverage: float
    question_count: int
    code_detail_count: int
    code_detail_ratio_actual: float
    repository_analysis: dict[str, Any]
    validation_report: dict[str, Any]
    coverage_report: dict[str, Any]
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    questions: list[dict[str, Any]] = []


class QuestionSetListResponse(BaseModel):
    """Response containing a list of question sets."""
    question_sets: list[QuestionSetResponse]
    total: int


class GeneratedQuestionResponse(BaseModel):
    """Response for a single generated question."""
    id: int
    question_set_id: int
    question_no: int
    phase: str
    question_text: str
    target_files: list[str]
    target_symbols: list[str]
    quality_score: float
    warnings: list[str]
    created_at: str | None = None
    updated_at: str | None = None
    revision_count: int = 0
