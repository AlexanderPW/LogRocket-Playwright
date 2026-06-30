from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class EnvStatus:
    name: str
    set: bool
    required_for: str


@dataclass
class FlowSummary:
    name: str
    has_flow_json: bool
    has_api_mocks: bool
    has_spec: bool
    has_har: bool
    fixture_count: int
    mock_count: int
    fulfill_count: int
    transform_count: int
    start_url: str | None = None
    step_count: int = 0
    session_ids: list[str] = field(default_factory=list)


def output_dir() -> Path:
    return Path(os.getenv("E2E_OUTPUT_DIR", "./generated-tests")).resolve()


def env_statuses() -> list[EnvStatus]:
    checks = [
        ("LOGROCKET_API_KEY", "generate"),
        ("LOGROCKET_ORG_ID", "generate"),
        ("LOGROCKET_PROJECT_ID", "generate"),
        ("OLLAMA_MODEL", "generate"),
        ("STAGING_BASE_URL", "record-fixtures"),
    ]
    return [
        EnvStatus(name=name, set=bool(os.getenv(name, "").strip()), required_for=purpose)
        for name, purpose in checks
    ]


def has_spec_for_flow(flow_name: str, base: Path | None = None) -> bool:
    root = base or output_dir()
    if (root / f"{flow_name}.spec.ts").exists():
        return True
    return any(root.glob(f"*{flow_name}*.spec.ts"))


def scan_flow_dir(flow_dir: Path, root: Path) -> FlowSummary:
    name = flow_dir.name
    flow_json_path = flow_dir / "flow.json"
    mocks_path = flow_dir / "api-mocks.json"
    har_path = flow_dir / "capture.har"

    start_url = None
    step_count = 0
    session_ids: list[str] = []
    mock_count = fulfill_count = transform_count = 0

    if flow_json_path.exists():
        flow_data = json.loads(flow_json_path.read_text(encoding="utf-8"))
        start_url = flow_data.get("start_url")
        step_count = len(flow_data.get("steps", []))
        session_ids = flow_data.get("source_session_ids", [])

    if mocks_path.exists():
        manifest = json.loads(mocks_path.read_text(encoding="utf-8"))
        mocks = manifest.get("mocks", [])
        mock_count = len(mocks)
        fulfill_count = sum(1 for m in mocks if not m.get("transformResponse"))
        transform_count = sum(1 for m in mocks if m.get("transformResponse"))

    fixture_files = [
        p
        for p in flow_dir.glob("*.json")
        if p.name not in {"api-mocks.json", "flow.json", "runtime.json"}
    ]

    return FlowSummary(
        name=name,
        has_flow_json=flow_json_path.exists(),
        has_api_mocks=mocks_path.exists(),
        has_spec=has_spec_for_flow(name, base=root),
        has_har=har_path.exists(),
        fixture_count=len(fixture_files),
        mock_count=mock_count,
        fulfill_count=fulfill_count,
        transform_count=transform_count,
        start_url=start_url,
        step_count=step_count,
        session_ids=session_ids,
    )


def list_flows(base: Path | None = None) -> list[FlowSummary]:
    """Return all flows from the cached index (syncs incrementally when needed)."""
    from .flow_index import list_flows_paginated

    page = list_flows_paginated(base=base, page=1, page_size=10_000)
    return page.items


def read_flow_file(flow_name: str, filename: str, base: Path | None = None) -> str | None:
    path = (base or output_dir()) / "fixtures" / flow_name / filename
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def read_spec_for_flow(flow_name: str, base: Path | None = None) -> tuple[str | None, str | None]:
    root = base or output_dir()
    exact = root / f"{flow_name}.spec.ts"
    if exact.exists():
        return exact.name, exact.read_text(encoding="utf-8")

    for path in sorted(root.glob(f"*{flow_name}*.spec.ts")):
        return path.name, path.read_text(encoding="utf-8")
    return None, None


def read_support_file(flow_name: str, base: Path | None = None) -> str | None:
    path = (base or output_dir()) / "support" / f"{flow_name}.test-data.ts"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
