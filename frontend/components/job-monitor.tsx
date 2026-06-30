"use client";

import { useEffect, useState } from "react";
import { fetchJob, type Job } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function JobMonitor({
  jobId,
  onComplete,
}: {
  jobId: string;
  onComplete?: (job: Job) => void;
}) {
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const data = await fetchJob(jobId);
        if (cancelled) return;
        setJob(data);
        if (data.done) {
          onComplete?.(data);
          return;
        }
        setTimeout(poll, 1500);
      } catch {
        if (!cancelled) setTimeout(poll, 3000);
      }
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [jobId, onComplete]);

  if (!job) {
    return <p className="text-sm text-zinc-400">Starting job…</p>;
  }

  const variant =
    job.status === "complete"
      ? "success"
      : job.status === "failed"
        ? "warning"
        : "default";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="text-base">Job {job.id}</CardTitle>
          <Badge variant={variant}>{job.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {job.error && (
          <p className="text-sm text-red-400 whitespace-pre-wrap">{job.error}</p>
        )}
        {job.result && (
          <pre className="text-xs bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-auto text-emerald-300">
            {JSON.stringify(job.result, null, 2)}
          </pre>
        )}
        {job.logs && (
          <pre className="text-xs bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-auto max-h-80 text-zinc-300">
            {job.logs}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
