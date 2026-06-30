from __future__ import annotations

import json
from pathlib import Path

from .pii.sanitizer import PIISanitizer
from .schemas import ApiMock, GeneratedTest, NormalizedFlow, SyntheticTestData

ROUTE_HELPER_TS = """\
import { Page, Route, Request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

export type ApiMockSpec = {
  method: string;
  urlPattern: string;
  fixtureFile: string;
  status?: number;
  transformResponse?: boolean;
};

type MockManifest = {
  flowName: string;
  mocks: ApiMockSpec[];
};

function redactPii(value: unknown): unknown {
  if (typeof value === 'string') {
    return value
      .replace(/\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\b/g, 'user@example.test')
      .replace(/\\b(?:\\+?1[-.\\s]?)?(?:\\(\\d{3}\\)|\\d{3})[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b/g, '555-010-0200')
      .replace(/\\b\\d{3}-\\d{2}-\\d{4}\\b/g, '000-00-0000');
  }
  if (Array.isArray(value)) return value.map(redactPii);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, redactPii(v)]),
    );
  }
  return value;
}

function matchesMock(request: Request, mock: ApiMockSpec): boolean {
  const pattern = mock.urlPattern.replace(/\\*\\*/g, '').replace(/\\*/g, '');
  return (
    request.method().toUpperCase() === mock.method.toUpperCase() &&
    request.url().includes(pattern)
  );
}

export async function setupPiiSafeRoutes(page: Page, flowName: string): Promise<void> {
  const fixturesDir = path.join(__dirname, '..', 'fixtures', flowName);
  const runtimePath = path.join(fixturesDir, 'runtime.json');
  if (fs.existsSync(runtimePath)) {
    const runtime = JSON.parse(fs.readFileSync(runtimePath, 'utf-8')) as { api_mode?: string };
    if (runtime.api_mode === 'passthrough') return;
  }

  const manifestPath = path.join(fixturesDir, 'api-mocks.json');
  if (!fs.existsSync(manifestPath)) return;

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8')) as MockManifest & {
    apiMode?: string;
  };
  if (manifest.apiMode === 'passthrough') return;

  await page.route('**/*', async (route: Route) => {
    const request = route.request();
    const mock = manifest.mocks.find((entry) => matchesMock(request, entry));
    if (!mock) {
      await route.continue();
      return;
    }

    const fixturePath = path.join(fixturesDir, mock.fixtureFile);
    if (mock.transformResponse) {
      try {
        const response = await route.fetch();
        const json = await response.json();
        await route.fulfill({
          status: response.status(),
          contentType: 'application/json',
          body: JSON.stringify(redactPii(json)),
        });
        return;
      } catch {
        await route.continue();
        return;
      }
    }

    if (!fs.existsSync(fixturePath)) {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: mock.status ?? 200,
      contentType: 'application/json',
      body: fs.readFileSync(fixturePath, 'utf-8'),
    });
  });
}
"""


RECORD_FLOW_TS = """\
import { BrowserContext, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { pathToFileURL } from 'url';

type FlowStep = {
  order: number;
  action: string;
  target: string;
  value?: string | null;
  url?: string | null;
};

type FlowJson = {
  name: string;
  start_url: string;
  steps: FlowStep[];
};

function fixturesDir(flowName: string): string {
  return path.join(__dirname, '..', 'fixtures', flowName);
}

async function runStep(page: Page, step: FlowStep, testData: Record<string, string>): Promise<void> {
  const value = step.value ?? '';
  const resolved = value.replace(/\\{\\{testData\\.(\\w+)\\}\\}/g, (_, key: string) => testData[key] ?? value);

  switch (step.action) {
    case 'navigate':
      await page.goto(step.url ?? resolved, { waitUntil: 'domcontentloaded' });
      return;
    case 'click':
      await page.getByRole('button', { name: step.target }).click({ timeout: 15_000 }).catch(async () => {
        await page.getByText(step.target, { exact: false }).first().click({ timeout: 15_000 });
      });
      return;
    case 'fill':
      await page.getByLabel(step.target).fill(resolved, { timeout: 15_000 }).catch(async () => {
        await page.getByPlaceholder(step.target).fill(resolved, { timeout: 15_000 });
      });
      return;
    case 'select':
      await page.getByLabel(step.target).selectOption(resolved);
      return;
    case 'wait':
      await page.waitForTimeout(500);
      return;
    default:
      return;
  }
}

export async function recordFlowFixtures(
  page: Page,
  context: BrowserContext,
  flowName: string,
): Promise<void> {
  const dir = fixturesDir(flowName);
  const flowPath = path.join(dir, 'flow.json');
  const testDataPath = path.join(__dirname, `${flowName}.test-data.ts`);
  const harPath = path.join(dir, 'capture.har');

  if (!fs.existsSync(flowPath)) {
    throw new Error(`Missing flow.json for ${flowName}`);
  }

  const flow = JSON.parse(fs.readFileSync(flowPath, 'utf-8')) as FlowJson;
  const testDataModule = await import(pathToFileURL(testDataPath).href);
  const testData = testDataModule.testData as Record<string, string>;

  await context.recordHar({
    path: harPath,
    mode: 'minimal',
    content: 'embed',
    urlFilter: /\\/api\\//,
  });

  const startUrl = flow.start_url.startsWith('http')
    ? flow.start_url
    : new URL(flow.start_url, process.env.STAGING_BASE_URL).toString();

  await page.goto(startUrl, { waitUntil: 'domcontentloaded' });

  const ordered = [...flow.steps].sort((a, b) => a.order - b.order);
  for (const step of ordered) {
    if (step.action === 'navigate') continue;
    await runStep(page, step, testData);
  }

  await page.waitForLoadState('networkidle').catch(() => undefined);
}
"""


RECORD_FLOW_SPEC_TS = """\
import { test } from '@playwright/test';
import { recordFlowFixtures } from './record-flow';

const flowName = process.env.FLOW_NAME;

test('record fixtures @recorder', async ({ page, context }) => {
  test.skip(!flowName, 'Set FLOW_NAME when running the recorder');
  await recordFlowFixtures(page, context, flowName!);
});
"""


def _render_test_data_ts(test_data: SyntheticTestData) -> str:
    payload = test_data.model_dump(by_alias=True)
    lines = [
        "// AUTO-GENERATED synthetic data — safe for CI and local runs",
        "export const testData = {",
    ]
    alias_to_ts = {
        "email": "email",
        "firstName": "firstName",
        "lastName": "lastName",
        "fullName": "fullName",
        "phone": "phone",
        "company": "company",
        "addressLine1": "addressLine1",
        "city": "city",
        "state": "state",
        "postalCode": "postalCode",
        "password": "password",
    }
    for key, ts_key in alias_to_ts.items():
        if key in payload:
            lines.append(f"  {ts_key}: {json.dumps(payload[key])},")
    lines.append("} as const;")
    lines.append("")
    lines.append("export type TestData = typeof testData;")
    lines.append("")
    return "\n".join(lines)


def _render_api_manifest(flow: NormalizedFlow) -> str:
    manifest = {
        "flowName": flow.name,
        "mocks": [
            {
                "method": mock.method,
                "urlPattern": mock.url_pattern,
                "fixtureFile": mock.fixture_file,
                "status": mock.status,
                "transformResponse": mock.transform_response,
            }
            for mock in flow.api_mocks
        ],
    }
    return json.dumps(manifest, indent=2)


def write_playwright_support(
    output_dir: Path,
    flow: NormalizedFlow,
    generated: GeneratedTest,
    sanitizer: PIISanitizer,
) -> list[Path]:
    written: list[Path] = []

    support_dir = output_dir / "support"
    fixtures_dir = output_dir / "fixtures" / flow.name
    support_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    route_helper = support_dir / "pii-routes.ts"
    route_helper.write_text(ROUTE_HELPER_TS, encoding="utf-8")
    written.append(route_helper)

    test_data_file = support_dir / f"{flow.name}.test-data.ts"
    test_data_file.write_text(_render_test_data_ts(flow.test_data), encoding="utf-8")
    written.append(test_data_file)

    manifest_file = fixtures_dir / "api-mocks.json"
    manifest_file.write_text(_render_api_manifest(flow), encoding="utf-8")
    written.append(manifest_file)

    from .flow_runtime import FlowRuntimeSettings
    from urllib.parse import urlparse

    start = flow.start_url or ""
    if start.startswith("http"):
        parsed = urlparse(start)
        default_base = f"{parsed.scheme}://{parsed.netloc}"
    else:
        default_base = "https://portfolio.alexwaldrop.com"

    runtime_file = fixtures_dir / "runtime.json"
    runtime_file.write_text(
        FlowRuntimeSettings(base_url=default_base, api_mode="live_obfuscate").model_dump_json(
            indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(runtime_file)

    flow_file = fixtures_dir / "flow.json"
    flow_file.write_text(flow.model_dump_json(indent=2) + "\n", encoding="utf-8")
    written.append(flow_file)

    record_flow = support_dir / "record-flow.ts"
    record_flow.write_text(RECORD_FLOW_TS, encoding="utf-8")
    written.append(record_flow)

    record_spec = support_dir / "record-flow.spec.ts"
    record_spec.write_text(RECORD_FLOW_SPEC_TS, encoding="utf-8")
    written.append(record_spec)

    for mock in flow.api_mocks:
        if mock.transform_response:
            continue
        fixture_path = fixtures_dir / mock.fixture_file
        fixture_path.write_text(
            sanitizer.default_fixture_body(mock, flow.test_data),
            encoding="utf-8",
        )
        written.append(fixture_path)

    spec_path = output_dir / generated.filename
    spec_path.write_text(generated.code + "\n", encoding="utf-8")
    written.append(spec_path)

    return written
