from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any

from .dashboard_data import FlowSummary, output_dir, scan_flow_dir
from .flow_runtime import load_runtime_settings


def _db_path(base: Path | None = None) -> Path:
    path = (base or output_dir()) / ".replaywright" / "flow-index.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(base: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(base))
    conn.row_factory = sqlite3.Row
    return conn


def init_flow_index(base: Path | None = None) -> None:
    with _connect(base) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flows (
                name TEXT PRIMARY KEY,
                has_flow_json INTEGER NOT NULL DEFAULT 0,
                has_api_mocks INTEGER NOT NULL DEFAULT 0,
                has_spec INTEGER NOT NULL DEFAULT 0,
                has_har INTEGER NOT NULL DEFAULT 0,
                fixture_count INTEGER NOT NULL DEFAULT 0,
                mock_count INTEGER NOT NULL DEFAULT 0,
                fulfill_count INTEGER NOT NULL DEFAULT 0,
                transform_count INTEGER NOT NULL DEFAULT 0,
                start_url TEXT,
                step_count INTEGER NOT NULL DEFAULT 0,
                session_ids TEXT NOT NULL DEFAULT '[]',
                base_url TEXT NOT NULL DEFAULT '',
                api_mode TEXT NOT NULL DEFAULT 'live_obfuscate',
                source_mtime REAL NOT NULL DEFAULT 0,
                indexed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_flows_has_spec ON flows(has_spec)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS index_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )


def _fixtures_root(base: Path | None = None) -> Path:
    return (base or output_dir()) / "fixtures"


def _flow_source_mtime(flow_dir: Path, root: Path) -> float:
    mtimes: list[float] = [flow_dir.stat().st_mtime]
    for name in ("flow.json", "api-mocks.json", "runtime.json", "capture.har"):
        path = flow_dir / name
        if path.exists():
            mtimes.append(path.stat().st_mtime)

    exact_spec = root / f"{flow_dir.name}.spec.ts"
    if exact_spec.exists():
        mtimes.append(exact_spec.stat().st_mtime)
    else:
        for spec in root.glob(f"*{flow_dir.name}*.spec.ts"):
            mtimes.append(spec.stat().st_mtime)

    return max(mtimes)


def _fixtures_signature(base: Path | None = None) -> tuple[int, float]:
    fixtures_root = _fixtures_root(base)
    if not fixtures_root.exists():
        return 0, 0.0

    count = 0
    max_mtime = fixtures_root.stat().st_mtime
    for entry in fixtures_root.iterdir():
        if not entry.is_dir():
            continue
        count += 1
        max_mtime = max(max_mtime, entry.stat().st_mtime)
    return count, max_mtime


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM index_meta WHERE key = ?",
        (key,),
    ).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO index_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _row_to_summary(row: sqlite3.Row) -> FlowSummary:
    session_ids = json.loads(row["session_ids"] or "[]")
    return FlowSummary(
        name=row["name"],
        has_flow_json=bool(row["has_flow_json"]),
        has_api_mocks=bool(row["has_api_mocks"]),
        has_spec=bool(row["has_spec"]),
        has_har=bool(row["has_har"]),
        fixture_count=row["fixture_count"],
        mock_count=row["mock_count"],
        fulfill_count=row["fulfill_count"],
        transform_count=row["transform_count"],
        start_url=row["start_url"],
        step_count=row["step_count"],
        session_ids=session_ids,
    )


def _summary_to_row(
    summary: FlowSummary,
    *,
    base_url: str,
    api_mode: str,
    source_mtime: float,
) -> tuple[Any, ...]:
    now = datetime.now(timezone.utc).isoformat()
    return (
        summary.name,
        int(summary.has_flow_json),
        int(summary.has_api_mocks),
        int(summary.has_spec),
        int(summary.has_har),
        summary.fixture_count,
        summary.mock_count,
        summary.fulfill_count,
        summary.transform_count,
        summary.start_url,
        summary.step_count,
        json.dumps(summary.session_ids),
        base_url,
        api_mode,
        source_mtime,
        now,
    )


def upsert_flow_index(
    summary: FlowSummary,
    *,
    base: Path | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
    source_mtime: float | None = None,
) -> None:
    init_flow_index(base)
    root = base or output_dir()
    flow_dir = _fixtures_root(base) / summary.name
    runtime = load_runtime_settings(summary.name, base=root)
    mtime = source_mtime if source_mtime is not None else _flow_source_mtime(flow_dir, root)

    with _connect(base) as conn:
        conn.execute(
            """
            INSERT INTO flows (
                name, has_flow_json, has_api_mocks, has_spec, has_har,
                fixture_count, mock_count, fulfill_count, transform_count,
                start_url, step_count, session_ids, base_url, api_mode,
                source_mtime, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                has_flow_json = excluded.has_flow_json,
                has_api_mocks = excluded.has_api_mocks,
                has_spec = excluded.has_spec,
                has_har = excluded.has_har,
                fixture_count = excluded.fixture_count,
                mock_count = excluded.mock_count,
                fulfill_count = excluded.fulfill_count,
                transform_count = excluded.transform_count,
                start_url = excluded.start_url,
                step_count = excluded.step_count,
                session_ids = excluded.session_ids,
                base_url = excluded.base_url,
                api_mode = excluded.api_mode,
                source_mtime = excluded.source_mtime,
                indexed_at = excluded.indexed_at
            """,
            _summary_to_row(
                summary,
                base_url=base_url or runtime.base_url,
                api_mode=api_mode or runtime.api_mode,
                source_mtime=mtime,
            ),
        )


def index_flow_from_disk(flow_name: str, base: Path | None = None) -> FlowSummary | None:
    root = base or output_dir()
    flow_dir = _fixtures_root(base) / flow_name
    if not flow_dir.is_dir():
        delete_flow_index(flow_name, base=base)
        return None

    summary = scan_flow_dir(flow_dir, root)
    upsert_flow_index(summary, base=base)
    return summary


def delete_flow_index(flow_name: str, base: Path | None = None) -> None:
    init_flow_index(base)
    with _connect(base) as conn:
        conn.execute("DELETE FROM flows WHERE name = ?", (flow_name,))


def update_flow_runtime_index(
    flow_name: str,
    *,
    base_url: str,
    api_mode: str,
    base: Path | None = None,
) -> None:
    init_flow_index(base)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(base) as conn:
        conn.execute(
            """
            UPDATE flows
            SET base_url = ?, api_mode = ?, indexed_at = ?
            WHERE name = ?
            """,
            (base_url, api_mode, now, flow_name),
        )


def sync_flow_index(*, base: Path | None = None, force: bool = False) -> dict[str, int]:
    init_flow_index(base)
    root = base or output_dir()
    fixtures_root = _fixtures_root(base)

    scanned = 0
    removed = 0
    skipped = 0

    dir_count, dir_mtime = _fixtures_signature(base)

    with _connect(base) as conn:
        if not force:
            stored_sig = _get_meta(conn, "fixtures_signature")
            current_sig = f"{dir_count}:{dir_mtime}"
            if stored_sig == current_sig:
                return {"scanned": 0, "removed": 0, "skipped": 0, "cached": True}

        indexed: dict[str, float] = {
            row["name"]: float(row["source_mtime"])
            for row in conn.execute("SELECT name, source_mtime FROM flows")
        }

        disk_names: set[str] = set()
        if fixtures_root.exists():
            for flow_dir in fixtures_root.iterdir():
                if not flow_dir.is_dir():
                    continue
                name = flow_dir.name
                disk_names.add(name)
                mtime = _flow_source_mtime(flow_dir, root)
                if not force and indexed.get(name) == mtime:
                    skipped += 1
                    continue
                summary = scan_flow_dir(flow_dir, root)
                upsert_flow_index(summary, base=base, source_mtime=mtime)
                scanned += 1

        for stale_name in set(indexed) - disk_names:
            conn.execute("DELETE FROM flows WHERE name = ?", (stale_name,))
            removed += 1

        _set_meta(conn, "fixtures_signature", f"{dir_count}:{dir_mtime}")
        _set_meta(conn, "last_sync", datetime.now(timezone.utc).isoformat())

    return {"scanned": scanned, "removed": removed, "skipped": skipped, "cached": False}


def ensure_flow_index_synced(base: Path | None = None) -> None:
    sync_flow_index(base=base, force=False)


@dataclass
class PaginatedFlows:
    items: list[FlowSummary]
    total: int
    page: int
    page_size: int
    pages: int
    base_url_by_name: dict[str, str]
    api_mode_by_name: dict[str, str]


def list_flows_paginated(
    *,
    base: Path | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    has_spec: bool | None = None,
    sort: str = "name",
) -> PaginatedFlows:
    ensure_flow_index_synced(base)
    init_flow_index(base)

    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    clauses: list[str] = []
    params: list[Any] = []

    if q:
        clauses.append("(name LIKE ? OR COALESCE(start_url, '') LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    if has_spec is not None:
        clauses.append("has_spec = ?")
        params.append(int(has_spec))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    order = "name ASC"
    if sort == "newest":
        order = "indexed_at DESC"

    with _connect(base) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM flows {where}",
            params,
        ).fetchone()["c"]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT * FROM flows
            {where}
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    items = [_row_to_summary(row) for row in rows]
    base_url_by_name = {row["name"]: row["base_url"] for row in rows}
    api_mode_by_name = {row["name"]: row["api_mode"] for row in rows}

    return PaginatedFlows(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, ceil(total / page_size)) if total else 1,
        base_url_by_name=base_url_by_name,
        api_mode_by_name=api_mode_by_name,
    )


def lookup_flows(
    *,
    base: Path | None = None,
    q: str | None = None,
    limit: int = 30,
    has_spec: bool | None = None,
) -> list[dict[str, Any]]:
    ensure_flow_index_synced(base)
    init_flow_index(base)
    limit = max(1, min(limit, 100))

    clauses: list[str] = []
    params: list[Any] = []

    if q:
        clauses.append("(name LIKE ? OR COALESCE(start_url, '') LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    if has_spec is not None:
        clauses.append("has_spec = ?")
        params.append(int(has_spec))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with _connect(base) as conn:
        rows = conn.execute(
            f"""
            SELECT name, has_spec, base_url, api_mode, start_url
            FROM flows
            {where}
            ORDER BY name ASC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [
        {
            "name": row["name"],
            "has_spec": bool(row["has_spec"]),
            "base_url": row["base_url"],
            "api_mode": row["api_mode"],
            "start_url": row["start_url"],
        }
        for row in rows
    ]


def get_flow_from_index(flow_name: str, base: Path | None = None) -> FlowSummary | None:
    ensure_flow_index_synced(base)
    init_flow_index(base)
    with _connect(base) as conn:
        row = conn.execute(
            "SELECT * FROM flows WHERE name = ?",
            (flow_name,),
        ).fetchone()
    if not row:
        return None
    return _row_to_summary(row)


def flow_exists_in_index(flow_name: str, base: Path | None = None) -> bool:
    ensure_flow_index_synced(base)
    init_flow_index(base)
    with _connect(base) as conn:
        row = conn.execute(
            "SELECT 1 FROM flows WHERE name = ?",
            (flow_name,),
        ).fetchone()
    return row is not None


def flow_index_stats(base: Path | None = None) -> dict[str, int]:
    ensure_flow_index_synced(base)
    init_flow_index(base)
    with _connect(base) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS flow_count,
                SUM(has_spec) AS with_specs,
                SUM(has_har) AS with_har,
                SUM(fulfill_count) AS offline_mocks
            FROM flows
            """
        ).fetchone()
    return {
        "flow_count": int(row["flow_count"] or 0),
        "with_specs": int(row["with_specs"] or 0),
        "with_har": int(row["with_har"] or 0),
        "offline_mocks": int(row["offline_mocks"] or 0),
    }


def flow_summary_to_api(
    summary: FlowSummary,
    *,
    base_url: str | None = None,
    api_mode: str | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    if base_url is None or api_mode is None:
        runtime = load_runtime_settings(summary.name, base=base or output_dir())
        base_url = base_url or runtime.base_url
        api_mode = api_mode or runtime.api_mode
    return {
        "name": summary.name,
        "has_flow_json": summary.has_flow_json,
        "has_api_mocks": summary.has_api_mocks,
        "has_spec": summary.has_spec,
        "has_har": summary.has_har,
        "fixture_count": summary.fixture_count,
        "mock_count": summary.mock_count,
        "fulfill_count": summary.fulfill_count,
        "transform_count": summary.transform_count,
        "start_url": summary.start_url,
        "step_count": summary.step_count,
        "session_ids": summary.session_ids,
        "base_url": base_url,
        "api_mode": api_mode,
    }
