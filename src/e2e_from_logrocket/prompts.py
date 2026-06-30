from __future__ import annotations


def build_research_prompt(
    query: str,
    *,
    source_env: str,
    session_ids: list[str] | None = None,
    recording_ids: list[str] | None = None,
) -> str:
    """Build the Session Researcher prompt from a query and optional session IDs."""
    lines = [
        "Investigate LogRocket sessions for this regression target:",
        query.strip(),
        "",
        f"Source environment: {source_env}",
        "",
        "POC rules:",
        "- This may be a simple site (portfolio, marketing, docs) — do NOT assume signup, checkout, or onboarding.",
        "- Use find_sessions first unless a recording ID is provided below.",
        "- Prefer the latest session that lasted >= 10 seconds and navigated across multiple pages/links.",
        "- Every URL, link label, and click MUST come from watch_sessions output. Never invent steps or example.com URLs.",
        "- If no matching sessions exist, say so explicitly — do not fabricate a flow.",
    ]

    if recording_ids:
        lines.extend(
            [
                "",
                "IMPORTANT: Watch these exact LogRocket recording ID(s) with sessionID 0:",
                ", ".join(recording_ids),
                "",
                "Call watch_sessions on each. Use recordingID + sessionID 0. Build the flow from those replays only.",
            ]
        )
    elif session_ids:
        ids = ", ".join(session_ids)
        lines.extend(
            [
                "",
                "IMPORTANT: Use these exact LogRocket session ID(s). Do not search for others unless they fail to load:",
                ids,
                "",
                "Call watch_sessions on each ID above and build the flow from those replays only.",
            ]
        )
    else:
        lines.append(
            "Watch 1 representative session (not 3). Focus on reproducible navigation clicks and page URLs."
        )

    return "\n".join(lines)
