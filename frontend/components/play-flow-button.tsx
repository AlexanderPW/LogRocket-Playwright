"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { startPlay } from "@/lib/api";
import { JobMonitor } from "@/components/job-monitor";
import { Button } from "@/components/ui/button";

export function PlayFlowButton({
  flowName,
  hasSpec,
  size = "sm",
}: {
  flowName: string;
  hasSpec: boolean;
  size?: "sm" | "md";
}) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!hasSpec) return null;

  const play = async () => {
    setError(null);
    setLoading(true);
    setJobId(null);
    try {
      const { job_id } = await startPlay(flowName, { headed: true, slow_mo: 1500 });
      setJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start test");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <Button variant="secondary" size={size} onClick={play} disabled={loading}>
        <Play className="h-4 w-4 mr-1.5" />
        {loading ? "Starting…" : "Play flow"}
      </Button>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {jobId && <JobMonitor jobId={jobId} />}
    </div>
  );
}
