import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.services import question_generator
from app.services.question_postprocessor import repair_question_locally


class _FakePrompt:
    def __init__(self, prompt_id: str, messages: list[dict[str, str]]):
        self.prompt_id = prompt_id
        self.version = "test"
        self.messages = messages


class _FakePromptManager:
    def render(self, prompt_id: str, variables: dict) -> _FakePrompt:
        return _FakePrompt(
            prompt_id,
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": f"{prompt_id}::{variables.get('original_question', variables.get('target_label', ''))}"},
            ],
        )


class QuestionGenerationRepairTests(unittest.TestCase):
    def test_repair_question_locally_converts_yes_no_and_removes_line_numbers(self):
        repaired = repair_question_locally(
            "Q8: Does app/services/question_generator.py handle retries at lines 12-20?",
            reasons=[
                "Avoid yes/no questions.",
                "Do not use exact line numbers (e.g., L123) in questions; reference logical names instead.",
            ],
            expected_turn_no=8,
            current_stage="Code Detail Completion",
        )

        self.assertEqual(
            repaired,
            "Q8: How does app/services/question_generator.py handle retries?",
        )

    def test_generate_next_question_uses_local_repair_without_refiner_when_reasons_are_repairable(self):
        provider = SimpleNamespace(
            generate_text=lambda **_kwargs: SimpleNamespace(
                text="Q8: Does app/services/question_generator.py handle retries at lines 12-20?",
                model="fake-model",
                usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8, total_tokens=28),
            )
        )

        with (
            patch.object(question_generator, "get_llm_provider", return_value=provider),
            patch.object(question_generator, "get_prompt_manager", return_value=_FakePromptManager()),
            patch.object(question_generator, "get_stage_instruction", return_value="trace implementation"),
            patch.object(question_generator, "default_planner_decision", return_value={
                "question_intent": "code_detail_deep_dive",
                "intent_mode": "understand_current_code",
                "target_type": "file",
                "target_label": "app/services/question_generator.py",
                "reasoning": "reason",
                "constraints": [],
            }),
            patch.object(question_generator, "validate_question_for_stage", side_effect=[
                {"is_valid": False, "reasons": [
                    "Avoid yes/no questions. Rephrase as an open-ended question.",
                    "Do not use exact line numbers (e.g., L123) in questions; reference logical names instead.",
                ]},
                {"is_valid": True, "reasons": []},
            ]),
            patch.object(question_generator, "format_human_review_context", return_value="none"),
        ):
            result = question_generator.generate_next_question_from_history(
                system_prompt="prompt",
                recent_context="recent",
                retrieved_context="retrieved",
                coverage_priorities="priorities",
                next_turn_no=8,
                current_stage="Code Detail Completion",
            )

        self.assertEqual(
            result["question_text"],
            "Q8: How does app/services/question_generator.py handle retries?",
        )

    def test_generate_next_question_falls_back_to_refiner_when_local_repair_cannot_fix(self):
        responses = iter(
            [
                SimpleNamespace(
                    text="Q8: What are its responsibilities, edge cases, and bottlenecks?",
                    model="fake-model",
                    usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8, total_tokens=28),
                ),
                SimpleNamespace(
                    text="How does app/services/question_generator.py handle retries?",
                    model="fake-model",
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                ),
            ]
        )

        provider = SimpleNamespace(generate_text=lambda **_kwargs: next(responses))

        with (
            patch.object(question_generator, "get_llm_provider", return_value=provider),
            patch.object(question_generator, "get_prompt_manager", return_value=_FakePromptManager()),
            patch.object(question_generator, "get_stage_instruction", return_value="trace implementation"),
            patch.object(question_generator, "default_planner_decision", return_value={
                "question_intent": "code_detail_deep_dive",
                "intent_mode": "understand_current_code",
                "target_type": "file",
                "target_label": "app/services/question_generator.py",
                "reasoning": "reason",
                "constraints": [],
            }),
            patch.object(question_generator, "validate_question_for_stage", side_effect=[
                {"is_valid": False, "reasons": [
                    "Avoid rigid review-style checklists. Focus on a specific implementation detail or call path.",
                ]},
                {"is_valid": True, "reasons": []},
            ]),
            patch.object(question_generator, "format_human_review_context", return_value="none"),
        ):
            result = question_generator.generate_next_question_from_history(
                system_prompt="prompt",
                recent_context="recent",
                retrieved_context="retrieved",
                coverage_priorities="priorities",
                next_turn_no=8,
                current_stage="Code Detail Completion",
            )

        self.assertEqual(
            result["question_text"],
            "Q8: How does app/services/question_generator.py handle retries?",
        )


if __name__ == "__main__":
    unittest.main()
