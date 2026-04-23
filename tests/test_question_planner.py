import os
import unittest
from unittest.mock import patch
from app.services.question_planner import plan_next_question
from app.core.config import settings

os.environ.setdefault("OPENAI_API_KEY", "test-key")

class QuestionPlannerTests(unittest.TestCase):
    def test_plan_next_question_can_disable_graph_frontier_planning(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "fallback-branch",
                    "label": "app/services/question_generator.py",
                    "stage": "Code Detail Completion",
                    "status": "needs_follow_up",
                    "priority": 0.9,
                    "keywords": ["question_generator.py"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [8],
                    "summary": "Fallback branch for code detail planning.",
                    "unresolved_points": [],
                    "last_turn_no": 8,
                }
            ],
            "investigation_frontier": {
                "items": [
                    {
                        "source_node_id": "turn-8",
                        "target_label": "app/services/question_planner.py",
                        "target_type": "file",
                        "relation_type": "downstream_of",
                        "developer_intent": "connect_related_module",
                        "depth_kind": "breadth",
                        "breadth_kind": "downstream_module",
                        "priority": 0.82,
                        "label": "Follow the planner side of the same handoff.",
                    }
                ]
            },
            "framework": {
                "stage_turn_counts": {"Code Detail Completion": 2},
                "human_collaboration": {
                    "human_judgment_turn_count": 1,
                    "human_correction_turn_count": 1,
                    "human_redirection_turn_count": 1,
                    "human_prioritization_turn_count": 1,
                },
                "gaps": {"code_detail": []},
            },
        }

        with patch.object(settings, "graph_frontier_planning_enabled", False, create=True):
            decision = plan_next_question(
                turns=[],
                current_stage="Code Detail Completion",
                next_turn_no=9,
                coverage_state=coverage_state,
            )

        self.assertEqual(decision["target_label"], "app/services/question_generator.py")
        self.assertNotIn("source_node_id", decision)

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

    def test_plan_next_question_prefers_connected_frontier_candidate_over_isolated_branch(self):
        coverage_state = {
            "branches": [
                {
                    "branch_id": "isolated-branch",
                    "label": "app/services/unrelated_service.py",
                    "stage": "Code Detail Completion",
                    "status": "partial",
                    "priority": 0.95,
                    "keywords": ["unrelated_service.py"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [5],
                    "summary": "A separate branch with little connection to the active investigation thread.",
                    "unresolved_points": [],
                    "last_turn_no": 5,
                }
            ],
            "question_history": [
                {
                    "turn_no": 8,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "active-thread",
                    "target_type": "file",
                    "target_label": "app/graphs/interview_nodes.py",
                    "signature": "Code Detail Completion|code_detail_deep_dive|active-thread|file|app/graphs/interview_nodes.py",
                    "question_text": "Q8: In app/graphs/interview_nodes.py, how does generate_question_for_state currently coordinate planning and grounding?",
                    "answer_summary": "The interview node rebuilds coverage and then hands off to planner and repo grounding.",
                }
            ],
            "investigation_frontier": {
                "items": [
                    {
                        "source_node_id": "turn-8",
                        "target_label": "app/services/question_planner.py",
                        "target_type": "file",
                        "relation_type": "downstream_of",
                        "developer_intent": "connect_related_module",
                        "depth_kind": "breadth",
                        "breadth_kind": "downstream_module",
                        "priority": 0.82,
                        "label": "Follow the planner side of the same handoff.",
                    }
                ]
            },
            "framework": {
                "stage_turn_counts": {"Code Detail Completion": 2},
                "human_collaboration": {
                    "human_judgment_turn_count": 1,
                    "human_correction_turn_count": 1,
                    "human_redirection_turn_count": 1,
                    "human_prioritization_turn_count": 1,
                },
                "gaps": {
                    "code_detail": [],
                },
            },
        }

        decision = plan_next_question(
            turns=[],
            current_stage="Code Detail Completion",
            next_turn_no=9,
            coverage_state=coverage_state,
        )

        self.assertEqual(decision["target_label"], "app/services/question_planner.py")
        self.assertEqual(decision["relation_type"], "downstream_of")
        self.assertEqual(decision["source_node_id"], "turn-8")
        self.assertEqual(decision["developer_intent"], "connect_related_module")
        self.assertIn("connected frontier", decision["why_this_question"])

    def test_plan_next_question_prefers_deeper_same_artifact_frontier_before_breadth_expansion(self):
        coverage_state = {
            "question_history": [
                {
                    "turn_no": 12,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "generator-thread",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "signature": "Code Detail Completion|code_detail_deep_dive|generator-thread|file|app/services/question_generator.py",
                    "question_text": "Q12: In app/services/question_generator.py, how does generate_next_question_from_history build the current prompt?",
                    "answer_summary": "The prompt build path is clear, but the error path is still unresolved.",
                }
            ],
            "investigation_frontier": {
                "items": [
                    {
                        "source_node_id": "turn-12",
                        "target_label": "app/services/question_generator.py",
                        "target_type": "file",
                        "relation_type": "same_artifact",
                        "developer_intent": "investigate_failure",
                        "depth_kind": "deep",
                        "breadth_kind": "same_artifact",
                        "priority": 0.76,
                        "label": "Drill into the repair and fallback path inside the same file.",
                    },
                    {
                        "source_node_id": "turn-12",
                        "target_label": "app/services/question_validator.py",
                        "target_type": "file",
                        "relation_type": "downstream_of",
                        "developer_intent": "connect_related_module",
                        "depth_kind": "breadth",
                        "breadth_kind": "downstream_module",
                        "priority": 0.88,
                        "label": "Expand into the validator side next.",
                    },
                ]
            },
            "framework": {
                "stage_turn_counts": {"Code Detail Completion": 5},
                "human_collaboration": {
                    "human_judgment_turn_count": 1,
                    "human_correction_turn_count": 1,
                    "human_redirection_turn_count": 1,
                    "human_prioritization_turn_count": 1,
                },
                "gaps": {
                    "code_detail": [],
                },
            },
        }

        decision = plan_next_question(
            turns=[],
            current_stage="Code Detail Completion",
            next_turn_no=13,
            coverage_state=coverage_state,
        )

        self.assertEqual(decision["target_label"], "app/services/question_generator.py")
        self.assertEqual(decision["relation_type"], "same_artifact")
        self.assertEqual(decision["developer_intent"], "investigate_failure")
        self.assertEqual(decision["depth_kind"], "deep")
        self.assertEqual(decision["frontier_rank"], 1)

    def test_plan_next_question_boosts_undercovered_developer_intent(self):
        coverage_state = {
            "question_history": [
                {
                    "turn_no": 15,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "generator-thread",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "signature": "Code Detail Completion|code_detail_deep_dive|generator-thread|file|app/services/question_generator.py",
                    "question_text": "Q15: In app/services/question_generator.py, how does generate_next_question_from_history build the current prompt?",
                }
            ],
            "investigation_frontier": {
                "items": [
                    {
                        "source_node_id": "turn-15",
                        "target_label": "app/services/question_generator.py",
                        "target_type": "file",
                        "relation_type": "same_artifact",
                        "developer_intent": "trace_execution",
                        "depth_kind": "deep",
                        "breadth_kind": "same_artifact",
                        "priority": 0.86,
                        "label": "Stay on the current execution path.",
                    },
                    {
                        "source_node_id": "turn-15",
                        "target_label": "app/services/question_generator.py",
                        "target_type": "file",
                        "relation_type": "same_artifact",
                        "developer_intent": "inspect_inputs_outputs",
                        "depth_kind": "deep",
                        "breadth_kind": "same_artifact",
                        "priority": 0.72,
                        "label": "Clarify the inputs and outputs on the same path.",
                    },
                ]
            },
            "developer_intent_coverage": {
                "trace_execution": 5,
                "inspect_inputs_outputs": 0,
                "understand_responsibility": 0,
                "investigate_failure": 0,
                "follow_state_change": 0,
                "check_dependency_usage": 0,
                "understand_data_contract": 0,
                "review_boundary_case": 0,
                "evaluate_optimization_tradeoff": 0,
                "connect_related_module": 0,
            },
            "framework": {
                "stage_turn_counts": {"Code Detail Completion": 6},
                "human_collaboration": {
                    "human_judgment_turn_count": 1,
                    "human_correction_turn_count": 1,
                    "human_redirection_turn_count": 1,
                    "human_prioritization_turn_count": 1,
                },
                "gaps": {"code_detail": []},
            },
        }

        decision = plan_next_question(
            turns=[],
            current_stage="Code Detail Completion",
            next_turn_no=16,
            coverage_state=coverage_state,
        )

        self.assertEqual(decision["developer_intent"], "inspect_inputs_outputs")
        self.assertIn("developer-intent", decision["why_this_question"])

if __name__ == "__main__":
    unittest.main()
