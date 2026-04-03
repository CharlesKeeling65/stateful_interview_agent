import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.graphs import interview_graph as graph_module
from app.main import app
from app.services import question_generator, summarization_service
from app.services import run_trace_service


class _FakeChatCompletions:
    def create(self, *, messages, **_kwargs):
        user_content = messages[-1]["content"]

        if "Summarize this answered interview turn." in user_content:
            content = "Concise summary with architecture detail and unresolved integration point."
        elif "Start the interview" in user_content:
            content = "Q1: What is the project trying to achieve for its primary users?"
        else:
            content = "Q2: Which modules coordinate the core workflow end to end?"

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30, total_tokens=150),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())


class RunTraceApiTests(unittest.TestCase):
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
        self.original_run_trace_session_local = run_trace_service.SessionLocal
        graph_module.SessionLocal = self.SessionLocal
        run_trace_service.SessionLocal = self.SessionLocal

        self.original_question_client = question_generator.get_openai_client
        self.original_summary_client = summarization_service.get_openai_client
        question_generator.get_openai_client = lambda: _FakeClient()
        summarization_service.get_openai_client = lambda: _FakeClient()

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        graph_module.SessionLocal = self.original_session_local
        run_trace_service.SessionLocal = self.original_run_trace_session_local
        question_generator.get_openai_client = self.original_question_client
        summarization_service.get_openai_client = self.original_summary_client
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_next_call_persists_run_trace_and_project_timing_metrics(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Trace Project",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)

        advanced = self.client.post(
            f"/projects/{project_id}/next",
            json={"answer_text": "Long answer about users, modules, and workflow."},
        )
        self.assertEqual(advanced.status_code, 200)

        runs = self.client.get(f"/projects/{project_id}/runs")
        self.assertEqual(runs.status_code, 200)
        runs_payload = runs.json()
        self.assertEqual(len(runs_payload), 1)

        latest_run = runs_payload[0]
        self.assertEqual(latest_run["status"], "completed")
        self.assertEqual(latest_run["turn_no"], 2)
        self.assertGreaterEqual(latest_run["step_count"], 1)
        self.assertGreaterEqual(latest_run["duration_ms"], 0)
        self.assertGreaterEqual(latest_run["total_llm_tokens"], 0)
        self.assertTrue(latest_run["steps"])

        step_keys = [step["step_key"] for step in latest_run["steps"]]
        self.assertIn("load_project_context", step_keys)
        self.assertIn("persist_result", step_keys)

        latest = self.client.get(f"/projects/{project_id}/runs/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["id"], latest_run["id"])

        status = self.client.get(f"/projects/{project_id}/status")
        self.assertEqual(status.status_code, 200)
        self.assertGreaterEqual(status.json()["cumulative_generation_time_ms"], 0)
        self.assertEqual(status.json()["run_count"], 1)


if __name__ == "__main__":
    unittest.main()
