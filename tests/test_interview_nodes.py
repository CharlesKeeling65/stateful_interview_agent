import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.graphs import interview_nodes
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn


class InterviewNodesTests(unittest.TestCase):
    def test_generate_question_for_state_builds_queue_from_planner_specs_before_llm(self):
        project = ProjectSession(
            id=22,
            project_name="Planner Queue",
            system_prompt="prompt",
            agent_mode="understand_current_code",
        )
        turns = [
            InterviewTurn(
                id=1,
                turn_no=1,
                stage="Code Detail Completion",
                question_text="Q1: Pending question",
                answer_text=None,
            ),
        ]
        planner_decision = {
            "question_intent": "code_detail_deep_dive",
            "intent_mode": "understand_current_code",
            "target_branch_id": "branch-a",
            "target_type": "file",
            "target_label": "app/services/question_generator.py",
            "selected_branch_ids": ["branch-a"],
            "selected_turn_ids": [1],
            "selected_framework_gap": None,
            "confidence": 0.8,
            "reasoning": "Complex path should be unfolded across queued single questions.",
            "constraints": [],
            "decomposition_mode": "queued_subquestions",
            "subquestion_specs": [
                {
                    "focus_kind": "main_flow",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "reason": "Cover the main flow first.",
                },
                {
                    "focus_kind": "error_path",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "reason": "Then isolate the error path.",
                },
            ],
        }

        with (
            patch.object(interview_nodes, "plan_next_question", return_value=planner_decision),
            patch.object(interview_nodes, "build_repo_grounding_context", return_value={
                "repo_grounding_context": "Grounding for app/services/question_generator.py",
                "repo_grounding_meta": {
                    "enabled": True,
                    "selected_paths": ["app/services/question_generator.py"],
                    "selected_symbols": [],
                    "queries": ["question_generator.py"],
                    "tool_calls": [],
                    "commit_sha": None,
                },
            }),
            patch.object(interview_nodes, "generate_next_question_from_history", return_value={
                "question_text": "Q2: In app/services/question_generator.py, how does generate_next_question_from_history build the main prompt?",
                "usage_metrics": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16, "is_estimated": False},
                "prompt_id": "next_question_code_detail",
                "prompt_version": "1.0",
            }) as generate_mock,
            patch.object(interview_nodes, "is_question_too_similar", return_value=False),
            patch.object(interview_nodes, "validate_question_for_stage", return_value={"is_valid": True, "reasons": []}),
            patch.object(interview_nodes, "validate_question_against_repository", return_value={"is_valid": True, "reasons": []}),
            patch.object(interview_nodes, "review_question_text", return_value={"is_valid": True, "reasons": []}),
            patch.object(interview_nodes, "check_scenario_completion", return_value={"is_complete": False, "missing_aspects": []}),
            patch.object(interview_nodes, "rebuild_coverage_state", return_value={"question_history": [], "branches": [], "framework": {}, "question_queue": {"status": "empty", "items": []}}),
            patch.object(interview_nodes, "build_generation_context", return_value={
                "recent_context": "recent",
                "retrieved_context": "retrieved",
                "coverage_priorities": "priorities",
                "repo_grounding_context": "stale",
                "repo_grounding_meta": {"enabled": False, "selected_paths": [], "selected_symbols": []},
                "selected_turn_ids": [1],
                "selected_branch_ids": ["branch-a"],
            }),
            patch.object(interview_nodes, "sync_task_board", return_value={}),
            patch.object(interview_nodes, "deserialize_task_board", return_value={}),
            patch.object(interview_nodes, "serialize_task_board", return_value="{}"),
        ):
            payload = interview_nodes.generate_question_for_state(
                current_stage="Code Detail Completion",
                db=None,
                human_review_signal=None,
                latest_answer_override=None,
                project=project,
                run_id=None,
                turn_no=2,
                turns=turns,
            )

        self.assertEqual(generate_mock.call_count, 1)
        self.assertEqual(
            payload["generated_question"],
            "Q2: In app/services/question_generator.py, how does generate_next_question_from_history build the main prompt?",
        )
        self.assertEqual(payload["planner_decision"]["generated_queue"]["status"], "active")
        self.assertEqual(len(payload["planner_decision"]["generated_queue"]["items"]), 1)
        self.assertEqual(
            payload["planner_decision"]["generated_queue"]["items"][0]["question_text"],
            "Q3: In app/services/question_generator.py, how does generate_next_question_from_history handle the error path?",
        )

    def test_similarity_retry_refreshes_repo_grounding_with_new_planner_target(self):
        project = ProjectSession(
            id=21,
            project_name="Retry Repo Grounding",
            system_prompt="prompt",
            agent_mode="understand_current_code",
        )
        turns = [
            InterviewTurn(
                id=1,
                turn_no=1,
                stage="Code Detail Completion",
                question_text="Q1: In app/services/original.py, how does the current path work?",
                answer_text="It starts from the original path.",
            ),
            InterviewTurn(
                id=2,
                turn_no=2,
                stage="Code Detail Completion",
                question_text="Q2: Pending question",
                answer_text=None,
            ),
        ]

        planner_decisions = [
            {
                "question_intent": "code_detail_deep_dive",
                "intent_mode": "understand_current_code",
                "target_branch_id": "branch-a",
                "target_type": "file",
                "target_label": "app/services/original.py",
                "selected_branch_ids": ["branch-a"],
                "selected_turn_ids": [1],
                "selected_framework_gap": None,
                "confidence": 0.8,
            },
            {
                "question_intent": "code_detail_deep_dive",
                "intent_mode": "understand_current_code",
                "target_branch_id": "branch-b",
                "target_type": "file",
                "target_label": "app/services/retried.py",
                "selected_branch_ids": ["branch-b"],
                "selected_turn_ids": [1],
                "selected_framework_gap": None,
                "confidence": 0.75,
            },
        ]

        def fake_repo_grounding_context(**kwargs):
            path = kwargs["planner_decision"]["target_label"]
            return {
                "repo_grounding_context": f"Grounding for {path}",
                "repo_grounding_meta": {
                    "enabled": True,
                    "selected_paths": [path],
                    "selected_symbols": [],
                    "queries": [path],
                    "tool_calls": [],
                    "commit_sha": None,
                },
            }

        generation_results = [
            {
                "question_text": "Q2: In app/services/original.py, how does the current path work?",
                "usage_metrics": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "is_estimated": False},
                "prompt_id": "next_question_code_detail",
                "prompt_version": "1.0",
            },
            {
                "question_text": "Q2: In app/services/retried.py, how does the retried path currently work?",
                "usage_metrics": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16, "is_estimated": False},
                "prompt_id": "next_question_code_detail",
                "prompt_version": "1.0",
            },
        ]

        with (
            patch.object(interview_nodes, "plan_next_question", side_effect=planner_decisions),
            patch.object(interview_nodes, "build_repo_grounding_context", side_effect=fake_repo_grounding_context),
            patch.object(interview_nodes, "generate_next_question_from_history", side_effect=generation_results),
            patch.object(interview_nodes, "is_question_too_similar", return_value=True),
            patch.object(interview_nodes, "validate_question_for_stage", return_value={"is_valid": True, "reasons": []}),
            patch.object(interview_nodes, "validate_question_against_repository", return_value={"is_valid": True, "reasons": []}),
            patch.object(interview_nodes, "review_question_text", return_value={"is_valid": True, "reasons": []}),
            patch.object(interview_nodes, "check_scenario_completion", return_value={"is_complete": False, "missing_aspects": []}),
            patch.object(interview_nodes, "rebuild_coverage_state", return_value={"question_history": [], "branches": [], "framework": {}}),
            patch.object(interview_nodes, "build_generation_context", return_value={
                "recent_context": "recent",
                "retrieved_context": "retrieved",
                "coverage_priorities": "priorities",
                "repo_grounding_context": "stale",
                "repo_grounding_meta": {"enabled": False, "selected_paths": [], "selected_symbols": []},
                "selected_turn_ids": [1],
                "selected_branch_ids": ["branch-a"],
            }),
            patch.object(interview_nodes, "sync_task_board", return_value={}),
            patch.object(interview_nodes, "deserialize_task_board", return_value={}),
            patch.object(interview_nodes, "serialize_task_board", return_value="{}"),
        ):
            payload = interview_nodes.generate_question_for_state(
                current_stage="Code Detail Completion",
                db=None,
                human_review_signal=None,
                latest_answer_override=None,
                project=project,
                run_id=None,
                turn_no=2,
                turns=turns,
            )

        self.assertEqual(payload["generated_question"], generation_results[1]["question_text"])
        self.assertEqual(payload["planner_decision"]["target_label"], "app/services/retried.py")
        self.assertEqual(payload["repo_grounding_meta"]["selected_paths"], ["app/services/retried.py"])
        self.assertEqual(payload["repo_grounding_context"], "Grounding for app/services/retried.py")


if __name__ == "__main__":
    unittest.main()
