"""Launch the FastAPI backend for the web dashboard."""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "e2e_from_logrocket.api.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8001",
                "--reload",
                *sys.argv[1:],
            ]
        )
    )
