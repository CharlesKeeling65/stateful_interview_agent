import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_project_root() -> Path:
    return PROJECT_ROOT


def get_bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return PROJECT_ROOT


def get_runtime_root(
    *,
    cwd: Path | None = None,
    executable: Path | None = None,
    frozen: bool | None = None,
    environ: dict[str, str] | None = None,
    project_root: Path | None = None,
) -> Path:
    env = environ or os.environ
    project_root = project_root or PROJECT_ROOT

    runtime_dir_override = env.get("STATEFUL_AGENT_RUNTIME_DIR")
    if runtime_dir_override:
        return Path(runtime_dir_override).expanduser().resolve()

    if frozen if frozen is not None else getattr(sys, "frozen", False):
        executable = executable or Path(sys.executable)
        return executable.resolve().parent

    cwd = (cwd or Path.cwd()).resolve()
    if (cwd / "pyproject.toml").exists() or (cwd / ".env").exists():
        return cwd

    return project_root


def get_env_file_path(
    *,
    environ: dict[str, str] | None = None,
    runtime_root: Path | None = None,
    project_root: Path | None = None,
) -> Path | None:
    env = environ or os.environ
    override = env.get("STATEFUL_AGENT_ENV_FILE")
    if override:
        return Path(override).expanduser().resolve()

    runtime_root = runtime_root or get_runtime_root(environ=env, project_root=project_root)
    candidate = runtime_root / ".env"
    if candidate.exists():
        return candidate

    project_root = project_root or PROJECT_ROOT
    fallback = project_root / ".env"
    if fallback.exists():
        return fallback

    return None


def resolve_runtime_path(path_value: str, runtime_root: Path) -> str:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return str(path)
    return str((runtime_root / path).resolve())


def normalize_database_url(database_url: str, runtime_root: Path) -> str:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return database_url

    sqlite_path = database_url[len(prefix):]
    if sqlite_path == ":memory:":
        return database_url

    normalized = Path(sqlite_path).expanduser()
    if normalized.is_absolute():
        return database_url

    return f"{prefix}{(runtime_root / normalized).resolve().as_posix()}"


def get_frontend_dist_dir(
    *,
    bundle_root: Path | None = None,
    runtime_root: Path | None = None,
    project_root: Path | None = None,
) -> Path | None:
    bundle_root = bundle_root or get_bundle_root()
    runtime_root = runtime_root or get_runtime_root(project_root=project_root)
    project_root = project_root or PROJECT_ROOT

    candidates = [
        bundle_root / "frontend" / "dist",
        runtime_root / "frontend" / "dist",
        project_root / "frontend" / "dist",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
