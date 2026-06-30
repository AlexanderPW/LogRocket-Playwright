"use client";

import { useState } from "react";
import { startGenerate } from "@/lib/api";
import { JobMonitor } from "@/components/job-monitor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const DEFAULT_QUERY =
  "POC: personal portfolio site (no signup, checkout, or forms). " +
  "Use find_sessions to get the most recent session from the last 30 days that " +
  "lasted at least 10 seconds and includes multiple page navigations or link clicks. " +
  "Watch that session and extract the real navigation flow only.";

export default function GeneratePage() {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [sessionIds, setSessionIds] = useState("");
  const [recordingIds, setRecordingIds] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setError(null);
    setLoading(true);
    setJobId(null);
    try {
      const sessions = sessionIds
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const recordings = recordingIds
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const { job_id } = await startGenerate({
        query,
        session_ids: sessions,
        recording_ids: recordings,
      });
      setJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generate failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-zinc-50">Generate</h1>
        <p className="text-zinc-400 mt-2">
          Run the 4-agent pipeline against your session source and local Ollama model.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Session query</CardTitle>
          <CardDescription>
            Describe the session(s) to find and watch, or pin specific recording IDs.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="query">Query</Label>
            <Textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={5}
            />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="recording">Recording ID(s)</Label>
              <Input
                id="recording"
                placeholder="6-019f0e91-ddb1-79cc-8daf-7d883f4db298"
                value={recordingIds}
                onChange={(e) => setRecordingIds(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sessions">Session ID(s)</Label>
              <Input
                id="sessions"
                placeholder="Optional — from session replay URL"
                value={sessionIds}
                onChange={(e) => setSessionIds(e.target.value)}
              />
            </div>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button onClick={run} disabled={loading}>
            {loading ? "Starting…" : "Run generate"}
          </Button>
        </CardContent>
      </Card>

      {jobId && <JobMonitor jobId={jobId} />}
    </div>
  );
}
