"""
Question Set Generator Service

Generates a complete question set for repository code understanding.
"""

import json
import re
from typing import Any

from app.core.config import settings
from app.core.llm_client import get_llm_provider
from app.prompts import get_prompt_manager
from app.services.repository_analyzer import repository_analyzer


class QuestionSetGenerator:
    """Generates a complete question set for repository code understanding."""

    # Phase definitions with quotas
    PHASE_DEFINITIONS = {
        "Panorama Mapping": {
            "description": "Quickly establish what the project is",
            "min_questions": 2,
            "max_questions": 3,
        },
        "Architecture Understanding": {
            "description": "Understand how the project is organized",
            "min_questions": 2,
            "max_questions": 4,
        },
        "Code Detail Completion": {
            "description": "Understand how the current implementation works",
            "min_ratio": 0.85,  # 85% of total questions
        },
        "Use Cases & Scenarios": {
            "description": "Connect code understanding to real usage",
            "min_questions": 1,
            "max_questions": 2,
        },
    }

    def __init__(self):
        self.prompt_manager = get_prompt_manager()
        self.llm_provider = get_llm_provider()

    def generate_question_set(
        self,
        repository_url: str,
        total_questions: int = 40,
        code_detail_ratio: float = 0.85,
        min_core_file_coverage: float = 0.90,
        ref: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a complete question set for a repository.
        
        Args:
            repository_url: URL of the repository
            total_questions: Total number of questions to generate
            code_detail_ratio: Minimum ratio of code detail questions
            min_core_file_coverage: Minimum core file coverage ratio
            ref: Optional git ref (branch, tag, commit)
            
        Returns:
            Dictionary containing generated questions and metadata
        """
        # Step 1: Analyze repository
        analysis = repository_analyzer.analyze_repository(repository_url, ref)
        
        # Step 2: Plan question distribution
        question_plan = self._plan_question_distribution(
            total_questions, code_detail_ratio, analysis
        )
        
        # Step 3: Generate questions for each phase
        questions = []
        for phase, phase_config in question_plan.items():
            phase_questions = self._generate_phase_questions(
                phase, phase_config, analysis
            )
            questions.extend(phase_questions)
        
        # Step 4: Validate and repair
        validation_result = self._validate_and_repair(
            questions, analysis, total_questions, code_detail_ratio, min_core_file_coverage
        )
        
        # Step 5: Generate coverage report
        coverage_report = self._generate_coverage_report(
            questions, analysis, min_core_file_coverage
        )
        
        return {
            "questions": questions,
            "validation_report": validation_result,
            "coverage_report": coverage_report,
            "repository_analysis": analysis,
        }

    def _plan_question_distribution(
        self,
        total_questions: int,
        code_detail_ratio: float,
        analysis: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Plan how questions should be distributed across phases."""
        plan = {}
        
        # Calculate code detail questions
        code_detail_count = int(total_questions * code_detail_ratio)
        remaining = total_questions - code_detail_count
        
        # Distribute remaining questions to other phases
        panorama_count = min(2, remaining // 3)
        architecture_count = min(3, remaining // 3)
        use_cases_count = remaining - panorama_count - architecture_count
        
        # Ensure minimums
        panorama_count = max(2, panorama_count)
        architecture_count = max(2, architecture_count)
        use_cases_count = max(1, use_cases_count)
        
        # Adjust if needed
        total_allocated = panorama_count + architecture_count + code_detail_count + use_cases_count
        if total_allocated > total_questions:
            # Reduce use_cases first
            use_cases_count = max(1, use_cases_count - (total_allocated - total_questions))
        
        plan["Panorama Mapping"] = {
            "count": panorama_count,
            "description": self.PHASE_DEFINITIONS["Panorama Mapping"]["description"],
        }
        
        plan["Architecture Understanding"] = {
            "count": architecture_count,
            "description": self.PHASE_DEFINITIONS["Architecture Understanding"]["description"],
        }
        
        plan["Code Detail Completion"] = {
            "count": code_detail_count,
            "description": self.PHASE_DEFINITIONS["Code Detail Completion"]["description"],
            "core_files": analysis.get("core_files", []),
        }
        
        plan["Use Cases & Scenarios"] = {
            "count": use_cases_count,
            "description": self.PHASE_DEFINITIONS["Use Cases & Scenarios"]["description"],
        }
        
        return plan

    def _generate_phase_questions(
        self,
        phase: str,
        phase_config: dict[str, Any],
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate questions for a specific phase."""
        if phase == "Code Detail Completion":
            return self._generate_code_detail_questions(phase_config, analysis)
        else:
            return self._generate_generic_phase_questions(phase, phase_config, analysis)

    def _generate_code_detail_questions(
        self,
        phase_config: dict[str, Any],
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate code detail questions targeting core files."""
        questions = []
        core_files = phase_config.get("core_files", [])
        target_count = phase_config.get("count", 34)
        
        # Group files by importance
        high_importance = [f for f in core_files if f.get("importance", 0) > 0.7]
        medium_importance = [f for f in core_files if 0.5 < f.get("importance", 0) <= 0.7]
        low_importance = [f for f in core_files if f.get("importance", 0) <= 0.5]
        
        # Allocate questions proportionally
        high_count = min(len(high_importance), target_count // 2)
        medium_count = min(len(medium_importance), target_count // 3)
        low_count = target_count - high_count - medium_count
        
        # Generate questions for high importance files
        for i, file_info in enumerate(high_importance[:high_count]):
            question = self._generate_file_specific_question(file_info, analysis, "high")
            if question:
                questions.append(question)
        
        # Generate questions for medium importance files
        for i, file_info in enumerate(medium_importance[:medium_count]):
            question = self._generate_file_specific_question(file_info, analysis, "medium")
            if question:
                questions.append(question)
        
        # Generate questions for low importance files
        for i, file_info in enumerate(low_importance[:low_count]):
            question = self._generate_file_specific_question(file_info, analysis, "low")
            if question:
                questions.append(question)
        
        return questions

    def _generate_file_specific_question(
        self,
        file_info: dict[str, Any],
        analysis: dict[str, Any],
        importance_level: str,
    ) -> dict[str, Any] | None:
        """Generate a specific question for a file."""
        file_path = file_info.get("path", "")
        language = file_info.get("language", "")
        
        # Find classes and functions in this file
        classes = [c for c in analysis.get("core_classes", []) if c.get("file") == file_path]
        functions = [f for f in analysis.get("core_functions", []) if f.get("file") == file_path]
        
        # Build context for LLM
        context = {
            "file_path": file_path,
            "language": language,
            "importance_level": importance_level,
            "classes": [c.get("name") for c in classes[:5]],  # Limit to 5
            "functions": [f.get("name") for f in functions[:10]],  # Limit to 10
            "frameworks": analysis.get("frameworks", []),
        }
        
        # Generate question using LLM
        try:
            prompt = self.prompt_manager.render(
                "generate_code_detail_question",
                {
                    "file_path": file_path,
                    "language": language,
                    "classes": ", ".join(context["classes"]) if context["classes"] else "none",
                    "functions": ", ".join(context["functions"]) if context["functions"] else "none",
                    "frameworks": ", ".join(context["frameworks"]) if context["frameworks"] else "none",
                    "importance_level": importance_level,
                }
            )
            
            response = self.llm_provider.generate_text(
                messages=prompt.messages,
                model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
                temperature=0.3,
            )
            
            # Parse response
            question_text = self._extract_question_from_response(response.text)
            
            return {
                "phase": "Code Detail Completion",
                "question_text": question_text,
                "target_files": [file_path],
                "target_symbols": context["classes"] + context["functions"],
                "importance_level": importance_level,
            }
            
        except Exception as e:
            # Fallback to template-based question
            return self._generate_template_question(file_info, context)

    def _generate_template_question(
        self,
        file_info: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a template-based question as fallback."""
        file_path = context["file_path"]
        classes = context["classes"]
        functions = context["functions"]
        
        if classes:
            question_text = f"How does the `{classes[0]}` class in `{file_path}` work?"
        elif functions:
            question_text = f"What does the `{functions[0]}` function in `{file_path}` do?"
        else:
            question_text = f"What is the purpose of `{file_path}` and how does it work?"
        
        return {
            "phase": "Code Detail Completion",
            "question_text": question_text,
            "target_files": [file_path],
            "target_symbols": classes + functions,
            "importance_level": context["importance_level"],
        }

    def _generate_generic_phase_questions(
        self,
        phase: str,
        phase_config: dict[str, Any],
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate questions for non-code-detail phases."""
        questions = []
        target_count = phase_config.get("count", 2)
        
        # Build context for LLM
        context = {
            "phase": phase,
            "description": phase_config.get("description", ""),
            "repository_url": analysis.get("repository_url", ""),
            "languages": list(analysis.get("languages", {}).keys()),
            "frameworks": analysis.get("frameworks", []),
            "top_level_structure": [s.get("name") for s in analysis.get("top_level_structure", [])],
            "entrypoints": [e.get("file") for e in analysis.get("entrypoints", [])],
        }
        
        try:
            prompt = self.prompt_manager.render(
                f"generate_{phase.lower().replace(' ', '_')}_questions",
                context
            )
            
            response = self.llm_provider.generate_text(
                messages=prompt.messages,
                model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
                temperature=0.3,
            )
            
            # Parse multiple questions from response
            parsed_questions = self._parse_multiple_questions(response.text, phase)
            questions.extend(parsed_questions[:target_count])
            
        except Exception as e:
            # Fallback to template-based questions
            questions.extend(self._generate_template_phase_questions(phase, context, target_count))
        
        return questions

    def _generate_template_phase_questions(
        self,
        phase: str,
        context: dict[str, Any],
        count: int,
    ) -> list[dict[str, Any]]:
        """Generate template-based questions for a phase."""
        questions = []
        
        if phase == "Panorama Mapping":
            templates = [
                f"What is the purpose of this project and what problem does it solve?",
                f"What are the main modules/components of this project?",
                f"What is the high-level architecture of this project?",
            ]
        elif phase == "Architecture Understanding":
            templates = [
                f"What architectural pattern does this project follow?",
                f"How are the main modules organized and how do they interact?",
                f"What are the key design decisions made in this project?",
            ]
        elif phase == "Use Cases & Scenarios":
            templates = [
                f"What is a typical usage scenario for this project?",
                f"What are the main user workflows in this project?",
            ]
        else:
            templates = []
        
        for i, template in enumerate(templates[:count]):
            questions.append({
                "phase": phase,
                "question_text": template,
                "target_files": [],
                "target_symbols": [],
                "importance_level": "medium",
            })
        
        return questions

    def _extract_question_from_response(self, response: str) -> str:
        """Extract a single question from LLM response."""
        # Try to find a question mark
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if "?" in line:
                # Clean up the question
                question = line.split("?")[0] + "?"
                # Remove markdown formatting
                question = re.sub(r'^[*#\-\d.]+\s*', '', question)
                return question.strip()
        
        # If no question mark found, return the first non-empty line
        for line in lines:
            line = line.strip()
            if line:
                # Remove markdown formatting
                question = re.sub(r'^[*#\-\d.]+\s*', '', line)
                return question.strip()
        
        return response.strip()

    def _parse_multiple_questions(
        self,
        response: str,
        phase: str,
    ) -> list[dict[str, Any]]:
        """Parse multiple questions from LLM response."""
        questions = []
        
        # Split by question marks
        parts = response.split("?")
        
        for part in parts[:-1]:  # Exclude last part (after last ?)
            question_text = part.strip()
            
            # Clean up
            question_text = re.sub(r'^[*#\-\d.]+\s*', '', question_text)
            question_text = question_text.strip()
            
            if question_text:
                questions.append({
                    "phase": phase,
                    "question_text": question_text + "?",
                    "target_files": [],
                    "target_symbols": [],
                    "importance_level": "medium",
                })
        
        return questions

    def _validate_and_repair(
        self,
        questions: list[dict[str, Any]],
        analysis: dict[str, Any],
        total_questions: int,
        code_detail_ratio: float,
        min_core_file_coverage: float,
    ) -> dict[str, Any]:
        """Validate and repair the generated question set."""
        validation_result = {
            "is_valid": True,
            "total_questions": len(questions),
            "code_detail_count": 0,
            "code_detail_ratio": 0.0,
            "core_files_detected": len(analysis.get("core_files", [])),
            "core_files_covered": 0,
            "core_file_coverage": 0.0,
            "phase_counts": {},
            "warnings": [],
            "errors": [],
        }
        
        # Count questions by phase
        phase_counts = {}
        for q in questions:
            phase = q.get("phase", "Unknown")
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        validation_result["phase_counts"] = phase_counts
        
        # Count code detail questions
        code_detail_count = phase_counts.get("Code Detail Completion", 0)
        validation_result["code_detail_count"] = code_detail_count
        
        # Calculate code detail ratio
        if len(questions) > 0:
            code_detail_ratio_actual = code_detail_count / len(questions)
            validation_result["code_detail_ratio"] = code_detail_ratio_actual
            
            if code_detail_ratio_actual < code_detail_ratio:
                validation_result["warnings"].append(
                    f"Code detail ratio ({code_detail_ratio_actual:.2%}) is below target ({code_detail_ratio:.2%})"
                )
        
        # Check total questions
        if len(questions) < total_questions:
            validation_result["warnings"].append(
                f"Total questions ({len(questions)}) is below target ({total_questions})"
            )
        
        # Check core file coverage
        core_files = set(f.get("path") for f in analysis.get("core_files", []))
        covered_files = set()
        for q in questions:
            covered_files.update(q.get("target_files", []))
        
        validation_result["core_files_covered"] = len(covered_files & core_files)
        
        if core_files:
            coverage = len(covered_files & core_files) / len(core_files)
            validation_result["core_file_coverage"] = coverage
            
            if coverage < min_core_file_coverage:
                validation_result["warnings"].append(
                    f"Core file coverage ({coverage:.2%}) is below target ({min_core_file_coverage:.2%})"
                )
        
        # Check for duplicates
        duplicates = self._find_duplicates(questions)
        if duplicates:
            validation_result["warnings"].append(f"Found {len(duplicates)} potential duplicate questions")
        
        # Check for modification-oriented questions
        modification_questions = self._find_modification_questions(questions)
        if modification_questions:
            validation_result["warnings"].append(
                f"Found {len(modification_questions)} questions that ask for modifications"
            )
        
        # Set overall validity
        if validation_result["errors"]:
            validation_result["is_valid"] = False
        
        return validation_result

    def _find_duplicates(self, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find duplicate or near-duplicate questions."""
        duplicates = []
        
        # Normalize questions for comparison
        normalized = []
        for q in questions:
            text = q.get("question_text", "").lower()
            # Remove common prefixes
            text = re.sub(r'^(how|what|why|when|where|which|who)\s+', '', text)
            # Remove punctuation
            text = re.sub(r'[^\w\s]', '', text)
            normalized.append(text)
        
        # Compare each pair
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                similarity = self._calculate_similarity(normalized[i], normalized[j])
                if similarity > 0.8:  # 80% similarity threshold
                    duplicates.append({
                        "question1_index": i,
                        "question2_index": j,
                        "similarity": similarity,
                    })
        
        return duplicates

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        # Simple word overlap similarity (Jaccard + containment)
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        jaccard = len(intersection) / len(union)
        # Also check containment: if one is mostly contained in the other
        containment = len(intersection) / min(len(words1), len(words2)) if min(len(words1), len(words2)) > 0 else 0.0
        
        return max(jaccard, containment)

    def _find_modification_questions(self, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find questions that ask for modifications."""
        modification_patterns = [
            r'how should .* be (changed|modified|improved|refactored)',
            r'what files need (to be )?(changed|modified|updated)',
            r'how would you (refactor|improve|change)',
            r'what (improvement|change|modification)',
            r'how to (improve|optimize|enhance)',
        ]
        
        modification_questions = []
        
        for q in questions:
            text = q.get("question_text", "").lower()
            for pattern in modification_patterns:
                if re.search(pattern, text):
                    modification_questions.append(q)
                    break
        
        return modification_questions

    def _generate_coverage_report(
        self,
        questions: list[dict[str, Any]],
        analysis: dict[str, Any],
        min_core_file_coverage: float,
    ) -> dict[str, Any]:
        """Generate a coverage report."""
        core_files = analysis.get("core_files", [])
        
        # Track coverage
        file_importance = {}
        for f in core_files:
            file_importance[f.get("path")] = f.get("importance", 0.0)
        
        covered_files = set()
        for q in questions:
            covered_files.update(q.get("target_files", []))
        
        core_file_paths = set(f.get("path") for f in core_files)
        covered_core_files = covered_files & core_file_paths
        uncovered_core_files = core_file_paths - covered_files
        
        coverage_percentage = len(covered_core_files) / len(core_file_paths) if core_file_paths else 0.0
        
        return {
            "total_core_files": len(core_file_paths),
            "covered_core_files": len(covered_core_files),
            "coverage_percentage": coverage_percentage,
            "uncovered_files": list(uncovered_core_files),
            "file_importance": file_importance,
            "meets_target": coverage_percentage >= min_core_file_coverage,
        }


# Singleton instance
question_set_generator = QuestionSetGenerator()
