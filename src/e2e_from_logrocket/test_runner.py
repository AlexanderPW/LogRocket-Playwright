from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _ensure_npm_deps(root: Path) -> None:
    if (root / "node_modules").exists():
        return
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


def _parse_playwright_report(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _summarize_report(report: dict[str, Any] | None) -> dict[str, int]:
    stats = (report or {}).get("stats") or {}
    return {
        "passed": int(stats.get("expected") or 0),
        "failed": int(stats.get("unexpected") or 0),
        "flaky": int(stats.get("flaky") or 0),
        "skipped": int(stats.get("skipped") or 0),
        "duration_ms": int(stats.get("duration") or 0),
    }


def _extract_error_summary(report: dict[str, Any] | None) -> str | None:
    if not report:
        return None

    for suite in report.get("suites") or []:
        for spec in suite.get("specs") or []:
            for test in spec.get("tests") or []:
                for result in test.get("results") or []:
                    if result.get("status") not in {"failed", "timedOut", "interrupted"}:
                        continue
                    for err in result.get("errors") or []:
                        message = err.get("message")
                        if message:
                            return str(message).split("\n")[0][:500]
    for err in report.get("errors") or []:
        message = err.get("message")
        if message:
            return str(message).split("\n")[0][:500]
    return None


def _derive_status(
    *,
    exit_code: int,
    summary: dict[str, int],
) -> str:
    if summary["flaky"] > 0:
        return "flaky"
    if exit_code != 0 or summary["failed"] > 0:
        return "failed"
    if summary["passed"] == 0 and summary["skipped"] > 0:
        return "skipped"
    return "passed"


def run_playwright_flow(
    flow_name: str,
    *,
    headed: bool = False,
    slow_mo: int = 0,
    retries: int = 0,
    capture_json: bool = False,
) -> dict[str, object]:
    root = output_dir()
    spec_path = find_spec_path(flow_name, base=root)
    if not spec_path:
        raise FileNotFoundError(f"No Playwright spec found for flow '{flow_name}'")

    staging = _staging_base_url(flow_name, root)
    runtime = load_runtime_settings(flow_name, base=root)
    ensure_playwright_project(root, staging)
    _ensure_npm_deps(root)

    started_at = datetime.now(timezone.utc)

    env = {
        **os.environ,
        "STAGING_BASE_URL": staging,
        "SLOW_MO": str(slow_mo) if slow_mo > 0 else "",
    }

    reporters = ["line"]
    json_path: Path | None = None
    if capture_json:
        json_path = Path(tempfile.mkdtemp()) / "playwright-report.json"
        env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = str(json_path)
        reporters = ["json", "line"]

    cmd = ["npx", "playwright", "test", spec_path.name]
    for reporter in reporters:
        cmd.extend(["--reporter", reporter])
    if headed:
        cmd.append("--headed")
    if retries > 0:
        cmd.extend(["--retries", str(retries)])

    proc = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )

    finished_at = datetime.now(timezone.utc)
    logs = (proc.stdout or "") + (proc.stderr or "")

    report: dict[str, Any] | None = None
    if capture_json and json_path and json_path.exists():
        report = _parse_playwright_report(json_path.read_text(encoding="utf-8"))
    elif capture_json:
        report = _parse_playwright_report(proc.stdout or "")

    summary = _summarize_report(report)
    status = _derive_status(exit_code=proc.returncode, summary=summary)
    passed = status in {"passed", "flaky"} and summary["failed"] == 0

    return {
        "flow_name": flow_name,
        "spec": spec_path.name,
        "headed": headed,
        "slow_mo": slow_mo,
        "retries": retries,
        "exit_code": proc.returncode,
        "passed": passed,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": summary["duration_ms"]
        or int((finished_at - started_at).total_seconds() * 1000),
        "passed_count": summary["passed"],
        "failed_count": summary["failed"],
        "flaky_count": summary["flaky"],
        "skipped_count": summary["skipped"],
        "error_summary": _extract_error_summary(report),
        "logs": logs,
        "report": report,
        "base_url": staging,
        "api_mode": runtime.api_mode,
    }
