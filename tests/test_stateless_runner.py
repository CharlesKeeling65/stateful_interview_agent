import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.baselines.stateless_qa import submit_answer_and_generate_next_stateless
from app.core import database as core_database_module
from app.core.database import Base
from app.graphs import interview_graph as graph_module
from app.models.agent_run import AgentRun
from app.models.project import ProjectSession
from app.models.turn import InterviewTurn
from app.services import question_generator, run_trace_service


class _FakeProvider:
    def generate_text(self, *, messages, **_kwargs):
        return SimpleNamespace(
            text="Q4: Which module now owns the unresolved flow from the last few turns?",
            model="fake-model",
            usage=SimpleNamespace(prompt_tokens=90, completion_tokens=20, total_tokens=110),
        )


class StatelessRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.database_path}",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        Base.metadata.create_all(bind=self.engine)

        self.original_graph_session_local = graph_module.SessionLocal
        self.original_trace_session_local = run_trace_service.SessionLocal
        self.original_core_session_local = core_database_module.SessionLocal
        graph_module.SessionLocal = self.SessionLocal
        run_trace_service.SessionLocal = self.SessionLocal
        core_database_module.SessionLocal = self.SessionLocal

        self.original_provider = question_generator.get_llm_provider
        question_generator.get_llm_provider = lambda: _FakeProvider()

        self.workspace_root = Path(self.temp_dir.name) / 'workspace'
        (self.workspace_root / 'experiment_assets' / 'tasks').mkdir(parents=True)
        (self.workspace_root / 'experiment_assets').mkdir(parents=True, exist_ok=True)
        (self.workspace_root / 'experiment_assets' / 'repos.csv').write_text(
            'repo_id,repo_label,repo_path_or_url,repo_snapshot_ref\n'
            'r001,stateful_interview_agent,/Users/wyb/File/Programming/Git_Code/stateful_interview_agent,commit\n',
            encoding='utf-8',
        )
        (self.workspace_root / 'experiment_assets' / 'tasks' / 'r001_t001.yaml').write_text(
            'task_id: r001_t001\n'
            'task_label: "Mock Task"\n'
            'operator_role: "Technical reviewer"\n'
            'objective: >\n'
            '  Validate initialization and gate bypass.\n',
            encoding='utf-8',
        )
        self.manifest_path = self.workspace_root / 'experiment_assets' / 'run_manifest.csv'
        self.manifest_path.write_text(
            "run_id,repo_id,task_id,system_id,system_config_id,replicate_id,repo_snapshot_ref,task_file,gold_file,coverage_schema_ref,turn_annotation_file,final_annotation_file,output_root,db_snapshot_path,logs_root,results_core_csv,results_turns_csv,results_ablations_csv,status,execution_status,started_at,completed_at,runner_version,random_seed,owner,notes\n"
            f"run_005,r001,r001_t001,no_human_review,no_human_review,1,commit,experiment_assets/tasks/r001_t001.yaml,experiment_assets/gold/r001_t001_gold_v1.yaml,experiment_assets/coverage_schema.yaml,turn.csv,final.csv,{self.temp_dir.name},{self.database_path},{Path(self.temp_dir.name) / 'logs'},core.csv,turns.csv,ablations.csv,planned,not_started,,,v0.1,42,tester,\n",
            encoding="utf-8",
        )

    def tearDown(self):
        graph_module.SessionLocal = self.original_graph_session_local
        run_trace_service.SessionLocal = self.original_trace_session_local
        core_database_module.SessionLocal = self.original_core_session_local
        question_generator.get_llm_provider = self.original_provider
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _seed_project_with_answered_turns(self) -> int:
        db = self.SessionLocal()
        try:
            project = ProjectSession(
                project_name="Stateless Baseline Project",
                system_prompt="You are a repository-understanding interviewer.",
                current_stage="Architecture Understanding",
                turn_count=4,
                status="active",
                coverage_state=json.dumps({
                    "version": 1,
                    "branch_count": 2,
                    "updated_through_turn_no": 4,
                    "branches": [{"branch_id": "b1", "status": "covered"}, {"branch_id": "b2", "status": "covered"}],
                }),
            )
            db.add(project)
            db.flush()
            turns = [
                InterviewTurn(project_id=project.id, turn_no=1, stage="Panorama Mapping", question_text="Q1: What problem does this system solve?", answer_text="It coordinates repository interviews."),
                InterviewTurn(project_id=project.id, turn_no=2, stage="Architecture Understanding", question_text="Q2: Which services orchestrate the interview?", answer_text="The routes and graph nodes orchestrate it."),
                InterviewTurn(project_id=project.id, turn_no=3, stage="Architecture Understanding", question_text="Q3: How is coverage tracked?", answer_text="Coverage is serialized on ProjectSession."),
                InterviewTurn(project_id=project.id, turn_no=4, stage="Architecture Understanding", question_text="Q4: Where is the current persistence boundary?", answer_text="Persistence happens after question drafting."),
            ]
            db.add_all(turns)
            db.commit()
            return project.id
        finally:
            db.close()

    def test_stateless_baseline_uses_three_turn_window_and_clears_coverage(self):
        project_id = self._seed_project_with_answered_turns()
        db = self.SessionLocal()
        try:
            result = submit_answer_and_generate_next_stateless(project_id=project_id, db=db)
            self.assertEqual(result["next_turn"].turn_no, 5)
            self.assertEqual(result["next_turn"].question_plan["system_id"], "stateless_qa")
            self.assertEqual(result["next_turn"].question_plan["sliding_window_size"], 3)
            self.assertEqual(result["next_turn"].question_plan["selected_turn_ids"], [2, 3, 4])
            self.assertTrue(result["next_turn"].question_plan["coverage_state_cleared"])
            self.assertEqual(result["project"].coverage_state_data["branch_count"], 0)
            self.assertEqual(result["project"].coverage_state_data["branches"], [])
            self.assertEqual(result["project"].coverage_state_data["updated_through_turn_no"], 5)

            run = db.query(AgentRun).filter(AgentRun.id == result["run_id"]).first()
            self.assertIsNotNone(run)
            self.assertEqual(run.status, "completed")
            self.assertGreaterEqual(run.step_count, 3)
            self.assertIn("build_compact_context", [step.step_key for step in run.steps])
            self.assertIn("render_prompt", [step.step_key for step in run.steps])
            self.assertIn("call_llm", [step.step_key for step in run.steps])
            self.assertIn("persist_result", [step.step_key for step in run.steps])
        finally:
            db.close()

    def test_runner_auto_initializes_project_from_manifest(self):
        from app import runner as runner_module

        os.environ["DATABASE_URL"] = f"sqlite:///{self.database_path.as_posix()}"
        project_id = runner_module.ensure_project_initialized(
            run_manifest=self.manifest_path,
            row=runner_module.load_manifest_row(self.manifest_path, "run_005"),
        )

        db = self.SessionLocal()
        try:
            project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
            self.assertIsNotNone(project)
            self.assertEqual(project.turn_count, 1)
            self.assertEqual(project.repo_source_type, "local_path")
            latest_turn = db.query(InterviewTurn).filter(InterviewTurn.project_id == project_id).order_by(InterviewTurn.turn_no.desc()).first()
            self.assertIsNotNone(latest_turn)
            self.assertIsNotNone(latest_turn.answer_text)
            self.assertIn("Mock execution answer", latest_turn.answer_text)
        finally:
            db.close()

    def test_runner_dispatches_stateless_condition(self):
        from app import runner as runner_module
        with patch("app.baselines.stateless_qa.submit_answer_and_generate_next_stateless", return_value={"run_id": 123, "message": "ok"}) as stateless_mock:
            result = runner_module.run_next_turn(project_id=77, system_id="stateless_qa")
        self.assertEqual(result["run_id"], 123)
        stateless_mock.assert_called_once()

    def test_runner_dispatches_from_manifest_run_id(self):
        project_id = self._seed_project_with_answered_turns()
        from app import runner as runner_module
        runner_module.configure_runtime_from_manifest(runner_module.load_manifest_row(self.manifest_path, "run_005"))
        with patch("app.baselines.stateless_qa.submit_answer_and_generate_next_stateless", return_value={"run_id": 321, "message": "ok"}) as stateless_mock:
            result = runner_module.run_next_turn(project_id=project_id, system_id="stateless_qa")
        self.assertEqual(result["run_id"], 321)
        stateless_mock.assert_called_once()

    def test_runner_dispatches_full_system_condition(self):
        from app import runner as runner_module
        with patch("app.api.routes.projects.submit_answer_and_generate_next", return_value={"run_id": 456, "message": "ok"}) as full_mock:
            result = runner_module.run_next_turn(project_id=88, system_id="full_system")
        self.assertEqual(result["run_id"], 456)
        full_mock.assert_called_once()

    def test_no_human_review_auto_resolves_pending_gate(self):
        from app import runner as runner_module

        project_id = self._seed_project_with_answered_turns()
        db = self.SessionLocal()
        try:
            project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
            project.pending_gate_json = json.dumps(
                {
                    "gate_id": "gate_001",
                    "gate_type": "phase_completion",
                    "reason": "Need confirmation",
                    "default_action": "confirm",
                    "options": [],
                    "resolved": False,
                    "resolution": None,
                }
            )
            db.commit()
        finally:
            db.close()

        call_state = {"calls": 0}

        def fake_submit_answer_and_generate_next(*, project_id, payload, db):
            call_state["calls"] += 1
            project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
            if call_state["calls"] == 1:
                return {"project": project, "pending_gate_active": True, "interview_finished": False, "message": "gate"}
            project.pending_gate_json = "null"
            db.commit()
            return {"project": project, "pending_gate_active": False, "interview_finished": False, "message": "ok", "run_id": 999}

        with patch("app.api.routes.projects.submit_answer_and_generate_next", side_effect=fake_submit_answer_and_generate_next):
            result = runner_module.run_next_turn(project_id=project_id, system_id="no_human_review")

        self.assertEqual(result["run_id"], 999)
        self.assertEqual(call_state["calls"], 2)

    def test_run_005_fresh_db_mock_execution(self):
        from app import runner as runner_module

        os.environ["DATABASE_URL"] = f"sqlite:///{self.database_path.as_posix()}"
        row = runner_module.load_manifest_row(self.manifest_path, "run_005")
        project_id = runner_module.ensure_project_initialized(run_manifest=self.manifest_path, row=row)

        def fake_submit_answer_and_generate_next(*, project_id, payload, db):
            project = db.query(ProjectSession).filter(ProjectSession.id == project_id).first()
            if project.pending_gate:
                project.pending_gate_json = "null"
                db.commit()
                return {"project": project, "pending_gate_active": False, "interview_finished": False, "message": "continued", "run_id": 2002}
            project.pending_gate_json = json.dumps(
                {
                    "gate_id": "gate_run005",
                    "gate_type": "phase_completion",
                    "reason": "Need confirmation",
                    "default_action": "confirm",
                    "options": [],
                    "resolved": False,
                    "resolution": None,
                }
            )
            db.commit()
            return {"project": project, "pending_gate_active": True, "interview_finished": False, "message": "gate"}

        with patch("app.api.routes.projects.submit_answer_and_generate_next", side_effect=fake_submit_answer_and_generate_next):
            result = runner_module.run_next_turn(project_id=project_id, system_id="no_human_review")

        self.assertEqual(result["run_id"], 2002)


if __name__ == "__main__":
    unittest.main()
