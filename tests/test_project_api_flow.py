import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import projects as project_routes
from app.core.database import Base, get_db
from app.graphs import interview_graph as graph_module
from app.main import app
from app.services import question_generator, summarization_service


class _FakeChatCompletions:
    def create(self, *, messages, **_kwargs):
        user_content = messages[-1]["content"]

        if "Summarize this answered interview turn." in user_content:
            content = "Concise summary with architecture detail and unresolved integration point."
        elif "Start the interview" in user_content:
            content = "Q1: What is the project trying to achieve for its primary users?"
        elif "Next question number: Q2" in user_content:
            content = "Q2: Which modules coordinate the core workflow end to end?"
        elif "Next question number: Q3" in user_content:
            content = "Q3: Where are the main extension points or unresolved design tradeoffs?"
        else:
            content = "Q9: Placeholder follow-up question?"

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30, total_tokens=150),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())


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

        self.original_question_client = question_generator.get_openai_client
        self.original_summary_client = summarization_service.get_openai_client
        question_generator.get_openai_client = lambda: _FakeClient()
        summarization_service.get_openai_client = lambda: _FakeClient()

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        graph_module.SessionLocal = self.original_session_local
        question_generator.get_openai_client = self.original_question_client
        summarization_service.get_openai_client = self.original_summary_client
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

        next_one = self.client.post(
            f"/projects/{project_id}/next",
            json={
                "answer_text": "Long answer one with product goals, user roles, data flow, and module boundaries.",
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

        next_two = self.client.post(
            f"/projects/{project_id}/next",
            json={
                "answer_text": "Long answer two with service orchestration, event handling, and integration constraints.",
            },
        )
        self.assertEqual(next_two.status_code, 200)
        self.assertEqual(next_two.json()["next_turn"]["turn_no"], 3)
        self.assertGreater(next_two.json()["usage_summary"]["total_tokens"], 0)

        turns = self.client.get(f"/projects/{project_id}/turns")
        self.assertEqual(turns.status_code, 200)
        turns_payload = turns.json()
        self.assertEqual(len(turns_payload), 3)
        self.assertEqual(
            turns_payload[0]["answer_text"],
            "Long answer one with product goals, user roles, data flow, and module boundaries.",
        )
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
            "Where are the main extension points or unresolved design tradeoffs?",
        )
        self.assertGreater(status.json()["usage_summary"]["total_tokens"], 0)

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
