import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.core.config import settings
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state, load_coverage_state
from app.services.question_planner import plan_next_question
from app.services.question_reviewer import review_question_plan
from app.services.repetition_guard import is_question_semantically_redundant
from app.services.question_validator import validate_question_for_stage, validate_queued_sub_questions
from app.services.rubric_task_service import initialize_task_board
from app.services.stage_manager import decide_next_stage
from app.services.question_queue_service import (
    build_queue_from_specs,
    detect_compound_question_candidate,
    decompose_code_detail_question_group,
    normalize_sub_question_text,
    renumber_sub_question_queue,
)


class FrameworkCoverageTests(unittest.TestCase):
    def test_rebuild_coverage_state_uses_same_version_as_default_state(self):
        coverage = rebuild_coverage_state([])

        self.assertEqual(coverage["version"], 3)
        self.assertIn("question_queue", coverage)
        self.assertIn("repo_file_coverage", coverage)
        self.assertIn("repo_tree_summary", coverage)
        self.assertIn("question_graph", coverage)
        self.assertIn("investigation_frontier", coverage)
        self.assertIn("developer_intent_coverage", coverage)
        self.assertIn("question_network_stats", coverage)

    def test_load_coverage_state_migrates_to_v3(self):
        project = ProjectSession(id=1, project_name="Test")
        # Simulate loading v2 state
        project.coverage_state = '{"version": 2, "branches": [], "branch_count": 0, "question_history": []}'
        coverage = load_coverage_state(project)
        self.assertEqual(coverage["version"], 3)
        self.assertEqual(coverage["question_queue"]["status"], "empty")
        self.assertEqual(coverage["repo_file_coverage"], {})
        self.assertEqual(coverage["repo_tree_summary"], {})
        self.assertEqual(coverage["question_graph"]["nodes"], [])
        self.assertEqual(coverage["question_graph"]["edges"], [])
        self.assertEqual(coverage["investigation_frontier"]["items"], [])
        self.assertIn("trace_execution", coverage["developer_intent_coverage"])
        self.assertEqual(coverage["question_network_stats"]["isolated_node_count"], 0)

    def test_rebuild_coverage_state_creates_question_graph_nodes_edges_and_frontier(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=3,
                stage="Code Detail Completion",
                question_text="Q3: In app/api/routes/projects.py, how does submit_answer_and_generate_next hand off into generate_question_for_state?",
                answer_text=(
                    "submit_answer_and_generate_next forwards the request into generate_question_for_state, "
                    "which rebuilds coverage, plans the next topic, and then grounds the prompt with repository context. "
                    "The follow-up gap is how the planner chooses the next target once coverage has been rebuilt."
                ),
                answer_summary=(
                    "The route hands off to generate_question_for_state and then into planner and repo grounding. "
                    "The planner target selection remains unresolved."
                ),
            ),
            InterviewTurn(
                id=2,
                turn_no=4,
                stage="Code Detail Completion",
                question_text="Q4: When generate_question_for_state rebuilds coverage, how does that affect the next planner target?",
                answer_text=(
                    "rebuild_coverage_state updates question_history and repository coverage scores. "
                    "That state then feeds plan_next_question. It is still unclear how neighboring files or downstream modules are considered."
                ),
                answer_summary=(
                    "Coverage state is rebuilt before plan_next_question runs. "
                    "Neighboring module expansion is still unclear."
                ),
            ),
        ]

        coverage = rebuild_coverage_state(turns)

        self.assertGreaterEqual(len(coverage["question_graph"]["nodes"]), 2)
        self.assertGreaterEqual(len(coverage["question_graph"]["edges"]), 1)
        self.assertGreaterEqual(len(coverage["investigation_frontier"]["items"]), 1)

        latest_node = coverage["question_graph"]["nodes"][-1]
        self.assertEqual(latest_node["turn_no"], 4)
        self.assertIn("artifact_keys", latest_node)
        self.assertIn("intent_type", latest_node)
        self.assertIn("depth_level", latest_node)

        latest_edge = coverage["question_graph"]["edges"][-1]
        self.assertIn(latest_edge["relation_type"], {"follows_from", "same_artifact", "same_concept"})
        self.assertTrue(latest_edge["from_node_id"])
        self.assertTrue(latest_edge["to_node_id"])

    def test_rebuild_coverage_state_tracks_developer_intent_distribution_and_network_stats(self):
        turns = [
            InterviewTurn(
                id=11,
                turn_no=8,
                stage="Code Detail Completion",
                question_text="Q8: In app/services/question_generator.py, how does generate_next_question_from_history build the current prompt?",
                answer_text="It builds the prompt from recent context and retrieved context before the model call.",
                answer_summary="Prompt construction path is covered.",
            ),
            InterviewTurn(
                id=12,
                turn_no=9,
                stage="Code Detail Completion",
                question_text="Q9: When that prompt fails to produce a usable result, how does the current error path recover?",
                answer_text="Validation and local repair run first, and then the fallback refiner handles repairable issues.",
                answer_summary="Failure handling and fallback behavior are covered.",
            ),
        ]

        coverage = rebuild_coverage_state(turns)

        self.assertGreaterEqual(coverage["developer_intent_coverage"]["trace_execution"], 1)
        self.assertGreaterEqual(coverage["developer_intent_coverage"]["investigate_failure"], 1)
        self.assertGreaterEqual(coverage["question_network_stats"]["connected_edge_count"], 1)
        self.assertEqual(coverage["question_network_stats"]["isolated_node_count"], 0)

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
        self.assertTrue(framework["panorama"]["initial_module_relationships"])
        self.assertGreaterEqual(framework["code_detail"]["specific_files_count"], 2)
        self.assertGreaterEqual(framework["code_detail"]["specific_methods_count"], 1)
        self.assertGreaterEqual(framework["code_detail"]["error_handling_points_count"], 1)
        self.assertGreaterEqual(framework["code_detail"]["protocol_implementation_points_count"], 1)

    def test_rebuild_coverage_state_tracks_use_case_scenario_contract(self):
        turns = [
            InterviewTurn(
                id=8,
                turn_no=14,
                stage="Use Cases & Scenarios",
                question_text="Q14: Walk through one representative scenario from trigger to result.",
                answer_text=(
                    "A support operator triggers the process by opening a new escalation. "
                    "The actor is the support operator. Inputs include the case payload and account metadata. "
                    "The process routes the request through intake, orchestration, and reporting. "
                    "The output is an updated case record and a ranked handling plan. "
                    "Boundary conditions include missing account data and unsupported escalation types. "
                    "An extension point allows a custom routing policy."
                ),
                answer_summary="One scenario covers trigger, actor, inputs, process, outputs, boundaries, and extension points.",
            )
        ]

        framework = rebuild_coverage_state(turns)["framework"]
        self.assertGreaterEqual(framework["use_cases"]["representative_scenarios_count"], 1)
        self.assertGreaterEqual(framework["use_cases"]["actors_roles_count"], 1)
        self.assertGreaterEqual(framework["use_cases"]["input_output_patterns_count"], 1)
        self.assertGreaterEqual(framework["use_cases"]["boundary_conditions_count"], 1)
        self.assertGreaterEqual(framework["use_cases"]["extension_points_count"], 1)

    def test_validator_can_skip_graph_continuity_requirements_when_flag_disabled(self):
        with patch.object(settings, "graph_continuity_validation_enabled", False, create=True):
            result = validate_question_for_stage(
                text="Q6: In app/services/question_generator.py, how does generate_next_question_from_history build the current prompt?",
                expected_turn_no=6,
                current_stage="Code Detail Completion",
                recent_question_signatures=[],
                developer_intent=None,
                relation_type=None,
            )

        self.assertTrue(result["is_valid"], result["reasons"])


class StageControllerTests(unittest.TestCase):
    def test_stage_controller_reserves_final_two_turns_for_use_cases_under_42_turn_cap(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 16,
                    "specific_classes_count": 7,
                    "specific_methods_count": 18,
                    "execution_paths_count": 10,
                    "library_usage_points_count": 5,
                    "error_handling_points_count": 4,
                    "protocol_implementation_points_count": 3,
                    "state_management_points_count": 2,
                },
                "use_cases": {
                    "representative_scenarios_count": 0,
                    "actors_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {},
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 2,
                    "Code Detail Completion": 35,
                    "Use Cases & Scenarios": 0,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": [],
                    "use_cases": ["representative_scenarios_count", "actors_roles_count"],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            }
        }

        decision_before_window = decide_next_stage(
            next_turn_no=40,
            coverage_state=coverage_state,
            current_stage="Code Detail Completion",
            max_turns=42,
        )
        self.assertEqual(decision_before_window["next_stage"], "Code Detail Completion")

        coverage_state["framework"]["stage_turn_counts"]["Code Detail Completion"] = 36
        decision_in_window = decide_next_stage(
            next_turn_no=41,
            coverage_state=coverage_state,
            current_stage="Code Detail Completion",
            max_turns=42,
        )
        self.assertEqual(decision_in_window["next_stage"], "Use Cases & Scenarios")

    def test_stage_controller_uses_two_architecture_turns_before_code_detail(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 0,
                    "specific_classes_count": 0,
                    "specific_methods_count": 0,
                    "execution_paths_count": 0,
                    "library_usage_points_count": 0,
                    "error_handling_points_count": 0,
                    "protocol_implementation_points_count": 0,
                    "state_management_points_count": 0,
                },
                "use_cases": {},
                "human_collaboration": {},
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 2,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": ["specific_files_count", "specific_methods_count"],
                    "use_cases": [],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=5,
            coverage_state=coverage_state,
            current_stage="Architecture Understanding",
            max_turns=42,
        )

        self.assertEqual(decision["next_stage"], "Code Detail Completion")

    def test_stage_controller_never_enters_wrap_up_for_43_turn_cap(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 20,
                    "specific_classes_count": 10,
                    "specific_methods_count": 24,
                    "execution_paths_count": 12,
                    "library_usage_points_count": 8,
                    "error_handling_points_count": 6,
                    "protocol_implementation_points_count": 4,
                    "state_management_points_count": 3,
                },
                "use_cases": {
                    "representative_scenarios_count": 1,
                    "actors_roles_count": 1,
                    "input_output_patterns_count": 1,
                    "boundary_conditions_count": 1,
                    "extension_points_count": 0,
                },
                "human_collaboration": {},
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 2,
                    "Code Detail Completion": 37,
                    "Use Cases & Scenarios": 1,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": [],
                    "use_cases": [],
                    "human_collaboration": [],
                },
                "wrap_up_ready": True,
            }
        }

        decision = decide_next_stage(
            next_turn_no=43,
            coverage_state=coverage_state,
            current_stage="Use Cases & Scenarios",
            max_turns=43,
        )

        self.assertEqual(decision["next_stage"], "Use Cases & Scenarios")

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
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 0,
                    "specific_classes_count": 0,
                    "specific_methods_count": 0,
                    "execution_paths_count": 0,
                    "library_usage_points_count": 0,
                    "error_handling_points_count": 0,
                    "protocol_implementation_points_count": 0,
                    "state_management_points_count": 0,
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

    def test_stage_controller_keeps_code_detail_after_architecture_when_use_case_gaps_exist(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 1,
                    "specific_classes_count": 0,
                    "specific_methods_count": 1,
                    "execution_paths_count": 1,
                    "library_usage_points_count": 0,
                    "error_handling_points_count": 0,
                    "protocol_implementation_points_count": 0,
                    "state_management_points_count": 0,
                },
                "use_cases": {
                    "representative_scenarios_count": 0,
                    "actors_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                },
                "stage_turn_counts": {
                    "Panorama Mapping": 3,
                    "Architecture Understanding": 3,
                    "Code Detail Completion": 2,
                    "Use Cases & Scenarios": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": ["specific_classes_count", "error_handling_points_count"],
                    "use_cases": ["representative_scenarios_count", "actors_roles_count"],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=10,
            coverage_state=coverage_state,
            current_stage="Architecture Understanding",
            max_turns=40,
        )

        self.assertEqual(decision["next_stage"], "Code Detail Completion")

    def test_stage_controller_allows_architecture_to_use_case_when_human_explicitly_requests_it(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 1,
                    "specific_classes_count": 0,
                    "specific_methods_count": 1,
                    "execution_paths_count": 1,
                    "library_usage_points_count": 0,
                    "error_handling_points_count": 0,
                    "protocol_implementation_points_count": 0,
                    "state_management_points_count": 0,
                },
                "use_cases": {
                    "representative_scenarios_count": 0,
                    "actors_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                },
                "stage_turn_counts": {
                    "Panorama Mapping": 3,
                    "Architecture Understanding": 3,
                    "Code Detail Completion": 2,
                    "Use Cases & Scenarios": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": ["specific_classes_count", "error_handling_points_count"],
                    "use_cases": ["representative_scenarios_count", "actors_roles_count"],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=10,
            coverage_state=coverage_state,
            current_stage="Architecture Understanding",
            max_turns=40,
            human_review_signal={"preferred_next_focus": "use_case"},
        )

        self.assertEqual(decision["next_stage"], "Code Detail Completion")

    def test_stage_controller_stays_in_code_detail_before_hardcoded_turn_window_even_if_coverage_is_strong(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 12,
                    "specific_classes_count": 7,
                    "specific_methods_count": 14,
                    "execution_paths_count": 8,
                    "library_usage_points_count": 4,
                    "error_handling_points_count": 5,
                    "protocol_implementation_points_count": 3,
                    "state_management_points_count": 2,
                },
                "use_cases": {
                    "representative_scenarios_count": 0,
                    "actors_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {
                    "judgment_turn_count": 2,
                    "correction_turn_count": 1,
                    "redirection_turn_count": 1,
                    "prioritization_turn_count": 1,
                },
                "stage_turn_counts": {
                    "Panorama Mapping": 5,
                    "Architecture Understanding": 4,
                    "Code Detail Completion": 18,
                    "Use Cases & Scenarios": 0,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": [],
                    "use_cases": [
                        "representative_scenarios_count",
                        "actors_roles_count",
                        "input_output_patterns_count",
                    ],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=34,
            coverage_state=coverage_state,
            current_stage="Code Detail Completion",
            max_turns=40,
        )

        self.assertEqual(decision["next_stage"], "Code Detail Completion")
        self.assertIn("hard-gated", decision["reason"].lower())

    def test_stage_controller_for_45_turn_cap_keeps_code_detail_until_final_two_turns(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "collaboration_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 20,
                    "specific_classes_count": 10,
                    "specific_methods_count": 24,
                    "execution_paths_count": 12,
                    "library_usage_points_count": 8,
                    "error_handling_points_count": 6,
                    "protocol_implementation_points_count": 4,
                    "state_management_points_count": 3,
                },
                "use_cases": {
                    "representative_scenarios_count": 0,
                    "actors_roles_count": 0,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "human_collaboration": {
                    "human_judgment_turn_count": 2,
                    "human_correction_turn_count": 1,
                    "human_redirection_turn_count": 0,
                    "human_prioritization_turn_count": 1,
                },
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 3,
                    "Code Detail Completion": 29,
                    "Use Cases & Scenarios": 0,
                    "Final Wrap-up": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": [],
                    "use_cases": [
                        "representative_scenarios_count",
                        "actors_roles_count",
                        "input_output_patterns_count",
                        "boundary_conditions_count",
                    ],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=34,
            coverage_state=coverage_state,
            current_stage="Code Detail Completion",
            max_turns=45,
        )

        self.assertEqual(decision["next_stage"], "Code Detail Completion")
        self.assertIn("turn 43", decision["reason"].lower())


class QuestionQueueTests(unittest.TestCase):
    def test_detect_compound_question_candidate(self):
        self.assertTrue(detect_compound_question_candidate("What does function X do? And how does it handle errors?"))
        self.assertFalse(detect_compound_question_candidate("What does function X do?"))
        
    def test_decompose_code_detail_question_group(self):
        queued = decompose_code_detail_question_group(
            "How does handle_request work? What is the edge case policy?",
            base_turn_no=12
        )
        self.assertEqual(len(queued), 2)
        self.assertEqual(queued[0].question_text, "Q12: How does handle_request work?")
        self.assertEqual(queued[0].turn_offset, 0)
        self.assertEqual(queued[1].question_text, "Q13: What is the edge case policy?")
        self.assertEqual(queued[1].turn_offset, 1)

    def test_renumber_sub_question_queue(self):
        queued = decompose_code_detail_question_group(
            "First question? Second question?",
            base_turn_no=5
        )
        # Shift to base_turn_no = 8
        renumbered = renumber_sub_question_queue(queued, 8)
        self.assertEqual(renumbered[0].question_text, "Q8: First question?")
        self.assertEqual(renumbered[1].question_text, "Q9: Second question?")

    def test_build_queue_from_specs_preserves_relation_metadata(self):
        queued = build_queue_from_specs(
            [
                {
                    "focus_kind": "error_path",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "relation_type": "same_artifact",
                    "developer_intent": "investigate_failure",
                    "parent_node_id": "turn-12",
                    "priority_score": 0.91,
                },
                {
                    "focus_kind": "library_usage",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "relation_type": "downstream_of",
                    "developer_intent": "check_dependency_usage",
                    "parent_node_id": "turn-12",
                    "priority_score": 0.67,
                },
            ],
            base_turn_no=13,
            intent="code_detail_deep_dive",
            target_branch_id="generator-thread",
            target_type="file",
            target_label="app/services/question_generator.py",
            seed_question_text="Q12: In app/services/question_generator.py, how does generate_next_question_from_history build the current prompt?",
        )
        self.assertEqual(queued[0].parent_node_id, "turn-12")
        self.assertEqual(queued[0].relation_type, "same_artifact")
        self.assertEqual(queued[0].developer_intent, "investigate_failure")
        self.assertEqual(queued[0].priority_score, 0.91)
        self.assertTrue(queued[0].node_id)

    def test_validate_queued_sub_questions(self):
        reasons = validate_queued_sub_questions([
            "Q12: How does auth.py handle missing tokens?",  # Valid
            "Q13: Does it retry?"                            # Invalid (yes/no, relies on 'it')
        ])
        self.assertTrue(any("avoid yes/no" in r for r in reasons))
        self.assertTrue(any("rely on previous siblings" in r for r in reasons))


class PlannerAndValidatorTests(unittest.TestCase):
    def test_question_planner_switches_to_a_different_code_file_when_recent_file_was_covered(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "projects_route",
                    "label": "app/api/routes/projects.py request flow",
                    "stage": "Code Detail Completion",
                    "status": "needs_follow_up",
                    "priority": 0.95,
                    "keywords": ["projects.py", "route flow"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [12],
                    "summary": "app/api/routes/projects.py coordinates request validation and persistence.",
                    "unresolved_points": ["Need the detailed persistence call path."],
                    "last_turn_no": 12,
                },
                {
                    "branch_id": "planner_path",
                    "label": "app/services/question_planner.py selection path",
                    "stage": "Code Detail Completion",
                    "status": "needs_follow_up",
                    "priority": 0.93,
                    "keywords": ["question_planner.py", "selection path"],
                    "evidence_turn_ids": [2],
                    "evidence_turn_nos": [13],
                    "summary": "question_planner.py uses choose_non_redundant_code_detail_target() to vary targets.",
                    "unresolved_points": ["Need the branch switching logic in detail."],
                    "last_turn_no": 13,
                },
            ],
            "framework": {
                "code_detail": {
                    "specific_files_count": 2,
                    "specific_classes_count": 0,
                    "specific_methods_count": 1,
                    "execution_paths_count": 1,
                    "library_usage_points_count": 0,
                    "error_handling_points_count": 0,
                    "protocol_implementation_points_count": 0,
                    "state_management_points_count": 0,
                },
                "gaps": {
                    "code_detail": ["specific_files_count", "specific_methods_count"],
                },
                "human_collaboration": {
                    "judgment_turn_count": 1,
                    "correction_turn_count": 1,
                    "redirection_turn_count": 1,
                    "prioritization_turn_count": 1,
                },
                "stage_turn_counts": {"Code Detail Completion": 12},
            },
            "question_history": [
                {
                    "turn_no": 12,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "projects_route",
                    "target_type": "file",
                    "target_label": "app/api/routes/projects.py",
                    "signature": "Code Detail Completion|code_detail_deep_dive|projects_route|file|app/api/routes/projects.py",
                }
            ],
        }

        planner = plan_next_question(
            turns=[],
            current_stage="Code Detail Completion",
            next_turn_no=13,
            coverage_state=coverage_state,
        )

        self.assertEqual(planner["question_intent"], "code_detail_deep_dive")
        self.assertEqual(planner["target_branch_id"], "planner_path")
        self.assertNotEqual(planner["target_label"], "app/api/routes/projects.py")
        self.assertIn("avoids recently repeated questions", planner["why_this_question"])

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
        self.assertEqual(planner["intent_mode"], "understand_current_code")
        self.assertIsNotNone(planner["selected_framework_gap"])

    def test_question_planner_avoids_recently_asked_same_code_detail_target(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=9,
                stage="Code Detail Completion",
                question_text="Q9: In app/services/question_generator.py, how does generate_next_question_from_history currently build the prompt before calling OpenAI?",
                answer_text="It renders a stage-specific prompt and then calls the OpenAI-compatible chat completions API.",
                answer_summary="question_generator.py builds the prompt and calls the model.",
            ),
        ]

        coverage_state = {
            "branches": [
                {
                    "branch_id": "question_generator",
                    "label": "app/services/question_generator.py prompt rendering path",
                    "stage": "Code Detail Completion",
                    "status": "needs_follow_up",
                    "priority": 0.98,
                    "keywords": ["question_generator.py", "render_prompt", "call_llm"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [9],
                    "summary": "question_generator.py builds the prompt before calling the model.",
                    "unresolved_points": ["Need to inspect validation and persistence path next."],
                    "last_turn_no": 9,
                },
                {
                    "branch_id": "persist_next_step",
                    "label": "app/graphs/interview_nodes.py persist_next_step path",
                    "stage": "Code Detail Completion",
                    "status": "needs_follow_up",
                    "priority": 0.91,
                    "keywords": ["interview_nodes.py", "persist_next_step", "pending_turn_id"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [9],
                    "summary": "persist_next_step updates the answered turn and creates the next one.",
                    "unresolved_points": ["Need to inspect how the stale pending turn is guarded."],
                    "last_turn_no": 9,
                },
            ],
            "framework": {
                "code_detail": {
                    "key_files_count": 1,
                    "key_classes_count": 0,
                    "key_methods_count": 1,
                    "execution_paths_count": 0,
                    "third_party_library_usage_count": 1,
                    "error_handling_count": 0,
                }
            },
            "question_history": [
                {
                    "turn_no": 9,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "question_generator",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "signature": "Code Detail Completion|code_detail_deep_dive|question_generator|file|app/services/question_generator.py",
                }
            ],
        }

        planner = plan_next_question(
            turns=turns,
            current_stage="Code Detail Completion",
            next_turn_no=10,
            coverage_state=coverage_state,
        )

        self.assertEqual(planner["question_intent"], "code_detail_deep_dive")
        self.assertNotEqual(planner["target_label"], "app/services/question_generator.py")
        self.assertNotEqual(planner.get("target_branch_id"), "question_generator")
        self.assertIn("recent", planner["why_this_question"].lower())

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
            developer_intent="trace_execution",
            relation_type="same_artifact",
        )

        self.assertFalse(invalid["is_valid"])
        self.assertTrue(valid["is_valid"])
        self.assertTrue(invalid["reasons"])

    def test_stage_validator_rejects_code_detail_question_without_intent_or_graph_linkage(self):
        invalid = validate_question_for_stage(
            text="Q11: In app/services/question_generator.py, how does generate_next_question_from_history currently work?",
            expected_turn_no=11,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
            developer_intent=None,
            relation_type=None,
        )
        valid = validate_question_for_stage(
            text="Q11: In app/services/question_generator.py, how does generate_next_question_from_history currently handle the validator handoff?",
            expected_turn_no=11,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
            developer_intent="trace_execution",
            relation_type="same_artifact",
        )

        self.assertFalse(invalid["is_valid"])
        self.assertTrue(any("developer intent" in reason.lower() or "graph linkage" in reason.lower() for reason in invalid["reasons"]))
        self.assertTrue(valid["is_valid"])

    def test_reviewer_flags_plan_without_developer_intent(self):
        review = review_question_plan(
            planner_decision={
                "question_intent": "code_detail_deep_dive",
                "target_label": "app/services/question_generator.py",
                "target_type": "file",
                "relation_type": None,
                "developer_intent": None,
                "confidence": 0.72,
                "intent_mode": "understand_current_code",
            },
            mode="understand_current_code",
            task_board=initialize_task_board(),
            coverage_state={"framework": {"wrap_up_ready": False}},
            current_stage="Code Detail Completion",
        )

        self.assertTrue(review.approved)
        self.assertTrue(any("developer intent" in item.lower() for item in review.suggested_modifications))

    def test_reviewer_surfaces_network_degradation_diagnostics(self):
        review = review_question_plan(
            planner_decision={
                "question_intent": "code_detail_deep_dive",
                "target_label": "app/services/question_generator.py",
                "target_type": "file",
                "relation_type": "same_artifact",
                "developer_intent": "trace_execution",
                "confidence": 0.82,
                "intent_mode": "understand_current_code",
            },
            mode="understand_current_code",
            task_board=initialize_task_board(),
            coverage_state={
                "framework": {"wrap_up_ready": False},
                "question_network_stats": {
                    "node_count": 6,
                    "connected_edge_count": 2,
                    "isolated_node_count": 3,
                },
                "developer_intent_coverage": {
                    "trace_execution": 5,
                    "investigate_failure": 0,
                    "inspect_inputs_outputs": 0,
                },
                "question_history": [
                    {
                        "turn_no": 8,
                        "stage": "Code Detail Completion",
                        "question_text": "Q8: How does retry logic handle timeout escalation?",
                    },
                    {
                        "turn_no": 9,
                        "stage": "Code Detail Completion",
                        "question_text": "Q9: How does retry logic handle retry backoff?",
                    },
                ],
                "investigation_frontier": {"items": []},
            },
            current_stage="Code Detail Completion",
        )

        self.assertTrue(review.approved)
        self.assertTrue(any("isolated" in item.lower() for item in review.suggested_modifications))
        self.assertTrue(any("intent" in item.lower() for item in review.suggested_modifications))

    def test_question_planner_prefers_macro_panorama_gap_before_local_branch(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "retry_edge_case",
                    "label": "retry edge-case handling in workflow_runner.py",
                    "stage": "Panorama Mapping",
                    "status": "needs_follow_up",
                    "priority": 0.98,
                    "keywords": ["retry", "edge", "workflow_runner.py"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [1],
                    "summary": "A narrow retry branch appeared before the global workflow was explained.",
                    "unresolved_points": ["The global workflow is still missing."],
                    "last_turn_no": 1,
                }
            ],
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": False,
                    "major_modules": True,
                    "high_level_workflow": False,
                    "initial_module_relationships": False,
                },
                "architecture": {},
                "code_detail": {},
                "use_cases": {},
                "human_collaboration": {},
                "stage_turn_counts": {"Panorama Mapping": 1},
                "gaps": {
                    "panorama": ["boundaries", "high_level_workflow", "initial_module_relationships"],
                    "architecture": [],
                    "code_detail": [],
                    "use_cases": [],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            },
        }

        planner = plan_next_question(
            turns=[],
            current_stage="Panorama Mapping",
            next_turn_no=2,
            coverage_state=coverage_state,
        )

        self.assertEqual(planner["question_intent"], "overview_gap_fill")
        self.assertEqual(planner["selected_framework_gap"], "boundaries")
        self.assertEqual(planner["target_type"], "framework_gap")
        self.assertIn("macro", " ".join(planner["constraints"]).lower())

    def test_question_planner_builds_structured_use_case_contract(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "operator_scenario",
                    "label": "operator handles a new escalation through the current workflow",
                    "stage": "Use Cases & Scenarios",
                    "status": "needs_follow_up",
                    "priority": 0.88,
                    "keywords": ["operator", "escalation", "workflow"],
                    "evidence_turn_ids": [11],
                    "evidence_turn_nos": [11],
                    "summary": "The actor and trigger are known, but the outputs and boundaries are incomplete.",
                    "unresolved_points": ["Need the current outputs and failure boundaries."],
                    "last_turn_no": 11,
                }
            ],
            "framework": {
                "use_cases": {
                    "representative_scenarios_count": 1,
                    "actors_roles_count": 1,
                    "input_output_patterns_count": 0,
                    "boundary_conditions_count": 0,
                    "extension_points_count": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [],
                    "code_detail": [],
                    "use_cases": [
                        "input_output_patterns_count",
                        "boundary_conditions_count",
                        "extension_points_count",
                    ],
                    "human_collaboration": [],
                },
                "human_collaboration": {},
                "stage_turn_counts": {"Use Cases & Scenarios": 1},
                "wrap_up_ready": False,
            },
        }

        planner = plan_next_question(
            turns=[],
            current_stage="Use Cases & Scenarios",
            next_turn_no=12,
            coverage_state=coverage_state,
        )

        self.assertEqual(planner["question_intent"], "scenario_completion")
        self.assertEqual(planner["selected_framework_gap"], "input_output_patterns_count")
        self.assertIn("trigger", " ".join(planner["constraints"]).lower())
        self.assertIn("outputs", " ".join(planner["constraints"]).lower())

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
            developer_intent="trace_execution",
            relation_type="same_artifact",
        )

        self.assertFalse(invalid["is_valid"])
        self.assertTrue(
            any("change" in reason.lower() or "current code" in reason.lower() for reason in invalid["reasons"])
        )
        self.assertTrue(valid["is_valid"])

    def test_stage_validator_rejects_semantically_redundant_recent_question(self):
        invalid = validate_question_for_stage(
            text="Q18: In app/services/question_generator.py, how does generate_next_question_from_history currently assemble the prompt right before the model call?",
            expected_turn_no=18,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
            developer_intent="trace_execution",
            relation_type="same_artifact",
            recent_question_signatures=[
                {
                    "turn_no": 17,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "question_generator",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "signature": "Code Detail Completion|code_detail_deep_dive|question_generator|file|app/services/question_generator.py",
                    "question_text": "Q17: In app/services/question_generator.py, how does generate_next_question_from_history build the prompt before calling OpenAI?",
                }
            ],
        )

        self.assertFalse(invalid["is_valid"])
        self.assertTrue(any("similar" in reason.lower() or "already" in reason.lower() for reason in invalid["reasons"]))

    def test_stage_validator_rejects_repeated_question_opening_pattern(self):
        invalid = validate_question_for_stage(
            text="Q19: In app/services/question_generator.py, how does generate_next_question_from_history handle retry recovery?",
            expected_turn_no=19,
            current_stage="Code Detail Completion",
            intent_mode="understand_current_code",
            developer_intent="investigate_failure",
            relation_type="same_artifact",
            recent_question_signatures=[
                {
                    "turn_no": 17,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "question_generator",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "signature": "s1",
                    "question_text": "Q17: In app/services/question_generator.py, how does generate_next_question_from_history build the prompt?",
                },
                {
                    "turn_no": 18,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "question_generator",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "signature": "s2",
                    "question_text": "Q18: In app/services/question_generator.py, how does generate_next_question_from_history validate the repaired question?",
                },
            ],
        )

        self.assertFalse(invalid["is_valid"])
        self.assertTrue(any("opening pattern" in reason.lower() for reason in invalid["reasons"]))

    def test_semantic_duplicate_guard_can_use_optional_embeddings(self):
        with patch("app.services.repetition_guard.settings.duplicate_guard_use_embeddings", True), patch(
            "app.services.repetition_guard.settings.duplicate_guard_embedding_threshold", 0.9
        ), patch("app.services.repetition_guard.get_embedding_similarity", return_value=0.96):
            is_redundant = is_question_semantically_redundant(
                text="Q18: In app/services/question_generator.py, how does that prompt assembly path work immediately before the model call?",
                stage="Code Detail Completion",
                intent="code_detail_deep_dive",
                branch_id="question_generator",
                recent_question_signatures=[
                    {
                        "turn_no": 17,
                        "stage": "Code Detail Completion",
                        "intent": "code_detail_deep_dive",
                        "branch_id": "question_generator_alt",
                        "target_type": "topic",
                        "target_label": "prompt assembly path",
                        "signature": "different-signature",
                        "question_text": "Q17: Walk me through the prompt assembly path before the OpenAI call in question_generator.",
                    }
                ],
            )

        self.assertTrue(is_redundant)


class CoverageCountingTests(unittest.TestCase):
    def test_use_case_counts_do_not_get_falsely_satisfied_by_code_detail_keyword_hits(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=30,
                stage="Code Detail Completion",
                question_text="Q30: In typer_agent.py, how are input payloads parsed and how are boundary errors logged in the current execution path?",
                answer_text=(
                    "The current code parses the input payload in typer_agent.py, passes it into the execution path, "
                    "and logs boundary or exception cases when subprocess execution fails."
                ),
                answer_summary="Code-detail answer discussing input payload parsing and boundary error logging.",
            )
        ]

        coverage = rebuild_coverage_state(turns)
        use_cases = coverage["framework"]["use_cases"]

        self.assertEqual(use_cases["representative_scenarios_count"], 0)
        self.assertEqual(use_cases["actors_roles_count"], 0)
        self.assertEqual(use_cases["input_output_patterns_count"], 0)
        self.assertEqual(use_cases["boundary_conditions_count"], 0)

    def test_stage_controller_keeps_architecture_until_core_structure_is_covered(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "communication_mechanisms": False,
                    "key_call_chains": False,
                    "system_structure": False,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {},
                "use_cases": {},
                "human_collaboration": {},
                "stage_turn_counts": {
                    "Panorama Mapping": 2,
                    "Architecture Understanding": 2,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": [
                        "communication_mechanisms",
                        "key_call_chains",
                        "system_structure",
                    ],
                    "code_detail": [],
                    "use_cases": [],
                    "human_collaboration": [],
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

        self.assertEqual(decision["next_stage"], "Architecture Understanding")
        self.assertIn("architecture", decision["reason"].lower())

    def test_stage_controller_does_not_regress_after_manual_stage_advance(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": False,
                    "target_users": False,
                    "boundaries": False,
                    "major_modules": False,
                    "high_level_workflow": False,
                    "initial_module_relationships": False,
                },
                "architecture": {
                    "architecture_style_or_organization": True,
                    "module_responsibilities": True,
                    "communication_mechanisms": True,
                    "key_call_chains": True,
                    "system_structure": True,
                    "design_rationale_or_quality_attributes": True,
                },
                "code_detail": {
                    "specific_files_count": 1,
                    "specific_methods_count": 0,
                    "execution_paths_count": 0,
                    "error_handling_points_count": 0,
                },
                "use_cases": {},
                "human_collaboration": {},
                "stage_turn_counts": {
                    "Architecture Understanding": 3,
                    "Code Detail Completion": 1,
                },
                "gaps": {
                    "panorama": [
                        "purpose",
                        "target_users",
                        "major_modules",
                        "high_level_workflow",
                    ],
                    "architecture": [],
                    "code_detail": [
                        "specific_methods_count",
                        "execution_paths_count",
                    ],
                    "use_cases": [],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            }
        }

        decision = decide_next_stage(
            next_turn_no=7,
            coverage_state=coverage_state,
            current_stage="Code Detail Completion",
            max_turns=40,
        )

        self.assertEqual(decision["next_stage"], "Code Detail Completion")


if __name__ == "__main__":
    unittest.main()
