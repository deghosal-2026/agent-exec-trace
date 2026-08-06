# agent-exec-trace v0.1.0 — E2E Testing Plan

> Covers: M11 (E2E Playwright Testing and Screenshot Validation)
> Stack: React + Vite frontend → FastAPI backend → Postgres read-model
> Test framework: Playwright

---

## 1. Objective

Validate the current product end-to-end with Playwright before any more product
changes. After this validation passes, the UI and major functionality are frozen
for the v0.1.0 release. All four standard views must render correctly with seeded
data, filters and navigation must work, and screenshots must be captured for the
user guide.

## 2. Prerequisites

| Item | State |
|------|-------|
| `docker compose up -d --build` boots all 6 services | ✅ M10.1 |
| `make migrate-db` creates read-model tables | ✅ M10.5 |
| `make seed-e2e` populates Postgres with 96 runs, 240 anomalies, 4 agents | ✅ M10.2 |
| All 4 API views return data | ✅ M10.3 |
| Python 3.10+ and Node 22+ available | ✅ |
| Playwright installed (`npx playwright install`) | pending |

## 3. Mock Data Seeded

The seed script (`scripts/seed-e2e-data.py`) populates:

```
4 agents × 2-3 versions × 12 runs = 96 run_summaries
~240 anomalies across all 41 anomaly types
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
  testDir: './tests/e2e',
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'on',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
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

## 5. Test Matrix

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

## 8. Acceptance Criteria for M11 Completion

- [ ] All 19 Playwright tests pass (FLEET-01 through ACC-04)
- [ ] 7 screenshots captured in `docs/screenshots/`
- [ ] `make e2e` runs end-to-end from cold start
- [ ] No test flakes on 3 consecutive runs
- [ ] Playwright config committed to repo
- [ ] Test files committed to `apps/web/tests/e2e/`

## 9. Risk and Mitigations

| Risk | Mitigation |
|------|------------|
| Tests depend on seeded data shape | Seed script is deterministic with fixed seed; document expected row counts |
| Vite dev proxy vs Docker networking | Tests use `baseURL: http://localhost:5173`; Vite proxies `/api` to `http://localhost:8000` |
| Playwright binary download | Document `npx playwright install chromium` in developer setup |
| Flaky tests from timing | Use `waitForSelector` / `waitForResponse` not fixed `sleep`; 1 retry in config |
| Postgres port conflict (5433 vs 5432) | Seed script defaults to 5433; document in setup |