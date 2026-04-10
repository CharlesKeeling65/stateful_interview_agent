import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models.agent_run import AgentRun
from app.models.llm_usage import LLMUsage
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn


class TurnTailDeleteApiTests(unittest.TestCase):
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
        self.client = TestClient(app)

        with self.SessionLocal() as db:
            project = ProjectSession(
                project_name="Tail Delete",
                system_prompt="You are a stateful interview agent.",
                current_stage="Code Detail Completion",
                turn_count=3,
            )
            db.add(project)
            db.flush()

            turn1 = InterviewTurn(
                project_id=project.id,
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What does the project do?",
                answer_text="It analyzes repositories.",
            )
            turn2 = InterviewTurn(
                project_id=project.id,
                turn_no=2,
                stage="Architecture Understanding",
                question_text="Q2: Which modules coordinate the flow?",
                answer_text="Gateway and orchestration.",
            )
            turn3 = InterviewTurn(
                project_id=project.id,
                turn_no=3,
                stage="Code Detail Completion",
                question_text="Q3: In app/services/question_generator.py, how does generation work?",
                answer_text=None,
            )
            db.add_all([turn1, turn2, turn3])
            db.flush()

            db.add_all([
                AgentRun(project_id=project.id, turn_no=1, status="completed"),
                AgentRun(project_id=project.id, turn_no=2, status="completed"),
                AgentRun(project_id=project.id, turn_no=3, status="running"),
                LLMUsage(project_id=project.id, turn_id=turn2.id, operation_type="question_generation", prompt_tokens=10, completion_tokens=4, total_tokens=14),
                LLMUsage(project_id=project.id, turn_id=turn3.id, operation_type="question_generation", prompt_tokens=12, completion_tokens=5, total_tokens=17),
            ])
            db.commit()

            self.project_id = project.id
            self.turn2_id = turn2.id

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_delete_turn_tail_removes_selected_turn_and_later_history(self):
        response = self.client.delete(f"/projects/{self.project_id}/turns/{self.turn2_id}/tail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project_id"], self.project_id)
        self.assertEqual(payload["deleted_from_turn_no"], 2)
        self.assertEqual(payload["remaining_turn_count"], 1)

        with self.SessionLocal() as db:
            turns = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.project_id == self.project_id)
                .order_by(InterviewTurn.turn_no.asc())
                .all()
            )
            self.assertEqual([turn.turn_no for turn in turns], [1])

            runs = (
                db.query(AgentRun)
                .filter(AgentRun.project_id == self.project_id)
                .order_by(AgentRun.turn_no.asc())
                .all()
            )
            self.assertEqual([run.turn_no for run in runs], [1])

            usages = (
                db.query(LLMUsage)
                .filter(LLMUsage.project_id == self.project_id)
                .order_by(LLMUsage.id.asc())
                .all()
            )
            self.assertEqual(usages, [])

            project = db.query(ProjectSession).filter(ProjectSession.id == self.project_id).first()
            self.assertIsNotNone(project)
            self.assertEqual(project.turn_count, 1)
            self.assertEqual(project.current_stage, "Panorama Mapping")


if __name__ == "__main__":
    unittest.main()
