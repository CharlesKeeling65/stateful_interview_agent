import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.models.turn import InterviewTurn
from app.services.context_engineering import build_generation_context


class ContextEngineeringTests(unittest.TestCase):
    def test_context_builder_keeps_latest_full_answer_and_retrieves_relevant_branches(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What does the project do?",
                answer_text="It supports operators, customers, and internal admins.",
                answer_summary="Users include operators, customers, and admins. Boundaries touch ingestion, APIs, and dashboards.",
            ),
            InterviewTurn(
                id=2,
                turn_no=2,
                stage="Architecture Understanding",
                question_text="Q2: Which modules coordinate the core workflow?",
                answer_text="The API gateway hands requests to auth and orchestration services.",
                answer_summary="API gateway routes to auth and orchestration services. Session handoff is still unclear.",
            ),
            InterviewTurn(
                id=3,
                turn_no=3,
                stage="Architecture Understanding",
                question_text="Q3: Where is the main execution path implemented?",
                answer_text=None,
            ),
        ]

        coverage_state = {
            "branches": [
                {
                    "branch_id": "user_roles",
                    "label": "user roles and system boundaries",
                    "stage": "Panorama Mapping",
                    "status": "partial",
                    "priority": 0.82,
                    "keywords": ["users", "operators", "admins", "boundaries"],
                    "evidence_turn_ids": [1],
                    "unresolved_points": ["Boundary between operator and admin tooling is still shallow."],
                },
                {
                    "branch_id": "auth_handoff",
                    "label": "auth and orchestration handoff",
                    "stage": "Architecture Understanding",
                    "status": "needs_follow_up",
                    "priority": 0.95,
                    "keywords": ["auth", "gateway", "session", "orchestration"],
                    "evidence_turn_ids": [2],
                    "unresolved_points": ["Session handoff between gateway and auth service is not yet explained."],
                },
                {
                    "branch_id": "deployment",
                    "label": "deployment topology",
                    "stage": "Panorama Mapping",
                    "status": "covered",
                    "priority": 0.2,
                    "keywords": ["kubernetes", "deployment"],
                    "evidence_turn_ids": [],
                    "unresolved_points": [],
                },
            ]
        }

        result = build_generation_context(
            turns=turns,
            current_stage="Architecture Understanding",
            next_turn_no=4,
            latest_answer_override="The latest answer focuses on API gateway routing, auth checks, and session propagation into orchestration.",
            coverage_state=coverage_state,
        )

        self.assertIn(
            "The latest answer focuses on API gateway routing, auth checks, and session propagation into orchestration.",
            result["context_text"],
        )
        self.assertIn("auth_handoff", result["selected_branch_ids"])
        self.assertIn(2, result["selected_turn_ids"])
        self.assertNotIn("deployment", result["selected_branch_ids"])
        self.assertNotIn("Turn 1", result["context_text"])

    def test_context_builder_surfaces_stage_gaps_even_without_recent_keyword_overlap(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: Who uses the system?",
                answer_text="Operators and analysts use it daily.",
                answer_summary="Operators and analysts are the main users. Their workflows are only partially described.",
            ),
            InterviewTurn(
                id=2,
                turn_no=2,
                stage="Architecture Understanding",
                question_text="Q2: How are services organized?",
                answer_text="Services are layered behind an API tier.",
                answer_summary="Services are layered behind an API tier.",
            ),
        ]

        coverage_state = {
            "branches": [
                {
                    "branch_id": "operator_workflow",
                    "label": "operator workflow scenarios",
                    "stage": "Use Cases & Scenarios",
                    "status": "needs_follow_up",
                    "priority": 0.91,
                    "keywords": ["operator", "workflow", "scenario"],
                    "evidence_turn_ids": [1],
                    "unresolved_points": ["No concrete operator workflow has been walked end to end."],
                }
            ]
        }

        result = build_generation_context(
            turns=turns,
            current_stage="Use Cases & Scenarios",
            next_turn_no=12,
            latest_answer_override="The latest answer discusses only service layering.",
            coverage_state=coverage_state,
        )

        self.assertIn("operator_workflow", result["selected_branch_ids"])
        self.assertIn("No concrete operator workflow has been walked end to end.", result["context_text"])

    def test_context_builder_applies_novelty_penalty_to_recently_asked_branch(self):
        turns = [
            InterviewTurn(
                id=1,
                turn_no=8,
                stage="Code Detail Completion",
                question_text="Q8: In app/services/question_generator.py, how does the prompt rendering path currently work?",
                answer_text="It renders prompt assets and calls the model.",
                answer_summary="question_generator.py renders prompts and calls the model.",
            ),
            InterviewTurn(
                id=2,
                turn_no=9,
                stage="Code Detail Completion",
                question_text="Q9: What should we deepen next?",
                answer_text=None,
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
                    "evidence_turn_nos": [8],
                    "unresolved_points": ["Need to inspect validation details."],
                },
                {
                    "branch_id": "persist_step",
                    "label": "app/graphs/interview_nodes.py persist_next_step path",
                    "stage": "Code Detail Completion",
                    "status": "needs_follow_up",
                    "priority": 0.88,
                    "keywords": ["interview_nodes.py", "persist_next_step", "pending_turn_id"],
                    "evidence_turn_ids": [1],
                    "evidence_turn_nos": [8],
                    "unresolved_points": ["Need to inspect how duplicate pending turns are rejected."],
                },
            ],
            "question_history": [
                {
                    "turn_no": 8,
                    "stage": "Code Detail Completion",
                    "intent": "code_detail_deep_dive",
                    "branch_id": "question_generator",
                    "target_type": "file",
                    "target_label": "app/services/question_generator.py",
                    "signature": "Code Detail Completion|code_detail_deep_dive|question_generator|file|app/services/question_generator.py",
                    "question_text": "Q8: In app/services/question_generator.py, how does the prompt rendering path currently work?",
                }
            ],
        }

        result = build_generation_context(
            turns=turns,
            current_stage="Code Detail Completion",
            next_turn_no=10,
            latest_answer_override="The latest answer discusses prompt rendering and model calls.",
            coverage_state=coverage_state,
        )

        self.assertNotIn("question_generator", result["selected_branch_ids"][:1])
        self.assertIn("persist_step", result["selected_branch_ids"])


if __name__ == "__main__":
    unittest.main()
