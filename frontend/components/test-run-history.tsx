"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { TestRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { fetchTestRun } from "@/lib/api";

function statusVariant(status: string): "success" | "warning" | "muted" | "default" {
  if (status === "passed") return "success";
  if (status === "flaky") return "warning";
  if (status === "failed") return "warning";
  return "muted";
}

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function TestRunHistory({ runs }: { runs: TestRun[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TestRun | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const toggle = async (run: TestRun) => {
    if (expandedId === run.id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(run.id);
    setLoadingId(run.id);
    try {
      const full = await fetchTestRun(run.id);
      setDetail(full);
    } catch {
      setDetail(run);
    } finally {
      setLoadingId(null);
    }
  };

  if (runs.length === 0) {
    return <p className="text-sm text-zinc-400">No test runs recorded yet.</p>;
  }

  return (
    <div className="space-y-2">
      {runs.map((run) => {
        const open = expandedId === run.id;
        return (
          <div
            key={run.id}
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden"
          >
            <button
              type="button"
              onClick={() => toggle(run)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-zinc-800/50 transition-colors"
            >
              {open ? (
                <ChevronDown className="h-4 w-4 shrink-0 text-zinc-500" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0 text-zinc-500" />
              )}
              <div className="flex-1 min-w-0 grid gap-1 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center sm:gap-4">
                <div>
                  <div className="font-medium text-zinc-100 truncate">{run.flow_name}</div>
                  <div className="text-xs text-zinc-500">{formatWhen(run.started_at)}</div>
                </div>
                <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                <span className="text-xs text-zinc-400 tabular-nums">
                  {formatDuration(run.duration_ms)}
                </span>
                <span className="text-xs text-zinc-500 font-mono truncate max-w-[8rem]">
                  {run.api_mode || "—"}
                </span>
              </div>
            </button>

            {open && (
              <div className="border-t border-zinc-800 px-4 py-4 space-y-3 text-sm">
                {loadingId === run.id && (
                  <p className="text-zinc-500">Loading details…</p>
                )}
                {detail?.id === run.id && (
                  <>
                    <div className="grid gap-2 sm:grid-cols-2 text-zinc-400">
                      <div>
                        <span className="text-zinc-500">Spec:</span>{" "}
                        <span className="font-mono text-zinc-300">{detail.spec_name}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500">Base URL:</span>{" "}
                        <span className="font-mono text-zinc-300 truncate">{detail.base_url}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500">Results:</span>{" "}
                        <span className="text-emerald-400">{detail.passed} passed</span>
                        {detail.failed > 0 && (
                          <span className="text-red-400"> · {detail.failed} failed</span>
                        )}
                        {detail.flaky > 0 && (
                          <span className="text-amber-400"> · {detail.flaky} flaky</span>
                        )}
                        {detail.skipped > 0 && (
                          <span className="text-zinc-400"> · {detail.skipped} skipped</span>
                        )}
                      </div>
                      <div>
                        <span className="text-zinc-500">Exit code:</span>{" "}
                        <span className="font-mono text-zinc-300">{detail.exit_code}</span>
                      </div>
                    </div>

                    {detail.error_summary && (
                      <p className="text-red-400 whitespace-pre-wrap">{detail.error_summary}</p>
                    )}

                    {detail.logs && (
                      <pre className="text-xs bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-auto max-h-64 text-zinc-300">
                        {detail.logs}
                      </pre>
                    )}

                    {detail.report && (
                      <details>
                        <summary className="cursor-pointer text-zinc-400 hover:text-zinc-200">
                          Playwright JSON report
                        </summary>
                        <pre className="mt-2 text-xs bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-auto max-h-64 text-zinc-300">
                          {JSON.stringify(detail.report, null, 2)}
                        </pre>
                      </details>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
