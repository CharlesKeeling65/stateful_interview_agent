import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import projects as project_routes
from app.core.database import Base, get_db
from app.graphs import interview_graph as graph_module
from app.services.human_gate_service import (
    create_drift_redirection_gate,
    create_low_confidence_gate,
    gate_resolution_to_human_review_signal,
)
from app.services.question_reviewer import ReviewResult
from app.main import app
from app.services import question_generator, summarization_service


class _FakeChatCompletions:
    def create(self, *, messages, **_kwargs):
        user_content = messages[-1]["content"]

        if "Summarize this answered interview turn" in user_content:
            content = "Concise summary with architecture detail and unresolved integration point."
        elif "Start the interview" in user_content:
            content = "Q1: What is the project trying to achieve for its primary users?"
        elif "Next question number: Q1" in user_content:
            content = "Q1: Which modules coordinate the core workflow, and how do requests move between them?"
        elif "Next question number: Q2" in user_content:
            content = "Q2: Which modules coordinate the core workflow end to end?"
        elif "Next question number: Q3" in user_content:
            content = "Q3: Along the main request path, how do auth and orchestration modules coordinate responsibilities and handoffs?"
        else:
            content = "Q9: Placeholder follow-up question?"

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30, total_tokens=150),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())


class _FakeProvider:
    def generate_text(self, *, messages, **_kwargs):
        response = _FakeChatCompletions().create(messages=messages)
        return SimpleNamespace(
            text=response.choices[0].message.content,
            model="fake-model",
            usage=response.usage,
            raw=response,
        )


class _RegenerationFromPreviousAnswerChatCompletions:
    def create(self, *, messages, **_kwargs):
        user_content = messages[-1]["content"]
        if "Latest turn answer: Answer that should drive regeneration." in user_content:
            content = "Q2: Regenerated from previous answer context?"
        else:
            content = "Q2: Wrong regeneration context?"

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=90, completion_tokens=20, total_tokens=110),
        )


class _RegenerationFromPreviousAnswerClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_RegenerationFromPreviousAnswerChatCompletions())


class _RegenerationFromPreviousAnswerProvider:
    def generate_text(self, *, messages, **_kwargs):
        response = _RegenerationFromPreviousAnswerChatCompletions().create(messages=messages)
        return SimpleNamespace(
            text=response.choices[0].message.content,
            model="fake-model",
            usage=response.usage,
            raw=response,
        )


class ProjectApiFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.original_session_local = graph_module.SessionLocal
        graph_module.SessionLocal = self.SessionLocal

        self.original_question_provider = question_generator.get_llm_provider
        self.original_summary_provider = summarization_service.get_llm_provider
        question_generator.get_llm_provider = lambda: _FakeProvider()
        summarization_service.get_llm_provider = lambda: _FakeProvider()

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        graph_module.SessionLocal = self.original_session_local
        question_generator.get_llm_provider = self.original_question_provider
        summarization_service.get_llm_provider = self.original_summary_provider
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_project_flow_persists_summaries_and_usage(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Initial Project Name",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        updated = self.client.patch(
            f"/projects/{project_id}",
            json={"project_name": "Renamed Interview Project"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["project_name"], "Renamed Interview Project")

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["first_turn"]["question_text_for_copy"], "What is the project trying to achieve for its primary users?")

        saved_one = self.client.post(
            f"/projects/{project_id}/answer",
            json={
                "answer_text": "Long answer one with product goals, user roles, data flow, and module boundaries.",
            },
        )
        self.assertEqual(saved_one.status_code, 200)
        self.assertTrue(saved_one.json()["can_generate_next"])
        self.assertTrue(saved_one.json()["updated_turn"]["answer_summary"])
        self.assertTrue(saved_one.json()["updated_turn"]["answer_analysis"]["key_points"])
        self.assertTrue(saved_one.json()["updated_turn"]["answer_analysis"]["rag_chunks"])
        self.assertEqual(
            saved_one.json()["updated_turn"]["answer_analysis"]["stage_focus"],
            "Panorama Mapping",
        )

        next_one = self.client.post(
            f"/projects/{project_id}/next",
            json={
                "human_review": {
                    "verdict": "insufficient",
                    "direction": "redirect",
                    "preferred_next_focus": "architecture",
                    "note": "Return to the current module interaction before proposing any changes.",
                },
            },
        )
        self.assertEqual(next_one.status_code, 200)
        self.assertEqual(next_one.json()["next_turn"]["turn_no"], 2)
        self.assertEqual(next_one.json()["next_turn"]["current_question_version_no"], 1)
        self.assertEqual(next_one.json()["next_turn"]["question_regeneration_count"], 0)
        self.assertEqual(len(next_one.json()["next_turn"]["question_versions"]), 1)

        saved_two = self.client.post(
            f"/projects/{project_id}/answer",
            json={
                "answer_text": "Long answer two with service orchestration, event handling, and integration constraints.",
            },
        )
        self.assertEqual(saved_two.status_code, 200)
        self.assertTrue(saved_two.json()["can_generate_next"])

        next_two = self.client.post(
            f"/projects/{project_id}/next",
            json={},
        )
        self.assertEqual(next_two.status_code, 200)
        self.assertEqual(next_two.json()["next_turn"]["turn_no"], 3)
        self.assertGreater(next_two.json()["usage_summary"]["total_tokens"], 0)
        self.assertEqual(next_two.json()["next_turn"]["current_question_version_no"], 1)
        self.assertEqual(next_two.json()["next_turn"]["question_regeneration_count"], 0)
        self.assertEqual(len(next_two.json()["next_turn"]["question_versions"]), 1)

        turns = self.client.get(f"/projects/{project_id}/turns")
        self.assertEqual(turns.status_code, 200)
        turns_payload = turns.json()
        self.assertEqual(len(turns_payload), 3)
        self.assertEqual(
            turns_payload[0]["answer_text"],
            "Long answer one with product goals, user roles, data flow, and module boundaries.",
        )
        self.assertTrue(turns_payload[0]["answer_analysis"]["key_points"])
        self.assertTrue(turns_payload[0]["answer_analysis"]["follow_up_anchors"])
        self.assertEqual(turns_payload[0]["human_review"]["verdict"], "insufficient")
        self.assertEqual(turns_payload[0]["human_review"]["preferred_next_focus"], "architecture")
        self.assertTrue(turns_payload[0]["answer_summary"])
        self.assertIn("question_plan", turns_payload[1])
        self.assertEqual(turns_payload[1]["question_plan"]["intent_mode"], "understand_current_code")
        self.assertTrue(turns_payload[1]["question_plan"]["why_this_question"])
        self.assertEqual(
            turns_payload[1]["answer_text"],
            "Long answer two with service orchestration, event handling, and integration constraints.",
        )
        self.assertGreaterEqual(len(turns_payload[0]["llm_usages"]), 1)

        status = self.client.get(f"/projects/{project_id}/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(
            status.json()["latest_question_text_for_copy"],
            "Along the main request path, how do auth and orchestration modules coordinate responsibilities and handoffs?",
        )
        self.assertGreater(status.json()["usage_summary"]["total_tokens"], 0)
        self.assertFalse(status.json()["latest_turn_ready_for_next_generation"])

        coverage = self.client.get(f"/debug/projects/{project_id}/coverage")
        self.assertEqual(coverage.status_code, 200)
        self.assertGreaterEqual(coverage.json()["branch_count"], 1)
        self.assertTrue(coverage.json()["branches"])
        self.assertTrue(coverage.json()["question_history"])

    def test_delete_project_removes_session_from_listing(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Disposable Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        deleted = self.client.delete(f"/projects/{project_id}")
        self.assertEqual(deleted.status_code, 204)

        fetched = self.client.get(f"/projects/{project_id}")
        self.assertEqual(fetched.status_code, 404)

        listed = self.client.get("/projects")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json(), [])

    def test_project_can_attach_local_repository_source(self):
        repo_root = Path(self.temp_dir.name) / "attached-repo"
        (repo_root / "app").mkdir(parents=True, exist_ok=True)
        (repo_root / "README.md").write_text("# Attached repo\n", encoding="utf-8")
        (repo_root / "app/main.py").write_text(
            "def bootstrap_app():\n    return 'ready'\n",
            encoding="utf-8",
        )

        created = self.client.post(
            "/projects",
            json={
                "project_name": "Repo Attached Session",
                "system_prompt": "You are a stateful interview agent.",
                "repository": {
                    "source_type": "local_path",
                    "local_path": str(repo_root),
                },
            },
        )
        self.assertEqual(created.status_code, 200)
        payload = created.json()
        self.assertEqual(payload["repository"]["source_type"], "local_path")
        self.assertEqual(payload["repository_manifest"]["file_count"], 2)
        self.assertIn("README.md", payload["repository_manifest"]["key_files"])

        started = self.client.post(f"/projects/{payload['id']}/start")
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["project"]["repository"]["source_type"], "local_path")

    def test_project_create_persists_explicit_agent_mode_and_task_board_summary(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Modeful Session",
                "system_prompt": "You are a stateful interview agent.",
                "agent_mode": "propose_changes",
            },
        )
        self.assertEqual(created.status_code, 200)
        payload = created.json()

        self.assertEqual(payload["agent_mode"], "propose_changes")
        self.assertIsNotNone(payload["rubric_task_board_summary"])
        self.assertEqual(
            payload["rubric_task_board_summary"]["current_phase"],
            "panorama_mapping",
        )
        self.assertGreater(payload["rubric_task_board_summary"]["incomplete_task_count"], 0)

    def test_next_call_can_pause_for_human_gate_and_resume_after_resolution(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Gate Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)

        saved = self.client.post(
            f"/projects/{project_id}/answer",
            json={"answer_text": "Answer with enough detail to require prioritization."},
        )
        self.assertEqual(saved.status_code, 200)

        forced_gate = create_low_confidence_gate(
            {
                "confidence": 0.18,
                "question_intent": "code_detail_deep_dive",
                "target_label": "authentication and orchestration handoff",
            }
        )
        review_result = ReviewResult(
            approved=False,
            review_reason="Need explicit human prioritization before deepening.",
            human_gate_triggered=True,
            human_gate=forced_gate,
            human_gate_reason=forced_gate.reason,
        )

        with patch("app.graphs.interview_nodes.review_question_plan", return_value=review_result):
            gated = self.client.post(f"/projects/{project_id}/next", json={})

        self.assertEqual(gated.status_code, 200)
        gated_payload = gated.json()
        self.assertIsNone(gated_payload["next_turn"])
        self.assertFalse(gated_payload["interview_finished"])
        self.assertEqual(gated_payload["project"]["pending_gate"]["gate_id"], forced_gate.gate_id)

        resumed = self.client.post(
            f"/projects/{project_id}/next",
            json={
                "human_gate": {
                    "gate_id": forced_gate.gate_id,
                    "action": forced_gate.default_action,
                    "preferred_next_focus": "authentication flow",
                    "note": "Continue with the current branch and prioritize the auth path.",
                }
            },
        )
        self.assertEqual(resumed.status_code, 200)
        resumed_payload = resumed.json()
        self.assertIsNotNone(resumed_payload["next_turn"])
        self.assertIsNone(resumed_payload["project"]["pending_gate"])
        self.assertTrue(resumed_payload["next_turn"]["question_plan"]["human_review_applied"])
        self.assertTrue(resumed_payload["next_turn"]["event_log"])

    def test_drift_gate_resolution_does_not_force_drifted_on_continue_or_new_branch(self):
        drift_gate = create_drift_redirection_gate({
            "detected": True,
            "reason": "Narrow branch drift detected",
            "branch_id": "depth-network-generator",
        })

        continue_signal = gate_resolution_to_human_review_signal(drift_gate, "continue")
        self.assertEqual(continue_signal["direction"], "continue")
        self.assertNotIn("verdict", continue_signal)

        new_branch_signal = gate_resolution_to_human_review_signal(drift_gate, "new_branch")
        self.assertEqual(new_branch_signal["direction"], "redirect")
        self.assertNotIn("verdict", new_branch_signal)

        redirect_signal = gate_resolution_to_human_review_signal(drift_gate, "redirect")
        self.assertEqual(redirect_signal["direction"], "redirect")
        self.assertEqual(redirect_signal.get("verdict"), "drifted")

    def test_regenerate_current_question_tracks_versions_and_usage(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Regeneration Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)
        current_turn = started.json()["first_turn"]
        self.assertEqual(current_turn["turn_no"], 1)
        self.assertEqual(current_turn["question_regeneration_count"], 0)
        self.assertEqual(current_turn["current_question_version_no"], 1)
        self.assertEqual(len(current_turn["question_versions"]), 1)

        regenerated = self.client.post(
            f"/projects/{project_id}/turns/{current_turn['id']}/regenerate-question",
            json={
                "human_review": {
                    "verdict": "insufficient",
                    "direction": "redirect",
                    "preferred_next_focus": "architecture",
                    "note": "The current question is too broad. Ask about the coordinating modules instead.",
                    "phase_ready": False,
                }
            },
        )
        self.assertEqual(regenerated.status_code, 200)
        payload = regenerated.json()
        self.assertEqual(payload["turn"]["turn_no"], 1)
        self.assertEqual(payload["turn"]["current_question_version_no"], 2)
        self.assertEqual(payload["turn"]["question_regeneration_count"], 1)
        self.assertEqual(len(payload["turn"]["question_versions"]), 2)
        self.assertEqual(payload["turn"]["question_versions"][0]["version_no"], 1)
        self.assertEqual(payload["turn"]["question_versions"][1]["version_no"], 2)
        self.assertEqual(
            payload["turn"]["question_versions"][1]["human_review"]["verdict"],
            "insufficient",
        )
        self.assertGreater(
            payload["turn"]["human_intervention_regeneration_usage_summary"]["total_tokens"],
            0,
        )
        self.assertGreater(payload["usage_summary"]["total_tokens"], 0)
        self.assertTrue(payload["applied_changes"]["review_persisted"])
        self.assertTrue(payload["applied_changes"]["planner_followed_review"])
        self.assertEqual(payload["applied_changes"]["question_version_before"], 1)
        self.assertEqual(payload["applied_changes"]["question_version_after"], 2)
        self.assertEqual(payload["applied_changes"]["regeneration_count_before"], 0)
        self.assertEqual(payload["applied_changes"]["regeneration_count_after"], 1)
        self.assertEqual(payload["applied_changes"]["requested_focus"], "architecture")
        self.assertEqual(payload["applied_changes"]["requested_verdict"], "insufficient")
        self.assertEqual(payload["applied_changes"]["requested_direction"], "redirect")
        self.assertTrue(payload["applied_changes"]["note_applied"])
        self.assertFalse(payload["applied_changes"]["phase_ready_applied"])

        turns = self.client.get(f"/projects/{project_id}/turns")
        self.assertEqual(turns.status_code, 200)
        turns_payload = turns.json()
        self.assertEqual(len(turns_payload), 1)
        self.assertEqual(turns_payload[0]["current_question_version_no"], 2)
        self.assertEqual(turns_payload[0]["question_regeneration_count"], 1)
        self.assertEqual(len(turns_payload[0]["question_versions"]), 2)
        self.assertGreater(
            turns_payload[0]["human_intervention_regeneration_usage_summary"]["total_tokens"],
            0,
        )

    def test_save_current_question_persists_manual_edit_into_turn_history(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Manual Question Edit Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)
        current_turn = started.json()["first_turn"]

        saved = self.client.patch(
            f"/projects/{project_id}/turns/{current_turn['id']}/question",
            json={
                "question_text": "Which modules coordinate the request path after startup?",
            },
        )
        self.assertEqual(saved.status_code, 200)
        payload = saved.json()
        self.assertEqual(
            payload["turn"]["question_text"],
            "Q1: Which modules coordinate the request path after startup?",
        )
        self.assertEqual(
            payload["turn"]["question_text_for_copy"],
            "Which modules coordinate the request path after startup?",
        )
        self.assertEqual(payload["turn"]["current_question_version_no"], 2)
        self.assertEqual(payload["turn"]["question_regeneration_count"], 0)
        self.assertEqual(len(payload["turn"]["question_versions"]), 2)
        self.assertEqual(payload["turn"]["question_versions"][-1]["generation_kind"], "human_edit")

        answered = self.client.post(
            f"/projects/{project_id}/answer",
            json={"answer_text": "The startup path flows through auth and orchestration."},
        )
        self.assertEqual(answered.status_code, 200)

        generated = self.client.post(f"/projects/{project_id}/next", json={})
        self.assertEqual(generated.status_code, 200)

        turns = self.client.get(f"/projects/{project_id}/turns")
        self.assertEqual(turns.status_code, 200)
        turns_payload = turns.json()
        self.assertEqual(
            turns_payload[0]["question_text"],
            "Q1: Which modules coordinate the request path after startup?",
        )
        self.assertEqual(turns_payload[0]["current_question_version_no"], 2)

    def test_regenerate_current_question_can_correct_stage_and_persist_review(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Stage Correction Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)
        current_turn = started.json()["first_turn"]

        regenerated = self.client.post(
            f"/projects/{project_id}/turns/{current_turn['id']}/regenerate-question",
            json={
                "human_review": {
                    "verdict": "drifted",
                    "direction": "redirect",
                    "preferred_next_focus": "architecture",
                    "note": "This should move to architecture instead of staying at panorama.",
                    "phase": "Architecture Understanding",
                    "phase_ready": False,
                }
            },
        )
        self.assertEqual(regenerated.status_code, 200)
        payload = regenerated.json()

        self.assertEqual(payload["turn"]["stage"], "Architecture Understanding")
        self.assertEqual(payload["turn"]["question_plan"]["phase"], "Architecture Understanding")
        self.assertEqual(payload["turn"]["human_review"]["phase"], "Architecture Understanding")
        self.assertEqual(payload["turn"]["question_versions"][-1]["human_review"]["phase"], "Architecture Understanding")
        self.assertEqual(payload["applied_changes"]["previous_stage"], "Panorama Mapping")
        self.assertEqual(payload["applied_changes"]["current_stage"], "Architecture Understanding")
        self.assertTrue(payload["applied_changes"]["stage_changed"])

        project = self.client.get(f"/projects/{project_id}")
        self.assertEqual(project.status_code, 200)
        self.assertEqual(project.json()["current_stage"], "Architecture Understanding")

        status = self.client.get(f"/projects/{project_id}/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["current_stage"], "Architecture Understanding")

    def test_multiple_regenerations_increment_version_numbers_without_duplicate_initial_versions(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Version Integrity Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)
        current_turn = started.json()["first_turn"]

        first_regeneration = self.client.post(
            f"/projects/{project_id}/turns/{current_turn['id']}/regenerate-question",
            json={
                "human_review": {
                    "verdict": "drifted",
                    "direction": "redirect",
                    "preferred_next_focus": "architecture",
                    "note": "Push this toward architecture.",
                }
            },
        )
        self.assertEqual(first_regeneration.status_code, 200)

        second_regeneration = self.client.post(
            f"/projects/{project_id}/turns/{current_turn['id']}/regenerate-question",
            json={
                "human_review": {
                    "verdict": "drifted",
                    "direction": "redirect",
                    "preferred_next_focus": "code_detail",
                    "note": "Now narrow it to the main code path.",
                }
            },
        )
        self.assertEqual(second_regeneration.status_code, 200)
        payload = second_regeneration.json()

        version_numbers = [version["version_no"] for version in payload["turn"]["question_versions"]]
        generation_kinds = [version["generation_kind"] for version in payload["turn"]["question_versions"]]

        self.assertEqual(version_numbers, [1, 2, 3])
        self.assertEqual(generation_kinds.count("initial"), 1)
        self.assertEqual(payload["turn"]["current_question_version_no"], 3)
        self.assertEqual(payload["turn"]["question_regeneration_count"], 2)

    def test_regenerate_current_question_replays_generation_from_previous_answer(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Replay Regeneration Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)

        saved = self.client.post(
            f"/projects/{project_id}/answer",
            json={
                "answer_text": "Answer that should drive regeneration.",
            },
        )
        self.assertEqual(saved.status_code, 200)

        next_one = self.client.post(
            f"/projects/{project_id}/next",
            json={},
        )
        self.assertEqual(next_one.status_code, 200)
        current_turn = next_one.json()["next_turn"]

        original_question_provider = question_generator.get_llm_provider
        try:
            question_generator.get_llm_provider = lambda: _RegenerationFromPreviousAnswerProvider()
            regenerated = self.client.post(
                f"/projects/{project_id}/turns/{current_turn['id']}/regenerate-question",
                json={
                    "human_review": {
                        "direction": "redirect",
                        "preferred_next_focus": "architecture",
                    }
                },
            )
        finally:
            question_generator.get_llm_provider = original_question_provider

        self.assertEqual(regenerated.status_code, 200)
        payload = regenerated.json()
        self.assertEqual(payload["turn"]["question_text"], "Q2: Regenerated from previous answer context?")
        self.assertTrue(payload["applied_changes"]["question_changed"])

    def test_regenerate_current_question_returns_bad_request_for_validation_failure(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Validation Failure Session",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)
        current_turn = started.json()["first_turn"]

        original_generate = project_routes.generate_question_for_state
        failure_client = TestClient(app, raise_server_exceptions=False)
        try:
            project_routes.generate_question_for_state = lambda **_kwargs: (_ for _ in ()).throw(
                ValueError(
                    "Generated question failed stage-specific validation: "
                    "Question is too similar to a recently asked question and should target a different branch or implementation detail."
                )
            )
            regenerated = failure_client.post(
                f"/projects/{project_id}/turns/{current_turn['id']}/regenerate-question",
                json={
                    "human_review": {
                        "verdict": "insufficient",
                        "direction": "redirect",
                        "preferred_next_focus": "branch detail",
                    }
                },
            )
        finally:
            project_routes.generate_question_for_state = original_generate

        self.assertEqual(regenerated.status_code, 400)
        self.assertIn("too similar to a recently asked question", regenerated.json()["detail"])


if __name__ == "__main__":
    unittest.main()
