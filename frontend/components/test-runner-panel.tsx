"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { TestTube2 } from "lucide-react";
import { startTest, type FlowLookup } from "@/lib/api";
import { FlowSearchSelect } from "@/components/flow-search-select";
import { JobMonitor } from "@/components/job-monitor";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

function apiModeLabel(mode?: string) {
  if (mode === "live_obfuscate") return "Live + obfuscate";
  if (mode === "offline_fixtures") return "Offline fixtures";
  if (mode === "passthrough") return "Passthrough";
  return mode ?? "live_obfuscate";
}

export function TestRunnerPanel() {
  const router = useRouter();
  const [flowName, setFlowName] = useState("");
  const [selectedFlow, setSelectedFlow] = useState<FlowLookup | null>(null);
  const [headed, setHeaded] = useState(false);
  const [slowMo, setSlowMo] = useState(0);
  const [retries, setRetries] = useState(1);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const runTest = async () => {
    if (!flowName) return;
    setError(null);
    setLoading(true);
    setJobId(null);
    try {
      const { job_id } = await startTest(flowName, {
        headed,
        slow_mo: slowMo,
        retries,
      });
      setJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start test");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <FlowSearchSelect
        value={flowName}
        hasSpec
        onChange={(name, flow) => {
          setFlowName(name);
          setSelectedFlow(flow ?? null);
        }}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="test-slow-mo">Slow motion (ms)</Label>
          <select
            id="test-slow-mo"
            value={slowMo}
            onChange={(e) => setSlowMo(Number(e.target.value))}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
          >
            <option value={0}>0 — full speed</option>
            <option value={500}>500</option>
            <option value={1500}>1500 — demo pace</option>
            <option value={3000}>3000 — slow debug</option>
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="test-retries">Retries (flake detection)</Label>
          <select
            id="test-retries"
            value={retries}
            onChange={(e) => setRetries(Number(e.target.value))}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
          >
            <option value={0}>0 — no retries</option>
            <option value={1}>1 — retry once</option>
            <option value={2}>2 — retry twice</option>
          </select>
        </div>
      </div>

      {selectedFlow && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/80 px-4 py-3 text-sm text-zinc-400 space-y-1">
          <p>
            <span className="text-zinc-500">Environment:</span>{" "}
            <span className="font-mono text-zinc-300">
              {selectedFlow.base_url || selectedFlow.start_url || "—"}
            </span>
          </p>
          <p>
            <span className="text-zinc-500">API mode:</span>{" "}
            <span className="text-zinc-300">{apiModeLabel(selectedFlow.api_mode)}</span>
            <span className="text-zinc-600">
              {" "}
              — from{" "}
              <code className="text-zinc-400">fixtures/{selectedFlow.name}/runtime.json</code>
            </span>
          </p>
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-zinc-300">
        <input
          type="checkbox"
          checked={headed}
          onChange={(e) => {
            setHeaded(e.target.checked);
            if (e.target.checked && slowMo === 0) setSlowMo(1500);
          }}
          className="rounded border-zinc-600"
        />
        Run headed (visible browser)
      </label>

      <Button onClick={runTest} disabled={loading || !flowName}>
        <TestTube2 className="h-4 w-4 mr-1.5" />
        {loading ? "Starting…" : "Run test"}
      </Button>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {jobId && (
        <JobMonitor
          jobId={jobId}
          onComplete={() => {
            router.refresh();
          }}
        />
      )}
    </div>
  );
}
