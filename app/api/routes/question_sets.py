"""
Question Sets API Routes

Endpoints for generating and managing question sets for repository code understanding.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.question_set import GeneratedQuestion, QuestionRevision, QuestionSet
from app.schemas.question_set import (
    CoverageReport,
    GeneratedQuestionResponse,
    QuestionRevisionRequest,
    QuestionRevisionResponse,
    QuestionSetCreate,
    QuestionSetListResponse,
    QuestionSetResponse,
    ValidationReport,
)
from app.services.question_set_generator import question_set_generator
from app.services.question_revision_service import question_revision_service

router = APIRouter(prefix="/question-sets", tags=["question-sets"])


def _serialize_question_set(question_set: QuestionSet) -> dict[str, Any]:
    """Serialize a QuestionSet to a dictionary."""
    return question_set.to_dict()


def _serialize_question(question: GeneratedQuestion) -> dict[str, Any]:
    """Serialize a GeneratedQuestion to a dictionary."""
    return question.to_dict()


@router.post("", response_model=QuestionSetResponse, status_code=201)
async def create_question_set(
    request: QuestionSetCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new question set generation task.
    
    The generation will run in the background. Poll the status endpoint to check progress.
    """
    # Create question set record
    question_set = QuestionSet(
        repository_url=request.repository_url,
        status="pending",
        total_questions=request.total_questions,
        code_detail_ratio=request.code_detail_ratio,
        min_core_file_coverage=request.min_core_file_coverage,
    )
    db.add(question_set)
    db.commit()
    db.refresh(question_set)
    
    # Start background generation task
    background_tasks.add_task(
        _generate_question_set_background,
        question_set.id,
        request.repository_url,
        request.total_questions,
        request.code_detail_ratio,
        request.min_core_file_coverage,
    )
    
    return _serialize_question_set(question_set)


def _generate_question_set_background(
    question_set_id: int,
    repository_url: str,
    total_questions: int,
    code_detail_ratio: float,
    min_core_file_coverage: float,
):
    """Background task to generate question set."""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Get question set record
        question_set = db.query(QuestionSet).filter(QuestionSet.id == question_set_id).first()
        if not question_set:
            return
        
        # Update status to analyzing
        question_set.status = "analyzing"
        db.commit()
        
        try:
            # Generate question set
            result = question_set_generator.generate_question_set(
                repository_url=repository_url,
                total_questions=total_questions,
                code_detail_ratio=code_detail_ratio,
                min_core_file_coverage=min_core_file_coverage,
            )
            
            # Update status to generating
            question_set.status = "generating"
            db.commit()
            
            # Save questions
            for i, q_data in enumerate(result.get("questions", [])):
                question = GeneratedQuestion(
                    question_set_id=question_set.id,
                    question_no=i + 1,
                    phase=q_data.get("phase", "Unknown"),
                    question_text=q_data.get("question_text", ""),
                    target_files_json=json.dumps(q_data.get("target_files", [])),
                    target_symbols_json=json.dumps(q_data.get("target_symbols", [])),
                    quality_score=q_data.get("quality_score", 0.0),
                    warnings_json=json.dumps(q_data.get("warnings", [])),
                )
                db.add(question)
            
            # Update status to validating
            question_set.status = "validating"
            db.commit()
            
            # Save validation and coverage reports
            question_set.validation_report_json = json.dumps(
                result.get("validation_report", {})
            )
            question_set.coverage_report_json = json.dumps(
                result.get("coverage_report", {})
            )
            question_set.repository_analysis_json = json.dumps(
                result.get("repository_analysis", {})
            )
            
            # Update status to completed
            question_set.status = "completed"
            db.commit()
            
        except Exception as e:
            # Update status to failed
            question_set.status = "failed"
            question_set.error_message = str(e)
            db.commit()
            
    finally:
        db.close()


@router.get("", response_model=QuestionSetListResponse)
async def list_question_sets(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all question sets."""
    question_sets = db.query(QuestionSet).order_by(
        QuestionSet.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    total = db.query(QuestionSet).count()
    
    return {
        "question_sets": [_serialize_question_set(qs) for qs in question_sets],
        "total": total,
    }


@router.get("/{question_set_id}", response_model=QuestionSetResponse)
async def get_question_set(
    question_set_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific question set with all questions."""
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    return _serialize_question_set(question_set)


@router.get("/{question_set_id}/questions", response_model=list[GeneratedQuestionResponse])
async def get_question_set_questions(
    question_set_id: int,
    db: Session = Depends(get_db),
):
    """Get all questions for a question set."""
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    questions = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.question_set_id == question_set_id
    ).order_by(GeneratedQuestion.question_no).all()
    
    return [_serialize_question(q) for q in questions]


@router.post("/{question_set_id}/revise", response_model=QuestionRevisionResponse)
async def revise_question(
    question_set_id: int,
    request: QuestionRevisionRequest,
    db: Session = Depends(get_db),
):
    """
    Revise a question using Chinese instructions.
    
    The revised question will be validated for:
    - English language
    - Phase constraints
    - Duplicate detection
    - Coverage impact
    """
    # Get question set
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Get the question to revise (check existence first)
    question = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.id == request.question_id,
        GeneratedQuestion.question_set_id == question_set_id,
    ).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question_set.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Question set must be completed before revision"
        )
    
    # Get all questions for duplicate checking
    all_questions = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.question_set_id == question_set_id
    ).all()
    
    all_questions_data = [
        {
            "question_no": q.question_no,
            "question_text": q.question_text,
            "phase": q.phase,
        }
        for q in all_questions
    ]
    
    # Perform revision
    revision_result = question_revision_service.revise_question(
        question_text=question.question_text,
        chinese_instruction=request.chinese_instruction,
        phase=question.phase,
        target_files=question.target_files,
        target_symbols=question.target_symbols,
        all_questions=all_questions_data,
    )
    
    # Save revision
    revision = QuestionRevision(
        question_set_id=question_set_id,
        question_id=question.id,
        chinese_instruction=request.chinese_instruction,
        original_question_text=question.question_text,
        revised_question_text=revision_result["revised_question"],
        validation_result_json=json.dumps(revision_result["validation_result"]),
    )
    db.add(revision)
    
    # Update question with revised text
    question.question_text = revision_result["revised_question"]
    question.warnings_json = json.dumps(revision_result.get("warnings", []))
    
    # Update target files if changed
    if revision_result.get("coverage_changed"):
        # Extract new target files from revised question
        new_target_files = question_revision_service._extract_target_files(
            revision_result["revised_question"],
            question.target_files,
        )
        question.target_files_json = json.dumps(new_target_files)
    
    db.commit()
    db.refresh(revision)
    
    return {
        "question_id": question.id,
        "original_question": revision_result["original_question"],
        "revised_question": revision_result["revised_question"],
        "chinese_instruction": request.chinese_instruction,
        "phase_changed": revision_result.get("phase_changed", False),
        "new_phase": revision_result.get("new_phase"),
        "coverage_changed": revision_result.get("coverage_changed", False),
        "duplicate_check_passed": revision_result.get("duplicate_check_passed", True),
        "validation_result": revision_result["validation_result"],
        "warnings": revision_result.get("warnings", []),
    }


@router.post("/{question_set_id}/validate", response_model=ValidationReport)
async def validate_question_set(
    question_set_id: int,
    db: Session = Depends(get_db),
):
    """
    Re-run validation on a question set.
    
    This will check:
    - Total question count
    - Code detail ratio
    - Core file coverage
    - Duplicate detection
    - Modification-oriented questions
    """
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Get all questions
    questions = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.question_set_id == question_set_id
    ).all()
    
    questions_data = [
        {
            "question_text": q.question_text,
            "phase": q.phase,
            "target_files": q.target_files,
        }
        for q in questions
    ]
    
    # Get repository analysis
    repository_analysis = question_set.repository_analysis
    
    # Re-run validation
    validation_result = question_set_generator._validate_and_repair(
        questions_data,
        repository_analysis,
        question_set.total_questions,
        question_set.code_detail_ratio,
        question_set.min_core_file_coverage,
    )
    
    # Update question set
    question_set.validation_report_json = json.dumps(validation_result)
    db.commit()
    
    return validation_result


@router.get("/{question_set_id}/coverage", response_model=CoverageReport)
async def get_coverage_report(
    question_set_id: int,
    db: Session = Depends(get_db),
):
    """Get the coverage report for a question set."""
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    report = question_set.coverage_report
    # Return default empty report if not yet generated
    if not report:
        return {
            "total_core_files": 0,
            "covered_core_files": 0,
            "coverage_percentage": 0.0,
            "uncovered_files": [],
            "file_importance": {},
        }
    return report


@router.delete("/{question_set_id}", status_code=204)
async def delete_question_set(
    question_set_id: int,
    db: Session = Depends(get_db),
):
    """Delete a question set and all associated questions and revisions."""
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Delete all revisions
    db.query(QuestionRevision).filter(
        QuestionRevision.question_set_id == question_set_id
    ).delete()
    
    # Delete all questions
    db.query(GeneratedQuestion).filter(
        GeneratedQuestion.question_set_id == question_set_id
    ).delete()
    
    # Delete question set
    db.delete(question_set)
    db.commit()
    
    return None
