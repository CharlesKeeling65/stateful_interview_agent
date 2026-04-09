import unittest
from pathlib import Path

import main


class DevLauncherTests(unittest.TestCase):
    def test_build_backend_command_uses_current_python(self):
        command = main.build_backend_command(
            python_executable="/tmp/venv/bin/python",
            host="127.0.0.1",
            port=8000,
        )

        self.assertEqual(
            command,
            [
                "/tmp/venv/bin/python",
                "-m",
                "uvicorn",
                "app.main:app",
                "--reload",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
        )

    def test_build_frontend_command_uses_windows_npm_cmd(self):
        command = main.build_frontend_command(is_windows=True)

        self.assertEqual(command, ["npm.cmd", "run", "dev"])

    def test_build_frontend_command_uses_unix_npm(self):
        command = main.build_frontend_command(is_windows=False)

        self.assertEqual(command, ["npm", "run", "dev"])

    def test_frontend_directory_points_to_repo_frontend(self):
        self.assertEqual(main.FRONTEND_DIR, Path(__file__).resolve().parents[1] / "frontend")


if __name__ == "__main__":
    unittest.main()
