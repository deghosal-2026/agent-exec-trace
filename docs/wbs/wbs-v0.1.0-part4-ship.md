# agent-exec-trace v0.1.0 WBS — Part 4-ship

> [← Back to WBS Table of Contents](wbs-v0.1.0.md)


## Milestone 10: End-to-End Local Stack ✅

### 10.1 Compose integration

This task assembles the product into one runnable local system. The compose stack is part of the OSS adoption strategy, so it should be treated like product surface, not internal plumbing.

**Success looks like:** one command (or a very small set of commands) brings up the complete local stack with all required services wired together.

- [x] Add API service to compose
- [x] Add analytics service to compose
- [x] Add web app to compose
- [x] Add Postgres to compose
- [x] Add networking and env wiring

**Notes:** Created Dockerfiles for api, analytics, and web services. Removed API profile so all services start with `docker compose up -d --build`. Fixed cross-package import in API (duplicated AnomalyType enum), fixed analytics worker coroutine bug, remapped Postgres host port to 5433 (local conflict), removed Jaeger METRICS_STORAGE_TYPE=none (unsupported). All 6 services healthy on startup.

### 10.2 Seed and replay workflow

This task makes the local stack demonstrable and testable. A good OSS project should let users reproduce interesting behavior deliberately rather than waiting for it to happen by chance.

**Success looks like:** contributors can run scripts or commands that reliably generate the good run and bad run scenarios needed for demos and tests.

- [x] Add script to run demo scenarios
- [x] Add script to seed bad runs
- [x] Add script or doc to replay traces into the stack

### 10.2.1 Replay acceptance requirement

This subtask makes replay a first-class requirement rather than a nice-to-have script. The product should be demonstrable repeatedly and should support debugging detector changes against stable evidence.

**Success looks like:** the same seeded traces or scenarios can be replayed multiple times to validate instrumentation, analytics, APIs, and UI behaviors predictably.

- [x] Confirm replay works after clean database reset
- [x] Confirm replay works after analytics code changes
- [x] Confirm replay outcomes are documented for demo and test use

### 10.3 End-to-end validation

This task verifies the product loop, not just individual services. It should confirm that trace generation, storage, analytics, APIs, and UI all line up in the ways the PRD promises.

**Success looks like:** the demo scenarios are visible across the whole stack and the core `v0.1.0` views all show meaningful, non-empty data.

- [x] Validate one normal run
- [x] Validate one loop anomaly run
- [x] Validate fleet view shows multiple runs/cohorts
- [x] Validate version compare shows non-empty deltas

### 10.4 Interoperability smoke checks

This task checks whether the stack still behaves like an OTel-native product rather than a tightly coupled local demo. The goal is to catch hidden assumptions early.

**Success looks like:** the local reference stack proves Jaeger-first operation while preserving collector-first and Tempo-compatible behavior with documented caveats.

- [x] Smoke test Jaeger-first stack
- [x] Smoke test Tempo-compatible path
- [x] Smoke test collector-mediated export
- [x] Record interop findings in docs

### 10.5 Failure-recovery smoke checks

This task verifies that the chosen architecture can recover from predictable development-time failures. The goal is not full chaos engineering, just enough confidence that the system can be reset and rebuilt without heroics.

**Success looks like:** developers can recover from common failures such as Postgres resets or analytics reprocessing needs using documented workflows.

- [x] Validate Postgres reset + rebuild flow
- [x] Validate analytics reprocessing flow after detector changes
- [x] Validate duplicate-run handling during replay
- [x] Document known weak recovery paths in `v0.1.0`

**Milestone 10 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

### 10.6 SDK tests

**Issue:** [#61](https://github.com/deghosal-2026/agent-exec-trace/issues/61)

**Context:** The instrumentation layer must be trustworthy. Since the whole product
rests on trace correctness, the SDK must be tested more rigorously than a casual
demo library.

**Success looks like:** root spans, nested spans, privacy defaults, and both
adapters are covered by tests that catch regressions in trace shape and metadata.

- [x] Unit tests for root span creation
- [x] Unit tests for tool span creation
- [x] Unit tests for privacy defaults
- [x] Integration tests for LangGraph adapter
- [x] Integration tests for raw Python decorator

### 10.7 Analytics tests

**Issue:** [#62](https://github.com/deghosal-2026/agent-exec-trace/issues/62)

**Context:** The product's interpretation layer must be protected. If summaries and
anomalies are wrong, the UI can look polished while telling users the wrong story.

**Success looks like:** summary rollups, anomaly detection, and persistence logic
are all validated against seeded scenarios and expected outputs.

- [x] Unit tests for summary materialization
- [x] Unit tests for loop detector
- [x] Unit tests for retry detector
- [x] Unit tests for cost detector
- [x] Integration tests for Postgres persistence

### 10.8 API tests

**Issue:** [#63](https://github.com/deghosal-2026/agent-exec-trace/issues/63)

**Context:** The API is a stable surface for the UI and future integrations.
Response shapes and filtering behavior should not drift silently.

**Success looks like:** each major endpoint has tests for shape, filtering, and
representative payloads for the core product views.

- [x] Test run timeline endpoint
- [x] Test fleet health endpoint
- [x] Test version compare endpoint
- [x] Test anomaly inbox endpoint

### 10.9 Web tests

**Issue:** [#64](https://github.com/deghosal-2026/agent-exec-trace/issues/64)

**Context:** The main views must remain navigable and intelligible as the product
evolves. Focus on the key interactions that express product value.

**Success looks like:** the main pages render, key filters and navigation work,
and at least one end-to-end UI flow can be exercised with confidence.

- [x] Render tests for key pages
- [x] Interaction tests for filters/navigation
- [x] End-to-end happy-path UI test if feasible

### 10.10 Acceptance scenario checks

**Issue:** [#65](https://github.com/deghosal-2026/agent-exec-trace/issues/65)

**Context:** Tests must tie back to product stories. Validate not just technical
correctness, but whether the product can support the main investigation workflows
promised in the PRD.

**Success looks like:** at least one automated or semi-automated check exists for
each `v0.1.0` standard view using seeded scenarios.

- [x] Validate single bad run workflow
- [x] Validate anomaly drill-down workflow
- [x] Validate fleet triage workflow
- [x] Validate version compare workflow

### 10.11 Service readiness checks

**Issue:** [#66](https://github.com/deghosal-2026/agent-exec-trace/issues/66)

**Context:** Split release thinking by service so one polished area does not hide
another weak one. Each service should have its own readiness signal before overall
release validation begins.

**Success looks like:** SDK, analytics, API, web, and docs each have explicit
readiness checks and no major service is assumed ready by association.

- [x] Confirm SDK readiness
- [x] Confirm analytics service readiness
- [x] Confirm API service readiness
- [x] Confirm web app readiness
- [x] Confirm docs/OSS readiness

---

## Milestone 11: E2E Playwright Testing and Screenshot Validation ✅

> **Priority:** Release gate. Before any remaining product changes, the current
> working stack must be validated end-to-end with Playwright. This milestone
> seeds mock data, runs automated UI tests against every product view, captures
> screenshots for the user guide, and asserts the product meets demo acceptance
> criteria. After this milestone passes, the UI and major functionality are frozen.
\n### 11.1 Playwright infrastructure and mock data seeding

**Issue:** (new)

**Context:** The compose stack boots cleanly (M10.1 ✅) but has no traces, no
anomalies, and no fleet data. Before Playwright can validate any view, the
database must contain realistic seeded data that exercises every product surface.

**Success looks like:** A single script populates Postgres with mock run summaries,
anomalies, fleet rollups, and version cohorts covering all 4 standard views.
Playwright is installed and configured with a project-level config.

- [x] Install Playwright and create `apps/web/playwright.config.ts`
- [x] Create `scripts/seed-e2e-data.py`: inserts mock runs (normal, loop, cost-spike, retry-storm), anomalies of every type, fleet rollups, and version cohorts
- [x] Add `make seed-e2e` to Makefile that runs the seed script against the compose Postgres
- [x] Verify all 4 views show non-empty data after seeding
- [x] Add Playwright test scripts under `apps/web/tests/e2e/`

### 11.2 Fleet Health view tests

**Issue:** (new)

**Context:** The fleet health page is the operator's first view — it should show
agent cohorts, run counts, anomaly counts, and filtering. Playwright must validate
that the page renders with data and filters work.

**Success looks like:** Playwright tests assert fleet health renders with
seeded data, agent name/status filters produce correct subsets, and empty
states do not crash.

- [x] Test: fleet health page renders with mock data (non-empty table)
- [x] Test: agent name filter narrows results correctly
- [x] Test: status filter narrows results correctly
- [x] Test: combined filters produce correct intersection
- [x] Test: empty filter result shows graceful empty state
- [x] Capture fleet health screenshot (with data) for user guide

### 11.3 Run Timeline view tests

**Issue:** (new)

**Context:** The run timeline shows span trees, anomalies, and run metadata
for a single trace. Playwright must validate navigation from fleet to timeline
and the anomaly detail display.

**Success looks like:** Playwright navigates fleet → click a run → timeline
renders with span tree, anomalies listed with severity badges, and the
drill-down flow works end-to-end.

- [x] Test: click a run in fleet table navigates to timeline
- [x] Test: run timeline renders span tree for a normal run
- [x] Test: run timeline shows anomalies with severity badges for a loop run
- [x] Test: run timeline shows cost spike anomaly details for a high-cost run
- [x] Test: back-navigation from timeline to fleet works
- [x] Capture run timeline screenshots (normal run + anomaly run) for user guide

### 11.4 Version Compare view tests

**Issue:** (new)

**Context:** The version compare view shows deltas between two agent versions.
Playwright must validate that selecting two versions shows non-empty compare
output and that the delta calculations are visible.

**Success looks like:** Playwright selects two versions, the compare page
renders with tool count deltas, cost deltas, and anomaly differences.

- [x] Test: version compare page renders version selector
- [x] Test: selecting two versions shows delta table with non-empty data
- [x] Test: single-version selection shows appropriate message
- [x] Test: versions with no anomalies show zero-delta display
- [x] Capture version compare screenshot (with visible deltas) for user guide

### 11.5 Anomaly Inbox view tests

**Issue:** (new)

**Context:** The anomaly inbox is the triage surface for operators. Playwright
must validate filtering by anomaly type, severity, and the drill-down to
individual anomaly details.

**Success looks like:** Playwright filters the inbox by anomaly type and
severity, verifies count changes, and navigates to anomaly detail.

- [x] Test: anomaly inbox renders with mock anomalies
- [x] Test: anomaly type filter narrows results
- [x] Test: severity filter (warning vs critical) works
- [x] Test: click anomaly navigates to run timeline with context
- [x] Test: empty inbox shows appropriate empty state
- [x] Capture anomaly inbox screenshot (with filtered anomalies) for user guide

### 11.6 Screenshot capture and user guide assembly

**Issue:** (new)

**Context:** Screenshots captured during test runs form the visual evidence for
the user guide. Rather than manually staging screenshots, the e2e test run
produces them automatically.

**Success looks like:** A single command (`make e2e`) runs all Playwright tests,
captures screenshots of each view into `docs/screenshots/`, and produces a
test report. Screenshots are named consistently and ready for the user guide.

- [x] Configure Playwright to capture screenshots on test completion
- [x] Ensure screenshots output to `docs/screenshots/` directory
- [x] Add `make e2e` target: seeds data, runs Playwright tests, captures screenshots
- [x] Verify all screenshots are non-empty and show seeded data
- [x] Add screenshot references to user guide template in `docs/`

### 11.7 Demo acceptance assertion

**Issue:** (new)

**Context:** The demo acceptance bar (defined in the WBS front matter) must be
verified programmatically before the product can move forward. This task
automates the acceptance criteria checks using Playwright assertions.

**Success looks like:** An acceptance test suite runs against the seeded stack
and asserts: one agent is easier to debug here than with logs alone, the
four standard views all show non-trivial data, and the anomaly inbox supports
the triage workflow.

- [x] Write acceptance test: normal run + loop run both visible and distinguishable
- [x] Write acceptance test: fleet view groups by agent name and version
- [x] Write acceptance test: version compare shows meaningful deltas between versions
- [x] Write acceptance test: anomaly inbox supports type and severity filtering
- [x] Run full acceptance suite and confirm all pass

**Milestone 11 Quality Gates:**
- [x] All Playwright e2e tests pass (`make e2e`)
- [x] Screenshots captured for all 4 standard views
- [x] Demo acceptance tests pass
- [x] Seed script runs cleanly from cold Postgres
- [x] Code review passed
- [x] Ruff: zero violations on seed scripts (`ruff check .`)
- [x] Mypy: strict mode passes on seed scripts (`mypy --strict .`)

---

## Milestone 12: Documentation and OSS Readiness ✅

### 12.1 Developer docs

This task turns the internal architecture into something another engineer can actually use. Docs should make the first local success path obvious and reduce hidden setup friction.

**Success looks like:** a new developer can set up the stack, instrument the demo, and understand the service layout by following docs alone.

- [x] Add local setup doc
- [x] Add architecture summary doc links
- [x] Add instrumentation quickstart
- [x] Add privacy/configuration doc

### 12.1.1 Configuration documentation

This task turns the configuration surface into something maintainable. Since the product spans SDK, analytics, API, and web, configuration drift would otherwise become a hidden source of failure.

**Success looks like:** contributors can find one clear place that lists all major config knobs and understands which service owns each one.

- [x] Document SDK configuration surface
- [x] Document analytics configuration surface
- [x] Document API configuration surface
- [x] Document web app configuration surface

### 12.2 Product docs

This task explains the product surfaces in user terms. The documentation should help people interpret what they are seeing, not just launch the software.

**Success looks like:** users can understand what each view is for, what an anomaly means, and how to interpret version comparison output.

- [x] Add "what each view means" doc
- [x] Add anomaly explanation doc
- [x] Add version compare interpretation doc

### 12.2.1 Versioning rules documentation

This task makes the compare model understandable. Since version comparison is a product feature, the project should document what counts as a version and how optional version dimensions are expected to behave.

**Success looks like:** users can read one doc and understand the required `agent_version` field, optional secondary version dimensions, and how compare cohorts are formed.

- [x] Document required `agent_version`
- [x] Document optional prompt/model/tool-schema version dimensions
- [x] Document compare cohort expectations and caveats

### 12.3 OSS readiness

This task prepares the repo to receive outside contributors. The goal is to make it obvious where help is welcome and how the monorepo is organized.

**Success looks like:** contribution paths are visible, roadmap context is easy to find, and the repo feels intentionally open rather than merely public.

- [x] Add contribution guidance for monorepo layout
- [x] Add contribution areas for adapters/detectors/views
- [x] Add issue templates if desired
- [x] Add roadmap reference to PRD/docs

### 12.4 OSS community scaffolding

This task prepares the repo to behave like a serious OSS project instead of a private build log that happens to be public. The goal is to reduce friction for first-time contributors and make the repo legible to people evaluating whether the project is real.

**Success looks like:** the repository has the minimum community and governance surfaces expected of a credible OSS project, and a new visitor can understand how to participate.

- [x] Add `CODE_OF_CONDUCT.md`
- [x] Add or refine `CONTRIBUTING.md`
- [x] Add issue templates for bug, feature request, and adapter proposal
- [x] Add pull request template
- [x] Add `SECURITY.md`

### 12.5 OSS maintainer guidance

This task creates the basic maintainer-facing operational layer. It should make it easier to accept contributions, review issues, and explain the project roadmap without improvising policy later.

**Success looks like:** the repo documents who the project is for, what contribution seams are welcomed, how roadmap work is organized, and how maintainers should evaluate incoming changes.

- [x] Add maintainer notes or `MAINTAINERS.md` if desired
- [x] Document supported contribution seams: adapters, detectors, views, docs, demo workloads
- [x] Document how semconv extension proposals should be discussed and tracked
- [x] Add a short roadmap snapshot for `v0.1.0` and `v0.2.0`

### 12.6 OSS release packaging

This task makes the first public release consumable. It covers the presentation and packaging details that often determine whether an OSS project feels usable or unfinished.

**Success looks like:** the release includes clear install/run instructions, visible screenshots or demo references, and enough packaging polish that someone can evaluate the project without reading the full codebase.

- [x] Add screenshots or animated captures for key views
- [x] Add quickstart section for running the local stack
- [x] Add SDK quickstart for instrumenting one demo agent
- [x] Add release notes draft for the first OSS release
- [x] Add known limitations section for `v0.1.0`

### 12.7 GitHub issue generation prep

This task makes the planning docs ready to turn into tracked work items. Since each WBS subsection is intended to become one issue, the repo should have enough structure to make that conversion straightforward.

**Success looks like:** maintainers can lift a subsection into a GitHub issue with minimal rewriting and consistent metadata.

- [x] Add suggested labels to issue conversion guidance
- [x] Add dependency notation guidance
- [x] Add example issue body template in docs if helpful
- [x] Identify milestone subsections that should become the first issue batch

**Milestone 12 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 13: LLM Validation on Synthetic Traces + GitHub Agent SDK Integration ✅

> **Priority:** Pre-release validation gate. Before declaring v0.1.0 release-ready,
> the LLM detector pipeline must be validated against synthetic traces, and the SDK
> integration workflow must be proven against real OSS agents.

### 13.1 LLM detector validation on 100 synthetic traces ✅

**Issue:** [#112](https://github.com/deghosal-2026/agent-exec-trace/issues/112) — **CLOSED**

**Context:** The 1M synthetic trace corpus already exists in `data/traces2/synthetic/`.
The LLM detectors (SemanticLoop, Hallucination, GoalDrift, QualityDegradation,
ConfusionPattern, EmbeddingDrift) were built in M8.7 but never validated against
a controlled sample. This task runs the rule-based pipeline first, then the LLM
pipeline with two models (4B and 9B), and compares results.

**Success looks like:** A single script generates a 3-way comparison report
showing which LLM detectors fired vs. rule-based only, per-detector counts,
model quality tradeoffs, and paper-grade telemetry.

- [x] Create `scripts/m13/run-llm-validation.sh`: orchestrates the full 3-way pipeline
- [x] Step 1: Run `analytics validate --max-traces 100` (no LLM) → output to `data/m13/no-llm/`
- [x] Step 2: Run `analytics validate --max-traces 100 --llm-sample 100` (4B model) → `data/m13/llm-Qwen3.5-4B-4bit/`
- [x] Step 3: Run `analytics validate --max-traces 100 --llm-sample 100` (9B model) → `data/m13/llm-Qwen3.5-9B-MLX-4bit/`
- [x] Step 4: Generate 3-way comparison report with per-detector diff counts
- [x] Log LLM responses + per-call telemetry (latency, tokens, cache, JSON parse, finish reason)
- [x] Fix thinking-mode issue: `enable_thinking: False` in `extra_body` (0% → 99.4-100% JSON)
- [x] Add per-call telemetry to `llm_client.py` (latency_ms, prompt_tokens, completion_tokens, finish_reason, cache_hit)
- [x] Add telemetry summary to validator output (p50/p95/p99 latency, token totals, parse rate, cache rate)
- [x] Run 25-trace pilot, save results to `docs/field-test/m13-results/25-traces/`
- [x] Run 100-trace full experiment, save results to `docs/field-test/m13-results/100-traces/`
- [x] Document findings in `docs/field-test/m13-100-trace-report.md`
- [x] Test plan: `docs/field-test/synthetic-llm-validation-plan.md`

### 13.2 GitHub agent SDK integration ✅

**Issue:** [#113](https://github.com/deghosal-2026/agent-exec-trace/issues/113) — **CLOSED**

**Context:** The v0.1.0 story depends on demonstrating that any agent can be
instrumented with the SDK in minutes. Downloading real OSS agents from GitHub,
instrumenting them, and running detectors proves the integration story and
generates real trace data.

**Success looks like:** 6 agents are identified, 3 integrated across 3 frameworks,
detectors identify meaningful anomalies, and the full pipeline is verified end-to-end.

- [x] Identify 8 target OSS agents from GitHub and agent-eval-forge field test roster
- [x] Narrow to 6 agents after framework incompatibility discovery (PydanticAI v1/v2 break)
- [x] Integrate 3 agents: Raw Python, PydanticAI v2, LangGraph
- [x] Run agents to generate 200+ traces per agent → Jaeger
- [x] Analytics worker auto-ingests traces → Postgres (after fixing `"*"` auto-discovery)
- [x] Verify anomalies visible in Anomaly Inbox, Run Timeline, Fleet UI
- [x] Document 7 pipeline bugs found and fixed during integration
- [x] Document SDK content capture fix (tool args, results, plan content, output)
- [x] Write M13.2 final report: `docs/real-agent-integration/m13-real-agent-report.md`

**Milestone 13 Quality Gates:**
- [x] Code review passed (all changes reviewed across multiple sessions)
- [x] Ruff: zero violations on changed code
- [x] Mypy: strict mode passes with zero errors (pre-existing errors only)
- [x] Tests pass: all unit/integration tests green (130 Python + 34 Playwright)
- [x] Coverage > 90%: line coverage maintained at 90%+ on changed code

---

## Milestone 14: Release Validation

### 14.1 Release criteria check

This task maps the implementation back to the PRD promises. The release should not be considered complete because components exist; it is complete when the core operator outcomes are visibly true.

**Success looks like:** each `v0.1.0` promise can be demonstrated with the local stack using the seeded scenarios and standard views.

- [ ] Confirm one real agent is easier to debug here than with logs alone
- [ ] Confirm run timeline works end-to-end
- [ ] Confirm fleet board works end-to-end
- [ ] Confirm anomaly inbox works end-to-end
- [ ] Confirm version compare works end-to-end
- [ ] Confirm the need for a separate field-test plan is documented and tracked as a required follow-on before stronger production confidence claims

### 14.1.1 Demo acceptance verification

This task explicitly checks the demo acceptance bar instead of assuming it is implied by other validations. Since demo-first is a design choice, the release should prove the demo is actually strong.

**Success looks like:** the product can be shown cleanly through the minimum demo scenarios and each standard view contributes something meaningful to that demonstration.

- [ ] Validate one normal run demo
- [ ] Validate one loop anomaly demo
- [ ] Validate one cost spike anomaly demo
- [ ] Validate one fleet grouping demo
- [ ] Validate one version compare demo

### 14.2 Final packaging

This task makes sure the repo is coherent as a releasable OSS artifact. The main concern is that docs, commands, package layout, and stack orchestration all agree with reality.

**Success looks like:** a clean clone of the repo can boot the stack, install the SDK, and follow the docs without hidden tribal knowledge.

- [ ] Confirm compose stack boots cleanly
- [ ] Confirm SDK package installs locally
- [ ] Confirm docs match actual commands and paths
- [ ] Confirm repo structure is reflected in README

### 14.3 Launch prep

This task prepares the project to be shown and evaluated as a real OSS release. It is about making the first external impression legible and honest.

**Success looks like:** screenshots or demos exist, near-term roadmap items are visible, and `v0.1.0` limitations are written down instead of hidden.

- [ ] Capture screenshots or demo artifacts
- [ ] Prepare initial issues for `v0.2.0`
- [ ] Prepare known limitations doc for `v0.1.0`

### 14.4 Post-release follow-on tracking

This task prevents `v0.1.0` from ending with undocumented next steps. It should capture the immediate follow-ons that are already known from the PRD and WBS.

**Success looks like:** the project has a visible and honest follow-on list covering field testing, additional adapters, richer anomaly work, and deeper interop tasks.

- [ ] Track separate field-test plan as follow-on work
- [ ] Track PydanticAI adapter as follow-on work
- [ ] Track memory review and policy overlay as follow-on work
- [ ] Track `v0.2.0` issue creation as a next step

**Milestone 14 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Critical Path

The critical path is:

1. demo agent
2. SDK instrumentation
3. Jaeger ingest
4. analytics normalization into Postgres
5. one loop anomaly
6. run timeline UI

Everything else should support that path, not delay it.
