import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import projects as project_routes
from app.core.database import Base, get_db
from app.main import app
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn


class OpenCodeApiRouteTests(unittest.TestCase):
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
                project_name="OpenCode Session",
                system_prompt="You are a stateful interview agent.",
                answer_provider_type="opencode",
                turn_count=1,
            )
            db.add(project)
            db.flush()
            turn = InterviewTurn(
                project_id=project.id,
                turn_no=1,
                stage="Panorama Mapping",
                question_text="Q1: What does this service do?",
            )
            db.add(turn)
            db.commit()
            self.project_id = project.id

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_plan_step_surfaces_provider_error_as_bad_gateway(self):
        with patch.object(
            project_routes,
            "ensure_opencode_session_with_status",
            return_value=("ses_123", False),
        ), patch.object(
            project_routes,
            "fetch_opencode_answer",
            side_effect=RuntimeError("auth_unavailable: no auth available"),
        ):
            response = self.client.post(
                f"/projects/{self.project_id}/opencode/plan-step",
                json={},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "auth_unavailable: no auth available",
        )


if __name__ == "__main__":
    unittest.main()
