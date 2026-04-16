import os
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state, calculate_structural_importance

class CoverageServiceTests(unittest.TestCase):
    def test_calculate_structural_importance(self):
        # High importance for src code at root
        self.assertGreater(calculate_structural_importance("src/main.py"), 0.8)
        
        # Lower importance for tests
        self.assertLess(calculate_structural_importance("tests/test_main.py"), 0.8)
        
        # Config files lose points
        self.assertLess(calculate_structural_importance("app/config.json"), calculate_structural_importance("app/main.py"))

        # Deep files lose points
        self.assertLess(calculate_structural_importance("app/a/b/c/d.py"), calculate_structural_importance("app/a.py"))

    def test_rebuild_coverage_state_tracks_file_exploration(self):
        project = ProjectSession(id=1, project_name="Test")
        # manually inject manifest mock for tests
        project.repo_manifest_json = '{"files_list": ["src/main.py", "tests/test_main.py", "README.md"]}'

        turn1 = InterviewTurn(
            id=1,
            turn_no=1,
            stage="Code Detail Completion",
            question_text="Q1",
            question_plan_json='{"repo_selected_paths": ["src/main.py"]}',
            answer_text="It works",
        )
        turn2 = InterviewTurn(
            id=2,
            turn_no=2,
            stage="Code Detail Completion",
            question_text="Q2",
            question_plan_json='{"repo_selected_paths": ["src/main.py"]}',
            answer_text="Another fact",
        )
        # Turn 3 accesses test, unanswered
        turn3 = InterviewTurn(
            id=3,
            turn_no=3,
            stage="Code Detail Completion",
            question_text="Q3",
            question_plan_json='{"repo_selected_paths": ["tests/test_main.py"]}',
            answer_text=None,
        )

        state = rebuild_coverage_state([turn1, turn2, turn3], project)
        repo_coverage = state.get("repo_file_coverage", {})
        
        self.assertIn("src/main.py", repo_coverage)
        self.assertIn("README.md", repo_coverage)
        self.assertIn("tests/test_main.py", repo_coverage)

        # src/main.py was asked 2 times and answered 2 times
        self.assertEqual(repo_coverage["src/main.py"]["times_asked"], 2)
        self.assertEqual(repo_coverage["src/main.py"]["times_answered"], 2)
        self.assertGreater(repo_coverage["src/main.py"]["exploration_score"], 0.0)
        self.assertEqual(repo_coverage["src/main.py"]["last_turn_no"], 2)

        # tests/test_main.py was asked 1 time but answered 0 times
        self.assertEqual(repo_coverage["tests/test_main.py"]["times_asked"], 1)
        self.assertEqual(repo_coverage["tests/test_main.py"]["times_answered"], 0)
        self.assertEqual(repo_coverage["tests/test_main.py"]["exploration_score"], 0.0)
        self.assertIsNone(repo_coverage["tests/test_main.py"]["last_turn_no"])
        
        # README.md is untouched
        self.assertEqual(repo_coverage["README.md"]["times_asked"], 0)
        self.assertEqual(repo_coverage["README.md"]["times_answered"], 0)

    def test_rebuild_coverage_state_implicit_discovery(self):
        project = ProjectSession(id=1, project_name="Test")
        project.repo_manifest_json = '{"files_list": ["src/main.py", "src/auth.py", "README.md"]}'

        turn = InterviewTurn(
            id=1,
            turn_no=1,
            stage="Code Detail Completion",
            question_text="Tell me about tests",
            question_plan_json='{"repo_selected_paths": ["src/main.py"]}',
            answer_text="Here is the test behavior.",
            answer_summary="The tests in src/main.py also interact with src/auth.py and mention `README.md`.",
        )

        state = rebuild_coverage_state([turn], project)
        repo_coverage = state.get("repo_file_coverage", {})

        # src/main.py is explicit target (+0.4)
        self.assertEqual(repo_coverage["src/main.py"]["times_asked"], 1)
        self.assertEqual(repo_coverage["src/main.py"]["times_answered"], 1)
        self.assertAlmostEqual(repo_coverage["src/main.py"]["exploration_score"], 0.4)

        # src/auth.py is implicit discovery (+0.1)
        self.assertEqual(repo_coverage["src/auth.py"]["times_asked"], 0)
        self.assertAlmostEqual(repo_coverage["src/auth.py"]["exploration_score"], 0.1)

        # README.md is implicit discovery (+0.1)
        self.assertEqual(repo_coverage["README.md"]["times_asked"], 0)
        self.assertAlmostEqual(repo_coverage["README.md"]["exploration_score"], 0.1)


if __name__ == "__main__":
    unittest.main()
