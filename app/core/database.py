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
