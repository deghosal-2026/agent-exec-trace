# agent-exec-trace v0.1.0 — E2E Testing Plan (Robust)

> Milestone: M11 (E2E Playwright Testing and Screenshot Validation)
> Stack: React + Vite → FastAPI → Postgres (read-model)
> Framework: Playwright

---

## 1. Objective & Scope

Validate the current product end-to-end with Playwright before any more product changes.
Success is defined as: every core user journey is automated, every major UI feature is
exercised (including loading, empty, and error states), and screenshots are captured
for the user guide. After this passes, the UI and major functionality are frozen for v0.1.0.

In scope
- Dashboard, Fleet Health, Run Timeline, Version Compare, Anomaly Inbox
- Filters, navigation, table rendering, summary cards, span tree interactions (via stubbing)
- Loading skeletons, error states, empty states
- Screenshot capture for all key views and interactions

Out of scope
- Backend performance, large-scale dataset performance (tracked separately)
- Cross-browser parity beyond Chromium (optional smoke only)

## 2. Prerequisites

| Item | State |
|------|-------|
| `docker compose up -d --build` boots all 6 services | ✅ M10.1 |
| `make migrate-db` creates read-model tables | ✅ M10.5 |
| `make seed-e2e` populates Postgres with 96 runs, 240 anomalies, 4 agents | ✅ M10.2 |
| All 4 API views return data | ✅ M10.3 |
| Python 3.10+ and Node 22+ available | ✅ |
| Playwright installed (`npx playwright install`) | pending |

## 3. Mock Data & Synthetic Traces

Primary seed (`scripts/seed-e2e-data.py`) populates:

```
4 agents × 2-3 versions × 12 runs = 96 run_summaries
~240 anomalies across 41+ anomaly types
28 fleet_rollups (7 days × 4 agents)
9 version_cohort_summaries
```

| Agent | Versions | Runs | Notes |
|-------|----------|------|-------|
| research_crew | v1.2.0, v1.3.0 | 24 | Has version compare data |
| support_triage | v1.0.0, v1.1.0, v2.0.0 | 36 | Multi-version, multi-compare |
| code_review | v1.0.0 | 12 | Single version |
| demo_triage | v0.1.0, v0.2.0 | 24 | Has version compare data |

Every 12-run batch has intentionally seeded failures: 4 error runs, 2 loop runs,
2 retry-storm runs, 2 cost-spike runs.

Current API returns `spans: []` for timelines; to exercise SpanTree UI, Playwright will
stub the timeline endpoint with a static nested span tree fixture for one test (other
tests hit the real API).

## 4. Playwright Setup

### 4.1 Installation

```bash
cd apps/web
npm install -D @playwright/test
npx playwright install chromium
```

### 4.2 Config (`apps/web/playwright.config.ts`)

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e', timeout: 30_000, retries: 1,
  use: { baseURL: 'http://localhost:5173', screenshot: 'on', trace: 'on-first-retry' },
  projects: [ { name: 'chromium', use: { browserName: 'chromium' } } ],
});
```

### 4.3 Directory Layout

```
apps/web/
├── tests/
│   └── e2e/
│       ├── fleet.spec.ts        # Fleet Health view tests
│       ├── timeline.spec.ts     # Run Timeline view tests
│       ├── compare.spec.ts      # Version Compare view tests
│       ├── anomalies.spec.ts    # Anomaly Inbox view tests
│       └── acceptance.spec.ts   # Demo acceptance assertions
├── playwright.config.ts
└── screenshots/                 # captured screenshots output
```

## 5. Customer User Journeys (CUJs)

CUJ-1: Triage a critical anomaly
1) Open Anomaly Inbox → filter severity=critical → click first row
2) Land on Run Timeline → verify error status, anomaly badges
Good looks like: critical-only list; timeline shows anomaly list; Inspect works

CUJ-2: Investigate a suspected loop from Fleet
1) Fleet → filter agent="research_crew" → click any row
2) Timeline → loop_detected badge present; (stub) expand SpanTree; SpanDetail shown
Good looks like: agent-filtering narrows rows; loop badge visible; span interactions work

CUJ-3: Compare versions after rollout
1) Compare → enter agent + version A/B → run compare
2) Verify cost/retry/success deltas non-zero; tool deltas populated or noted
Good looks like: non-empty deltas for seeded cohorts; warnings for sparse cohorts

CUJ-4: Fleet overview from Dashboard
1) Dashboard → verify summary cards → click an agent card
2) Land on Fleet filtered by that agent
Good looks like: non-zero totals; navigation persists context

CUJ-5: Empty/error/slow states
1) Fleet/Anomalies: apply filters that produce no results → EmptyState
2) Intercept 500 on each page → ErrorState with retry
3) Intercept slow responses → loading skeletons visible
Good looks like: all auxiliary states render correctly; no crashes

## 6. Test Catalog (What/How/Good Looks Like)

Route: `/` Dashboard — `dashboard.spec.ts`
1) DASH-01 Overview cards — Visit `/`; assert 4 cards > 0; Shot `dashboard-overview.png`; Good: matches API aggregates
2) DASH-02 Agent cards grid — ≥4 cards show name/version/workload/runs; anomaly badge conditional
3) DASH-03 Card navigation — Click first card → `/fleet?agent=...`; table filtered; Shot `dashboard-to-fleet.png`
4) DASH-04 Empty state — Intercept `/api/v1/fleet` empty → EmptyState visible

Route: `/fleet` Fleet Health — `fleet.spec.ts`
1) FLEET-01 Default table — rows > 0; columns correct; Shot `fleet-default.png`
2) FLEET-02 Agent filter — select `research_crew` → only that agent
3) FLEET-03 Version filter — version-only rows
4) FLEET-04 Combined filters — intersection subset
5) FLEET-05 Empty filters — EmptyState; clear filters resets; Shot `fleet-error-filter.png` (if useful)
6) FLEET-06 Row click → Timeline — navigates to `/runs?...` and/or `/runs/:id`
7) FLEET-07 Loading — intercept slow; skeletons visible
8) FLEET-08 Error — intercept 500; ErrorState with retry

Route: `/runs` & `/runs/:runId` Run Timeline — `timeline.spec.ts`
1) TL-01 Direct by ID — header (agent, status), anomalies list; Shot `timeline-normal.png`
2) TL-02 Empty spans — EmptyState when `spans: []`
3) TL-03 Stubbed spans — route.fulfill with nested spans; expand/collapse; SpanDetail; Shot `timeline-spans.png`
4) TL-04 Cost spike evidence — anomaly list includes cost_spike item
5) TL-05 Back nav — return to Fleet; filters preserved

Route: `/compare` Version Compare — `compare.spec.ts`
1) CMP-01 Two versions — cohorts render; non-zero deltas; Shot `compare-deltas.png`
2) CMP-02 Selector population — dropdown lists seeded versions
3) CMP-03 Single version — validation message; no crash
4) CMP-04 Zero-delta — identical cohorts → zero-delta; sparse warning if <5 runs
5) CMP-05 Sparse warning — cohorts <5 runs show warning

Route: `/anomalies` Inbox — `anomalies.spec.ts`
1) ANM-01 Default list — items > 0; type/severity/agent/summary/time; Shot `anomalies-default.png`
2) ANM-02 Type filter — loop-only items
3) ANM-03 Severity filter — critical-only; Shot `anomalies-critical.png`
4) ANM-04 Agent filter — substring match narrows results
5) ANM-05 Click-through — navigates to `/runs/:runId`
6) ANM-06 Loading — intercept slow; skeletons visible
7) ANM-07 Error — intercept 500; ErrorState with retry
8) ANM-08 Empty — filter to none; EmptyState

Total tests (target): 26+ across 6 spec files.

### 5.1 Fleet Health View (`fleet.spec.ts`)

| Test ID | Scenario | Assertions | Screenshot |
|---------|----------|------------|------------|
| FLEET-01 | Page loads with seeded data | Table has >0 rows, shows agent name, version, run count | `fleet-default.png` |
| FLEET-02 | Agent name filter: "research_crew" | Only research_crew rows visible, count changed | — |
| FLEET-03 | Status filter: "error" | Only error-status rows visible | `fleet-error-filter.png` |
| FLEET-04 | Combined filters | Intersection produces correct subset | — |
| FLEET-05 | Empty filter result | Graceful empty state shown, no crash | — |

### 5.2 Run Timeline View (`timeline.spec.ts`)

| Test ID | Scenario | Assertions | Screenshot |
|---------|----------|------------|------------|
| TL-01 | Navigate fleet → click run | URL changes to `/runs/{run_id}`, page renders | `timeline-normal.png` |
| TL-02 | Normal run | Span tree visible, no anomaly badges, status "success" | — |
| TL-03 | Loop anomaly run | Anomaly badges visible, loop detected, status "error" | `timeline-loop-anomaly.png` |
| TL-04 | Cost spike run | Cost spike anomaly in badge list, evidence visible | — |
| TL-05 | Back navigation | Navigate back to fleet, previous filters preserved | — |

### 5.3 Version Compare View (`compare.spec.ts`)

| Test ID | Scenario | Assertions | Screenshot |
|---------|----------|------------|------------|
| CMP-01 | Select two versions | Delta table renders with non-empty data | `compare-deltas.png` |
| CMP-02 | Version selector populated | Dropdown shows all versions for selected agent | — |
| CMP-03 | Single version selected | Appropriate message shown (not a crash) | — |
| CMP-04 | Versions with no anomalies | Zero-delta display, no error | — |

### 5.4 Anomaly Inbox View (`anomalies.spec.ts`)

| Test ID | Scenario | Assertions | Screenshot |
|---------|----------|------------|------------|
| ANM-01 | Inbox loads with seeded anomalies | Table has >0 rows, shows type, severity, agent | `anomalies-default.png` |
| ANM-02 | Type filter: "loop" | Only loop anomalies visible | — |
| ANM-03 | Severity filter: "critical" | Only critical anomalies visible | `anomalies-critical.png` |
| ANM-04 | Click anomaly → navigate | URL changes to run timeline with context | — |
| ANM-05 | Empty inbox | Appropriate empty state, no crash | — |

### 5.5 Demo Acceptance (`acceptance.spec.ts`)

| Test ID | Scenario | Assertions |
|---------|----------|------------|
| ACC-01 | Normal + loop runs distinguishable | Fleet shows both success and error runs; clicking each navigates to different timelines |
| ACC-02 | Fleet groups by agent | Multiple agent names visible in fleet table; version column populated |
| ACC-03 | Version compare shows deltas | Two versions selected → deltas non-zero for cost, retries, success rate |
| ACC-04 | Anomaly inbox filters | Type and severity filters change visible rows |

## 6. Screenshot Capture Strategy

Screenshots are captured automatically by Playwright (`screenshot: 'on'` in
config). After each test run, relevant screenshots are copied to
`docs/screenshots/` for the user guide.

| Screenshot | Source Test | Used In |
|------------|-------------|---------|
| `fleet-default.png` | FLEET-01 | User guide: Fleet Health |
| `fleet-error-filter.png` | FLEET-03 | User guide: Filtering |
| `timeline-normal.png` | TL-01 | User guide: Run Timeline |
| `timeline-loop-anomaly.png` | TL-03 | User guide: Anomalies |
| `compare-deltas.png` | CMP-01 | User guide: Version Compare |
| `anomalies-default.png` | ANM-01 | User guide: Anomaly Inbox |
| `anomalies-critical.png` | ANM-03 | User guide: Severity filtering |

## 7. Makefile Integration

```makefile
e2e: ## Run Playwright e2e tests and capture screenshots.
	@echo "==> Starting compose stack"
	@docker compose up -d
	@echo "==> Running migrations"
	@python3 scripts/migrate-db.py
	@echo "==> Seeding e2e data"
	@python3 scripts/seed-e2e-data.py
	@echo "==> Running Playwright tests"
	@cd apps/web && npx playwright test
	@echo "==> Copying screenshots"
	@mkdir -p docs/screenshots
	@cp apps/web/test-results/**/*.png docs/screenshots/ 2>/dev/null || true
	@echo "E2E tests complete. Screenshots in docs/screenshots/"
```

## 8. Acceptance Criteria (What Good Looks Like)

- [ ] All 26+ Playwright tests pass (DASH-01 … ANM-08, ACC-04)
- [ ] 10+ screenshots in `docs/screenshots/` (see matrix)
- [ ] `make e2e` runs end-to-end from cold start
- [ ] No test flakes on 3 consecutive runs
- [ ] Playwright config committed to repo
- [ ] Test files committed to `apps/web/tests/e2e/`

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Tests depend on seeded data shape | Seed script is deterministic with fixed seed; document expected row counts |
| Vite dev proxy vs Docker networking | Tests use `baseURL: http://localhost:5173`; Vite proxies `/api` to `http://localhost:8000` |
| Playwright binary download | Document `npx playwright install chromium` in developer setup |
| Flaky tests from timing | Use `waitForSelector` / `waitForResponse` not fixed `sleep`; 1 retry in config |
| Postgres port conflict (5433 vs 5432) | Seed script defaults to 5433; document in setup |
| Span tree not present in API | Stub timeline once per run with a static fixture; plan API enhancement for v0.2.0 |

## 10. Coverage Checklist (UI Features → Tests)

- Dashboard: summary cards, agent cards, navigation, empty
- Fleet: filters (agent/version/workload), clear, row nav, loading, error, empty, summary cards
- Timeline: header, anomalies list, empty spans, (stubbed) SpanTree expand/collapse + detail, back nav
- Compare: inputs, validation, cohorts + deltas, tool deltas/notes, sparse warning, zero-delta
- Inbox: type/severity/agent filters, loading, error, empty, click-through

## 11. Execution & Artifacts

- Command: `make e2e`
- Outputs: Playwright traces (on-first-retry), screenshots in `docs/screenshots/`
- CI: Add a job gating merges on e2e (non-blocking on optional cross-browser)

## 12. Failure Triage

1) Collect Playwright trace and screenshot from failure
2) Identify if seed, API response, or UI timing caused the issue
3) If seed drift: adjust seed or relax overly strict assertion (but keep value)
4) If timing: prefer event-based waits over fixed delays
5) If API drift: confirm backend contracts, then update client/tests
