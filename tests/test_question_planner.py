import os
import unittest
from app.services.question_planner import plan_next_question

os.environ.setdefault("OPENAI_API_KEY", "test-key")

class QuestionPlannerTests(unittest.TestCase):
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
            if "Prioritize asking about unexplored but highly important files" in c:
                self.assertIn("src/neglected.py", c)
                constraint_found = True
        self.assertTrue(constraint_found)

if __name__ == "__main__":
    unittest.main()
