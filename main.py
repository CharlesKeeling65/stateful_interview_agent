import os
import subprocess
import sys
import time
from pathlib import Path

from app.core.config import settings


ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"


def build_backend_command(*, python_executable: str, host: str, port: int) -> list[str]:
    return [
        python_executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        host,
        "--port",
        str(port),
    ]


def build_frontend_command(*, is_windows: bool) -> list[str]:
    npm_command = "npm.cmd" if is_windows else "npm"
    return [npm_command, "run", "dev"]


def terminate_process(process: subprocess.Popen[bytes] | subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    backend_command = build_backend_command(
        python_executable=sys.executable,
        host=settings.app_host,
        port=settings.app_port,
    )
    frontend_command = build_frontend_command(is_windows=os.name == "nt")

    backend = subprocess.Popen(backend_command, cwd=ROOT_DIR)
    frontend = subprocess.Popen(frontend_command, cwd=FRONTEND_DIR)
    processes = [backend, frontend]

    try:
        while True:
            backend_code = backend.poll()
            frontend_code = frontend.poll()
            if backend_code is not None or frontend_code is not None:
                return backend_code or frontend_code or 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in reversed(processes):
            terminate_process(process)


if __name__ == "__main__":
    raise SystemExit(main())
