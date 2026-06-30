import { fetchTestRuns, fetchTestStats, type TestRun, type TestRunStats } from "@/lib/api";
import { TestRunnerPanel } from "@/components/test-runner-panel";
import { TestRunHistory } from "@/components/test-run-history";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const dynamic = "force-dynamic";

export default async function TestsPage() {
  let runs: TestRun[] = [];
  let stats: TestRunStats | null = null;
  let error: string | null = null;

  try {
    [runs, stats] = await Promise.all([
      fetchTestRuns({ limit: 30 }),
      fetchTestStats(),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load tests";
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-zinc-50">Tests</h1>
        <p className="text-zinc-400 mt-2">
          Run Playwright tests headless, capture pass/fail/flake results, and track history over time.
        </p>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-zinc-400">Total runs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-zinc-50">{stats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-zinc-400">Passed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-emerald-400">{stats.passed}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-zinc-400">Failed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-400">{stats.failed}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-zinc-400">Flaky</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-amber-400">{stats.flaky}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-zinc-400">Pass rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-zinc-50">
                {stats.pass_rate != null ? `${stats.pass_rate}%` : "—"}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Run test</CardTitle>
        </CardHeader>
        <CardContent>
          <TestRunnerPanel />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          <TestRunHistory runs={runs} />
        </CardContent>
      </Card>
    </div>
  );
}
