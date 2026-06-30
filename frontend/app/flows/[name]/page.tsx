"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { fetchFlow } from "@/lib/api";
import { PlayFlowButton } from "@/components/play-flow-button";
import { FlowRuntimePanel } from "@/components/flow-runtime-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const tabs = [
  { id: "flow", label: "flow.json" },
  { id: "mocks", label: "api-mocks.json" },
  { id: "spec", label: "Playwright spec" },
  { id: "testdata", label: "test-data.ts" },
  { id: "fixtures", label: "Fixtures" },
] as const;

export default function FlowDetailPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const [name, setName] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("flow");
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchFlow>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    params.then((p) => setName(decodeURIComponent(p.name)));
  }, [params]);

  useEffect(() => {
    if (!name) return;
    fetchFlow(name)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [name]);

  const code = useMemo(() => {
    if (!data) return "";
    switch (tab) {
      case "flow":
        return data.flow_json ?? "Not found";
      case "mocks":
        return data.api_mocks_json ?? "Not found";
      case "spec":
        return data.spec_text ?? "Not found";
      case "testdata":
        return data.test_data_ts ?? "Not found";
      case "fixtures":
        return JSON.stringify(data.fixtures, null, 2);
      default:
        return "";
    }
  }, [data, tab]);

  if (!name) return null;

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/flows" className="text-sm text-indigo-400 hover:underline">
            ← Flows
          </Link>
          <h1 className="text-3xl font-bold text-zinc-50 mt-2">{name}</h1>
          {data?.summary.start_url && (
            <p className="text-zinc-500 font-mono text-sm mt-1">{data.summary.start_url}</p>
          )}
        </div>
        {data && (
          <PlayFlowButton flowName={name} hasSpec={data.summary.has_spec} size="md" />
        )}
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {data && (
        <>
          <FlowRuntimePanel
            flowName={name}
            runtime={data.runtime}
            onSaved={(runtime) => setData((d) => (d ? { ...d, runtime } : d))}
          />

          <div className="flex flex-wrap gap-2">
            <Badge variant="muted">{data.summary.step_count} steps</Badge>
            {data.summary.has_spec && <Badge variant="success">spec</Badge>}
            {data.summary.has_har && <Badge variant="success">HAR</Badge>}
          </div>

          <div className="flex gap-2 flex-wrap border-b border-zinc-800 pb-2">
            {tabs.map((t) => (
              <Button
                key={t.id}
                variant={tab === t.id ? "default" : "ghost"}
                size="sm"
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </Button>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {tab === "spec" && data.spec_name ? data.spec_name : tabs.find((t) => t.id === tab)?.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-xs bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-auto max-h-[32rem] text-zinc-300">
                {code}
              </pre>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
