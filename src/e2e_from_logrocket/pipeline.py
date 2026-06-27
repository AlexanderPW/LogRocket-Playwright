from __future__ import annotations

import json
import re
from pathlib import Path

from agents import Runner
from agents.mcp import MCPServerStreamableHttp

from .agents import build_agents
from .config import Settings
from .models import configure_local_llm
from .pii import PIISanitizer
from .playwright_emitter import write_playwright_support
from .prompts import build_research_prompt
from .schemas import GeneratedTest, NormalizedFlow


def _extract_filename(code: str, fallback: str) -> tuple[str, str]:
    match = re.search(r"^//\s*file:\s*(\S+)", code, re.MULTILINE)
    if match:
        filename = match.group(1)
        code = re.sub(r"^//\s*file:\s*\S+\s*\n?", "", code, count=1)
        return filename, code.strip()
    return fallback, code.strip()


def _parse_normalized_flow(raw: str) -> NormalizedFlow:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return NormalizedFlow.model_validate(json.loads(text))


def _parse_reviewed_test(raw: str, flow_name: str) -> GeneratedTest:
    approved = raw.strip().startswith("APPROVED")
    body = raw.split("\n", 1)[1] if "\n" in raw else raw
    if body.startswith("NEEDS_REVISION"):
        body = body.split("\n", 1)[1] if "\n" in body else body

    filename, code = _extract_filename(body, f"{flow_name}.spec.ts")
    return GeneratedTest(
        filename=filename,
        code=code,
        flow_name=flow_name,
        rationale="approved" if approved else "revised_after_review",
    )


async def generate_e2e_from_query(
    settings: Settings,
    query: str,
    session_ids: list[str] | None = None,
) -> tuple[GeneratedTest, NormalizedFlow, list[Path]]:
    """
    Multi-agent pipeline:
    1. Session Researcher (+ LogRocket MCP) gathers real flows
    2. PII sanitizer redacts production values (Faker, deterministic)
    3. Flow Normalizer structures steps + API mock hints
    4. Test Writer emits Playwright code with route intercept hooks
    5. Test Reviewer critiques and polishes
    """
    model = configure_local_llm(settings)
    agents = build_agents(model)
    sanitizer = PIISanitizer(seed=settings.faker_seed)

    logrocket_server = MCPServerStreamableHttp(
        name="logrocket",
        params={
            "url": settings.logrocket_mcp_url,
            "headers": {"Authorization": f"Bearer {settings.logrocket_api_key}"},
        },
    )

    async with logrocket_server:
        research = await Runner.run(
            agents["session_researcher"],
            build_research_prompt(
                query,
                source_env=settings.source_env,
                session_ids=session_ids,
            ),
            mcp_servers=[logrocket_server],
        )

        session_text = research.final_output
        if settings.pii_sanitize:
            session_text = sanitizer.sanitize_text(session_text)

        normalized_raw = await Runner.run(
            agents["flow_normalizer"],
            (
                "Normalize this session analysis into JSON.\n"
                "Use synthetic placeholders for any user-entered values.\n\n"
                f"{session_text}"
            ),
        )
        flow = _parse_normalized_flow(normalized_raw.final_output)

        if settings.pii_sanitize:
            flow, _, _ = sanitizer.sanitize_flow_bundle(flow, session_text)

        writer_prompt = (
            "Write a Playwright regression test for this flow JSON.\n"
            "All fill values must come from testData; API traffic is mocked via setupPiiSafeRoutes.\n\n"
            f"FLOW JSON:\n{flow.model_dump_json(indent=2)}\n\n"
            f"SYNTHETIC TEST DATA:\n{flow.test_data.model_dump_json(indent=2) if flow.test_data else '{}'}"
        )
        draft = await Runner.run(agents["test_writer"], writer_prompt)

        reviewed = await Runner.run(
            agents["test_reviewer"],
            (
                "Review this Playwright test against the flow JSON.\n\n"
                f"FLOW JSON:\n{flow.model_dump_json(indent=2)}\n\n"
                f"TEST:\n{draft.final_output}"
            ),
        )

    generated = _parse_reviewed_test(reviewed.final_output, flow.name)
    out_dir = Path(settings.e2e_output_dir)
    written = write_playwright_support(out_dir, flow, generated, sanitizer)
    return generated, flow, written


def write_generated_test(settings: Settings, generated: GeneratedTest) -> Path:
    """Backward-compatible single-file writer (prefer generate_e2e_from_query)."""
    out_dir = Path(settings.e2e_output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / generated.filename
    path.write_text(generated.code + "\n", encoding="utf-8")
    return path
