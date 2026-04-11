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
                current_stage="Code Detail Completion",
            ),
            "Q7: What does the scheduler do right after startup?",
        )

    def test_question_copy_variant_removes_ai_sounding_lead_in(self):
        self.assertEqual(
            clean_generated_question(
                "Q8: To better understand the current implementation, could you walk me through how app/services/question_generator.py builds the prompt?",
                8,
                current_stage="Code Detail Completion",
            ),
            "Q8: How does app/services/question_generator.py build the prompt?",
        )

    def test_question_copy_variant_does_not_hard_truncate_long_code_detail_question(self):
        self.assertEqual(
            clean_generated_question(
                "Q11: In modules/typer_agent.py, what does the build_prompt() method do with its full signature, how does it read the scratchpad file, and how does it assemble the final prompt before returning it?",
                11,
                current_stage="Code Detail Completion",
            ),
            "Q11: In modules/typer_agent.py, what does the build_prompt() method do with its full signature, how does it read the scratchpad file, and how does it assemble the final prompt before returning it?",
        )

    def test_question_copy_variant_keeps_multi_part_panorama_question(self):
        self.assertEqual(
            clean_generated_question(
                "Q4: To better understand the current system, could you walk me through what the project does and who it serves?",
                4,
                current_stage="Panorama Mapping",
            ),
            "Q4: What does the project do and who does it serve?",
        )

    def test_question_copy_variant_removes_specifically_lead_in_across_stages(self):
        self.assertEqual(
            clean_generated_question(
                "Q5: Specifically, how do the major modules collaborate during the main request flow?",
                5,
                current_stage="Architecture Understanding",
            ),
            "Q5: How do the major modules collaborate during the main request flow?",
        )

    def test_question_copy_variant_removes_cross_turn_reference_lead_in(self):
        self.assertEqual(
            clean_generated_question(
                "Q6: In Q3, how does the cache layer interact with the request path?",
                6,
                current_stage="Architecture Understanding",
            ),
            "Q6: How does the cache layer interact with the request path?",
        )

    def test_question_copy_variant_removes_as_mentioned_lead_in(self):
        self.assertEqual(
            clean_generated_question(
                "Q14: As mentioned above, what input and output boundaries define this scenario today?",
                14,
                current_stage="Use Cases & Scenarios",
            ),
            "Q14: What input and output boundaries define this scenario today?",
        )

    def test_question_copy_variant_normalizes_windows_unfriendly_symbols_to_ascii(self):
        self.assertEqual(
            clean_generated_question(
                'Q13: What does “build_prompt()” do — and how does it route errors → retries? 🤖',
                13,
                current_stage="Code Detail Completion",
            ),
            'Q13: What does "build_prompt()" do - and how does it route errors -> retries?',
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
            current_stage="Code Detail Completion",
        )

        self.assertFalse(review["is_valid"])
        self.assertIn("Question must contain exactly one question mark.", review["reasons"])

    def test_reviewer_rejects_overlong_question_text(self):
        review = review_question_text(
            (
                "Q10: In app/services/question_generator.py, how does generate_next_question_from_history "
                "assemble the prompt, merge planner constraints, weave in retrieved context, and then "
                "decide which repository evidence matters most before calling the model right now, while also "
                "tracking every intermediate formatting branch, fallback path, retry-specific mutation, "
                "validator-facing adaptation, post-call packaging detail across the full execution flow, "
                "the branch-priority scoring state, the exact shape of every retrieval payload, the way "
                "prompt fragments are concatenated before the provider call, the fallback handling for "
                "missing repository evidence, the cleanup path for malformed intermediate text, and the "
                "final persistence-facing packaging fields that are handed to downstream workflow steps?"
            ),
            "understand_current_code",
            current_stage="Code Detail Completion",
        )

        self.assertFalse(review["is_valid"])
        self.assertIn("Question is too long; keep it concise and direct.", review["reasons"])

    def test_reviewer_allows_reasonably_long_code_detail_question(self):
        review = review_question_text(
            (
                "Q12: In modules/typer_agent.py, what does the build_prompt() method do with its full signature, "
                "how does it read the scratchpad file, and how does it assemble the final prompt before returning it?"
            ),
            "understand_current_code",
            current_stage="Code Detail Completion",
        )

        self.assertTrue(review["is_valid"])

    def test_reviewer_allows_longer_non_code_detail_question(self):
        review = review_question_text(
            (
                "Q3: How do the major modules collaborate across request intake, orchestration, persistence, "
                "and delivery boundaries when a user moves through the main workflow and the system hands "
                "off responsibility between services and layers?"
            ),
            "understand_current_code",
            current_stage="Architecture Understanding",
        )

        self.assertTrue(review["is_valid"])


if __name__ == "__main__":
    unittest.main()
