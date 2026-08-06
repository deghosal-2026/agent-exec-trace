# agent-exec-trace v0.1.0 — E2E Seed Data Spec

> Purpose: Document all seed data required to exercise E2E UI tests reliably across Dashboard, Fleet Health, Run Timeline, Version Compare, and Anomaly Inbox.

---

## 1) Overview & Principles

- Goal: Provide a deterministic, sufficiently rich dataset that enables Playwright tests to validate core journeys and auxiliary states without flaky data dependencies.
- Determinism: Counts and distributions are stable between runs. Specific run IDs are opaque; tests assert on shapes/filters rather than hardcoded IDs.
- What is seeded vs. stubbed:
  - Seeded: run summaries, anomalies, fleet rollups, version cohort summaries.
  - Stubbed in tests: span tree for one timeline test (API currently returns `spans: []`).
  - Simulated by network intercepts: empty, error (500), and slow/loading states.

Seed source: `scripts/seed-e2e-data.py` (default DSN `postgresql://analytics:analytics@localhost:5433/analytics`).

---

## 2) Baseline Dataset Summary (Current Seed)

Agents and versions
- research_crew: v1.2.0, v1.3.0
- support_triage: v1.0.0, v1.1.0, v2.0.0
- code_review: v1.0.0
- demo_triage: v0.1.0, v0.2.0

Volumes and distributions
- Runs: 12 per agent-version; total 96 runs.
- Status mix per 12-run batch: 8 success, 4 error (by index rule `ri >= 8`).
- Notable patterns per batch:
  - Loop runs at `ri in {2, 9}` with `loop_detected=True` and `loop_count=8`.
  - Retry storms at `ri in {4, 10}`; `total_retries = ri * 3`.
  - Cost spikes at `ri in {1, 7}` via higher `estimated_cost`.
  - One timeout-like long run at `ri == 6` (via duration/cost patterns; no explicit status).
- Anomalies: Each run gets 1–4 anomalies, severities: first=critical, others=warning. Total ~240 across many types.
- Fleet rollups: 7 daily rollups per agent-version (period_start..end), with stable aggregates.
- Version cohorts: one per agent-version with totals, success/error, loops, avg cost, retries, and top_tools placeholder.
- Time window: last 7 days, staggered by agent/version/run index to ensure ordering variety.

Notes
- Tool deltas: current seed writes `top_tools` as a JSON array string (e.g., `["fetch_data", ...]`). The API’s tool-delta computation expects a dict of counts per tool. Result: `tool_deltas` is typically empty in compare responses.
- Spans: not populated; timeline `spans` is an empty list by design in v0.1.0.

---

## 3) View-by-View Seed Requirements

### Dashboard
- Needs non-zero aggregates so four summary cards render with values > 0.
- Agent card grid: ≥4 agents with versions and runs.
- Navigation from an agent card should land in Fleet filtered by that agent; seed already provides multiple agents and versions.
- No extra data beyond baseline required.

### Fleet Health (`/fleet`)
- Non-empty table: baseline provides many rows (agent × version rollups).
- Filters must narrow results:
  - Agent filter (e.g., `research_crew`) yields a strict subset.
  - Version filter reduces further within that agent.
  - Workload filter matches agent workload fields.
- Status/error coverage: error rows present due to `ri >= 8` logic feeding aggregates.
- Combined filters produce intersections; some combos should yield 0 rows to exercise EmptyState.
- Loading/error states are covered via test intercepts; no special seed needed.

### Run Timeline (`/runs/:runId`)
- Valid run IDs exist across success and error statuses.
- Anomalies list must include examples of `cost_spike`, `loop`, and `retry_storm` to validate badges and evidence UI.
- Spans: real API returns `spans: []`; one Playwright test stubs a nested span tree to exercise expand/collapse and detail panel.
- Back navigation state is router-driven and not seed-dependent.

### Version Compare (`/compare`)
- Agents with ≥2 versions where cohort aggregates differ so `deltas` are non-zero:
  - research_crew (v1.2.0 vs v1.3.0)
  - demo_triage (v0.1.0 vs v0.2.0)
  - support_triage (v1.0.0 vs v1.1.0 vs v2.0.0)
- Selector population: all versions for a selected agent must appear; baseline satisfies this.
- Zero-delta case: compare same version to itself; no special seed required.
- Sparse-cohort warning: baseline can trigger “not-found” warnings by selecting a non-existent version. To explicitly test “small cohort (<5 runs)” warning, see Recommended Augmentations.
- Tool deltas UI: For visible per-tool deltas, seed must store dict-shaped `top_tools` with differing counts between versions. Applied: research_crew v1.2.0 uses `{ fetch_data: 30, analyze: 20, search: 10 }` and v1.3.0 uses `{ fetch_data: 25, analyze: 35, search: 5 }`, producing non-empty `tool_deltas`. Other agents retain array-shaped `top_tools` and will show empty `tool_deltas`.

### Anomaly Inbox (`/anomalies`)
- Non-empty list with multiple types and severities; baseline satisfies.
- Filters:
  - By type (e.g., `loop`) reduces to loop-only items.
  - By severity (e.g., `critical`) reduces items accordingly.
- Click-through navigates to Timeline for the selected run.
- Empty/loading/error states use test intercepts; seed not required.

---

## 4) Edge Cases via Test Intercepts (No Seed Needed)

- Empty states: apply over-constrained filters client-side or intercept API with empty payloads.
- Error states: intercept endpoints with 500 to render ErrorState and retry control.
- Slow/loading: intercept with artificial delays to display skeletons.
- Zero-delta: select identical versions on both sides in the compare form.

---

## 5) Gaps & Recommended Minimal Augmentations (Optional for v0.1.0)

1. Small Cohorts (<5 runs) Warning — ✅ Applied
   - Added `research_crew` v1.4.0 with 3 runs (type `runs_per_agent_version // 3` for 1 error, `ri == 2` for a loop, `ri == 1` for a cost spike).
   - Comparing v1.4.0 (3 runs) vs any 12-run version triggers the `sparse_cohorts` warning (`min(runs) = 3 < 5`).

2. Tool Deltas in Version Compare
   - Purpose: Render non-empty `tool_deltas` table with positive/negative deltas.
   - Minimal change: For a single agent with two versions (e.g., `research_crew` v1.2.0 vs v1.3.0), set `top_tools` to dicts of per-tool counts, e.g.:
     - v1.2.0: `{ fetch_data: 30, analyze: 20, search: 10 }`
     - v1.3.0: `{ fetch_data: 25, analyze: 35, search: 5 }`
   - The API computes rate-per-run deltas from these counts; ensure run counts remain ≥5 to avoid conflating with sparse warnings.

3. Full Enum Coverage (Low Priority)
   - The API exposes additional anomaly types not critical to UI tests (e.g., `semantic_loop`, `hallucination`, `goal_drift`, `quality_degradation`, `confusion_pattern`). Current seed covers many types but not necessarily all. Only augment if documentation or demos require those specific labels in the Inbox.

---

## 6) Table → Scenario Mapping

- run_summaries: Drives Dashboard cards, Fleet grouping metrics, Timeline header/stats. Needs status mix (success/error), variance in retries, cost, duration, and loop flags.
- anomalies: Drives Timeline anomaly list and Inbox. Needs a type and severity mix with at least some `critical` entries for filter validation.
- fleet_rollups: Drives Fleet aggregates over time windows; ensures the table has stable rows for filters and navigation.
- version_cohort_summaries: Drives Compare cohorts and deltas; to produce non-empty `tool_deltas`, `top_tools` must be a dict of tool→count.

---

## 7) Deterministic Counts & Selector Expectations

- Total runs: 96; per agent-version: 12.
- Per 12-run batch:
  - Errors: 4 (indices 8–11)
  - Loops: 2 (indices 2, 9)
  - Retry storms: 2 (indices 4, 10)
  - Cost spikes: 2 (indices 1, 7)
- Anomalies per run: 1–4; first anomaly is `critical`, others `warning`.
- Versions per agent: support_triage has 3; others have 1–2, ensuring both single- and multi-version flows are exercised.

---

## 8) Span Tree Strategy (v0.1.0)

- No span records are seeded; API returns `spans: []` for timelines.
- One Playwright test stubs a realistic nested span tree response to validate the SpanTree component (expand/collapse, detail pane). All other timeline tests use real API data.

---

## 9) Execution & Environment Notes

- Bring up stack: `docker compose up -d --build` (Postgres host port 5433 → container 5432).
- Migrate: `python3 scripts/migrate-db.py`
- Seed: `python3 scripts/seed-e2e-data.py` (or `make seed-e2e` if defined)
- Playwright tests: `cd apps/web && npx playwright test`
- Base URL: `http://localhost:5173` (Vite dev server; proxies `/api` to `http://localhost:8000`).

---

## 10) Appendix: Seed Generation Logic (Reference)

Formulas per run index `ri` (0..11) in each agent-version cohort:
- Status: `error` if `ri >= 8`, else `success`.
- Retries: `ri * 3` for retry-storm indices `{4, 10}`, else `ri`.
- Tool calls: `(ri + 1) * 4 + (retries * 2)`.
- Estimated cost (USD): `0.05 + ri * 0.15 + retries * 0.02`.
- Duration (ms): `12000 + ri * 8000 + (tool_calls * 1200)`.
- Loop signal: `loop_detected=True` and `loop_count=8` for `ri in {2, 9}`, else 0.
- Start/complete times: spread over the last 7 days by version index and run index.

Anomaly assignment per run:
- 1–4 anomalies, newest first; first `severity=critical`, others `warning`.
- Types rotate across a broad list to produce diversity (e.g., loop, retry patterns, cost spikes, timeouts, token/cost efficiency).

---

## 11) Acceptance for Seed Sufficiency

- Dashboard: non-zero aggregates; agent cards present; card navigation lands on Fleet filtered.
- Fleet: table has rows; filters narrow as expected; combined filters can yield empty; error/loading via intercepts.
- Timeline: real runs show header/anomalies; one test uses stubbed spans; back nav preserves filters.
- Compare: multiple versions per agent; deltas non-zero for selected pairs; zero-delta by identical versions; sparse warning tested (not-found by default; optional small-cohort augmentation); tool_deltas visible if augmentation applied.
- Inbox: list populated; type/severity filters reduce rows; click-through to timeline works; empty/error/loading via intercepts.

---

## 12) Open Choice

Do we implement the two recommended augmentations now for v0.1.0 E2E?
1) Add one small cohort (<5 runs) to explicitly test size-based sparse warning.
2) Set dict-shaped `top_tools` with differing counts for one agent’s two versions to exercise tool-deltas UI.

If yes, we’ll update `scripts/seed-e2e-data.py` minimally and note exact expectations in this doc.
