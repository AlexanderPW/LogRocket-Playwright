from __future__ import annotations


def build_research_prompt(
    query: str,
    *,
    source_env: str,
    session_ids: list[str] | None = None,
) -> str:
    """Build the Session Researcher prompt from a query and optional session IDs."""
    lines = [
        "Investigate LogRocket sessions for this regression target:",
        query.strip(),
        "",
        f"Source environment: {source_env}",
    ]

    if session_ids:
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
        lines.append("Watch 1-3 representative sessions. Focus on reproducible UI steps and API calls.")

    return "\n".join(lines)
