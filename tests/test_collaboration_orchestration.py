import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state
from app.services.question_planner import plan_next_question
from app.services.rubric_task_service import initialize_task_board, mark_task_completed
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
    def test_planner_uses_task_board_priority_when_runtime_supplies_it(self):
        coverage_state = {
            "branches": [],
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": False,
                    "boundaries": False,
                    "major_modules": True,
                    "high_level_workflow": False,
                },
                "architecture": {},
                "code_detail": {},
                "use_cases": {},
                "human_collaboration": {},
                "stage_turn_counts": {"Panorama Mapping": 1},
                "gaps": {"panorama": ["target_users", "high_level_workflow"]},
                "wrap_up_ready": False,
            },
        }
        task_board = initialize_task_board()
        task_board = mark_task_completed(task_board, "pan_purpose")

        planner = plan_next_question(
            turns=[],
            current_stage="Panorama Mapping",
            next_turn_no=2,
            coverage_state=coverage_state,
            task_board_json=task_board.model_dump_json(),
        )

        self.assertEqual(planner["rubric_task_id"], "pan_modules")
        self.assertEqual(planner["rubric_task_label"], "Major Modules")

    def test_planner_applies_explicit_human_redirection_signal(self):
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
                    "summary": "Main request path is known at module level but the collaboration chain is still unclear.",
                    "unresolved_points": ["Return to the main call chain before going deeper into retry logic."],
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
                    "module_responsibilities": False,
                    "communication_mechanisms": False,
                    "key_call_chains": False,
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
                    "scenario_count": 0,
                    "user_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {
                    "judgment_turn_count": 1,
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
                    "architecture": ["module_responsibilities", "communication_mechanisms", "key_call_chains"],
                    "code_detail": ["key_files_count", "key_methods_count"],
                    "use_cases": ["scenario_count"],
                    "human_collaboration": ["redirection_turn_count", "prioritization_turn_count"],
                },
                "wrap_up_ready": False,
            },
        }

        planner = plan_next_question(
            turns=[],
            current_stage="Architecture Understanding",
            next_turn_no=6,
            coverage_state=coverage_state,
            human_review_signal={
                "verdict": "drifted",
                "direction": "redirect",
                "preferred_next_focus": "architecture",
                "note": "Return to the main call chain before talking about safety retries.",
            },
        )

        self.assertTrue(planner["human_review_applied"])
        self.assertEqual(planner["question_intent"], "human_guided_redirect")
        self.assertEqual(planner["intent_mode"], "understand_current_code")
        self.assertIn("call chain", planner["why_this_question"].lower())

    def test_planner_can_apply_partial_human_review_signal_without_verdict(self):
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
                    "summary": "Main request path is known at module level but the collaboration chain is still unclear.",
                    "unresolved_points": ["Return to the main call chain before going deeper into retry logic."],
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
                    "module_responsibilities": False,
                    "communication_mechanisms": False,
                    "key_call_chains": False,
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
                    "scenario_count": 0,
                    "user_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {
                    "judgment_turn_count": 1,
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
                    "architecture": ["module_responsibilities", "communication_mechanisms", "key_call_chains"],
                    "code_detail": ["key_files_count", "key_methods_count"],
                    "use_cases": ["scenario_count"],
                    "human_collaboration": ["redirection_turn_count", "prioritization_turn_count"],
                },
                "wrap_up_ready": False,
            },
        }

        planner = plan_next_question(
            turns=[],
            current_stage="Architecture Understanding",
            next_turn_no=6,
            coverage_state=coverage_state,
            human_review_signal={
                "direction": "redirect",
                "preferred_next_focus": "architecture",
                "note": "Return to the main call chain before talking about safety retries.",
            },
        )

        self.assertTrue(planner["human_review_applied"])
        self.assertEqual(planner["question_intent"], "human_guided_redirect")
        self.assertIn("call chain", planner["why_this_question"].lower())

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
    def test_stage_controller_can_honor_explicit_phase_ready_signal(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": False,
                    "major_modules": True,
                    "high_level_workflow": False,
                },
                "architecture": {
                    "architecture_style": False,
                    "module_responsibilities": False,
                    "communication_mechanisms": False,
                    "key_call_chains": False,
                    "design_rationale": False,
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
                    "scenario_count": 0,
                    "user_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {
                    "judgment_turn_count": 1,
                    "correction_turn_count": 0,
                    "redirection_turn_count": 0,
                    "prioritization_turn_count": 0,
                },
                "stage_turn_counts": {
                    "Panorama Mapping": 3,
                    "Architecture Understanding": 0,
                    "Code Detail Completion": 0,
                    "Use Cases & Scenarios": 0,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "panorama": ["boundaries", "high_level_workflow"],
                    "architecture": [
                        "architecture_style",
                        "module_responsibilities",
                        "communication_mechanisms",
                        "key_call_chains",
                        "design_rationale",
                    ],
                    "code_detail": ["key_files_count"],
                    "use_cases": ["scenario_count"],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=4,
            coverage_state=coverage_state,
            current_stage="Panorama Mapping",
            max_turns=40,
            human_review_signal={"phase_ready": True},
        )

        self.assertEqual(decision["next_stage"], "Architecture Understanding")
        self.assertIn("human", decision["reason"].lower())

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

        self.assertEqual(decision["next_stage"], "Code Detail Completion")
        self.assertIn("hard-gated", decision["reason"].lower())

    def test_stage_controller_blocks_wrap_up_until_scenario_contract_is_complete(self):
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
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                },
                "code_detail": {
                    "specific_files_count": 4,
                    "specific_methods_count": 5,
                    "execution_paths_count": 3,
                    "error_handling_points_count": 2,
                },
                "use_cases": {
                    "representative_scenarios_count": 1,
                    "actors_roles_count": 1,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                },
                "human_collaboration": {},
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 3,
                    "Code Detail Completion": 10,
                    "Use Cases & Scenarios": 1,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "use_cases": ["input_output_patterns_count", "boundary_conditions_count"],
                },
                "wrap_up_ready": True,
            }
        }

        decision = decide_next_stage(
            next_turn_no=17,
            coverage_state=coverage_state,
            current_stage="Use Cases & Scenarios",
            max_turns=18,
        )

        self.assertEqual(decision["next_stage"], "Use Cases & Scenarios")
        self.assertTrue(decision["gaps"])


if __name__ == "__main__":
    unittest.main()
