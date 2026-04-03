import os
import tempfile
import textwrap
import unittest
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.prompts.manager import PromptManager


class PromptManagementTests(unittest.TestCase):
    def test_prompt_manager_loads_yaml_template_and_renders_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_file = Path(temp_dir) / "first_question.yaml"
            prompt_file.write_text(
                textwrap.dedent(
                    """
                    id: first_question
                    version: "1.0"
                    description: First question bootstrap prompt
                    system_template: |
                      You are interviewing about {project_name}.
                    user_template: |
                      Stage: {stage}
                      Objective: {objective}
                    required_variables:
                      - project_name
                      - stage
                      - objective
                    """
                ).strip(),
                encoding="utf-8",
            )

            manager = PromptManager(prompt_directory=Path(temp_dir))
            rendered = manager.render_messages(
                "first_question",
                {
                    "project_name": "Stateful Interview Agent",
                    "stage": "Panorama Mapping",
                    "objective": "Establish the overall system scope.",
                },
            )

            self.assertEqual(rendered[0]["role"], "system")
            self.assertIn("Stateful Interview Agent", rendered[0]["content"])
            self.assertEqual(rendered[1]["role"], "user")
            self.assertIn("Panorama Mapping", rendered[1]["content"])
            self.assertIn("Establish the overall system scope.", rendered[1]["content"])

    def test_prompt_manager_rejects_missing_required_variables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_file = Path(temp_dir) / "summary.yaml"
            prompt_file.write_text(
                textwrap.dedent(
                    """
                    id: answer_summary
                    version: "1.0"
                    description: Summary prompt
                    system_template: |
                      You are a summarizer.
                    user_template: |
                      Stage: {stage}
                      Answer: {answer_text}
                    required_variables:
                      - stage
                      - answer_text
                    """
                ).strip(),
                encoding="utf-8",
            )

            manager = PromptManager(prompt_directory=Path(temp_dir))

            with self.assertRaises(ValueError):
                manager.render_messages(
                    "answer_summary",
                    {
                        "stage": "Code Detail Completion",
                    },
                )


if __name__ == "__main__":
    unittest.main()
