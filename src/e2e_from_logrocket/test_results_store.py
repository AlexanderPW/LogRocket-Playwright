from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dashboard_data import output_dir


def _db_path() -> Path:
    path = output_dir() / ".replaywright" / "test-runs.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_runs (
                id TEXT PRIMARY KEY,
                flow_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                headed INTEGER NOT NULL DEFAULT 0,
                slow_mo INTEGER NOT NULL DEFAULT 0,
                retries INTEGER NOT NULL DEFAULT 0,
                base_url TEXT NOT NULL DEFAULT '',
                api_mode TEXT NOT NULL DEFAULT '',
                spec_name TEXT NOT NULL DEFAULT '',
                exit_code INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                flaky INTEGER NOT NULL DEFAULT 0,
                skipped INTEGER NOT NULL DEFAULT 0,
                error_summary TEXT,
                logs TEXT NOT NULL DEFAULT '',
                report_json TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_runs_flow ON test_runs(flow_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_runs_started ON test_runs(started_at DESC)"
        )


@dataclass
class TestRunRecord:
    id: str
    flow_name: str
    status: str
    started_at: str
    finished_at: str
    duration_ms: int
    headed: bool
    slow_mo: int
    retries: int
    base_url: str
    api_mode: str
    spec_name: str
    exit_code: int
    passed: int
    failed: int
    flaky: int
    skipped: int
    error_summary: str | None
    logs: str
    report: dict[str, Any] | None

    def to_dict(self, *, include_report: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "flow_name": self.flow_name,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "headed": self.headed,
            "slow_mo": self.slow_mo,
            "retries": self.retries,
            "base_url": self.base_url,
            "api_mode": self.api_mode,
            "spec_name": self.spec_name,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "failed": self.failed,
            "flaky": self.flaky,
            "skipped": self.skipped,
            "error_summary": self.error_summary,
            "logs": self.logs,
        }
        if include_report:
            data["report"] = self.report
        return data


def _row_to_record(row: sqlite3.Row, *, include_report: bool) -> TestRunRecord:
    report_raw = row["report_json"]
    report = json.loads(report_raw) if include_report and report_raw else None
    return TestRunRecord(
        id=row["id"],
        flow_name=row["flow_name"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        duration_ms=row["duration_ms"],
        headed=bool(row["headed"]),
        slow_mo=row["slow_mo"],
        retries=row["retries"],
        base_url=row["base_url"],
        api_mode=row["api_mode"],
        spec_name=row["spec_name"],
        exit_code=row["exit_code"],
        passed=row["passed"],
        failed=row["failed"],
        flaky=row["flaky"],
        skipped=row["skipped"],
        error_summary=row["error_summary"],
        logs=row["logs"],
        report=report,
    )


def save_test_run(payload: dict[str, Any]) -> TestRunRecord:
    init_db()
    run_id = payload.get("id") or uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    started_at = payload.get("started_at") or now
    finished_at = payload.get("finished_at") or now
    report = payload.get("report")
    report_json = json.dumps(report) if report is not None else None

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO test_runs (
                id, flow_name, status, started_at, finished_at, duration_ms,
                headed, slow_mo, retries, base_url, api_mode, spec_name,
                exit_code, passed, failed, flaky, skipped,
                error_summary, logs, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                payload["flow_name"],
                payload["status"],
                started_at,
                finished_at,
                int(payload.get("duration_ms") or 0),
                int(bool(payload.get("headed"))),
                int(payload.get("slow_mo") or 0),
                int(payload.get("retries") or 0),
                payload.get("base_url") or "",
                payload.get("api_mode") or "",
                payload.get("spec") or payload.get("spec_name") or "",
                int(payload.get("exit_code") or 0),
                int(payload.get("passed") or 0),
                int(payload.get("failed") or 0),
                int(payload.get("flaky") or 0),
                int(payload.get("skipped") or 0),
                payload.get("error_summary"),
                payload.get("logs") or "",
                report_json,
            ),
        )

    record = get_test_run(run_id, include_report=True)
    assert record is not None
    return record


def list_test_runs(
    *,
    flow_name: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[TestRunRecord]:
    init_db()
    clauses: list[str] = []
    params: list[Any] = []

    if flow_name:
        clauses.append("flow_name = ?")
        params.append(flow_name)
    if status:
        clauses.append("status = ?")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 200)))

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM test_runs
            {where}
            ORDER BY started_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [_row_to_record(row, include_report=False) for row in rows]


def get_test_run(run_id: str, *, include_report: bool = False) -> TestRunRecord | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM test_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_record(row, include_report=include_report)


def test_run_stats() -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'flaky' THEN 1 ELSE 0 END) AS flaky,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped
            FROM test_runs
            """
        ).fetchone()
        recent_failed = conn.execute(
            """
            SELECT id, flow_name, status, started_at, error_summary
            FROM test_runs
            WHERE status IN ('failed', 'flaky')
            ORDER BY started_at DESC
            LIMIT 5
            """
        ).fetchall()

    total = int(totals["total"] or 0)
    passed = int(totals["passed"] or 0)
    return {
        "total": total,
        "passed": passed,
        "failed": int(totals["failed"] or 0),
        "flaky": int(totals["flaky"] or 0),
        "skipped": int(totals["skipped"] or 0),
        "pass_rate": round((passed / total) * 100, 1) if total else None,
        "recent_failures": [
            {
                "id": row["id"],
                "flow_name": row["flow_name"],
                "status": row["status"],
                "started_at": row["started_at"],
                "error_summary": row["error_summary"],
            }
            for row in recent_failed
        ],
    }
