from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys

from .config import load_record_settings, load_settings
from .pipeline import generate_e2e_from_query
from .record_fixtures import record_fixtures_from_har

DEFAULT_QUERY = (
    "Find checkout sessions from the last 7 days where users abandoned on the payment step. "
    "Watch a few and extract the common happy-path flow we should regression-test."
)


def _cmd_generate(query: str, session_ids: list[str] | None = None) -> None:
    try:
        settings = load_settings()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    generated, flow, written = asyncio.run(
        generate_e2e_from_query(settings, query, session_ids=session_ids)
    )
    print(f"Wrote {len(written)} files for flow '{flow.name}' ({generated.rationale})")
    for path in written:
        print(f"  - {path}")


def _cmd_record_fixtures(flow: str, har: str | None) -> None:
    from pathlib import Path

    try:
        settings = load_record_settings()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    har_path = Path(har).resolve() if har else None
    try:
        result = record_fixtures_from_har(settings, flow, har_path=har_path)
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print(
        f"Recorded fixtures for '{result.flow_name}': "
        f"{result.matched} matched, {result.skipped} skipped"
    )
    if result.har_path:
        print(f"  HAR: {result.har_path}")
    print(f"  Manifest: {result.manifest_path}")
    for path in result.fixtures_written:
        print(f"  - {path}")


def main() -> None:
    # Legacy usage: e2e-from-logrocket "some query" (no subcommand)
    if len(sys.argv) > 1 and sys.argv[1] not in {"generate", "record-fixtures", "-h", "--help"}:
        _cmd_generate(" ".join(sys.argv[1:]))
        return

    parser = argparse.ArgumentParser(
        description="Generate Playwright e2e tests from LogRocket flows, then record staging API fixtures."
    )
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate tests from a LogRocket flow query")
    gen.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    gen.add_argument(
        "--session-id",
        action="append",
        dest="session_ids",
        metavar="ID",
        help="LogRocket session ID to watch (repeatable). Skips broad session search.",
    )

    rec = sub.add_parser(
        "record-fixtures",
        help="Replay a flow on staging, capture HAR, and write sanitized API fixtures",
    )
    rec.add_argument("flow", help="Flow name (fixtures/<flow> directory)")
    rec.add_argument("--har", help="Process an existing HAR file instead of running Playwright")

    args = parser.parse_args()
    if args.command == "generate":
        _cmd_generate(args.query, session_ids=args.session_ids)
    elif args.command == "record-fixtures":
        _cmd_record_fixtures(args.flow, args.har)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
