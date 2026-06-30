from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

SECRET_KEYS = {"LOGROCKET_API_KEY"}


class SettingField(BaseModel):
    key: str
    label: str
    description: str
    group: str
    required_for: str
    secret: bool = False
    value: str = ""
    masked_value: str = ""
    is_set: bool = False


SETTING_DEFINITIONS: list[dict[str, str | bool]] = [
    {
        "key": "LOGROCKET_API_KEY",
        "label": "LogRocket API Key",
        "description": "Project-scoped API key from LogRocket Settings → API Keys",
        "group": "LogRocket",
        "required_for": "generate",
        "secret": True,
    },
    {
        "key": "LOGROCKET_ORG_ID",
        "label": "Organization ID",
        "description": "From your LogRocket dashboard URL or project settings",
        "group": "LogRocket",
        "required_for": "generate",
    },
    {
        "key": "LOGROCKET_PROJECT_ID",
        "label": "Project ID",
        "description": "LogRocket project / app identifier",
        "group": "LogRocket",
        "required_for": "generate",
    },
    {
        "key": "OLLAMA_BASE_URL",
        "label": "Ollama base URL",
        "description": "OpenAI-compatible endpoint for local LLM",
        "group": "Local LLM",
        "required_for": "generate",
    },
    {
        "key": "OLLAMA_MODEL",
        "label": "Ollama model",
        "description": "Model name (e.g. qwen3-coder:30b)",
        "group": "Local LLM",
        "required_for": "generate",
    },
    {
        "key": "E2E_OUTPUT_DIR",
        "label": "Output directory",
        "description": "Where generated tests and fixtures are written",
        "group": "Output",
        "required_for": "all",
    },
    {
        "key": "PII_SANITIZE",
        "label": "PII sanitize",
        "description": "Enable Faker redaction at generation time",
        "group": "PII safety",
        "required_for": "generate",
    },
    {
        "key": "FAKER_SEED",
        "label": "Faker seed",
        "description": "Deterministic synthetic data across runs",
        "group": "PII safety",
        "required_for": "generate",
    },
    {
        "key": "SOURCE_ENV",
        "label": "Source environment",
        "description": "Hint to agents about session origin (production/staging)",
        "group": "PII safety",
        "required_for": "generate",
    },
    {
        "key": "STAGING_BASE_URL",
        "label": "Staging base URL",
        "description": "Target for fixture recording (e.g. https://staging.example.com)",
        "group": "Fixture recording",
        "required_for": "record-fixtures",
    },
    {
        "key": "PLAYWRIGHT_BROWSER",
        "label": "Playwright browser",
        "description": "Browser for HAR capture",
        "group": "Fixture recording",
        "required_for": "record-fixtures",
    },
]

DEFAULTS: dict[str, str] = {
    "OLLAMA_BASE_URL": "http://localhost:11434/v1",
    "OLLAMA_MODEL": "qwen3-coder:30b",
    "E2E_OUTPUT_DIR": "./generated-tests",
    "PII_SANITIZE": "true",
    "FAKER_SEED": "42",
    "SOURCE_ENV": "production",
    "PLAYWRIGHT_BROWSER": "chromium",
}


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:4]}…{value[-4:]}"


def _env_file_values() -> dict[str, str]:
    if ENV_PATH.exists():
        return {k: v for k, v in dotenv_values(ENV_PATH).items() if v is not None}
    return {}


def reload_env() -> None:
    load_dotenv(ENV_PATH, override=True)


def get_settings() -> list[SettingField]:
    file_values = _env_file_values()
    fields: list[SettingField] = []
    for spec in SETTING_DEFINITIONS:
        key = str(spec["key"])
        value = file_values.get(key) or os.getenv(key) or DEFAULTS.get(key, "")
        fields.append(
            SettingField(
                key=key,
                label=str(spec["label"]),
                description=str(spec["description"]),
                group=str(spec["group"]),
                required_for=str(spec["required_for"]),
                secret=bool(spec.get("secret", False)),
                value=value if key not in SECRET_KEYS else "",
                masked_value=_mask_secret(value) if key in SECRET_KEYS else value,
                is_set=bool(value.strip()),
            )
        )
    return fields


class SettingsUpdate(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


def update_settings(payload: SettingsUpdate) -> list[SettingField]:
    current = _env_file_values()
    for key, value in payload.values.items():
        if key not in {str(s["key"]) for s in SETTING_DEFINITIONS}:
            continue
        stripped = value.strip()
        if key in SECRET_KEYS and (not stripped or "…" in stripped):
            continue
        if stripped:
            current[key] = stripped
        elif key in current:
            del current[key]

    # Preserve order from example + known keys
    lines: list[str] = []
    written: set[str] = set()
    if ENV_EXAMPLE_PATH.exists():
        for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^([A-Z_][A-Z0-9_]*)=", line)
            if match:
                key = match.group(1)
                if key in current:
                    lines.append(f"{key}={current[key]}")
                    written.add(key)
                elif line.strip() and not line.strip().startswith("#"):
                    continue
                else:
                    lines.append(line)
            else:
                lines.append(line)

    for key, value in current.items():
        if key not in written:
            lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    reload_env()
    return get_settings()
