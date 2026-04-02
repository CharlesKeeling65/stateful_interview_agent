from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.debug import router as debug_router
from app.api.routes.projects import router as project_router
from app.core.config import settings
from app.core.database import ensure_database_schema
from app.models import InterviewTurn, LLMUsage, ProjectSession

ensure_database_schema()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
    }


app.include_router(project_router)
app.include_router(debug_router)
