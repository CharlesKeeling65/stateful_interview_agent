import os
import unittest
from app.services.question_planner import plan_next_question

os.environ.setdefault("OPENAI_API_KEY", "test-key")

class QuestionPlannerTests(unittest.TestCase):
    def test_plan_next_question_marks_complex_code_detail_target_for_decomposition(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "complex-flow",
                    "label": "app/services/question_generator.py request path",
                    "stage": "Code Detail Completion",
                    "status": "needs_follow_up",
                    "priority": 0.95,
                    "keywords": ["question_generator.py", "request path"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [7],
                    "summary": (
                        "app/services/question_generator.py coordinates the main execution path, "
                        "error handling, and state management for question drafting."
                    ),
                    "unresolved_points": [
                        "Need the main execution path in detail.",
                        "Need the error handling path in detail.",
                        "Need how state changes across the path.",
                    ],
                    "last_turn_no": 7,
                }
            ],
            "framework": {
                "stage_turn_counts": {"Code Detail Completion": 2},
            },
        }

        decision = plan_next_question(
            turns=[],
            current_stage="Code Detail Completion",
            next_turn_no=8,
            coverage_state=coverage_state,
        )

        self.assertEqual(decision["decomposition_mode"], "queued_subquestions")
        self.assertEqual(len(decision["subquestion_specs"]), 3)
        self.assertEqual(
            [item["focus_kind"] for item in decision["subquestion_specs"]],
            ["main_flow", "error_path", "state_management"],
        )
        self.assertEqual(decision["subquestion_specs"][0]["target_label"], "app/services/question_generator.py")

    def test_plan_next_question_rebalances_targets(self):
        coverage_state = {
            "framework": {
                "stage_turn_counts": {"Code Detail Completion": 1}
            },
            "repo_file_coverage": {
                "src/neglected.py": {
                    "importance_score": 0.9,
                    "exploration_score": 0.0,
                },
                "src/explored.py": {
                    "importance_score": 0.8,
                    "exploration_score": 0.9,
                }
            }
        }
        
        decision = plan_next_question(
            turns=[],
            current_stage="Code Detail Completion",
            next_turn_no=2,
            coverage_state=coverage_state,
        )
        
        # It should prioritize src/neglected.py which has gap 0.9
        self.assertEqual(decision["target_label"], "src/neglected.py")
        self.assertEqual(decision["target_type"], "file")
        
        # Check constraints
        constraint_found = False
        for c in decision["constraints"]:
            if "STRATEGIC PRIORITY" in c:
                self.assertIn("src/neglected.py", c)
                constraint_found = True
        self.assertTrue(constraint_found)

        # Check rationale
        self.assertIn("coverage rebalancing strategy", decision["why_this_question"])
        self.assertIn("src/neglected.py", decision["why_this_question"])

if __name__ == "__main__":
    unittest.main()
