import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state
from app.services.question_planner import plan_next_question
from app.services.stage_manager import decide_next_stage


class CollaborationCoverageTests(unittest.TestCase):
    def test_rebuild_coverage_state_tracks_human_collaboration_signals(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What is the project for?",
                answer_text=(
                    "I think the main purpose is helping operators process support requests. "
                    "The users are operators and admins. The main modules are api, workflow, and reporting."
                ),
                answer_summary="Purpose, users, and modules were covered.",
            ),
            InterviewTurn(
                id=2,
                turn_no=2,
                stage="Architecture Understanding",
                question_text="Q2: Which area should we deepen next?",
                answer_text=(
                    "Let's prioritize the request path before the safety edge cases. "
                    "The previous branch on safety is useful, but I want to redirect back to the main call chain "
                    "because that is more central to understanding the project."
                ),
                answer_summary="Human redirected focus toward the main request path and prioritized it over safety auditing.",
            ),
        ]

        coverage = rebuild_coverage_state(turns)
        collaboration = coverage["framework"]["human_collaboration"]

        self.assertGreaterEqual(collaboration["judgment_turn_count"], 1)
        self.assertGreaterEqual(collaboration["redirection_turn_count"], 1)
        self.assertGreaterEqual(collaboration["prioritization_turn_count"], 1)


class PlannerGateTests(unittest.TestCase):
    def test_planner_requests_human_judgment_before_deep_code_detail_when_collaboration_is_thin(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "request_path",
                    "label": "request path through api_gateway and orchestration_service",
                    "stage": "Architecture Understanding",
                    "status": "needs_follow_up",
                    "priority": 0.92,
                    "keywords": ["api_gateway", "orchestration_service", "request_path"],
                    "evidence_turn_ids": [4],
                    "evidence_turn_nos": [4],
                    "summary": "Main request path is known at module level but still needs concrete deep dive selection.",
                    "unresolved_points": ["A human should choose whether to deepen auth or orchestration first."],
                    "last_turn_no": 4,
                }
            ],
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                },
                "architecture": {
                    "architecture_style": True,
                    "module_responsibilities": True,
                    "communication_mechanisms": True,
                    "key_call_chains": True,
                    "design_rationale": True,
                },
                "code_detail": {
                    "key_files_count": 0,
                    "key_classes_count": 0,
                    "key_methods_count": 0,
                    "execution_paths_count": 0,
                    "third_party_library_usage_count": 0,
                    "error_handling_count": 0,
                },
                "use_cases": {
                    "typical_scenarios_count": 0,
                    "user_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {
                    "judgment_turn_count": 0,
                    "correction_turn_count": 0,
                    "redirection_turn_count": 0,
                    "prioritization_turn_count": 0,
                },
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 3,
                    "Code Detail Completion": 0,
                    "Use Cases & Scenarios": 0,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": ["key_files_count", "key_methods_count"],
                    "use_cases": ["typical_scenarios_count"],
                },
                "wrap_up_ready": False,
            },
        }

        planner = plan_next_question(
            turns=[],
            current_stage="Code Detail Completion",
            next_turn_no=6,
            coverage_state=coverage_state,
        )

        self.assertEqual(planner["question_intent"], "human_review")
        self.assertEqual(planner["target_type"], "prioritization")
        self.assertTrue(planner["human_collaboration_gate"])

    def test_planner_repairs_drift_when_safety_branch_expands_too_early(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "safety_audit",
                    "label": "error handling and safety audit in one narrow subprocess path",
                    "stage": "Panorama Mapping",
                    "status": "needs_follow_up",
                    "priority": 1.05,
                    "keywords": ["safety", "error", "subprocess", "exception"],
                    "evidence_turn_ids": [1, 2],
                    "evidence_turn_nos": [1, 2],
                    "summary": "The discussion is drifting into safety auditing before the main architecture is clear.",
                    "unresolved_points": ["Purpose and high-level workflow are still not fully covered."],
                    "last_turn_no": 2,
                }
            ],
            "framework": {
                "panorama": {
                    "purpose": False,
                    "target_users": True,
                    "boundaries": False,
                    "major_modules": False,
                    "high_level_workflow": False,
                },
                "architecture": {},
                "code_detail": {},
                "use_cases": {},
                "human_collaboration": {
                    "judgment_turn_count": 1,
                    "correction_turn_count": 0,
                    "redirection_turn_count": 0,
                    "prioritization_turn_count": 0,
                },
            },
        }

        planner = plan_next_question(
            turns=[],
            current_stage="Panorama Mapping",
            next_turn_no=3,
            coverage_state=coverage_state,
        )

        self.assertEqual(planner["question_intent"], "drift_repair")
        self.assertTrue(planner["drift_detected"])
        self.assertIn("purpose", planner["target_label"])


class StageGateTests(unittest.TestCase):
    def test_stage_controller_moves_to_use_cases_after_code_detail_dominates(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                },
                "architecture": {
                    "architecture_style": True,
                    "module_responsibilities": True,
                    "communication_mechanisms": True,
                    "key_call_chains": True,
                    "design_rationale": True,
                },
                "code_detail": {
                    "key_files_count": 4,
                    "key_classes_count": 3,
                    "key_methods_count": 6,
                    "execution_paths_count": 3,
                    "third_party_library_usage_count": 2,
                    "error_handling_count": 2,
                },
                "use_cases": {
                    "typical_scenarios_count": 0,
                    "user_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {
                    "judgment_turn_count": 2,
                    "correction_turn_count": 1,
                    "redirection_turn_count": 1,
                    "prioritization_turn_count": 2,
                },
                "stage_turn_counts": {
                    "Panorama Mapping": 3,
                    "Architecture Understanding": 4,
                    "Code Detail Completion": 24,
                    "Use Cases & Scenarios": 0,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": [],
                    "use_cases": ["typical_scenarios_count", "input_output_patterns_count"],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=32,
            coverage_state=coverage_state,
            current_stage="Code Detail Completion",
            max_turns=40,
        )

        self.assertEqual(decision["next_stage"], "Use Cases & Scenarios")
        self.assertIn("use-case", decision["reason"].lower())


if __name__ == "__main__":
    unittest.main()
