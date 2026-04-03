import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.graphs import interview_graph as graph_module
from app.logging import configure_logging
from app.main import app
from app.services import question_generator, summarization_service


class _FakeChatCompletions:
    def create(self, *, messages, **_kwargs):
        user_content = messages[-1]["content"]

        if "Summarize this answered interview turn" in user_content:
            content = "Concise summary with unresolved auth handoff."
        elif "Start the interview" in user_content:
            content = "Q1: What is the project trying to achieve for its primary users?"
        else:
            content = "Q2: Which modules coordinate the core workflow end to end?"

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=24, total_tokens=124),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())


class LoggingObservabilityTests(unittest.TestCase):
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
        self.original_log_dir = settings.log_dir
        settings.log_dir = str(Path(self.temp_dir.name) / "logs")
        configure_logging(force=True)

        self.original_question_client = question_generator.get_openai_client
        self.original_summary_client = summarization_service.get_openai_client
        question_generator.get_openai_client = lambda: _FakeClient()
        summarization_service.get_openai_client = lambda: _FakeClient()

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        graph_module.SessionLocal = self.original_session_local
        settings.log_dir = self.original_log_dir
        question_generator.get_openai_client = self.original_question_client
        summarization_service.get_openai_client = self.original_summary_client
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_flow_writes_structured_logs_to_files(self):
        created = self.client.post(
            "/projects",
            json={
                "project_name": "Logging Test Project",
                "system_prompt": "You are a stateful interview agent.",
            },
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        started = self.client.post(f"/projects/{project_id}/start")
        self.assertEqual(started.status_code, 200)

        advanced = self.client.post(
            f"/projects/{project_id}/next",
            json={"answer_text": "The answer describes auth, sessions, and orchestration."},
        )
        self.assertEqual(advanced.status_code, 200)

        logs_dir = Path(settings.log_dir)
        self.assertTrue(logs_dir.exists())

        jsonl_files = sorted(logs_dir.rglob("*.jsonl"))
        self.assertTrue(jsonl_files, "Expected structured log files to be created.")

        events = []
        for file_path in jsonl_files:
            with file_path.open("r", encoding="utf-8") as handle:
                events.extend(json.loads(line) for line in handle if line.strip())

        event_names = {event["event"] for event in events}
        self.assertIn("http.request.start", event_names)
        self.assertIn("http.request.complete", event_names)
        self.assertIn("workflow.node.start", event_names)
        self.assertIn("workflow.node.complete", event_names)
        self.assertIn("llm.call.complete", event_names)

        next_request_events = [
            event
            for event in events
            if event.get("project_id") == project_id and event.get("request_path") == f"/projects/{project_id}/next"
        ]
        self.assertTrue(next_request_events)
        trace_ids = {
            event.get("trace_id")
            for event in next_request_events
            if event.get("trace_id")
        }
        self.assertTrue(trace_ids)


if __name__ == "__main__":
    unittest.main()
