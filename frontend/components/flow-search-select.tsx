"use client";

import { useEffect, useRef, useState } from "react";
import { lookupFlows, type FlowLookup } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function FlowSearchSelect({
  value,
  onChange,
  hasSpec,
  placeholder = "Search flows…",
  id = "flow-search",
}: {
  value: string;
  onChange: (name: string, flow?: FlowLookup) => void;
  hasSpec?: boolean;
  placeholder?: string;
  id?: string;
}) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<FlowLookup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initialized = useRef(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await lookupFlows({
          q: query || undefined,
          limit: 50,
          has_spec: hasSpec,
        });
        if (cancelled) return;
        setOptions(data);
        if (!initialized.current && data.length > 0 && !value) {
          initialized.current = true;
          onChangeRef.current(data[0].name, data[0]);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load flows");
          setOptions([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, hasSpec, value]);

  const selected = options.find((f) => f.name === value);

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>Flow</Label>
      <Input
        id={id}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        className="mb-2"
      />
      <select
        value={value}
        onChange={(e) => {
          const flow = options.find((f) => f.name === e.target.value);
          onChange(e.target.value, flow);
        }}
        disabled={loading || options.length === 0}
        className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
      >
        {options.length === 0 ? (
          <option value="">{loading ? "Loading…" : "No flows found"}</option>
        ) : (
          options.map((flow) => (
            <option key={flow.name} value={flow.name}>
              {flow.name}
              {flow.has_spec ? "" : " (no spec)"}
            </option>
          ))
        )}
      </select>
      {selected && (
        <p className="text-xs text-zinc-500 font-mono truncate">
          {selected.base_url || selected.start_url || "No URL"}
        </p>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
