from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..dashboard_data import (
    list_flows,
    output_dir,
    read_flow_file,
    read_spec_for_flow,
    read_support_file,
)
from ..flow_runtime import (
    FlowRuntimeSettings,
    load_runtime_settings,
    runtime_status,
    save_runtime_settings,
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


@app.on_event("startup")
def on_startup() -> None:
    reload_env()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    flows = list_flows()
    settings = get_settings()
    return {
        "output_dir": str(output_dir()),
        "flow_count": len(flows),
        "with_specs": sum(1 for f in flows if f.has_spec),
        "with_har": sum(1 for f in flows if f.has_har),
        "offline_mocks": sum(f.fulfill_count for f in flows),
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
def flows() -> list[dict[str, Any]]:
    result = []
    for f in list_flows():
        runtime = load_runtime_settings(f.name)
        result.append(
            {
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
                "base_url": runtime.base_url,
                "api_mode": runtime.api_mode,
            }
        )
    return result


@app.get("/api/flows/{flow_name}")
def flow_detail(flow_name: str) -> dict[str, Any]:
    flows = {f.name: f for f in list_flows()}
    if flow_name not in flows:
        raise HTTPException(status_code=404, detail="Flow not found")
    f = flows[flow_name]
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
    if flow_name not in {f.name for f in list_flows()}:
        raise HTTPException(status_code=404, detail="Flow not found")
    return runtime_status(flow_name)


@app.put("/api/flows/{flow_name}/runtime")
def put_flow_runtime(flow_name: str, body: FlowRuntimeSettings) -> dict[str, object]:
    if flow_name not in {f.name for f in list_flows()}:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        save_runtime_settings(flow_name, body)
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
    flows = {f.name for f in list_flows()}
    if flow_name not in flows:
        raise HTTPException(status_code=404, detail="Flow not found")

    summary = next(f for f in list_flows() if f.name == flow_name)
    if not summary.has_spec:
        raise HTTPException(status_code=400, detail="Flow has no Playwright spec yet")

    opts = body or PlayRequest()
    job = job_manager.start_play(
        flow_name,
        headed=opts.headed,
        slow_mo=opts.slow_mo,
    )
    return {"job_id": job.id}


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
