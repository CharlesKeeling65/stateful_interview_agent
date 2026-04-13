import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core import runtime


class RuntimePackagingTests(unittest.TestCase):
    def test_prefers_current_working_directory_in_source_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            (cwd / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

            runtime_root = runtime.get_runtime_root(cwd=cwd, frozen=False)

            self.assertEqual(runtime_root, cwd.resolve())

    def test_uses_windows_executable_directory_when_frozen(self):
        executable = Path("/bundle/StatefulInterviewAgent.exe")

        runtime_root = runtime.get_runtime_root(
            cwd=Path("/ignored"),
            executable=executable,
            frozen=True,
        )

        self.assertEqual(runtime_root, executable.parent.resolve())

    def test_uses_linux_executable_directory_when_frozen(self):
        executable = Path("/bundle/StatefulInterviewAgent")

        runtime_root = runtime.get_runtime_root(
            cwd=Path("/ignored"),
            executable=executable,
            frozen=True,
        )

        self.assertEqual(runtime_root, executable.parent.resolve())

    def test_uses_explicit_env_file_override(self):
        env_file = Path("/tmp/custom.env")

        resolved = runtime.get_env_file_path(
            environ={"STATEFUL_AGENT_ENV_FILE": str(env_file)},
            runtime_root=Path("/unused"),
            project_root=Path("/project"),
        )

        self.assertEqual(resolved, env_file.resolve())

    def test_normalizes_relative_runtime_paths(self):
        runtime_root = Path("/bundle")

        self.assertEqual(
            runtime.normalize_database_url("sqlite:///./data/app.db", runtime_root),
            "sqlite:////bundle/data/app.db",
        )
        self.assertEqual(
            runtime.resolve_runtime_path("./logs", runtime_root),
            "/bundle/logs",
        )

    def test_prefers_packaged_frontend_dist_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = Path(temp_dir)
            packaged_dist = bundle_root / "frontend" / "dist"
            packaged_dist.mkdir(parents=True)

            resolved = runtime.get_frontend_dist_dir(
                bundle_root=bundle_root,
                runtime_root=bundle_root / "runtime",
            )

            self.assertEqual(resolved, packaged_dist)

    def test_creates_runtime_data_and_log_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)

            runtime.ensure_runtime_directories(
                database_url="sqlite:///./data/app.db",
                log_dir=str(runtime_root / "logs"),
                runtime_root=runtime_root,
            )

            self.assertTrue((runtime_root / "data").is_dir())
            self.assertTrue((runtime_root / "logs").is_dir())

    def test_linux_build_workflow_pins_compatible_ubuntu_runner(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "build-linux-bundle.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("runs-on: ubuntu-22.04", workflow)


class AppFactoryTests(unittest.TestCase):
    def test_serves_built_frontend_when_dist_is_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            frontend_dist = Path(temp_dir) / "frontend" / "dist"
            frontend_dist.mkdir(parents=True)
            (frontend_dist / "index.html").write_text(
                "<html><body>Stateful Interview Agent</body></html>",
                encoding="utf-8",
            )

            from app.main import create_app

            client = TestClient(create_app(frontend_dist_dir=frontend_dist))
            response = client.get("/")

            self.assertEqual(response.status_code, 200)
            self.assertIn("Stateful Interview Agent", response.text)


if __name__ == "__main__":
    unittest.main()
