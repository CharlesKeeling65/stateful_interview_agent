import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.repo_grounding_service import build_repo_grounding_context
from app.services.repository_service import (
    apply_repository_configuration,
    resolve_project_repository,
)
from app.services.question_validator import validate_question_against_repository


class RepositoryGroundingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name) / "repo"
        (self.repo_root / "app/services").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "frontend/src").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "README.md").write_text("# Demo repo\n", encoding="utf-8")
        (
            self.repo_root / "app/services/question_generator.py"
        ).write_text(
            "\n".join(
                [
                    "class QuestionGenerator:",
                    "    pass",
                    "",
                    "def generate_next_question_from_history():",
                    "    return build_repo_manifest()",
                    "",
                    "def build_repo_manifest():",
                    "    return {'ready': True}",
                ]
            ),
            encoding="utf-8",
        )
        (
            self.repo_root / "frontend/src/App.tsx"
        ).write_text(
            "export function App() { return <main>demo</main> }\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_local_repository_configuration_resolves_manifest(self):
        project = ProjectSession(
            id=7,
            project_name="Repo Project",
            system_prompt="prompt",
        )
        apply_repository_configuration(
            project,
            {
                "source_type": "local_path",
                "local_path": str(self.repo_root),
            },
        )
        workspace = resolve_project_repository(project)
        self.assertIsNotNone(workspace)
        self.assertEqual(project.repo_source_type, "local_path")
        self.assertEqual(project.repo_manifest_data["file_count"], 3)
        self.assertIn("README.md", project.repo_manifest_data["key_files"])
        self.assertGreaterEqual(project.repo_manifest_data["symbol_count"], 2)

    def test_repo_grounding_collects_paths_symbols_and_queries(self):
        project = ProjectSession(
            id=8,
            project_name="Repo Grounded",
            system_prompt="prompt",
        )
        apply_repository_configuration(
            project,
            {
                "source_type": "local_path",
                "local_path": str(self.repo_root),
            },
        )
        resolve_project_repository(project)
        payload = build_repo_grounding_context(
            project=project,
            turns=[
                InterviewTurn(
                    id=1,
                    turn_no=1,
                    stage="Architecture Understanding",
                    question_text="Q1: What coordinates the workflow?",
                    answer_text="The question generator and app services coordinate the workflow.",
                )
            ],
            current_stage="Code Detail Completion",
            next_turn_no=2,
            planner_decision={
                "target_label": "app/services/question_generator.py",
                "question_intent": "code_detail_deep_dive",
                "retrieval_focus": "question generator path",
            },
            latest_answer_override=None,
            project_id=project.id,
            run_id=None,
        )
        self.assertTrue(payload["repo_grounding_meta"]["enabled"])
        self.assertIn("app/services/question_generator.py", payload["repo_grounding_meta"]["selected_paths"])
        self.assertIn("generate_next_question_from_history", payload["repo_grounding_context"])
        self.assertTrue(payload["repo_grounding_meta"]["queries"])

    def test_repository_validator_rejects_unknown_path_reference(self):
        validation = validate_question_against_repository(
            text="Q4: In app/services/missing_file.py, how does MissingThing currently work?",
            current_stage="Code Detail Completion",
            repo_grounding_meta={
                "enabled": True,
                "selected_paths": ["app/services/question_generator.py"],
                "selected_symbols": ["QuestionGenerator", "generate_next_question_from_history"],
            },
            repo_manifest={
                "key_files": ["README.md"],
            },
        )
        self.assertFalse(validation["is_valid"])
        self.assertIn("missing_file.py", " ".join(validation["reasons"]))

    def test_repository_validator_accepts_real_repo_path_outside_selected_bundle(self):
        validation = validate_question_against_repository(
            text="Q4: In frontend/src/App.tsx, how is the current UI shell wired?",
            current_stage="Code Detail Completion",
            repo_grounding_meta={
                "enabled": True,
                "selected_paths": ["app/services/question_generator.py"],
                "selected_symbols": ["QuestionGenerator", "generate_next_question_from_history"],
            },
            repo_manifest={
                "root_path": str(self.repo_root),
                "key_files": ["README.md"],
            },
        )
        self.assertTrue(validation["is_valid"])
        self.assertEqual(validation["reasons"], [])
