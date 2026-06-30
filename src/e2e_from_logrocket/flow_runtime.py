from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .dashboard_data import output_dir

ApiMode = Literal["live_obfuscate", "offline_fixtures", "passthrough"]


class FlowRuntimeSettings(BaseModel):
    """Per-flow settings for where tests run and how API traffic is handled."""

    base_url: str = Field(description="Playwright baseURL / target environment")
    api_mode: ApiMode = Field(
        default="live_obfuscate",
        description=(
            "live_obfuscate: hit real APIs, redact PII in responses; "
            "offline_fixtures: serve sanitized JSON fixtures; "
            "passthrough: no route interception"
        ),
    )


def _flow_dir(flow_name: str, base: Path | None = None) -> Path:
    return (base or output_dir()) / "fixtures" / flow_name


def _runtime_path(flow_name: str, base: Path | None = None) -> Path:
    return _flow_dir(flow_name, base) / "runtime.json"


def _manifest_path(flow_name: str, base: Path | None = None) -> Path:
    return _flow_dir(flow_name, base) / "api-mocks.json"


def _default_base_url(flow_name: str, base: Path | None = None) -> str:
    import os

    staging = os.getenv("STAGING_BASE_URL", "").strip()
    if staging:
        return staging.rstrip("/")

    flow_json = _flow_dir(flow_name, base) / "flow.json"
    if flow_json.exists():
        data = json.loads(flow_json.read_text(encoding="utf-8"))
        start = data.get("start_url") or ""
        if start.startswith("http"):
            from urllib.parse import urlparse

            parsed = urlparse(start)
            return f"{parsed.scheme}://{parsed.netloc}"

    return "https://portfolio.alexwaldrop.com"


def load_runtime_settings(flow_name: str, base: Path | None = None) -> FlowRuntimeSettings:
    path = _runtime_path(flow_name, base)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return FlowRuntimeSettings.model_validate(data)

    return FlowRuntimeSettings(base_url=_default_base_url(flow_name, base))


def _sync_manifest_api_mode(flow_name: str, api_mode: ApiMode, base: Path | None = None) -> None:
    manifest_path = _manifest_path(flow_name, base)
    if not manifest_path.exists():
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["apiMode"] = api_mode

    if api_mode == "live_obfuscate":
        for mock in manifest.get("mocks", []):
            mock["transformResponse"] = True
    elif api_mode == "offline_fixtures":
        for mock in manifest.get("mocks", []):
            mock["transformResponse"] = False

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def save_runtime_settings(
    flow_name: str,
    settings: FlowRuntimeSettings,
    base: Path | None = None,
) -> FlowRuntimeSettings:
    flow_dir = _flow_dir(flow_name, base)
    if not flow_dir.exists():
        raise FileNotFoundError(f"Flow '{flow_name}' not found")

    path = _runtime_path(flow_name, base)
    path.write_text(settings.model_dump_json(indent=2) + "\n", encoding="utf-8")
    _sync_manifest_api_mode(flow_name, settings.api_mode, base=base)
    return settings


def runtime_status(flow_name: str, base: Path | None = None) -> dict[str, object]:
    settings = load_runtime_settings(flow_name, base)
    manifest_path = _manifest_path(flow_name, base)
    fixture_dir = _flow_dir(flow_name, base)

    offline_ready = False
    mock_count = 0
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mocks = manifest.get("mocks", [])
        mock_count = len(mocks)
        if settings.api_mode == "offline_fixtures" and mocks:
            offline_ready = all(
                (fixture_dir / m.get("fixtureFile", "")).exists()
                for m in mocks
                if not m.get("transformResponse", False)
            )

    return {
        "settings": settings.model_dump(),
        "mock_count": mock_count,
        "offline_ready": offline_ready,
        "has_manifest": manifest_path.exists(),
    }
