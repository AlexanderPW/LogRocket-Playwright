from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import RecordSettings
from .fixture_recorder import (
    ensure_playwright_project,
    process_har_to_fixtures,
    RecordFixturesResult,
)
from .pii import PIISanitizer


def _resolve_flow_dir(settings: RecordSettings, flow_name: str) -> Path:
    flow_dir = Path(settings.e2e_output_dir) / "fixtures" / flow_name
    if not flow_dir.exists():
        raise FileNotFoundError(
            f"Flow fixtures not found at {flow_dir}. Run `e2e-from-logrocket generate` first."
        )
    return flow_dir


def run_playwright_har_capture(settings: RecordSettings, flow_name: str) -> Path:
    output_dir = Path(settings.e2e_output_dir).resolve()
    flow_dir = _resolve_flow_dir(settings, flow_name)
    har_path = flow_dir / "capture.har"

    ensure_playwright_project(output_dir, settings.staging_base_url)

    if shutil.which("npx") is None:
        raise RuntimeError("npx not found. Install Node.js to record fixtures with Playwright.")

    if not (output_dir / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=output_dir, check=True)
        subprocess.run(
            ["npx", "playwright", "install", settings.playwright_browser],
            cwd=output_dir,
            check=True,
        )

    env = {
        **os.environ,
        "FLOW_NAME": flow_name,
        "STAGING_BASE_URL": settings.staging_base_url,
    }
    subprocess.run(
        [
            "npx",
            "playwright",
            "test",
            "support/record-flow.spec.ts",
            "--grep",
            "@recorder",
        ],
        cwd=output_dir,
        env=env,
        check=True,
    )

    if not har_path.exists():
        raise FileNotFoundError(
            f"Expected HAR at {har_path} after recording. "
            "Check that staging is reachable and the flow replays successfully."
        )
    return har_path


def record_fixtures_from_har(
    settings: RecordSettings,
    flow_name: str,
    har_path: Path | None = None,
) -> RecordFixturesResult:
    flow_dir = _resolve_flow_dir(settings, flow_name)
    sanitizer = PIISanitizer(seed=settings.faker_seed)

    if har_path is None:
        har_path = run_playwright_har_capture(settings, flow_name)
    elif not har_path.exists():
        raise FileNotFoundError(f"HAR file not found: {har_path}")

    return process_har_to_fixtures(har_path, flow_dir, sanitizer)
