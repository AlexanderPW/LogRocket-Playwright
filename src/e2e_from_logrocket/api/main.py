from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..dashboard_data import (
    output_dir,
    read_flow_file,
    read_spec_for_flow,
    read_support_file,
)
from ..flow_index import (
    flow_exists_in_index,
    flow_index_stats,
    flow_summary_to_api,
    get_flow_from_index,
    index_flow_from_disk,
    init_flow_index,
    list_flows_paginated,
    lookup_flows,
    sync_flow_index,
    update_flow_runtime_index,
)
from ..flow_runtime import (
    FlowRuntimeSettings,
    load_runtime_settings,
    runtime_status,
    save_runtime_settings,
)
from ..test_results_store import (
    get_test_run,
    init_db,
    list_test_runs,
    test_run_stats,
)
from .jobs import JobStatus, job_manager
from .settings_service import SettingsUpdate, get_settings, reload_env, update_settings

app = FastAPI(title="Replaywright API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    query: str
    session_ids: list[str] = Field(default_factory=list)
    recording_ids: list[str] = Field(default_factory=list)


class RecordRequest(BaseModel):
    flow_name: str
    har_base64: str | None = None
    har_filename: str | None = None


class PlayRequest(BaseModel):
    headed: bool = True
    slow_mo: int = 1500


class TestRequest(BaseModel):
    headed: bool = False
    slow_mo: int = 0
    retries: int = 1


@app.on_event("startup")
def on_startup() -> None:
    reload_env()
    init_db()
    init_flow_index()
    sync_flow_index()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    stats = flow_index_stats()
    settings = get_settings()
    return {
        "output_dir": str(output_dir()),
        **stats,
        "settings_ok": {
            "generate": all(s.is_set for s in settings if s.required_for == "generate" and s.key != "STAGING_BASE_URL"),
            "record": all(s.is_set for s in settings if s.required_for == "record-fixtures"),
        },
    }


@app.get("/api/settings")
def read_settings() -> list[dict[str, Any]]:
    return [s.model_dump() for s in get_settings()]


@app.put("/api/settings")
def write_settings(payload: SettingsUpdate) -> list[dict[str, Any]]:
    return [s.model_dump() for s in update_settings(payload)]


@app.get("/api/flows")
def flows(
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    has_spec: bool | None = None,
    sort: str = "name",
) -> dict[str, Any]:
    result = list_flows_paginated(
        q=q,
        page=page,
        page_size=page_size,
        has_spec=has_spec,
        sort=sort,
    )
    items = [
        flow_summary_to_api(
            summary,
            base_url=result.base_url_by_name.get(summary.name),
            api_mode=result.api_mode_by_name.get(summary.name),
        )
        for summary in result.items
    ]
    return {
        "items": items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "pages": result.pages,
    }


@app.get("/api/flows/lookup")
def flows_lookup(
    q: str | None = None,
    limit: int = 30,
    has_spec: bool | None = None,
) -> list[dict[str, Any]]:
    return lookup_flows(q=q, limit=limit, has_spec=has_spec)


@app.post("/api/flows/reindex")
def flows_reindex() -> dict[str, Any]:
    return sync_flow_index(force=True)


@app.get("/api/flows/{flow_name}")
def flow_detail(flow_name: str) -> dict[str, Any]:
    f = get_flow_from_index(flow_name)
    if not f:
        raise HTTPException(status_code=404, detail="Flow not found")
    spec_name, spec_text = read_spec_for_flow(flow_name)
    fixture_dir = output_dir() / "fixtures" / flow_name
    fixture_files = sorted(
        p.name
        for p in fixture_dir.glob("*.json")
        if p.name not in {"api-mocks.json", "flow.json"}
    )
    return {
        "summary": {
            "name": f.name,
            "has_flow_json": f.has_flow_json,
            "has_api_mocks": f.has_api_mocks,
            "has_spec": f.has_spec,
            "has_har": f.has_har,
            "fixture_count": f.fixture_count,
            "mock_count": f.mock_count,
            "fulfill_count": f.fulfill_count,
            "transform_count": f.transform_count,
            "start_url": f.start_url,
            "step_count": f.step_count,
            "session_ids": f.session_ids,
        },
        "flow_json": read_flow_file(flow_name, "flow.json"),
        "api_mocks_json": read_flow_file(flow_name, "api-mocks.json"),
        "spec_name": spec_name,
        "spec_text": spec_text,
        "test_data_ts": read_support_file(flow_name),
        "fixture_files": fixture_files,
        "fixtures": {
            name: read_flow_file(flow_name, name) for name in fixture_files
        },
        "runtime": runtime_status(flow_name),
    }


@app.get("/api/flows/{flow_name}/runtime")
def get_flow_runtime(flow_name: str) -> dict[str, object]:
    if not flow_exists_in_index(flow_name):
        raise HTTPException(status_code=404, detail="Flow not found")
    return runtime_status(flow_name)


@app.put("/api/flows/{flow_name}/runtime")
def put_flow_runtime(flow_name: str, body: FlowRuntimeSettings) -> dict[str, object]:
    if not flow_exists_in_index(flow_name):
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        save_runtime_settings(flow_name, body)
        update_flow_runtime_index(
            flow_name,
            base_url=body.base_url,
            api_mode=body.api_mode,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return runtime_status(flow_name)


@app.post("/api/generate")
def start_generate(body: GenerateRequest) -> dict[str, str]:
    job = job_manager.start_generate(
        body.query,
        session_ids=body.session_ids or None,
        recording_ids=body.recording_ids or None,
    )
    return {"job_id": job.id}


@app.post("/api/flows/{flow_name}/play")
def start_play(flow_name: str, body: PlayRequest | None = None) -> dict[str, str]:
    summary = get_flow_from_index(flow_name)
    if not summary:
        raise HTTPException(status_code=404, detail="Flow not found")
    if not summary.has_spec:
        raise HTTPException(status_code=400, detail="Flow has no Playwright spec yet")

    opts = body or PlayRequest()
    job = job_manager.start_play(
        flow_name,
        headed=opts.headed,
        slow_mo=opts.slow_mo,
    )
    return {"job_id": job.id}


@app.post("/api/flows/{flow_name}/test")
def start_test(flow_name: str, body: TestRequest | None = None) -> dict[str, str]:
    summary = get_flow_from_index(flow_name)
    if not summary:
        raise HTTPException(status_code=404, detail="Flow not found")
    if not summary.has_spec:
        raise HTTPException(status_code=400, detail="Flow has no Playwright spec yet")

    opts = body or TestRequest()
    job = job_manager.start_test(
        flow_name,
        headed=opts.headed,
        slow_mo=opts.slow_mo,
        retries=opts.retries,
    )
    return {"job_id": job.id}


@app.get("/api/test-runs")
def test_runs(
    flow_name: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    runs = list_test_runs(flow_name=flow_name, status=status, limit=limit)
    return [run.to_dict() for run in runs]


@app.get("/api/test-runs/stats")
def test_stats() -> dict[str, Any]:
    return test_run_stats()


@app.get("/api/test-runs/{run_id}")
def test_run_detail(run_id: str) -> dict[str, Any]:
    run = get_test_run(run_id, include_report=True)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run.to_dict(include_report=True)


@app.post("/api/record")
def start_record(body: RecordRequest) -> dict[str, str]:
    har_path: str | None = None
    if body.har_base64:
        data = base64.b64decode(body.har_base64)
        suffix = Path(body.har_filename or "capture.har").suffix or ".har"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(data)
        tmp.close()
        har_path = tmp.name

    job = job_manager.start_record(body.flow_name, har_path=har_path)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status.value,
        "logs": job.logs,
        "result": job.result,
        "error": job.error,
        "meta": job.meta,
        "done": job.status in {JobStatus.COMPLETE, JobStatus.FAILED},
    }
