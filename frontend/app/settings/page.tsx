"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchSettings, saveSettings, type SettingField } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  const [fields, setFields] = useState<SettingField[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings()
      .then((data) => {
        setFields(data);
        const initial: Record<string, string> = {};
        for (const f of data) {
          initial[f.key] = f.secret ? "" : f.masked_value || f.value;
        }
        setDraft(initial);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load settings"))
      .finally(() => setLoading(false));
  }, []);

  const groups = useMemo(() => {
    const map = new Map<string, SettingField[]>();
    for (const f of fields) {
      if (!map.has(f.group)) map.set(f.group, []);
      map.get(f.group)!.push(f);
    }
    return [...map.entries()];
  }, [fields]);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await saveSettings(draft);
      setFields(updated);
      const next: Record<string, string> = {};
      for (const f of updated) {
        next[f.key] = f.secret ? "" : f.masked_value || f.value;
      }
      setDraft(next);
      setMessage("Settings saved to .env");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-zinc-50">Settings</h1>
        <p className="text-zinc-400 mt-2">
          Credentials for your session replay provider, Ollama, output paths, and staging.
          Stored in{" "}
          <code className="text-zinc-300">.env</code> at the project root.
        </p>
      </div>

      {loading && <p className="text-zinc-400 text-sm">Loading…</p>}
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {message && <p className="text-emerald-400 text-sm">{message}</p>}

      {groups.map(([group, items]) => (
        <Card key={group}>
          <CardHeader>
            <CardTitle>{group}</CardTitle>
            <CardDescription>
              {items[0]?.required_for !== "all" && (
                <span>Required for: {items[0]?.required_for}</span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {items.map((field) => (
              <div key={field.key} className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label htmlFor={field.key}>{field.label}</Label>
                  <Badge variant={field.is_set ? "success" : "warning"}>
                    {field.is_set ? "set" : "missing"}
                  </Badge>
                </div>
                <p className="text-xs text-zinc-500">{field.description}</p>
                <Input
                  id={field.key}
                  type={field.secret ? "password" : "text"}
                  placeholder={
                    field.secret
                      ? field.masked_value
                        ? `Current: ${field.masked_value}`
                        : "Enter API key"
                      : field.key
                  }
                  value={draft[field.key] ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, [field.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </CardContent>
        </Card>
      ))}

      {!loading && (
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </Button>
      )}
    </div>
  );
}
