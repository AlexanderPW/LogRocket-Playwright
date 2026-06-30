import { fetchOverview } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  let overview;
  let error: string | null = null;
  try {
    overview = await fetchOverview();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to reach API";
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-50">Overview</h1>
        <p className="text-zinc-400 mt-2 max-w-2xl">
          Turn real user session replays into Playwright regression tests using local
          Qwen, multi-agent codegen, and PII-safe fixtures.
        </p>
      </div>

      {error && (
        <Card className="border-red-900/50 bg-red-950/20">
          <CardContent className="pt-6 text-red-300 text-sm">
            API unreachable — start the backend with{" "}
            <code className="text-red-200">e2e-api</code>. ({error})
          </CardContent>
        </Card>
      )}

      {overview && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Flows", value: overview.flow_count },
              { label: "With specs", value: overview.with_specs },
              { label: "With HAR", value: overview.with_har },
              { label: "Offline mocks", value: overview.offline_mocks },
            ].map((m) => (
              <Card key={m.label}>
                <CardHeader className="pb-2">
                  <CardDescription>{m.label}</CardDescription>
                  <CardTitle className="text-3xl tabular-nums">{m.value}</CardTitle>
                </CardHeader>
              </Card>
            ))}
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Agent pipeline</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs text-zinc-300 leading-relaxed">
{`Your query
    ↓
Session Researcher  ←→  session replay source (MCP)
    ↓
Faker PII sanitizer
    ↓
Flow Normalizer     →  flow.json
    ↓
Test Writer         →  Playwright .spec.ts
    ↓
Test Reviewer
    ↓
record-fixtures     →  HAR → fixtures (optional)
    ↓
npx playwright test`}
                </pre>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Environment</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">Generate ready</span>
                  <Badge variant={overview.settings_ok.generate ? "success" : "warning"}>
                    {overview.settings_ok.generate ? "Configured" : "Missing vars"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">Record fixtures ready</span>
                  <Badge variant={overview.settings_ok.record ? "success" : "warning"}>
                    {overview.settings_ok.record ? "Configured" : "Missing vars"}
                  </Badge>
                </div>
                <p className="text-xs text-zinc-500 pt-2">
                  Output: <code className="text-zinc-300">{overview.output_dir}</code>
                </p>
                <p className="text-xs text-zinc-500">
                  Configure credentials and models in{" "}
                  <a href="/settings" className="text-indigo-400 hover:underline">
                    Settings
                  </a>
                  .
                </p>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function CardDescription({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-zinc-400">{children}</p>;
}
