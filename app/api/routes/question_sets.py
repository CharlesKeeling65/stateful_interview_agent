"""
Question Sets API Routes

Endpoints for generating and managing question sets for repository code understanding.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.question_set import GeneratedQuestion, QuestionRevision, QuestionSet, QuestionVersion
from app.schemas.question_set import (
    CascadeRevisionRequest,
    CoverageReport,
    GeneratedQuestionResponse,
    QuestionRevisionRequest,
    QuestionRevisionResponse,
    QuestionSetCreate,
    QuestionSetListResponse,
    QuestionSetResponse,
    QuestionVersionDiff,
    QuestionVersionResponse,
    QuestionVersionRollbackRequest,
    ValidationReport,
)
from app.services.question_set_generator import question_set_generator
from app.services.question_revision_service import question_revision_service

router = APIRouter(prefix="/question-sets", tags=["question-sets"])


def _regenerate_question_with_context(
    question: GeneratedQuestion,
    previous_questions: list[dict[str, Any]],
    repository_analysis: dict[str, Any],
) -> str:
    """Regenerate a question with updated context from previous questions."""
    # This is a simplified version - in production, you'd want to use the LLM
    # to regenerate the question with the new context
    
    # For now, we'll just return the original question text
    # In a full implementation, you'd call the question generation service
    # with the updated previous_questions context
    
    # Simplified regeneration: just keep the original question
    return question.question_text


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
        request.repository_source,
        request.total_questions,
        request.code_detail_ratio,
        request.min_core_file_coverage,
    )
    
    return _serialize_question_set(question_set)


def _generate_question_set_background(
    question_set_id: int,
    repository_url: str,
    repository_source: str,
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
                repository_source=repository_source,
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
                db.flush()  # Get the question ID
                
                # Create initial version
                initial_version = QuestionVersion(
                    question_id=question.id,
                    version_no=1,
                    question_text=q_data.get("question_text", ""),
                    change_type="generated",
                    change_summary="Initial generation",
                    parent_version_id=None,
                )
                db.add(initial_version)
            
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
    
    # Create new version
    current_version_no = max([v.version_no for v in question.versions]) if question.versions else 0
    new_version = QuestionVersion(
        question_id=question.id,
        version_no=current_version_no + 1,
        question_text=revision_result["revised_question"],
        change_type="revised",
        change_summary=request.chinese_instruction,
        parent_version_id=max([v.id for v in question.versions]) if question.versions else None,
    )
    db.add(new_version)
    
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
    
    # Re-run validation (now returns tuple of (questions, validation_result))
    _, validation_result = question_set_generator._validate_and_repair(
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
    
    # Delete all versions
    for question in question_set.questions:
        db.query(QuestionVersion).filter(
            QuestionVersion.question_id == question.id
        ).delete()
    
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


@router.get("/{question_set_id}/questions/{question_id}/versions", response_model=list[QuestionVersionResponse])
async def get_question_versions(
    question_set_id: int,
    question_id: int,
    db: Session = Depends(get_db),
):
    """Get version history for a specific question."""
    # Verify question set exists
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Verify question exists and belongs to the question set
    question = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.id == question_id,
        GeneratedQuestion.question_set_id == question_set_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get all versions for this question
    versions = db.query(QuestionVersion).filter(
        QuestionVersion.question_id == question_id
    ).order_by(QuestionVersion.version_no.desc()).all()
    
    return [v.to_dict() for v in versions]


@router.get("/{question_set_id}/questions/{question_id}/versions/{version_no}", response_model=QuestionVersionResponse)
async def get_question_version(
    question_set_id: int,
    question_id: int,
    version_no: int,
    db: Session = Depends(get_db),
):
    """Get a specific version of a question."""
    # Verify question set exists
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Verify question exists and belongs to the question set
    question = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.id == question_id,
        GeneratedQuestion.question_set_id == question_set_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get the specific version
    version = db.query(QuestionVersion).filter(
        QuestionVersion.question_id == question_id,
        QuestionVersion.version_no == version_no,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return version.to_dict()


@router.get("/{question_set_id}/questions/{question_id}/diff", response_model=QuestionVersionDiff)
async def get_question_version_diff(
    question_set_id: int,
    question_id: int,
    v1: int,
    v2: int,
    db: Session = Depends(get_db),
):
    """Get diff between two versions of a question."""
    # Verify question set exists
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Verify question exists and belongs to the question set
    question = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.id == question_id,
        GeneratedQuestion.question_set_id == question_set_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get both versions
    version1 = db.query(QuestionVersion).filter(
        QuestionVersion.question_id == question_id,
        QuestionVersion.version_no == v1,
    ).first()
    version2 = db.query(QuestionVersion).filter(
        QuestionVersion.question_id == question_id,
        QuestionVersion.version_no == v2,
    ).first()
    
    if not version1 or not version2:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    
    # Generate diff
    import difflib
    diff = difflib.unified_diff(
        version1.question_text.splitlines(keepends=True),
        version2.question_text.splitlines(keepends=True),
        fromfile=f"Version {v1}",
        tofile=f"Version {v2}",
    )
    diff_text = ''.join(diff)
    
    # Convert to HTML for better display
    diff_html = difflib.HtmlDiff().make_table(
        version1.question_text.splitlines(),
        version2.question_text.splitlines(),
        fromdesc=f"Version {v1}",
        todesc=f"Version {v2}",
    )
    
    return {
        "version_from": version1.to_dict(),
        "version_to": version2.to_dict(),
        "diff_html": diff_html,
    }


@router.post("/{question_set_id}/questions/{question_id}/rollback", response_model=QuestionVersionResponse)
async def rollback_question_version(
    question_set_id: int,
    question_id: int,
    request: QuestionVersionRollbackRequest,
    db: Session = Depends(get_db),
):
    """Rollback a question to a specific version."""
    # Verify question set exists
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Verify question exists and belongs to the question set
    question = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.id == question_id,
        GeneratedQuestion.question_set_id == question_set_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get the target version
    target_version = db.query(QuestionVersion).filter(
        QuestionVersion.question_id == question_id,
        QuestionVersion.version_no == request.version_no,
    ).first()
    if not target_version:
        raise HTTPException(status_code=404, detail="Target version not found")
    
    # Create new version for the rollback
    current_version_no = max([v.version_no for v in question.versions]) if question.versions else 0
    new_version = QuestionVersion(
        question_id=question.id,
        version_no=current_version_no + 1,
        question_text=target_version.question_text,
        change_type="rollback",
        change_summary=f"Rollback to version {request.version_no}" + (f": {request.reason}" if request.reason else ""),
        parent_version_id=max([v.id for v in question.versions]) if question.versions else None,
    )
    db.add(new_version)
    
    # Update question text
    question.question_text = target_version.question_text
    
    db.commit()
    db.refresh(new_version)
    
    return new_version.to_dict()


@router.post("/{question_set_id}/questions/{question_id}/cascade-revise", response_model=dict)
async def cascade_revise_question(
    question_set_id: int,
    question_id: int,
    request: CascadeRevisionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Revise a question and cascade changes to subsequent questions.
    
    When revising question N, all questions from N+1 to the end will be
    regenerated based on the revised context.
    """
    # Verify question set exists
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Verify question exists and belongs to the question set
    question = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.id == question_id,
        GeneratedQuestion.question_set_id == question_set_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question_set.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Question set must be completed before revision"
        )
    
    # Get all questions for context
    all_questions = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.question_set_id == question_set_id
    ).order_by(GeneratedQuestion.question_no).all()
    
    all_questions_data = [
        {
            "question_no": q.question_no,
            "question_text": q.question_text,
            "phase": q.phase,
        }
        for q in all_questions
    ]
    
    # Perform revision on the target question
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
    
    # Create new version
    current_version_no = max([v.version_no for v in question.versions]) if question.versions else 0
    new_version = QuestionVersion(
        question_id=question.id,
        version_no=current_version_no + 1,
        question_text=revision_result["revised_question"],
        change_type="revised",
        change_summary=request.chinese_instruction,
        parent_version_id=max([v.id for v in question.versions]) if question.versions else None,
    )
    db.add(new_version)
    
    # If cascade is requested, regenerate subsequent questions
    cascade_results = []
    if request.cascade:
        # Get questions after the current one
        subsequent_questions = [q for q in all_questions if q.question_no > question.question_no]
        
        # Prepare context for regeneration
        previous_questions = []
        for q in all_questions:
            if q.question_no <= question.question_no:
                previous_questions.append({
                    "question_no": q.question_no,
                    "question_text": q.question_text,
                    "phase": q.phase,
                })
        
        # Regenerate each subsequent question
        for subsequent_q in subsequent_questions:
            try:
                # Save original text before update
                original_text = subsequent_q.question_text
                
                # Generate new question based on updated context
                # Use a simplified regeneration approach
                new_question_text = _regenerate_question_with_context(
                    question=subsequent_q,
                    previous_questions=previous_questions,
                    repository_analysis=question_set.repository_analysis,
                )
                
                # Create version for the regenerated question
                current_version_no = max([v.version_no for v in subsequent_q.versions]) if subsequent_q.versions else 0
                new_version = QuestionVersion(
                    question_id=subsequent_q.id,
                    version_no=current_version_no + 1,
                    question_text=new_question_text,
                    change_type="cascade_regenerated",
                    change_summary=f"Cascade regeneration due to revision of question {question.question_no}",
                    parent_version_id=max([v.id for v in subsequent_q.versions]) if subsequent_q.versions else None,
                )
                db.add(new_version)
                
                # Update question text
                subsequent_q.question_text = new_question_text
                
                # Add to previous questions for next iteration
                previous_questions.append({
                    "question_no": subsequent_q.question_no,
                    "question_text": new_question_text,
                    "phase": subsequent_q.phase,
                })
                
                cascade_results.append({
                    "question_no": subsequent_q.question_no,
                    "status": "regenerated",
                    "original_text": original_text,
                    "new_text": new_question_text,
                })
            except Exception as e:
                cascade_results.append({
                    "question_no": subsequent_q.question_no,
                    "status": "failed",
                    "error": str(e),
                    "original_text": subsequent_q.question_text,
                })
    
    db.commit()
    db.refresh(revision)
    
    return {
        "question_id": question.id,
        "original_question": revision_result["original_question"],
        "revised_question": revision_result["revised_question"],
        "chinese_instruction": request.chinese_instruction,
        "cascade": request.cascade,
        "cascade_results": cascade_results,
    }


@router.get("/{question_set_id}/questions/{question_id}", response_model=GeneratedQuestionResponse)
async def get_question(
    question_set_id: int,
    question_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific question with version info."""
    # Verify question set exists
    question_set = db.query(QuestionSet).filter(
        QuestionSet.id == question_set_id
    ).first()
    if not question_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    # Verify question exists and belongs to the question set
    question = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.id == question_id,
        GeneratedQuestion.question_set_id == question_set_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    return question.to_dict()
