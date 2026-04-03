import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.graphs.interview_nodes import load_project_context, persist_next_step
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn


class WorkflowStateIntegrityTests(unittest.TestCase):
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

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_load_project_context_resets_request_scoped_graph_fields(self):
        db = self.SessionLocal()
        try:
            project = ProjectSession(
                project_name="Integrity Test",
                system_prompt="You are a stateful interview agent.",
                current_stage="Panorama Mapping",
                turn_count=1,
                status="active",
            )
            db.add(project)
            db.flush()
            db.add(
                InterviewTurn(
                    project_id=project.id,
                    turn_no=1,
                    stage="Panorama Mapping",
                    question_text="Q1: What does the project do?",
                    answer_text=None,
                )
            )
            db.commit()

            payload = load_project_context(
                {
                    "project_id": project.id,
                    "answer_text": "fresh answer",
                    "next_turn_no": 99,
                    "next_stage": "Code Detail Completion",
                    "generated_question": "Q99: stale",
                    "selected_branch_ids": ["stale-branch"],
                    "planner_decision": {"target_label": "stale"},
                },
                db,
            )

            self.assertIsNone(payload["next_turn_no"])
            self.assertIsNone(payload["next_stage"])
            self.assertIsNone(payload["generated_question"])
            self.assertEqual(payload["selected_branch_ids"], [])
            self.assertEqual(payload["planner_decision"], {})
        finally:
            db.close()

    def test_persist_next_step_rejects_stale_duplicate_pending_turn_submission(self):
        db = self.SessionLocal()
        try:
            project = ProjectSession(
                project_name="Duplicate Protection",
                system_prompt="You are a stateful interview agent.",
                current_stage="Panorama Mapping",
                turn_count=1,
                status="active",
            )
            db.add(project)
            db.flush()

            pending_turn = InterviewTurn(
                project_id=project.id,
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What does the project do?",
                answer_text=None,
            )
            db.add(pending_turn)
            db.commit()
            db.refresh(project)
            db.refresh(pending_turn)

            stale_state = {
                "project_id": project.id,
                "pending_turn_id": pending_turn.id,
                "answer_text": "First answer.",
                "next_turn_no": 2,
                "next_stage": "Panorama Mapping",
                "generated_question": "Q2: Which modules are involved?",
                "question_usage_metrics": [],
                "selected_branch_ids": [],
            }

            first_result = persist_next_step(stale_state, db)
            self.assertIn("successfully", first_result["message"].lower())

            with self.assertRaises(ValueError):
                persist_next_step(stale_state, db)

            turns = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.project_id == project.id)
                .order_by(InterviewTurn.turn_no.asc(), InterviewTurn.id.asc())
                .all()
            )
            self.assertEqual([turn.turn_no for turn in turns], [1, 2])
            self.assertEqual(sum(1 for turn in turns if turn.turn_no == 2), 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
