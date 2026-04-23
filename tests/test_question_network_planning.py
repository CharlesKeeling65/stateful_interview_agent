import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.core.config import settings
from app.models.turn import InterviewTurn
from app.services.coverage_service import rebuild_coverage_state


class QuestionNetworkPlanningTests(unittest.TestCase):
    def test_question_graph_can_be_disabled_by_feature_flag(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=12,
                stage="Code Detail Completion",
                question_text="Q12: In app/api/routes/jobs.py, where does the timeout failure first surface on the request path?",
                answer_text="The timeout first surfaces in app/api/routes/jobs.py before the retry helper takes over.",
                answer_summary="The timeout first surfaces in app/api/routes/jobs.py. The retry helper path is still unclear.",
            ),
        ]

        with patch.object(settings, "question_graph_enabled", False, create=True):
            coverage = rebuild_coverage_state(turns)

        self.assertEqual(coverage["question_graph"], {"nodes": [], "edges": []})
        self.assertEqual(coverage["investigation_frontier"], {"items": []})
        self.assertEqual(coverage["question_network_stats"]["node_count"], 0)
        self.assertEqual(coverage["developer_intent_coverage"]["trace_execution"], 0)

    def test_bug_investigation_fixture_tracks_breadth_depth_and_intent_diversity(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=12,
                stage="Code Detail Completion",
                question_text="Q12: In app/api/routes/jobs.py, where does the timeout failure first surface on the request path?",
                answer_text="The timeout first surfaces in app/api/routes/jobs.py before the retry helper takes over.",
                answer_summary="The timeout first surfaces in app/api/routes/jobs.py. The retry helper path is still unclear.",
            ),
            InterviewTurn(
                id=2,
                turn_no=13,
                stage="Code Detail Completion",
                question_text="Q13: In app/services/retry_runner.py, how does the retry helper decide whether to back off or fail fast after a timeout?",
                answer_text="retry_runner.py inspects timeout categories, backs off for transient failures, and forwards terminal cases downstream.",
                answer_summary="retry_runner.py classifies timeout failures and forwards terminal cases downstream. The remaining gap is how session state changes when retries exhaust.",
            ),
            InterviewTurn(
                id=3,
                turn_no=14,
                stage="Code Detail Completion",
                question_text="Q14: In app/services/session_store.py, when retries exhaust, how does the session state update before the caller sees the failure?",
                answer_text="session_store.py marks the session as failed and exposes that state to the caller before returning the error.",
                answer_summary="session_store.py marks failed state before the caller sees the error.",
            ),
        ]

        coverage = rebuild_coverage_state(turns)
        stats = coverage["question_network_stats"]

        self.assertEqual(stats["node_count"], 3)
        self.assertGreaterEqual(stats["connected_edge_count"], 2)
        self.assertGreaterEqual(stats["breadth_transition_count"], 1)
        self.assertGreaterEqual(stats["depth_transition_count"], 1)
        self.assertGreaterEqual(stats["developer_intent_count"], 2)
        self.assertLess(stats["dominant_intent_ratio"], 1.0)

    def test_api_contract_fixture_tracks_cross_module_expansion_without_becoming_isolated(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=21,
                stage="Code Detail Completion",
                question_text="Q21: In app/api/routes/contracts.py, what input fields does create_contract accept before validation runs?",
                answer_text="create_contract accepts tenant_id, schedule, and retry_policy before validation runs.",
                answer_summary="create_contract accepts tenant_id, schedule, and retry_policy. The validation path and downstream consumer are still unclear.",
            ),
            InterviewTurn(
                id=2,
                turn_no=22,
                stage="Code Detail Completion",
                question_text="Q22: In app/services/contract_validator.py, how does the validator reject invalid retry_policy combinations?",
                answer_text="contract_validator.py rejects invalid retry_policy combinations before persistence and exposes field-level errors.",
                answer_summary="contract_validator.py rejects invalid retry_policy combinations. The downstream consumer in scheduling is still unresolved.",
            ),
            InterviewTurn(
                id=3,
                turn_no=23,
                stage="Code Detail Completion",
                question_text="Q23: In app/services/scheduler.py, where does the validated retry_policy get consumed when the schedule is materialized?",
                answer_text="scheduler.py consumes retry_policy when it materializes the execution schedule.",
                answer_summary="scheduler.py consumes retry_policy during schedule materialization.",
            ),
        ]

        coverage = rebuild_coverage_state(turns)
        stats = coverage["question_network_stats"]

        self.assertEqual(stats["isolated_node_count"], 0)
        self.assertGreaterEqual(stats["breadth_transition_count"], 1)
        self.assertGreaterEqual(stats["developer_intent_count"], 2)
        self.assertGreater(len(coverage["question_graph"]["edges"]), 1)


if __name__ == "__main__":
    unittest.main()
