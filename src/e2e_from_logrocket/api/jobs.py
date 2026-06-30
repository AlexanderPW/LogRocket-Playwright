from __future__ import annotations

import asyncio
import io
import traceback
import uuid
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock, Thread
from typing import Any

from ..config import load_record_settings, load_settings
from ..pipeline import generate_e2e_from_query
from ..record_fixtures import record_fixtures_from_har
from ..flow_index import index_flow_from_disk
from ..test_results_store import save_test_run
from ..test_runner import run_playwright_flow


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    type: str
    status: JobStatus = JobStatus.PENDING
    logs: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(self, job_type: str, meta: dict[str, Any] | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], type=job_type, meta=meta or {})
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _append_log(self, job: Job, text: str) -> None:
        with self._lock:
            job.logs += text

    def _set_status(self, job: Job, status: JobStatus) -> None:
        with self._lock:
            job.status = status

    def _finish(self, job: Job, *, result: dict | None = None, error: str | None = None) -> None:
        with self._lock:
            job.result = result
            job.error = error
            job.status = JobStatus.COMPLETE if error is None else JobStatus.FAILED

    def start_generate(
        self,
        query: str,
        session_ids: list[str] | None = None,
        recording_ids: list[str] | None = None,
    ) -> Job:
        job = self.create("generate", {"query": query})

        def runner() -> None:
            self._set_status(job, JobStatus.RUNNING)
            buffer = io.StringIO()

            def run() -> dict[str, Any]:
                settings = load_settings()
                generated, flow, written = asyncio.run(
                    generate_e2e_from_query(
                        settings,
                        query,
                        session_ids=session_ids,
                        recording_ids=recording_ids,
                    )
                )
                return {
                    "flow_name": flow.name,
                    "rationale": generated.rationale,
                    "files": [str(p) for p in written],
                    "filename": generated.filename,
                }

            try:
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    result = run()
                self._append_log(job, buffer.getvalue())
                index_flow_from_disk(result["flow_name"])
                self._finish(job, result=result)
            except Exception as exc:
                self._append_log(job, buffer.getvalue() + "\n" + traceback.format_exc())
                self._finish(job, error=str(exc))

        Thread(target=runner, daemon=True).start()
        return job

    def start_record(self, flow_name: str, har_path: str | None = None) -> Job:
        job = self.create("record", {"flow_name": flow_name})

        def runner() -> None:
            self._set_status(job, JobStatus.RUNNING)
            buffer = io.StringIO()

            def run() -> dict[str, Any]:
                from pathlib import Path

                settings = load_record_settings()
                result = record_fixtures_from_har(
                    settings,
                    flow_name,
                    har_path=Path(har_path) if har_path else None,
                )
                return {
                    "flow_name": result.flow_name,
                    "matched": result.matched,
                    "skipped": result.skipped,
                    "har_path": str(result.har_path) if result.har_path else None,
                    "manifest_path": str(result.manifest_path),
                    "fixtures_written": [str(p) for p in result.fixtures_written],
                }

            try:
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    result = run()
                self._append_log(job, buffer.getvalue())
                index_flow_from_disk(result["flow_name"])
                self._finish(job, result=result)
            except Exception as exc:
                self._append_log(job, buffer.getvalue() + "\n" + traceback.format_exc())
                self._finish(job, error=str(exc))

        Thread(target=runner, daemon=True).start()
        return job

    def start_play(
        self,
        flow_name: str,
        *,
        headed: bool = True,
        slow_mo: int = 1500,
    ) -> Job:
        job = self.create("play", {"flow_name": flow_name, "headed": headed, "slow_mo": slow_mo})

        def runner() -> None:
            self._set_status(job, JobStatus.RUNNING)
            buffer = io.StringIO()

            try:
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    result = run_playwright_flow(
                        flow_name,
                        headed=headed,
                        slow_mo=slow_mo,
                    )
                self._append_log(job, buffer.getvalue() + str(result.get("logs", "")))
                if not result.get("passed"):
                    self._finish(
                        job,
                        result=result,
                        error=f"Playwright test failed (exit {result.get('exit_code')})",
                    )
                else:
                    self._finish(job, result=result)
            except Exception as exc:
                self._append_log(job, buffer.getvalue() + "\n" + traceback.format_exc())
                self._finish(job, error=str(exc))

        Thread(target=runner, daemon=True).start()
        return job

    def start_test(
        self,
        flow_name: str,
        *,
        headed: bool = False,
        slow_mo: int = 0,
        retries: int = 1,
    ) -> Job:
        job = self.create(
            "test",
            {
                "flow_name": flow_name,
                "headed": headed,
                "slow_mo": slow_mo,
                "retries": retries,
            },
        )

        def runner() -> None:
            self._set_status(job, JobStatus.RUNNING)
            buffer = io.StringIO()

            try:
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    result = run_playwright_flow(
                        flow_name,
                        headed=headed,
                        slow_mo=slow_mo,
                        retries=retries,
                        capture_json=True,
                    )
                record = save_test_run(
                    {
                        **result,
                        "passed": result.get("passed_count", 0),
                        "failed": result.get("failed_count", 0),
                        "flaky": result.get("flaky_count", 0),
                        "skipped": result.get("skipped_count", 0),
                    }
                )
                payload = record.to_dict(include_report=False)
                payload["run_id"] = record.id
                self._append_log(job, buffer.getvalue() + str(result.get("logs", "")))
                if result.get("status") == "failed":
                    self._finish(
                        job,
                        result=payload,
                        error=result.get("error_summary")
                        or f"Test failed (exit {result.get('exit_code')})",
                    )
                else:
                    self._finish(job, result=payload)
            except Exception as exc:
                self._append_log(job, buffer.getvalue() + "\n" + traceback.format_exc())
                self._finish(job, error=str(exc))

        Thread(target=runner, daemon=True).start()
        return job


job_manager = JobManager()
