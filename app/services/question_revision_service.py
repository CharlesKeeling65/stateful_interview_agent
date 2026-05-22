"""
Question Revision Service

Handles revision of questions based on Chinese instructions.
"""

import json
import re
from typing import Any

from app.core.config import settings
from app.core.llm_client import get_llm_provider
from app.prompts import get_prompt_manager


class QuestionRevisionService:
    """Handles revision of questions based on Chinese instructions."""

    def __init__(self):
        self.prompt_manager = get_prompt_manager()
        self.llm_provider = get_llm_provider()

    def revise_question(
        self,
        question_text: str,
        chinese_instruction: str,
        phase: str,
        target_files: list[str],
        target_symbols: list[str],
        all_questions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Revise a question based on Chinese instructions.
        
        Args:
            question_text: Original question text
            chinese_instruction: Chinese instruction for revision
            phase: Current phase of the question
            target_files: Current target files
            target_symbols: Current target symbols
            all_questions: All questions in the set (for duplicate checking)
            
        Returns:
            Dictionary containing revision result
        """
        # Generate revised question
        revised_question = self._generate_revised_question(
            question_text, chinese_instruction, phase, target_files, target_symbols
        )
        
        # Validate revision
        validation_result = self._validate_revision(
            question_text, revised_question, phase, target_files, target_symbols, all_questions
        )
        
        return {
            "original_question": question_text,
            "revised_question": revised_question,
            "chinese_instruction": chinese_instruction,
            "phase_changed": validation_result.get("phase_changed", False),
            "new_phase": validation_result.get("new_phase"),
            "coverage_changed": validation_result.get("coverage_changed", False),
            "duplicate_check_passed": validation_result.get("duplicate_check_passed", True),
            "validation_result": validation_result,
            "warnings": validation_result.get("warnings", []),
        }

    def _generate_revised_question(
        self,
        original_question: str,
        chinese_instruction: str,
        phase: str,
        target_files: list[str],
        target_symbols: list[str],
    ) -> str:
        """Generate revised question using LLM."""
        try:
            prompt = self.prompt_manager.render(
                "revise_question_with_chinese_instruction",
                {
                    "original_question": original_question,
                    "chinese_instruction": chinese_instruction,
                    "phase": phase,
                    "target_files": ", ".join(target_files) if target_files else "none",
                    "target_symbols": ", ".join(target_symbols) if target_symbols else "none",
                }
            )
            
            response = self.llm_provider.generate_text(
                messages=prompt.messages,
                model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
                temperature=0.3,
            )
            
            # Extract question from response
            revised_question = self._extract_question_from_response(response.text)
            
            # Ensure exactly one question
            revised_question = self._ensure_single_question(revised_question)
            
            return revised_question
            
        except Exception as e:
            # Fallback: apply simple transformations based on Chinese instruction
            return self._apply_chinese_instruction_fallback(
                original_question, chinese_instruction
            )

    def _apply_chinese_instruction_fallback(
        self,
        original_question: str,
        chinese_instruction: str,
    ) -> str:
        """Apply Chinese instruction using simple heuristics."""
        instruction_lower = chinese_instruction.lower()
        
        # Common instruction patterns
        if "太泛" in chinese_instruction or "太宽泛" in chinese_instruction:
            # Make more specific
            if "?" in original_question:
                return original_question.replace("?", " in the current implementation?")
            return original_question
        
        if "具体" in chinese_instruction or "更具体" in chinese_instruction:
            # Add specificity
            if "?" in original_question:
                return original_question.replace("?", " specifically?")
            return original_question
        
        if "改成" in chinese_instruction or "改为" in chinese_instruction:
            # Extract the new focus from instruction
            # This is a simplified version
            return original_question
        
        # Default: return original with minor modification
        return original_question

    def _extract_question_from_response(self, response: str) -> str:
        """Extract a single question from LLM response.
        
        CRITICAL: This method ensures exactly ONE question is extracted.
        If the response contains multiple questions, only the first one is returned.
        """
        # Try to find the first question mark
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if "?" in line:
                # Extract only the first question (up to the first question mark)
                question_part = line.split("?")[0] + "?"
                # Remove markdown formatting
                question_part = re.sub(r'^[*#\-\d.]+\s*', '', question_part)
                question_part = question_part.strip()
                
                # Additional cleaning: remove any trailing content after the question mark
                # that might be part of another question
                if question_part:
                    return question_part
        
        # If no question mark found, return the first non-empty line
        for line in lines:
            line = line.strip()
            if line:
                # Remove markdown formatting
                question = re.sub(r'^[*#\-\d.]+\s*', '', line)
                return question.strip()
        
        return response.strip()
    
    def _ensure_single_question(self, question_text: str) -> str:
        """Ensure the question text contains exactly one question.
        
        If multiple questions are detected, extract only the first one.
        Also validates that the question is a single sentence.
        """
        # Split by question marks to detect multiple questions
        parts = question_text.split("?")
        
        if len(parts) > 2:  # More than one question mark
            # Extract only the first question
            first_question = parts[0].strip() + "?"
            # Clean up any leading/trailing whitespace or formatting
            first_question = re.sub(r'^[*#\-\d.]+\s*', '', first_question)
            return first_question.strip()
        
        # Check for multiple sentences that might be separate questions
        # Look for patterns like "How does X work? What about Y?"
        sentences = re.split(r'[.!?]+', question_text)
        if len(sentences) > 2:  # More than one sentence
            # Take only the first sentence that looks like a question
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and any(sentence.lower().startswith(q) for q in ['how', 'what', 'why', 'when', 'where', 'which', 'who']):
                    # Add question mark if missing
                    if not sentence.endswith('?'):
                        sentence += '?'
                    return sentence
        
        # If it's a single question, ensure it ends with a question mark
        if not question_text.strip().endswith('?'):
            question_text = question_text.strip() + '?'
        
        return question_text

    def _validate_revision(
        self,
        original_question: str,
        revised_question: str,
        phase: str,
        target_files: list[str],
        target_symbols: list[str],
        all_questions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate the revised question."""
        validation_result = {
            "is_valid": True,
            "phase_changed": False,
            "new_phase": None,
            "coverage_changed": False,
            "duplicate_check_passed": True,
            "warnings": [],
            "errors": [],
        }
        
        # Check if question is in English
        if not self._is_english(revised_question):
            validation_result["warnings"].append("Revised question is not in English")
        
        # Check for modification-oriented language
        if self._is_modification_oriented(revised_question):
            validation_result["warnings"].append(
                "Revised question asks for modifications rather than understanding"
            )
        
        # Check for duplicates
        duplicate = self._check_duplicate(revised_question, all_questions, original_question)
        if duplicate:
            validation_result["duplicate_check_passed"] = False
            validation_result["warnings"].append(
                f"Revised question is similar to question {duplicate.get('question_no')}"
            )
        
        # Check phase fit
        phase_fit = self._check_phase_fit(revised_question, phase)
        if not phase_fit:
            validation_result["warnings"].append(
                f"Revised question may not fit the {phase} phase"
            )
        
        # Check if target files are still relevant
        new_target_files = self._extract_target_files(revised_question, target_files)
        if set(new_target_files) != set(target_files):
            validation_result["coverage_changed"] = True
        
        return validation_result

    def _is_english(self, text: str) -> bool:
        """Check if text is primarily in English."""
        # Count ASCII characters vs non-ASCII
        ascii_count = sum(1 for c in text if ord(c) < 128)
        total_count = len(text)
        
        if total_count == 0:
            return True
        
        # Consider it English if > 80% ASCII
        return ascii_count / total_count > 0.8

    def _is_modification_oriented(self, question: str) -> bool:
        """Check if question asks for modifications."""
        modification_patterns = [
            r'how should .* be (changed|modified|improved|refactored)',
            r'what files need (to be )?(changed|modified|updated)',
            r'how would you (refactor|improve|change)',
            r'what (improvement|change|modification)',
            r'how to (improve|optimize|enhance)',
            r'what test.* should be (added|written|updated)',
            r'how should .* be (implemented|built|created)',
        ]
        
        question_lower = question.lower()
        for pattern in modification_patterns:
            if re.search(pattern, question_lower):
                return True
        
        return False

    def _check_duplicate(
        self,
        new_question: str,
        all_questions: list[dict[str, Any]],
        original_question: str,
    ) -> dict[str, Any] | None:
        """Check if revised question is a duplicate."""
        new_normalized = self._normalize_question(new_question)
        
        for q in all_questions:
            existing_question = q.get("question_text", "")
            
            # Skip the original question
            if existing_question == original_question:
                continue
            
            existing_normalized = self._normalize_question(existing_question)
            
            similarity = self._calculate_similarity(new_normalized, existing_normalized)
            if similarity > 0.8:  # 80% similarity threshold
                return q
        
        return None

    def _normalize_question(self, question: str) -> str:
        """Normalize a question for comparison."""
        text = question.lower()
        # Remove common prefixes
        text = re.sub(r'^(how|what|why|when|where|which|who)\s+', '', text)
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        return text

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
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

    def _check_phase_fit(self, question: str, phase: str) -> bool:
        """Check if question fits the phase."""
        question_lower = question.lower()
        
        if phase == "Panorama Mapping":
            # Should be about project overview, not about specific code
            panorama_keywords = ["purpose", "goal", "project", "modules", "overview", "does this"]
            # Exclude questions that reference specific code artifacts
            has_specific_artifact = bool(re.search(r'`[^`]+`', question))
            has_function_ref = bool(re.search(r'\b(function|method|class)\b', question_lower))
            if has_specific_artifact or has_function_ref:
                return False
            return any(keyword in question_lower for keyword in panorama_keywords)
        
        elif phase == "Architecture Understanding":
            # Should be about architecture
            arch_keywords = ["architecture", "design", "pattern", "structure", "how.*organized"]
            return any(keyword in question_lower for keyword in arch_keywords)
        
        elif phase == "Code Detail Completion":
            # Should reference specific code artifacts
            has_artifact = bool(re.search(r'`[^`]+`', question))
            has_specific = bool(re.search(r'(file|class|function|method|path)', question_lower))
            return has_artifact or has_specific
        
        elif phase == "Use Cases & Scenarios":
            # Should be about usage scenarios
            scenario_keywords = ["scenario", "use case", "workflow", "how.*used", "when.*user"]
            return any(keyword in question_lower for keyword in scenario_keywords)
        
        return True

    def _extract_target_files(
        self,
        question: str,
        existing_files: list[str],
    ) -> list[str]:
        """Extract target files from question."""
        # Look for file paths in backticks
        file_pattern = r'`([^`]+\.[a-zA-Z]+)`'
        matches = re.findall(file_pattern, question)
        
        # Filter to valid file paths
        target_files = []
        for match in matches:
            if '/' in match or '.' in match:
                target_files.append(match)
        
        # If no files found, keep existing
        if not target_files:
            return existing_files
        
        return target_files


# Singleton instance
question_revision_service = QuestionRevisionService()
