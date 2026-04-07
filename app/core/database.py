from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    connect_args=(
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    ),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database_schema():
    Base.metadata.create_all(bind=engine)

    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "interview_turns" in inspector.get_table_names():
        existing_columns = {
            column["name"] for column in inspector.get_columns("interview_turns")
        }
        with engine.begin() as connection:
            if "answer_summary" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE interview_turns ADD COLUMN answer_summary TEXT")
                )
            if "answer_analysis_json" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE interview_turns ADD COLUMN answer_analysis_json TEXT")
                )
            if "question_plan_json" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE interview_turns ADD COLUMN question_plan_json TEXT")
                )
            if "human_review_json" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE interview_turns ADD COLUMN human_review_json TEXT")
                )
            if "event_log_json" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE interview_turns ADD COLUMN event_log_json TEXT DEFAULT '[]'")
                )

    if "interview_question_versions" not in inspector.get_table_names():
        Base.metadata.tables["interview_question_versions"].create(bind=engine)

    if "project_sessions" in inspector.get_table_names():
        existing_columns = {
            column["name"] for column in inspector.get_columns("project_sessions")
        }
        with engine.begin() as connection:
            if "coverage_state" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE project_sessions ADD COLUMN coverage_state TEXT DEFAULT "
                        "'{\"version\": 1, \"branch_count\": 0, \"updated_through_turn_no\": 0, \"branches\": []}'"
                    )
                )
            if "repo_source_type" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE project_sessions ADD COLUMN repo_source_type TEXT DEFAULT 'none'"
                    )
                )
            if "repo_local_path" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE project_sessions ADD COLUMN repo_local_path TEXT")
                )
            if "repo_git_url" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE project_sessions ADD COLUMN repo_git_url TEXT")
                )
            if "repo_git_ref" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE project_sessions ADD COLUMN repo_git_ref TEXT")
                )
            if "repo_cache_path" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE project_sessions ADD COLUMN repo_cache_path TEXT")
                )
            if "repo_commit_sha" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE project_sessions ADD COLUMN repo_commit_sha TEXT")
                )
            if "repo_manifest_json" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE project_sessions ADD COLUMN repo_manifest_json TEXT DEFAULT '{}'"
                    )
                )
            if "agent_mode" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE project_sessions ADD COLUMN agent_mode TEXT DEFAULT 'understand_current_code'"
                    )
                )
            if "rubric_task_board" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE project_sessions ADD COLUMN rubric_task_board TEXT DEFAULT '{}'"
                    )
                )
            if "answer_provider_type" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE project_sessions ADD COLUMN answer_provider_type TEXT DEFAULT 'manual'"
                    )
                )
            if "answer_automation_enabled" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE project_sessions ADD COLUMN answer_automation_enabled BOOLEAN DEFAULT 0"
                    )
                )
            if "opencode_session_id" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE project_sessions ADD COLUMN opencode_session_id TEXT")
                )
