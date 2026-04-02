from fastapi import FastAPI

from app.api.routes.debug import router as debug_router
from app.api.routes.projects import router as project_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import InterviewTurn, ProjectSession

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
    }


app.include_router(project_router)
app.include_router(debug_router)
