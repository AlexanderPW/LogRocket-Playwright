"use client";

import { useEffect, useState } from "react";
import { fetchFlows, startRecord } from "@/lib/api";
import { JobMonitor } from "@/components/job-monitor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function RecordPage() {
  const [flows, setFlows] = useState<string[]>([]);
  const [flowName, setFlowName] = useState("");
  const [harFile, setHarFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchFlows()
      .then((data) => {
        const names = data.map((f) => f.name);
        setFlows(names);
        if (names.length) setFlowName(names[0]);
      })
      .catch(() => setFlows([]));
  }, []);

  const run = async () => {
    if (!flowName) return;
    setError(null);
    setLoading(true);
    setJobId(null);
    try {
      let har_base64: string | undefined;
      let har_filename: string | undefined;
      if (harFile) {
        har_base64 = await fileToBase64(harFile);
        har_filename = harFile.name;
      }
      const { job_id } = await startRecord({
        flow_name: flowName,
        har_base64,
        har_filename,
      });
      setJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Record failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-zinc-50">Record fixtures</h1>
        <p className="text-zinc-400 mt-2">
          Replay a flow on staging, capture HAR, and write sanitized API fixtures.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Staging capture</CardTitle>
          <CardDescription>
            Requires <code className="text-zinc-300">STAGING_BASE_URL</code> in Settings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {flows.length === 0 ? (
            <p className="text-sm text-zinc-400">Generate a flow first.</p>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="flow">Flow</Label>
              <select
                id="flow"
                value={flowName}
                onChange={(e) => setFlowName(e.target.value)}
                className="flex h-10 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 text-sm text-zinc-100"
              >
                {flows.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="har">Upload existing HAR (optional)</Label>
            <input
              id="har"
              type="file"
              accept=".har,.json"
              onChange={(e) => setHarFile(e.target.files?.[0] ?? null)}
              className="text-sm text-zinc-400 file:mr-4 file:rounded-lg file:border-0 file:bg-zinc-800 file:px-4 file:py-2 file:text-sm file:text-zinc-200"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button onClick={run} disabled={loading || !flowName}>
            {loading ? "Starting…" : "Record fixtures"}
          </Button>
        </CardContent>
      </Card>

      {jobId && <JobMonitor jobId={jobId} />}
    </div>
  );
}
