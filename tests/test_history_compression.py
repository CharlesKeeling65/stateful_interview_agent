import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.turn import InterviewTurn
from app.services.question_postprocessor import clean_generated_question
from app.services.question_reviewer import review_question_text
from app.services.transcript_service import build_compact_interview_context
from app.services.usage_service import (
    aggregate_project_usage,
    estimate_token_count,
    extract_usage_metrics,
)


class HistoryCompressionTests(unittest.TestCase):
    def test_compact_context_uses_summaries_for_older_turns(self):
        turns = [
            InterviewTurn(
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What does the project do?",
                answer_text="A very long first answer with many details.",
                answer_summary="Project purpose, target user, and major boundary summary.",
            ),
            InterviewTurn(
                turn_no=2,
                stage="Architecture Understanding",
                question_text="Q2: How is it structured?",
                answer_text="A detailed latest answer that should remain verbatim.",
                answer_summary="Older summary should not be used for the latest completed turn.",
            ),
            InterviewTurn(
                turn_no=3,
                stage="Architecture Understanding",
                question_text="Q3: What is the next question?",
                answer_text=None,
            ),
        ]

        compact = build_compact_interview_context(turns)

        self.assertIn("Summary: Project purpose, target user, and major boundary summary.", compact)
        self.assertIn("Answer: A detailed latest answer that should remain verbatim.", compact)
        self.assertNotIn("Answer: A very long first answer with many details.", compact)

    def test_question_copy_variant_strips_prefix(self):
        self.assertEqual(
            clean_generated_question("**Q2:** What happens next?", 2),
            "Q2: What happens next?",
        )

    def test_question_copy_variant_rewrites_wrong_turn_prefix_during_regeneration(self):
        self.assertEqual(
            clean_generated_question("Q20: Which method handles the edge case?", 19),
            "Q19: Which method handles the edge case?",
        )
        self.assertEqual(
            clean_generated_question("Q19: Q20: Which method handles the edge case?", 19),
            "Q19: Which method handles the edge case?",
        )

    def test_question_copy_variant_strips_markdown_heading_prefix(self):
        self.assertEqual(
            clean_generated_question("# Q6: Call Chain Walkthrough?", 6),
            "Q6: Call Chain Walkthrough?",
        )

    def test_question_copy_variant_keeps_only_first_question_sentence(self):
        self.assertEqual(
            clean_generated_question(
                "Q7: What does the scheduler do right after startup? What happens if the config is missing?",
                7,
            ),
            "Q7: What does the scheduler do right after startup?",
        )

    def test_question_copy_variant_removes_ai_sounding_lead_in(self):
        self.assertEqual(
            clean_generated_question(
                "Q8: To better understand the current implementation, could you walk me through how app/services/question_generator.py builds the prompt?",
                8,
            ),
            "Q8: How does app/services/question_generator.py build the prompt?",
        )

    def test_compact_context_uses_override_for_latest_pending_answer(self):
        turns = [
            InterviewTurn(
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What does the project do?",
                answer_text="Older full answer.",
                answer_summary="Older compressed answer.",
            ),
            InterviewTurn(
                turn_no=2,
                stage="Architecture Understanding",
                question_text="Q2: What changed?",
                answer_text=None,
            ),
        ]

        compact = build_compact_interview_context(
            turns,
            latest_answer_override="Fresh latest answer from the current submission.",
        )

        self.assertIn("Summary: Older compressed answer.", compact)
        self.assertIn("Answer: Fresh latest answer from the current submission.", compact)


class UsageServiceTests(unittest.TestCase):
    def test_extract_usage_metrics_reads_openai_compatible_usage(self):
        response = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=35, total_tokens=155)
        )

        usage = extract_usage_metrics(response)

        self.assertEqual(usage["prompt_tokens"], 120)
        self.assertEqual(usage["completion_tokens"], 35)
        self.assertEqual(usage["total_tokens"], 155)
        self.assertFalse(usage["is_estimated"])

    def test_extract_usage_metrics_supports_input_output_token_fields(self):
        response = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=90, output_tokens=30, total_tokens=120)
        )

        usage = extract_usage_metrics(response)

        self.assertEqual(usage["prompt_tokens"], 90)
        self.assertEqual(usage["completion_tokens"], 30)
        self.assertEqual(usage["total_tokens"], 120)

    def test_estimate_token_count_returns_positive_estimate(self):
        self.assertGreater(estimate_token_count("This is a compact estimation sample."), 0)

    def test_aggregate_project_usage_sums_multiple_operations(self):
        usage_rows = [
            SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120),
            SimpleNamespace(prompt_tokens=40, completion_tokens=10, total_tokens=50),
        ]

        aggregated = aggregate_project_usage(usage_rows)

        self.assertEqual(aggregated["prompt_tokens"], 140)
        self.assertEqual(aggregated["completion_tokens"], 30)
        self.assertEqual(aggregated["total_tokens"], 170)


class QuestionReviewerTests(unittest.TestCase):
    def test_reviewer_rejects_multiple_question_marks(self):
        review = review_question_text(
            "Q9: What triggers the job runner? What happens after that?",
            "understand_current_code",
        )

        self.assertFalse(review["is_valid"])
        self.assertIn("Question must contain exactly one question mark.", review["reasons"])

    def test_reviewer_rejects_overlong_question_text(self):
        review = review_question_text(
            (
                "Q10: In app/services/question_generator.py, how does generate_next_question_from_history "
                "assemble the prompt, merge planner constraints, weave in retrieved context, and then "
                "decide which repository evidence matters most before calling the model right now?"
            ),
            "understand_current_code",
        )

        self.assertFalse(review["is_valid"])
        self.assertIn("Question is too long; keep it concise and direct.", review["reasons"])


if __name__ == "__main__":
    unittest.main()
