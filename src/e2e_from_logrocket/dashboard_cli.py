"""Launch the local Streamlit dashboard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    entry = Path(__file__).resolve().parent / "dashboard_entry.py"
    extra = sys.argv[1:] if len(sys.argv) > 1 else []
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(entry), *extra],
        )
    )
