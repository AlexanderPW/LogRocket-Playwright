from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    logrocket_api_key: str
    logrocket_org_id: str
    logrocket_project_id: str
    ollama_base_url: str
    ollama_model: str
    e2e_output_dir: str
    pii_sanitize: bool
    faker_seed: int
    source_env: str

    @property
    def logrocket_mcp_url(self) -> str:
        base = (
            f"https://mcp.logrocket.com/mcp/"
            f"{self.logrocket_org_id}/{self.logrocket_project_id}"
        )
        # sessions toolset: find_sessions + watch_sessions
        return f"{base}?toolsets=sessions"


@dataclass(frozen=True)
class RecordSettings:
    e2e_output_dir: str
    faker_seed: int
    staging_base_url: str
    playwright_browser: str = "chromium"


def load_settings() -> Settings:
    missing = [
        name
        for name, value in {
            "LOGROCKET_API_KEY": os.getenv("LOGROCKET_API_KEY"),
            "LOGROCKET_ORG_ID": os.getenv("LOGROCKET_ORG_ID"),
            "LOGROCKET_PROJECT_ID": os.getenv("LOGROCKET_PROJECT_ID"),
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required env vars: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in values."
        )

    return Settings(
        logrocket_api_key=os.environ["LOGROCKET_API_KEY"],
        logrocket_org_id=os.environ["LOGROCKET_ORG_ID"],
        logrocket_project_id=os.environ["LOGROCKET_PROJECT_ID"],
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3-coder:30b"),
        e2e_output_dir=os.getenv("E2E_OUTPUT_DIR", "./generated-tests"),
        pii_sanitize=os.getenv("PII_SANITIZE", "true").lower() in {"1", "true", "yes"},
        faker_seed=int(os.getenv("FAKER_SEED", "42")),
        source_env=os.getenv("SOURCE_ENV", "production"),
    )


def load_record_settings() -> RecordSettings:
    staging = os.getenv("STAGING_BASE_URL", "").strip()
    if not staging:
        raise RuntimeError(
            "Missing STAGING_BASE_URL. Set it in .env (e.g. https://staging.example.com)."
        )

    return RecordSettings(
        e2e_output_dir=os.getenv("E2E_OUTPUT_DIR", "./generated-tests"),
        faker_seed=int(os.getenv("FAKER_SEED", "42")),
        staging_base_url=staging.rstrip("/"),
        playwright_browser=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
    )
