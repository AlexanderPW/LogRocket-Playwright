from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .dashboard_data import output_dir, read_spec_for_flow
from .fixture_recorder import ensure_playwright_project
from .flow_runtime import load_runtime_settings


def find_spec_path(flow_name: str, base: Path | None = None) -> Path | None:
    root = base or output_dir()
    spec_name, _ = read_spec_for_flow(flow_name, base=root)
    if not spec_name:
        return None
    path = root / spec_name
    return path if path.exists() else None


def _staging_base_url(flow_name: str, root: Path) -> str:
    return load_runtime_settings(flow_name, base=root).base_url


def run_playwright_flow(
    flow_name: str,
    *,
    headed: bool = False,
    slow_mo: int = 0,
) -> dict[str, object]:
    root = output_dir()
    spec_path = find_spec_path(flow_name, base=root)
    if not spec_path:
        raise FileNotFoundError(f"No Playwright spec found for flow '{flow_name}'")

    staging = _staging_base_url(flow_name, root)
    ensure_playwright_project(root, staging)

    if not (root / "node_modules").exists():
        install = subprocess.run(
            ["npm", "install"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            raise RuntimeError(
                "npm install failed in generated-tests:\n"
                + (install.stderr or install.stdout)
            )

    env = {
        **os.environ,
        "STAGING_BASE_URL": staging,
        "SLOW_MO": str(slow_mo) if slow_mo > 0 else "",
    }

    cmd = ["npx", "playwright", "test", spec_path.name, "--reporter=line"]
    if headed:
        cmd.append("--headed")

    proc = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )

    logs = (proc.stdout or "") + (proc.stderr or "")
    passed = proc.returncode == 0

    return {
        "flow_name": flow_name,
        "spec": spec_path.name,
        "headed": headed,
        "slow_mo": slow_mo,
        "exit_code": proc.returncode,
        "passed": passed,
        "logs": logs,
        "base_url": staging,
        "api_mode": load_runtime_settings(flow_name, base=root).api_mode,
    }
