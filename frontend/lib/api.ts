import { API_BASE } from "./utils";

export type FlowSummary = {
  name: string;
  has_flow_json: boolean;
  has_api_mocks: boolean;
  has_spec: boolean;
  has_har: boolean;
  fixture_count: number;
  mock_count: number;
  fulfill_count: number;
  transform_count: number;
  start_url: string | null;
  step_count: number;
  session_ids: string[];
  base_url?: string;
  api_mode?: "live_obfuscate" | "offline_fixtures" | "passthrough";
};

export type SettingField = {
  key: string;
  label: string;
  description: string;
  group: string;
  required_for: string;
  secret: boolean;
  value: string;
  masked_value: string;
  is_set: boolean;
};

export type Overview = {
  output_dir: string;
  flow_count: number;
  with_specs: number;
  with_har: number;
  offline_mocks: number;
  settings_ok: { generate: boolean; record: boolean };
};

export type FlowRuntime = {
  settings: {
    base_url: string;
    api_mode: "live_obfuscate" | "offline_fixtures" | "passthrough";
  };
  mock_count: number;
  offline_ready: boolean;
  has_manifest: boolean;
};

export type FlowDetail = {
  summary: FlowSummary;
  flow_json: string | null;
  api_mocks_json: string | null;
  spec_name: string | null;
  spec_text: string | null;
  test_data_ts: string | null;
  fixture_files: string[];
  fixtures: Record<string, string | null>;
  runtime: FlowRuntime;
};

export type Job = {
  id: string;
  type: string;
  status: "pending" | "running" | "complete" | "failed";
  logs: string;
  result: Record<string, unknown> | null;
  error: string | null;
  meta: Record<string, unknown>;
  done: boolean;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const fetchOverview = () => api<Overview>("/api/overview");
export const fetchFlows = () => api<FlowSummary[]>("/api/flows");
export const fetchFlow = (name: string) => api<FlowDetail>(`/api/flows/${encodeURIComponent(name)}`);
export const fetchFlowRuntime = (name: string) =>
  api<FlowRuntime>(`/api/flows/${encodeURIComponent(name)}/runtime`);
export const saveFlowRuntime = (
  name: string,
  body: { base_url: string; api_mode: FlowRuntime["settings"]["api_mode"] },
) =>
  api<FlowRuntime>(`/api/flows/${encodeURIComponent(name)}/runtime`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
export const fetchSettings = () => api<SettingField[]>("/api/settings");
export const saveSettings = (values: Record<string, string>) =>
  api<SettingField[]>("/api/settings", {
    method: "PUT",
    body: JSON.stringify({ values }),
  });
export const startGenerate = (body: {
  query: string;
  session_ids?: string[];
  recording_ids?: string[];
}) =>
  api<{ job_id: string }>("/api/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const startRecord = (body: {
  flow_name: string;
  har_base64?: string;
  har_filename?: string;
}) =>
  api<{ job_id: string }>("/api/record", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const startPlay = (
  flowName: string,
  body?: { headed?: boolean; slow_mo?: number },
) =>
  api<{ job_id: string }>(`/api/flows/${encodeURIComponent(flowName)}/play`, {
    method: "POST",
    body: JSON.stringify(body ?? { headed: true, slow_mo: 1500 }),
  });
export const fetchJob = (id: string) => api<Job>(`/api/jobs/${id}`);
