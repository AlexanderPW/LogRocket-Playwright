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

export type FlowsPage = {
  items: FlowSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type FlowLookup = {
  name: string;
  has_spec: boolean;
  base_url: string;
  api_mode: FlowSummary["api_mode"];
  start_url: string | null;
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

export type TestRun = {
  id: string;
  flow_name: string;
  status: "passed" | "failed" | "flaky" | "skipped";
  started_at: string;
  finished_at: string;
  duration_ms: number;
  headed: boolean;
  slow_mo: number;
  retries: number;
  base_url: string;
  api_mode: string;
  spec_name: string;
  exit_code: number;
  passed: number;
  failed: number;
  flaky: number;
  skipped: number;
  error_summary: string | null;
  logs: string;
  report?: Record<string, unknown> | null;
};

export type TestRunStats = {
  total: number;
  passed: number;
  failed: number;
  flaky: number;
  skipped: number;
  pass_rate: number | null;
  recent_failures: Array<{
    id: string;
    flow_name: string;
    status: string;
    started_at: string;
    error_summary: string | null;
  }>;
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

export const fetchFlowsPage = (params?: {
  q?: string;
  page?: number;
  page_size?: number;
  has_spec?: boolean;
  sort?: string;
}) => {
  const query = new URLSearchParams();
  if (params?.q) query.set("q", params.q);
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  if (params?.has_spec !== undefined) query.set("has_spec", String(params.has_spec));
  if (params?.sort) query.set("sort", params.sort);
  const suffix = query.toString() ? `?${query}` : "";
  return api<FlowsPage>(`/api/flows${suffix}`);
};

/** @deprecated Prefer fetchFlowsPage or lookupFlows for large flow lists. */
export const fetchFlows = async (params?: {
  q?: string;
  has_spec?: boolean;
}) => {
  const page = await fetchFlowsPage({ ...params, page: 1, page_size: 10_000 });
  return page.items;
};

export const lookupFlows = (params?: {
  q?: string;
  limit?: number;
  has_spec?: boolean;
}) => {
  const query = new URLSearchParams();
  if (params?.q) query.set("q", params.q);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.has_spec !== undefined) query.set("has_spec", String(params.has_spec));
  const suffix = query.toString() ? `?${query}` : "";
  return api<FlowLookup[]>(`/api/flows/lookup${suffix}`);
};

export const reindexFlows = () =>
  api<{ scanned: number; removed: number; skipped: number; cached: boolean }>(
    "/api/flows/reindex",
    { method: "POST" },
  );
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
export const startTest = (
  flowName: string,
  body?: { headed?: boolean; slow_mo?: number; retries?: number },
) =>
  api<{ job_id: string }>(`/api/flows/${encodeURIComponent(flowName)}/test`, {
    method: "POST",
    body: JSON.stringify(body ?? { headed: false, slow_mo: 0, retries: 1 }),
  });
export const fetchTestRuns = (params?: {
  flow_name?: string;
  status?: string;
  limit?: number;
}) => {
  const query = new URLSearchParams();
  if (params?.flow_name) query.set("flow_name", params.flow_name);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query}` : "";
  return api<TestRun[]>(`/api/test-runs${suffix}`);
};
export const fetchTestRun = (id: string) => api<TestRun>(`/api/test-runs/${id}`);
export const fetchTestStats = () => api<TestRunStats>("/api/test-runs/stats");
export const fetchJob = (id: string) => api<Job>(`/api/jobs/${id}`);
