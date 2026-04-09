import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.debug import router as debug_router
from app.api.routes.projects import router as project_router
from app.core.config import settings
from app.core.database import ensure_database_schema
from app.core.http_clients import close_opencode_client
from app.core.runtime import get_frontend_dist_dir
from app.logging import clear_log_context, configure_logging, emit_event, set_log_context
from app.models import InterviewTurn, LLMUsage, ProjectSession

ensure_database_schema()
configure_logging()


def create_app(*, frontend_dist_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            close_opencode_client()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        trace_id = request.headers.get("x-trace-id") or request_id
        token = set_log_context(
            request_id=request_id,
            trace_id=trace_id,
            request_method=request.method,
            request_path=request.url.path,
        )
        start_time = time.perf_counter()

        emit_event(
            "requests",
            "http.request.start",
            "HTTP request started",
            status="started",
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            emit_event(
                "requests",
                "http.request.error",
                "HTTP request failed",
                level=40,
                status="error",
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                exc_info=exc,
            )
            clear_log_context(token)
            raise

        response.headers["x-request-id"] = request_id
        response.headers["x-trace-id"] = trace_id
        emit_event(
            "requests",
            "http.request.complete",
            "HTTP request completed",
            status="success",
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )
        clear_log_context(token)
        return response

    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "app_name": settings.app_name,
            "environment": settings.app_env,
        }

    app.include_router(project_router)
    app.include_router(debug_router)

    frontend_dist_dir = frontend_dist_dir or get_frontend_dist_dir()
    if frontend_dist_dir:
        app.mount("/", StaticFiles(directory=frontend_dist_dir, html=True), name="frontend")

    return app


app = create_app()
