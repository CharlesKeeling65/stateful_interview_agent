"""
Tests for the question revision service.
"""

import json
import pytest
from unittest.mock import Mock, patch

from app.services.question_revision_service import QuestionRevisionService


class TestQuestionRevisionService:
    """Test the QuestionRevisionService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionRevisionService()

    def test_is_english_true(self):
        """Test English detection with English text."""
        assert self.service._is_english("How does the main function work?") is True

    def test_is_english_false(self):
        """Test English detection with Chinese text."""
        assert self.service._is_english("主要函数是如何工作的？") is False

    def test_is_english_mixed(self):
        """Test English detection with mixed text."""
        # Mostly English should be considered English
        assert self.service._is_english("How does the main 函数 work?") is True

    def test_is_modification_oriented_true(self):
        """Test modification detection with modification-oriented questions."""
        assert self.service._is_modification_oriented("How should this code be improved?") is True
        assert self.service._is_modification_oriented("What files need to be changed?") is True
        assert self.service._is_modification_oriented("How would you refactor this?") is True

    def test_is_modification_oriented_false(self):
        """Test modification detection with understanding-oriented questions."""
        assert self.service._is_modification_oriented("How does the main function work?") is False
        assert self.service._is_modification_oriented("What is the purpose of utils.py?") is False

    def test_check_duplicate_found(self):
        """Test duplicate detection with similar questions."""
        new_question = "How does the main function work?"
        all_questions = [
            {"question_no": 1, "question_text": "How does the main function work in the codebase?"},
            {"question_no": 2, "question_text": "What is the purpose of utils.py?"},
        ]
        
        result = self.service._check_duplicate(new_question, all_questions, "original question")
        
        assert result is not None
        assert result["question_no"] == 1

    def test_check_duplicate_not_found(self):
        """Test duplicate detection with different questions."""
        new_question = "What is the architecture of this project?"
        all_questions = [
            {"question_no": 1, "question_text": "How does the main function work?"},
            {"question_no": 2, "question_text": "What is the purpose of utils.py?"},
        ]
        
        result = self.service._check_duplicate(new_question, all_questions, "original question")
        
        assert result is None

    def test_check_phase_fit_panorama(self):
        """Test phase fit check for panorama mapping."""
        assert self.service._check_phase_fit("What is the purpose of this project?", "Panorama Mapping") is True
        assert self.service._check_phase_fit("How does the main function work?", "Panorama Mapping") is False

    def test_check_phase_fit_architecture(self):
        """Test phase fit check for architecture understanding."""
        assert self.service._check_phase_fit("What is the architecture of this project?", "Architecture Understanding") is True
        assert self.service._check_phase_fit("What is the purpose of this project?", "Architecture Understanding") is False

    def test_check_phase_fit_code_detail(self):
        """Test phase fit check for code detail completion."""
        assert self.service._check_phase_fit("How does `main.py` work?", "Code Detail Completion") is True
        assert self.service._check_phase_fit("What is the purpose of this project?", "Code Detail Completion") is False

    def test_check_phase_fit_use_cases(self):
        """Test phase fit check for use cases and scenarios."""
        assert self.service._check_phase_fit("What is a typical usage scenario?", "Use Cases & Scenarios") is True
        assert self.service._check_phase_fit("How does the main function work?", "Use Cases & Scenarios") is False

    def test_extract_target_files_found(self):
        """Test target file extraction from question."""
        question = "How does `src/main.py` and `utils/helper.py` work?"
        existing_files = ["other.py"]
        
        result = self.service._extract_target_files(question, existing_files)
        
        assert "src/main.py" in result
        assert "utils/helper.py" in result

    def test_extract_target_files_not_found(self):
        """Test target file extraction when no files found."""
        question = "How does the main function work?"
        existing_files = ["main.py"]
        
        result = self.service._extract_target_files(question, existing_files)
        
        assert result == existing_files

    def test_normalize_question(self):
        """Test question normalization."""
        question = "How does the main function work?"
        normalized = self.service._normalize_question(question)
        
        assert "how" not in normalized.lower()
        assert "main function work" in normalized

    def test_calculate_similarity_identical(self):
        """Test similarity calculation with identical texts."""
        text1 = "how does main function work"
        text2 = "how does main function work"
        
        similarity = self.service._calculate_similarity(text1, text2)
        
        assert similarity == 1.0

    def test_calculate_similarity_different(self):
        """Test similarity calculation with different texts."""
        text1 = "how does main function work"
        text2 = "what is purpose of utils"
        
        similarity = self.service._calculate_similarity(text1, text2)
        
        assert similarity < 0.5

    def test_calculate_similarity_partial(self):
        """Test similarity calculation with partially similar texts."""
        text1 = "how does main function work"
        text2 = "how does main function operate"
        
        similarity = self.service._calculate_similarity(text1, text2)
        
        assert 0.5 < similarity < 1.0

    @patch('app.services.question_revision_service.get_llm_provider')
    @patch('app.services.question_revision_service.get_prompt_manager')
    def test_revise_question_success(self, mock_prompt_manager, mock_llm_provider):
        """Test successful question revision."""
        # Mock prompt manager
        mock_prompt = Mock()
        mock_prompt.messages = [{"role": "user", "content": "test"}]
        mock_prompt_manager.return_value.render.return_value = mock_prompt
        
        # Mock LLM provider
        mock_llm = Mock()
        mock_llm.generate.return_value = "How does the `main()` function in `main.py` initialize the application?"
        mock_llm_provider.return_value = mock_llm
        
        service = QuestionRevisionService()
        
        result = service.revise_question(
            question_text="How does the main function work?",
            chinese_instruction="改成具体问 main.py 里的 main 函数",
            phase="Code Detail Completion",
            target_files=["main.py"],
            target_symbols=["main"],
            all_questions=[],
        )
        
        assert "original_question" in result
        assert "revised_question" in result
        assert "chinese_instruction" in result
        assert "validation_result" in result

    def test_apply_chinese_instruction_fallback_too_broad(self):
        """Test fallback for 'too broad' instruction."""
        original = "How does the authentication system work?"
        instruction = "这个问题太泛了"
        
        result = self.service._apply_chinese_instruction_fallback(original, instruction)
        
        assert "?" in result
        assert len(result) > len(original)

    def test_apply_chinese_instruction_fallback_specific(self):
        """Test fallback for 'more specific' instruction."""
        original = "How does the authentication system work?"
        instruction = "更具体一些"
        
        result = self.service._apply_chinese_instruction_fallback(original, instruction)
        
        assert "?" in result


if __name__ == "__main__":
    pytest.main([__file__])
