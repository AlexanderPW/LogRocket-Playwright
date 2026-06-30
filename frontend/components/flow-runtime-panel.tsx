"use client";

import { useState } from "react";
import { saveFlowRuntime, type FlowRuntime } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_MODES = [
  {
    id: "live_obfuscate" as const,
    label: "Live + obfuscate",
    description:
      "Hit real APIs on the target URL. Responses are fetched live and PII is redacted before reaching the page.",
  },
  {
    id: "offline_fixtures" as const,
    label: "Offline fixtures",
    description:
      "Serve sanitized JSON fixture files. Best for CI — run Record fixtures first to capture shapes from staging.",
  },
  {
    id: "passthrough" as const,
    label: "Passthrough",
    description: "No route interception — raw network traffic (use only on staging with no real PII).",
  },
];

function modeLabel(mode: string) {
  return API_MODES.find((m) => m.id === mode)?.label ?? mode;
}

export function FlowRuntimePanel({
  flowName,
  runtime,
  onSaved,
}: {
  flowName: string;
  runtime: FlowRuntime;
  onSaved?: (runtime: FlowRuntime) => void;
}) {
  const [baseUrl, setBaseUrl] = useState(runtime.settings.base_url);
  const [apiMode, setApiMode] = useState(runtime.settings.api_mode);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await saveFlowRuntime(flowName, {
        base_url: baseUrl.trim(),
        api_mode: apiMode,
      });
      onSaved?.(updated);
      setMessage("Runtime settings saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const selected = API_MODES.find((m) => m.id === apiMode);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Run environment</CardTitle>
        <CardDescription>
          Control which URL Playwright hits and how API traffic is handled during Play flow.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap gap-2">
          <Badge variant="muted">API mode: {modeLabel(apiMode)}</Badge>
          {apiMode === "offline_fixtures" && (
            <Badge variant={runtime.offline_ready ? "success" : "warning"}>
              {runtime.offline_ready ? "Fixtures ready" : "Record fixtures first"}
            </Badge>
          )}
          {runtime.mock_count > 0 && (
            <Badge variant="muted">{runtime.mock_count} mock route(s)</Badge>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="base-url">Target base URL</Label>
          <Input
            id="base-url"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://staging.example.com"
          />
          <p className="text-xs text-zinc-500">
            Playwright opens this site when you click Play flow. Defaults from flow start URL or
            global Staging URL in Settings.
          </p>
        </div>

        <div className="space-y-3">
          <Label>API data mode</Label>
          <div className="grid gap-2">
            {API_MODES.map((mode) => (
              <button
                key={mode.id}
                type="button"
                onClick={() => setApiMode(mode.id)}
                className={`text-left rounded-lg border p-3 transition-colors ${
                  apiMode === mode.id
                    ? "border-indigo-500/50 bg-indigo-500/10"
                    : "border-zinc-800 hover:border-zinc-700"
                }`}
              >
                <div className="text-sm font-medium text-zinc-100">{mode.label}</div>
                <div className="text-xs text-zinc-500 mt-1">{mode.description}</div>
              </button>
            ))}
          </div>
          {selected && (
            <p className="text-xs text-zinc-400">
              Global <code className="text-zinc-300">PII_SANITIZE</code> still applies at generation
              time. This setting only affects test runtime API handling.
            </p>
          )}
        </div>

        {message && <p className="text-sm text-emerald-400">{message}</p>}
        {error && <p className="text-sm text-red-400">{error}</p>}

        <Button onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save runtime settings"}
        </Button>
      </CardContent>
    </Card>
  );
}

export function FlowRuntimeBadge({ runtime }: { runtime: FlowRuntime }) {
  return (
    <Badge variant="muted" title={runtime.settings.base_url}>
      {modeLabel(runtime.settings.api_mode)}
    </Badge>
  );
}
