import os
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.turn import InterviewTurn
from app.services.summarization_service import build_answer_analysis, evaluate_turn_question
from app.services.context_engineering import build_recent_context

class QuestionEvaluationTests(unittest.TestCase):
    @patch("app.services.summarization_service.get_llm_provider")
    def test_evaluate_turn_question(self, mock_provider):
        mock_response = MagicMock()
        mock_response.text = "This question was too broad, the human had to narrow it down."
        mock_response.model = "test-model"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate_text.return_value = mock_response
        mock_provider.return_value = mock_provider_instance

        turn = InterviewTurn(
            id=1,
            turn_no=1,
            stage="Code Detail Completion",
            question_text="How does the whole file work?",
            answer_text="That's too broad. I'll just explain lines 1-10.",
        )
        
        result = evaluate_turn_question(
            project_id=1,
            turn=turn,
            system_prompt="You are an evaluator.",
            answer_summary="The user found it too broad.",
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result["evaluation"], "This question was too broad, the human had to narrow it down.")

    def test_build_recent_context_includes_evaluation(self):
        turn = InterviewTurn(
            id=1,
            turn_no=1,
            stage="Code Detail Completion",
            question_text="How does the system work?",
            answer_text="Details here.",
            answer_analysis_json='{"question_evaluation": "Good question, but missing boundary info."}',
        )
        # Using build_answer_analysis for real parsing behavior
        analysis = build_answer_analysis(
            stage="Code Detail Completion",
            answer_text="Details here.",
            summary="Details here.",
            summary_source="llm",
            question_evaluation="Good question, but missing boundary info."
        )
        import json
        turn.answer_analysis_json = json.dumps(analysis)

        # Now test build_recent_context
        context_str = build_recent_context([turn])
        
        self.assertIn("Latest turn question: How does the system work?", context_str)
        self.assertIn("Latest Human Evaluation (use to adjust question style): Good question, but missing boundary info.", context_str)

if __name__ == "__main__":
    unittest.main()
