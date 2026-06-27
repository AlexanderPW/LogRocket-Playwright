from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .pii.sanitizer import PIISanitizer
from .schemas import ApiMock


@dataclass
class CapturedResponse:
    method: str
    url: str
    status: int
    content_type: str
    body: str


@dataclass
class RecordFixturesResult:
    flow_name: str
    fixtures_written: list[Path]
    manifest_path: Path
    har_path: Path | None
    matched: int
    skipped: int


def _pattern_matches(url: str, method: str, mock: ApiMock) -> bool:
    needle = mock.url_pattern.replace("**", "").replace("*", "")
    return method.upper() == mock.method.upper() and needle in url


def load_api_manifest(fixtures_dir: Path) -> dict[str, Any]:
    manifest_path = fixtures_dir / "api-mocks.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing api-mocks.json at {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def parse_har_entries(har_path: Path) -> list[CapturedResponse]:
    payload = json.loads(har_path.read_text(encoding="utf-8"))
    entries = payload.get("log", {}).get("entries", [])
    captured: list[CapturedResponse] = []

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        content = response.get("content", {})
        text = content.get("text") or ""

        if content.get("encoding") == "base64" and text:
            text = base64.b64decode(text).decode("utf-8", errors="replace")

        captured.append(
            CapturedResponse(
                method=request.get("method", "GET"),
                url=request.get("url", ""),
                status=int(response.get("status", 0)),
                content_type=content.get("mimeType", ""),
                body=text,
            )
        )

    return captured


def _pick_best_capture(captures: list[CapturedResponse]) -> CapturedResponse | None:
    if not captures:
        return None
    # Prefer latest successful JSON response for the mock.
    json_ok = [
        c
        for c in captures
        if 200 <= c.status < 300 and ("json" in c.content_type.lower() or c.body.strip().startswith(("{", "[")))
    ]
    pool = json_ok or [c for c in captures if 200 <= c.status < 300] or captures
    return pool[-1]


def process_har_to_fixtures(
    har_path: Path,
    fixtures_dir: Path,
    sanitizer: PIISanitizer,
) -> RecordFixturesResult:
    manifest = load_api_manifest(fixtures_dir)
    flow_name = manifest.get("flowName", fixtures_dir.name)
    mocks_raw = manifest.get("mocks", [])
    mocks = [ApiMock.model_validate(item) for item in mocks_raw]

    entries = parse_har_entries(har_path)
    written: list[Path] = []
    matched = 0
    skipped = 0
    updated_mocks: list[dict[str, Any]] = []

    for mock in mocks:
        captures = [
            entry
            for entry in entries
            if _pattern_matches(entry.url, entry.method, mock)
        ]
        best = _pick_best_capture(captures)

        mock_dict: dict[str, Any] = {
            "method": mock.method,
            "urlPattern": mock.url_pattern,
            "fixtureFile": mock.fixture_file,
            "status": mock.status,
            "transformResponse": mock.transform_response,
        }
        if mock.description:
            mock_dict["description"] = mock.description

        if not best or not best.body.strip():
            skipped += 1
            updated_mocks.append(mock_dict)
            continue

        sanitized = sanitizer.sanitize_response_body(best.body, best.content_type)
        fixture_path = fixtures_dir / mock.fixture_file
        fixture_path.write_text(sanitized + "\n", encoding="utf-8")
        written.append(fixture_path)

        mock_dict["status"] = best.status
        mock_dict["transformResponse"] = False
        mock_dict["description"] = mock.description or f"Recorded from staging ({best.method} {best.url})"
        updated_mocks.append(mock_dict)
        matched += 1

    manifest_path = fixtures_dir / "api-mocks.json"
    manifest_path.write_text(
        json.dumps({"flowName": flow_name, "mocks": updated_mocks}, indent=2) + "\n",
        encoding="utf-8",
    )

    return RecordFixturesResult(
        flow_name=flow_name,
        fixtures_written=written,
        manifest_path=manifest_path,
        har_path=har_path,
        matched=matched,
        skipped=skipped,
    )


def ensure_playwright_project(output_dir: Path, staging_base_url: str) -> None:
    """Write minimal Playwright project files if missing."""
    package_json = output_dir / "package.json"
    if not package_json.exists():
        package_json.write_text(
            json.dumps(
                {
                    "name": "generated-e2e-tests",
                    "private": True,
                    "scripts": {
                        "test": "playwright test",
                        "record-fixtures": "playwright test support/record-flow.spec.ts --grep @recorder",
                    },
                    "devDependencies": {"@playwright/test": "^1.49.0"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    config_ts = output_dir / "playwright.config.ts"
    if not config_ts.exists():
        config_ts.write_text(
            f"""\
import {{ defineConfig }} from '@playwright/test';

export default defineConfig({{
  testDir: '.',
  timeout: 120_000,
  use: {{
    baseURL: process.env.STAGING_BASE_URL ?? '{staging_base_url}',
    trace: 'on-first-retry',
  }},
}});
""",
            encoding="utf-8",
        )
