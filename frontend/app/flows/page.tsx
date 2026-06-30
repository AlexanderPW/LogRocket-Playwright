import Link from "next/link";
import { fetchFlows, type FlowSummary } from "@/lib/api";
import { PlayFlowButton } from "@/components/play-flow-button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

export default async function FlowsPage() {
  let flows: FlowSummary[] = [];
  let error: string | null = null;
  try {
    flows = await fetchFlows();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load flows";
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-zinc-50">Flows</h1>
          <p className="text-zinc-400 mt-2">Generated regression flows and their artifacts.</p>
        </div>
        <Link href="/generate">
          <Button>Generate new flow</Button>
        </Link>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {flows.length === 0 && !error && (
        <Card>
          <CardContent className="pt-6 text-zinc-400 text-sm">
            No flows yet. Use Generate to create one from a session replay.
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
                  <Badge variant="muted">
                    {flow.api_mode === "live_obfuscate"
                      ? "Live + obfuscate"
                      : flow.api_mode === "offline_fixtures"
                        ? "Offline fixtures"
                        : "Passthrough"}
                  </Badge>
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
    </div>
  );
}
