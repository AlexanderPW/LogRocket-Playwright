"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { fetchFlowsPage, type FlowSummary } from "@/lib/api";
import { PlayFlowButton } from "@/components/play-flow-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const PAGE_SIZE = 20;

function apiModeLabel(mode?: string) {
  if (mode === "live_obfuscate") return "Live + obfuscate";
  if (mode === "offline_fixtures") return "Offline fixtures";
  if (mode === "passthrough") return "Passthrough";
  return mode ?? "—";
}

export function FlowsExplorer() {
  const [flows, setFlows] = useState<FlowSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (nextPage: number, q: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFlowsPage({
        page: nextPage,
        page_size: PAGE_SIZE,
        q: q || undefined,
      });
      setFlows(data.items);
      setTotal(data.total);
      setPage(data.page);
      setPages(data.pages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load flows");
      setFlows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page, search);
  }, [load, page, search]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or URL…"
            className="pl-9"
          />
        </div>
        <p className="text-sm text-zinc-500 tabular-nums">
          {loading ? "Loading…" : `${total} flow${total === 1 ? "" : "s"}`}
        </p>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && flows.length === 0 && !error && (
        <Card>
          <CardContent className="pt-6 text-zinc-400 text-sm">
            {search
              ? "No flows match your search."
              : "No flows yet. Use Generate to create one from a session replay."}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {flows.map((flow) => (
          <Card key={flow.name} className="hover:border-zinc-700 transition-colors">
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle>{flow.name}</CardTitle>
                  <p className="text-sm text-zinc-500 mt-1 font-mono truncate max-w-xl">
                    {flow.start_url ?? "No start URL"}
                  </p>
                </div>
                <Link href={`/flows/${flow.name}`}>
                  <Button variant="secondary" size="sm">
                    View detail
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2 text-sm">
                <Badge variant="muted">{flow.step_count} steps</Badge>
                {flow.has_spec && <Badge variant="success">spec</Badge>}
                {flow.has_har && <Badge variant="success">HAR</Badge>}
                {flow.fixture_count > 0 && (
                  <Badge variant="muted">{flow.fixture_count} fixtures</Badge>
                )}
                {flow.api_mode && (
                  <Badge variant="muted">{apiModeLabel(flow.api_mode)}</Badge>
                )}
                <Badge variant="muted">
                  {flow.fulfill_count} fulfill / {flow.transform_count} transform
                </Badge>
              </div>
              <PlayFlowButton flowName={flow.name} hasSpec={flow.has_spec} />
            </CardContent>
          </Card>
        ))}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-between gap-4 pt-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <span className="text-sm text-zinc-500 tabular-nums">
            Page {page} of {pages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= pages || loading}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
