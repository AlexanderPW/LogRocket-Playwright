"""Local web dashboard for e2e-from-logrocket."""

from __future__ import annotations

import asyncio
import io
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import streamlit as st

from .config import load_record_settings, load_settings
from .dashboard_data import (
    env_statuses,
    list_flows,
    output_dir,
    read_flow_file,
    read_spec_for_flow,
    read_support_file,
)
from .pipeline import generate_e2e_from_query
from .record_fixtures import record_fixtures_from_har

st.set_page_config(
    page_title="Replaywright",
    page_icon="🧪",
    layout="wide",
)

PIPELINE = """
```
Your query
    ↓
Session Researcher  ←→  LogRocket MCP (find/watch sessions)
    ↓
Faker PII sanitizer
    ↓
Flow Normalizer     →  flow.json
    ↓
Test Writer         →  Playwright .spec.ts
    ↓
Test Reviewer
    ↓
record-fixtures     →  HAR → sanitized API fixtures (staging, optional)
    ↓
CI / npx playwright test
```
"""


def _capture_run(func, *args, **kwargs):
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer), redirect_stderr(buffer):
            result = func(*args, **kwargs)
        return True, buffer.getvalue(), result
    except Exception:
        return False, buffer.getvalue() + "\n" + traceback.format_exc(), None


def _sidebar() -> str:
    st.sidebar.title("Replaywright")
    st.sidebar.caption("Local dashboard")
    st.sidebar.markdown(f"**Output dir:** `{output_dir()}`")
    st.sidebar.markdown(f"**Model:** `{st.session_state.get('ollama_model', '—')}`")

    page = st.sidebar.radio(
        "Navigate",
        ["Overview", "Flows", "Generate", "Record fixtures", "Flow detail"],
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Environment")
    for item in env_statuses():
        icon = "✅" if item.set else "⚠️"
        st.sidebar.markdown(f"{icon} `{item.name}` ({item.required_for})")

    return page


def _page_overview() -> None:
    st.title("What this tool does")
    st.markdown(
        """
This is a **CLI pipeline with a local dashboard** — not a hosted SaaS.

It turns **LogRocket session replays** into **Playwright regression tests** using:
- **LogRocket MCP** to watch real user sessions
- **Local Qwen** (`qwen3-coder:30b` via Ollama) for multi-agent codegen
- **Faker** to strip PII from production data
- **Playwright `page.route()`** to mock/sanitize API responses in tests
"""
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Agent pipeline")
        st.code(
            PIPELINE.strip().removeprefix("```").removesuffix("```").strip(),
            language="text",
        )
    with col2:
        st.subheader("Agents")
        st.markdown(
            """
| Agent | Job |
|-------|-----|
| **Session Researcher** | LogRocket MCP — find & watch sessions |
| **Flow Normalizer** | Session narrative → `flow.json` |
| **Test Writer** | Emits Playwright TypeScript |
| **Test Reviewer** | Catches brittle selectors & PII leaks |
"""
        )

    flows = list_flows()
    st.subheader("Quick stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Flows", len(flows))
    c2.metric("With specs", sum(1 for f in flows if f.has_spec))
    c3.metric("With HAR", sum(1 for f in flows if f.has_har))
    c4.metric("Offline mocks", sum(f.fulfill_count for f in flows))


def _page_flows() -> None:
    st.title("Flows")
    flows = list_flows()
    if not flows:
        st.info("No flows yet. Use **Generate** to create one from LogRocket.")
        return

    for flow in flows:
        with st.expander(f"**{flow.name}**", expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Steps:** {flow.step_count}")
            c1.markdown(f"**Start URL:** `{flow.start_url or '—'}`")
            c2.markdown(f"**Sessions:** {', '.join(flow.session_ids) or '—'}")
            c2.markdown(f"**Mocks:** {flow.fulfill_count} fulfill / {flow.transform_count} transform")
            c3.markdown(f"**Files:** spec={'✅' if flow.has_spec else '❌'} har={'✅' if flow.has_har else '❌'} fixtures={flow.fixture_count}")


def _page_generate() -> None:
    st.title("Generate from LogRocket")
    st.caption("Runs the 4-agent pipeline against your local Qwen model + LogRocket MCP.")

    query = st.text_area(
        "LogRocket query",
        value=st.session_state.get(
            "last_query",
            "Build a regression test from the watched session(s).",
        ),
        height=80,
    )
    session_ids_raw = st.text_input(
        "Session ID(s)",
        placeholder="abc123def456 or comma-separated IDs from LogRocket URL …/s/SESSION_ID",
        help="Optional. Paste the ID from a LogRocket session URL to target that exact replay.",
    )
    session_ids = [s.strip() for s in session_ids_raw.replace(",", " ").split() if s.strip()]

    if st.button("Run generate", type="primary"):
        st.session_state["last_query"] = query
        with st.status("Running agent pipeline…", expanded=True) as status:
            try:
                settings = load_settings()
                st.session_state["ollama_model"] = settings.ollama_model
            except RuntimeError as exc:
                st.error(str(exc))
                return

            ok, logs, result = _capture_run(
                lambda: asyncio.run(
                    generate_e2e_from_query(
                        settings,
                        query,
                        session_ids=session_ids or None,
                    )
                )
            )
            st.code(logs or "(no log output)")
            if not ok or result is None:
                status.update(label="Generate failed", state="error")
                return

            generated, flow, written = result
            status.update(label=f"Done — flow `{flow.name}`", state="complete")
            st.success(f"Wrote {len(written)} files ({generated.rationale})")
            for path in written:
                st.markdown(f"- `{path}`")


def _page_record() -> None:
    st.title("Record staging fixtures")
    st.caption("Replays a flow on staging, captures HAR, writes sanitized API fixtures.")

    flows = list_flows()
    if not flows:
        st.warning("Generate a flow first.")
        return

    flow_name = st.selectbox("Flow", [f.name for f in flows])
    har_upload = st.file_uploader("Or upload existing HAR (optional)", type=["har", "json"])

    if st.button("Record fixtures", type="primary"):
        with st.status("Recording…", expanded=True) as status:
            try:
                settings = load_record_settings()
            except RuntimeError as exc:
                st.error(str(exc))
                return

            har_path = None
            if har_upload is not None:
                har_path = output_dir() / "fixtures" / flow_name / "uploaded-capture.har"
                har_path.write_bytes(har_upload.getvalue())

            ok, logs, result = _capture_run(
                record_fixtures_from_har, settings, flow_name, har_path=har_path
            )
            st.code(logs or "(no log output)")
            if not ok or result is None:
                status.update(label="Recording failed", state="error")
                return

            status.update(label="Fixtures recorded", state="complete")
            st.success(
                f"Matched {result.matched} mocks, skipped {result.skipped}. "
                f"Manifest: `{result.manifest_path}`"
            )
            for path in result.fixtures_written:
                st.markdown(f"- `{path}`")


def _page_detail() -> None:
    st.title("Flow detail")
    flows = list_flows()
    if not flows:
        st.info("No flows to inspect.")
        return

    flow_name = st.selectbox("Select flow", [f.name for f in flows], key="detail_flow")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["flow.json", "api-mocks.json", "Playwright spec", "test-data.ts", "Fixtures"]
    )

    with tab1:
        text = read_flow_file(flow_name, "flow.json")
        st.code(text or "Not found", language="json")

    with tab2:
        text = read_flow_file(flow_name, "api-mocks.json")
        st.code(text or "Not found", language="json")

    with tab3:
        spec_name, spec_text = read_spec_for_flow(flow_name)
        if spec_text:
            st.caption(spec_name)
            st.code(spec_text, language="typescript")
        else:
            st.info("No spec found for this flow.")

    with tab4:
        text = read_support_file(flow_name)
        st.code(text or "Not found", language="typescript")

    with tab5:
        fixture_dir = output_dir() / "fixtures" / flow_name
        files = sorted(p.name for p in fixture_dir.glob("*.json") if p.name not in {"api-mocks.json", "flow.json"})
        if not files:
            st.info("No fixture JSON files yet.")
        for name in files:
            st.markdown(f"**{name}**")
            st.code(read_flow_file(flow_name, name), language="json")


def main() -> None:
    page = _sidebar()
    if page == "Overview":
        _page_overview()
    elif page == "Flows":
        _page_flows()
    elif page == "Generate":
        _page_generate()
    elif page == "Record fixtures":
        _page_record()
    elif page == "Flow detail":
        _page_detail()


if __name__ == "__main__":
    main()
