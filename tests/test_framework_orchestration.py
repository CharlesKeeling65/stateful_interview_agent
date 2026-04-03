import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state
from app.services.question_planner import plan_next_question
from app.services.question_validator import validate_question_for_stage
from app.services.stage_manager import decide_next_stage


class FrameworkCoverageTests(unittest.TestCase):
    def test_rebuild_coverage_state_tracks_framework_targets_and_code_detail_counts(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What is the project trying to achieve?",
                answer_text=(
                    "The project helps support agents and operators process customer requests. "
                    "Its boundaries cover intake, workflow orchestration, and dashboard reporting. "
                    "Major modules include api_gateway, orchestration, and analytics. "
                    "The high-level workflow goes from intake to routing to reporting."
                ),
                answer_summary="Purpose, users, boundaries, major modules, and workflow were described.",
            ),
            InterviewTurn(
                id=2,
                turn_no=2,
                stage="Architecture Understanding",
                question_text="Q2: How are the modules organized?",
                answer_text=(
                    "The system is layered around an API gateway. Module responsibilities are split between auth, "
                    "orchestration, and analytics services. Communication uses HTTP and async events. "
                    "A key call chain flows from api_gateway -> auth -> orchestration. "
                    "The design rationale favors isolation and reliability."
                ),
                answer_summary="Architecture style, responsibilities, communication, call chains, and rationale are covered.",
            ),
            InterviewTurn(
                id=3,
                turn_no=3,
                stage="Code Detail Completion",
                question_text="Q3: Which code paths are most important?",
                answer_text=(
                    "Key files include app/api/routes/projects.py and app/services/question_generator.py. "
                    "The ProjectSession class coordinates state, and generate_next_question_from_history() "
                    "handles question writing. The execution path goes through submit_answer_and_generate_next -> "
                    "draft_next_question -> persist_next_step. OpenAI is the main third-party library. "
                    "Error handling raises HTTPException and logs workflow failures."
                ),
                answer_summary="Specific files, classes, methods, execution path, library usage, and error handling were covered.",
            ),
        ]

        coverage = rebuild_coverage_state(turns)
        framework = coverage["framework"]

        self.assertTrue(framework["panorama"]["purpose"])
        self.assertTrue(framework["panorama"]["target_users"])
        self.assertTrue(framework["architecture"]["module_responsibilities"])
        self.assertTrue(framework["architecture"]["key_call_chains"])
        self.assertGreaterEqual(framework["code_detail"]["key_files_count"], 2)
        self.assertGreaterEqual(framework["code_detail"]["key_methods_count"], 1)
        self.assertGreaterEqual(framework["code_detail"]["error_handling_count"], 1)


class StageControllerTests(unittest.TestCase):
    def test_stage_controller_stays_in_panorama_when_framework_gaps_remain(self):
        coverage_state = {
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
                "stage_turn_counts": {"Panorama Mapping": 2},
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=3,
            coverage_state=coverage_state,
            current_stage="Panorama Mapping",
            max_turns=40,
        )

        self.assertEqual(decision["next_stage"], "Panorama Mapping")
        self.assertIn("panorama", decision["reason"].lower())

    def test_stage_controller_moves_into_code_detail_when_foundations_are_ready(self):
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
                    "key_files_count": 0,
                    "key_classes_count": 0,
                    "key_methods_count": 0,
                    "execution_paths_count": 0,
                    "third_party_library_usage_count": 0,
                    "error_handling_count": 0,
                },
                "use_cases": {},
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 3,
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=6,
            coverage_state=coverage_state,
            current_stage="Architecture Understanding",
            max_turns=40,
        )

        self.assertEqual(decision["next_stage"], "Code Detail Completion")
        self.assertIn("code detail", decision["reason"].lower())


class PlannerAndValidatorTests(unittest.TestCase):
    def test_question_planner_prioritizes_concrete_code_detail_targets(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=4,
                stage="Architecture Understanding",
                question_text="Q4: Which modules collaborate on the request path?",
                answer_text="api_gateway hands requests to auth_service and orchestration_service.",
                answer_summary="api_gateway, auth_service, and orchestration_service collaborate on the request path.",
            ),
            InterviewTurn(
                id=2,
                turn_no=5,
                stage="Architecture Understanding",
                question_text="Q5: What is still unclear?",
                answer_text=None,
            ),
        ]

        coverage_state = {
            "branches": [
                {
                    "branch_id": "request_path",
                    "label": "request path through api_gateway and auth_service",
                    "stage": "Architecture Understanding",
                    "status": "needs_follow_up",
                    "priority": 0.94,
                    "keywords": ["api_gateway", "auth_service", "orchestration_service"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [4],
                    "summary": "api_gateway hands requests to auth_service and orchestration_service.",
                    "unresolved_points": ["Specific files and methods in the request path are still missing."],
                    "last_turn_no": 4,
                }
            ],
            "framework": {
                "code_detail": {
                    "key_files_count": 0,
                    "key_classes_count": 0,
                    "key_methods_count": 0,
                    "execution_paths_count": 0,
                    "third_party_library_usage_count": 0,
                    "error_handling_count": 0,
                }
            },
        }

        planner = plan_next_question(
            turns=turns,
            current_stage="Code Detail Completion",
            next_turn_no=6,
            coverage_state=coverage_state,
        )

        self.assertEqual(planner["question_intent"], "code_detail_deep_dive")
        self.assertIn(planner["target_type"], {"file", "class", "method", "execution_path"})
        self.assertTrue(planner["target_label"])
        self.assertTrue(planner["constraints"])

    def test_stage_validator_rejects_generic_code_detail_questions(self):
        invalid = validate_question_for_stage(
            text="Q11: How is this implemented in the project overall?",
            expected_turn_no=11,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
        )
        valid = validate_question_for_stage(
            text="Q11: In app/services/question_generator.py, how does generate_next_question_from_history build the prompt before calling OpenAI?",
            expected_turn_no=11,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
        )

        self.assertFalse(invalid["is_valid"])
        self.assertTrue(valid["is_valid"])
        self.assertTrue(invalid["reasons"])

    def test_stage_validator_rejects_change_proposal_questions_in_understand_mode(self):
        invalid = validate_question_for_stage(
            text="Q12: Which files should be modified to redesign the return type and update the related tests?",
            expected_turn_no=12,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
        )
        valid = validate_question_for_stage(
            text="Q12: In app/api/routes/projects.py, how does submit_answer_and_generate_next currently persist the answered turn before creating the next one?",
            expected_turn_no=12,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
        )

        self.assertFalse(invalid["is_valid"])
        self.assertTrue(
            any("change" in reason.lower() or "current code" in reason.lower() for reason in invalid["reasons"])
        )
        self.assertTrue(valid["is_valid"])


if __name__ == "__main__":
    unittest.main()
