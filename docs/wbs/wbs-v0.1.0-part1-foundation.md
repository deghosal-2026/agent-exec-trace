# agent-exec-trace v0.1.0 WBS — Part 1-foundation

> [← Back to WBS Table of Contents](wbs-v0.1.0.md)


# agent-exec-trace v0.1.0 Work Breakdown Structure

> Checklist-style, granular, execution-oriented breakdown for `v0.1.0`.

## Quality Gates — Required for Every Milestone

Every milestone exits through these gates. No task is complete if any gate fails.

| Gate | Requirement | Command / Tool |
|---|---|---|
| **Code review** | All changes reviewed by at least one other pair of human eyes before merge | PR review, not self-approval |
| **Comments** | Public API, complex logic, and design decisions have clear inline comments | Manual review |
| **Ruff** | Zero ruff violations on Python code | `ruff check .` |
| **Mypy strict** | Strict type checking passes with zero errors | `mypy --strict .` |
| **Tests pass** | All unit and integration tests pass | `pytest` |
| **Coverage > 90%** | Line coverage at or above 90% for new/changed code | `pytest --cov --cov-report=term` |

These gates are non-negotiable. A milestone is not ready for review if any gate is red.

At the end of each milestone below, a quality gate checklist line is repeated as a reminder. In practice, these are the same gates verified once per milestone.

## WBS to GitHub Issue Conversion Notes

Each subsection in this WBS is intended to become one GitHub issue, not one checkbox per issue.

Recommended issue body shape:

- context
- checklist
- success criteria
- dependencies
- suggested labels

Recommended label families:

- `sdk`
- `analytics`
- `api`
- `web`
- `infra`
- `docs`
- `oss`
- `field-test`

Recommended issue metadata fields:

- **Suggested labels**
- **Depends on**
- **Primary deliverable**
- **Acceptance notes**
- **Demo / screenshot needed?**

Recommended ownership buckets:

- SDK
- Analytics
- API
- Web
- Infra
- Docs / OSS

## Issue Taxonomy

Suggested issue types for later GitHub conversion:

- `adapter`
- `detector`
- `view`
- `backend`
- `interop`
- `db`
- `docs`
- `oss`
- `field-test`
- `design-followup`

## Milestone-to-Issue Mapping

| Milestone | GitHub issue bucket |
|---|---|
| Milestone 0 | repo/setup issues |
| Milestone 1 | demo workload issues |
| Milestone 2 | SDK issues |
| Milestone 3 | ingest/backend issues |
| Milestone 4 | analytics service issues |
| Milestone 5 | read-model/materialization issues |
| Milestone 6 | anomaly engine issues |
| Milestone 7 | API issues |
| Milestone 8 | web UI issues |
| Milestone 8.6 | robust detector engine issues |
| Milestone 8.7 | LLM-augmented anomaly detection issues |
| Milestone 8.8 | trace dataset ingestion/validation issues |
| Milestone 8.9 | field-test execution issues |
| Milestone 9 | non-LLM + LLM trace compatibility issues (9.1.x ✅, 9.2.x ⟳ v0.2.0) ✅ |
| Milestone 10 | local stack/demo + service-level testing issues |
| Milestone 11 | e2e Playwright testing and screenshot validation |
| Milestone 12 | docs/OSS readiness issues |
| Milestone 13 | release validation issues |

## Phased Issue Creation Strategy

To avoid creating too many tickets too early, issue creation should happen in waves.

### Wave 1

- Milestone 0
- Milestone 1
- Milestone 2
- Milestone 3

### Wave 2

- Milestone 4
- Milestone 5
- Milestone 6

### Wave 3

- Milestone 7
- Milestone 8
- Milestone 8.6
- Milestone 8.7
- Milestone 8.8
- Milestone 8.9

### Wave 4

- Milestone 9 (compatibility)
- Milestone 10 (local stack)
- Milestone 11 (testing)
- Milestone 12 (docs/OSS)
- Milestone 13 (release validation)

This keeps the tracker aligned with actual execution readiness.

## Wave 1 Issue Bodies

These are the first issues to create. Each follows the recommended issue body shape: context, checklist, success criteria, dependencies, suggested labels.

### Issue: Monorepo skeleton

**Context:** Create the physical repo layout matching the product architecture. Contributor-facing clarity must be achieved immediately.

**Dependencies:** none.

**Suggested labels:** `infra`

**Success criteria:**
- `packages/python-sdk/`, `services/api/`, `services/analytics/`, `apps/web/`, `deploy/`, `examples/`, `docs/` exist
- repo tree clearly maps to architecture document
- no future restructuring required

**Checklist:**
- [x] Create `packages/python-sdk/`
- [x] Create `services/api/`
- [x] Create `services/analytics/`
- [x] Create `apps/web/`
- [x] Create `deploy/`
- [x] Create `examples/`
- [x] Create `tests/`

---

### Issue: Root project scaffolding

**Context:** Add root-level operating surface: README layout summary, gitignore, Makefile entrypoints, compose placeholder, developer setup doc.

**Dependencies:** monorepo skeleton.

**Suggested labels:** `infra`, `docs`

**Success criteria:**
- new contributor can open repo, understand layout from root README, see how local stack will work, understand workspace governance

**Checklist:**
- [x] Add root `README.md` section for monorepo layout
- [x] Update root `.gitignore` for monorepo paths
- [x] Add root `Makefile` or task runner entrypoints
- [x] Add root `docker-compose.yml` placeholder
- [x] Add root developer setup doc

---

### Issue: Shared dev conventions

**Context:** Remove ambiguity about versions, formatting, and developer expectations. Keep setup light but lock enough that multi-service work does not drift immediately.

**Dependencies:** monorepo skeleton.

**Suggested labels:** `infra`

**Success criteria:**
- Python and web tooling are predictable
- local setup instructions match actual versions

**Checklist:**
- [x] Define Python version target
- [x] Define Node version target for web app
- [x] Define formatting/lint tools for Python
- [x] Define formatting/lint tools for web app
- [x] Add pre-commit hooks

---

### Issue: Demo agent scenario definition

**Context:** This is the reality anchor for the whole product. Define one LangGraph agent with three paths: normal, loop, high-cost.

**Dependencies:** none.

**Suggested labels:** `demo`, `design-followup`

**Success criteria:**
- documented example scenario clearly explains happy path, bad path, and expensive path
- later SDK/UI/analytics work can reference this as truth

**Checklist:**
- [x] Choose one LangGraph demo agent scenario
- [x] Document what "bad run" looks like
- [x] Document what normal run looks like
- [x] Define one seeded loop scenario
- [x] Define one seeded high-cost scenario

---

### Issue: Demo agent skeleton

**Context:** Turn the scenario into runnable code. Must be small, deterministic, and manipulable for repeatable seeded failures.

**Dependencies:** demo agent scenario definition.

**Suggested labels:** `demo`, `sdk`

**Success criteria:**
- example agent runs locally
- exercises at least one tool path
- can be forced into loop-like behavior
- carries version metadata through execution

**Checklist:**
- [x] Create example LangGraph app folder under `examples/`
- [x] Add minimal graph workflow
- [x] Add at least one tool call path
- [x] Add at least one path that can loop under seeded conditions
- [x] Add version metadata injection

---

### Issue: Demo datasets and fixtures

**Context:** Make the demo reproducible. Named fixtures for success, loop, and high-cost with expected outcomes.

**Dependencies:** demo agent skeleton.

**Suggested labels:** `demo`

**Success criteria:**
- named fixtures exist for all three cases
- contributor can run them intentionally and know what to expect

**Checklist:**
- [x] Add sample inputs for success case
- [x] Add sample inputs for loop case
- [x] Add sample inputs for high-cost case
- [x] Add expected run outcomes doc
- [x] Create scenario matrix doc mapping inputs to expected anomalies and views

---

### Issue: SDK package setup

**Context:** Create the home for the instrumentation SDK. Keep layout publishable later without over-building packaging now.

**Dependencies:** monorepo skeleton, shared dev conventions.

**Suggested labels:** `sdk`

**Success criteria:**
- SDK package installs locally
- source layout is conventional
- tests/docs can be added without moving files later

**Checklist:**
- [x] Create `packages/python-sdk/pyproject.toml`
- [x] Create package source layout
- [x] Add package README stub
- [x] Add unit test folder

---

### Issue: Base tracing primitives

**Context:** Core building blocks: config, tracer bootstrap, run context, attribute mapping, redaction support. Every adapter leans on these.

**Dependencies:** SDK package setup.

**Suggested labels:** `sdk`

**Success criteria:**
- later tasks can build adapters and spans using shared primitives
- no duplicated setup logic across adapters

**Checklist:**
- [x] Create SDK config object
- [x] Create tracer initialization helper
- [x] Create run context model
- [x] Create helper for OTel attribute mapping
- [x] Create redaction configuration model

---

### Issue: Root run instrumentation

**Context:** Every agent run must become a coherent root span with enough metadata for run views, fleet views, and version comparisons.

**Dependencies:** base tracing primitives.

**Suggested labels:** `sdk`

**Success criteria:**
- one agent run creates one stable root span
- agent identity, version, runtime context, and run ID are attached consistently

**Checklist:**
- [x] Implement root `invoke_agent` span creation
- [x] Attach agent name
- [x] Attach agent version when provided
- [x] Attach model/provider metadata when provided
- [x] Attach workload type when provided
- [x] Attach generated run ID

---

### Issue: Nested behavior spans

**Context:** Make traces behaviorally meaningful. Planning, tool execution, retrieval, and memory become first-class observability concepts.

**Dependencies:** root run instrumentation.

**Suggested labels:** `sdk`

**Success criteria:**
- a single run can express its full behavior as a navigable span tree

**Checklist:**
- [x] Implement `plan` span helper
- [x] Implement `execute_tool` span helper
- [x] Implement `retrieval` span helper
- [x] Implement memory operation span helper
- [x] Implement generic event helper

---

### Issue: Raw Python adapter

**Context:** Prove the product is not locked to one framework. Mirror the same semantic model used for LangGraph.

**Dependencies:** nested behavior spans.

**Suggested labels:** `sdk`, `adapter`

**Success criteria:**
- a plain Python agent can be instrumented with decorator and helpers
- traces look structurally consistent with LangGraph adapter output

**Checklist:**
- [x] Implement `@trace_agent` decorator
- [x] Implement nested helper context manager for tools
- [x] Implement nested helper context manager for planning
- [x] Implement nested helper context manager for retrieval
- [x] Add tests for decorator-based tracing

---

### Issue: LangGraph adapter

**Context:** First first-class framework integration. Preserve LangGraph execution shape in OTel-first model.

**Dependencies:** nested behavior spans, demo agent skeleton.

**Suggested labels:** `sdk`, `adapter`

**Success criteria:**
- demo workload emits coherent run tree with root spans and nested behavior spans
- metadata is propagated without graph-specific hacks

**Checklist:**
- [x] Define LangGraph wrapper integration surface
- [x] Map graph lifecycle to run root span
- [x] Map graph planning step to `plan` span
- [x] Map tool nodes to `execute_tool` spans
- [x] Propagate version and run metadata
- [x] Add adapter tests against demo graph

---

### Issue: Privacy defaults

**Context:** Enforce trust posture at earliest boundary. Sensitive content decisions happen in SDK before data fans out.

**Dependencies:** base tracing primitives.

**Suggested labels:** `sdk`

**Success criteria:**
- metadata-only is default
- unsafe content absent unless explicitly enabled
- opt-in capture paths configurable and documented

**Checklist:**
- [x] Set metadata-only mode as default
- [x] Ensure prompts are not captured by default
- [x] Ensure tool args are not captured by default
- [x] Ensure memory content is not captured by default
- [x] Add opt-in config for truncated or hashed content capture

---

### Issue: OTLP configuration

**Context:** Make SDK operationally useful outside local function calls. OTLP-first, backend details hidden behind config.

**Dependencies:** root run instrumentation.

**Suggested labels:** `sdk`, `backend`

**Success criteria:**
- instrumented agent can emit traces through OTLP to collector or direct backend without code changes

**Checklist:**
- [x] Add SDK exporter configuration for OTLP
- [x] Support collector endpoint configuration
- [x] Support direct Jaeger OTLP endpoint configuration
- [x] Document environment variables for exporter setup

---

### Issue: Jaeger local stack

**Context:** Primary local proof path. Jaeger is the first backend users should see in docs and demos.

**Dependencies:** OTLP configuration.

**Suggested labels:** `infra`, `backend`

**Success criteria:**
- contributor can run local stack, execute demo agent, inspect traces in Jaeger

**Checklist:**
- [x] Add Jaeger service to `docker-compose.yml`
- [x] Add collector service config
- [x] Validate SDK traces appear in Jaeger UI
- [x] Capture validation note in docs

---

### Issue: Tempo compatibility path

**Context:** Preserve long-term OTel positioning. Tempo compatibility must be real enough to prevent accidental Jaeger lock-in.

**Dependencies:** Jaeger local stack.

**Suggested labels:** `backend`, `interop`

**Success criteria:**
- same trace data viewable in Tempo with only config changes
- compatibility notes documented clearly

**Checklist:**
- [x] Add optional Tempo service config
- [x] Validate same SDK traces can be viewed in Tempo
- [x] Document compatibility notes

---

### Issue: Collector interoperability

**Context:** Ensure the product stays OTel-first. Collector path treated as product contract, not local convenience.

**Dependencies:** Jaeger local stack, Tempo compatibility path.

**Suggested labels:** `interop`, `backend`

**Success criteria:**
- SDK emits through collector cleanly
- backend switching does not require code rewrites

**Checklist:**
- [x] Validate collector-based OTLP export to Jaeger
- [x] Validate collector-based OTLP export to Tempo
- [x] Document collector config expectations
- [x] Document backend-specific caveats

## Minimum Definition of Field Test

The separate field-test plan will be written later, but the term should already mean something specific in this WBS.

A valid field test must include:

- more than one workload or scenario family
- more than one failure shape (loop, retry-heavy, cost spike, or similar)
- at least one human usefulness review of anomaly quality
- explicit review of false positives and false negatives where practical

Seeded demo validation is necessary, but it does not count as the full field test.

## Release Blockers

The following conditions should be treated as blockers for `v0.1.0` release confidence:

- trace shape is inconsistent across LangGraph and raw Python adapters
- anomaly output is too noisy to trust
- local stack is too hard to boot reliably
- run timeline is not materially better than backend-native debugging alone
- version comparison cannot produce stable, understandable deltas
- field-test plan requirement is undocumented or ignored

## Non-Functional Expectations

Even in `v0.1.0`, the implementation should satisfy a few operational expectations:

- local stack startup should be straightforward and documented
- main product views should load from materialized data rather than expensive live trace queries
- analytics processing should be idempotent for already-processed runs
- metadata-only mode must remain the default
- read-model rebuilds should be possible without changing the trace semantics

## Trace Replay and Reprocessing Requirement

Trace replay is part of both the demo story and the testing story.

`v0.1.0` should assume:

- seeded traces can be replayed intentionally
- analytics can reprocess runs when detector logic changes
- read models can be rebuilt from trace truth when necessary

This requirement is important enough to appear in milestone work below.

## Known `v0.1.0` Limitation Tracking

The project should explicitly track these likely limitations during implementation:

- no PydanticAI adapter yet
- no policy overlay view yet
- no full memory audit UI yet
- anomaly classes intentionally narrow in first release
- field testing still pending beyond seeded demo validation

## Demo Acceptance Bar

The demo-first strategy should be judged against a concrete bar.

A strong `v0.1.0` demo should show:

- one normal run visible end-to-end
- one loop anomaly detected and drill-down capable
- one cost spike anomaly detected and explainable
- one fleet view with more than one meaningful grouping row
- one version compare view with a non-trivial delta

If the product cannot demonstrate these cleanly, more implementation work is needed before claiming readiness.

## Milestone 0: Foundation and Repo Layout

### 0.1 Create monorepo skeleton

**Issue:** [#1](https://github.com/deghosal-2026/agent-exec-trace/issues/1) — **CLOSED**

This task creates the physical shape of the product. The goal is not just folders; it is to make the repo reflect the product boundaries already locked in the architecture. A contributor should be able to tell where SDK work, API work, analytics work, and UI work belong without reading a long explanation.

**Success looks like:** the repo tree clearly matches the intended architecture, empty folders are replaced with minimal keep files or scaffold files where needed, and future work can be placed without restructuring the repository again.

- [x] Create `packages/python-sdk/`
- [x] Create `services/api/`
- [x] Create `services/analytics/`
- [x] Create `apps/web/`
- [x] Create `deploy/`
- [x] Create `examples/`
- [x] Create `tests/`

### 0.2 Add root project scaffolding

**Issue:** [#2](https://github.com/deghosal-2026/agent-exec-trace/issues/2) — **CLOSED**

This task establishes the root-level operating surface for the monorepo. It should give contributors one place to start, one place to read setup instructions, and one place to run the local stack. Keep it small, but make it real enough that implementation can begin immediately after scaffolding.

**Success looks like:** a new contributor can open the repo, understand the layout from the root README, see how local orchestration will work, and understand which top-level files govern the workspace.

- [x] Add root `README.md` section for monorepo layout
- [x] Add root `.gitignore` updates for monorepo paths
- [x] Add root `Makefile` or task runner entrypoints
- [x] Add root `docker-compose.yml` placeholder for local stack
- [x] Add root developer setup doc in `docs/`

### 0.3 Choose and wire shared dev conventions

**Issue:** [#3](https://github.com/deghosal-2026/agent-exec-trace/issues/3) — **CLOSED**

This task removes ambiguity early. The point is to avoid a repo where each service invents its own versions, formatting, and developer expectations. Keep the setup light, but lock enough conventions that multi-service work does not drift immediately.

**Success looks like:** Python and web tooling are predictable, local setup instructions match the actual versions used, and the project has one obvious lint/format/test baseline.

- [x] Define Python version target
- [x] Define Node version target for web app
- [x] Define formatting/lint tools for Python
- [x] Define formatting/lint tools for web app
- [x] Add pre-commit or equivalent baseline hooks if desired

### 0.4 Record assumptions and open questions

**Issue:** [#4](https://github.com/deghosal-2026/agent-exec-trace/issues/4) — **CLOSED**

This task keeps planning uncertainty visible instead of letting it disappear into implementation chatter. It should create an explicit place where contributors can see what is assumed, what is unresolved, and what may need revisiting.

**Success looks like:** assumptions and open questions from the spec are visible, current, and easy to convert into future issues if they become blockers.

- [x] Link assumptions register from implementation-facing docs
- [x] Link open questions register from implementation-facing docs
- [x] Mark which open questions are safe to defer past `v0.1.0`

**Milestone 0 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 1: Demo-First Agent Workload

### 1.1 Create first demo agent scenario

**Issue:** [#5](https://github.com/deghosal-2026/agent-exec-trace/issues/5) — **CLOSED**

This is the reality anchor for the whole product. The first agent scenario should be simple enough to run locally but rich enough to produce meaningful traces: one normal path, one loop path, and one high-cost path. The product should be designed around this lived behavior, not around abstract ideas of how agents might behave.

**Success looks like:** there is a documented example scenario that clearly explains the happy path, the bad path, and the expensive path, and later SDK/UI/analytics work can reference this scenario as the source of truth.

- [x] Choose one LangGraph demo agent scenario
- [x] Document what "bad run" looks like for this agent
- [x] Document what normal run looks like for this agent
- [x] Define one seeded loop scenario
- [x] Define one seeded high-cost scenario

### 1.2 Implement demo agent skeleton

**Issue:** [#6](https://github.com/deghosal-2026/agent-exec-trace/issues/6) — **CLOSED**

This task turns the scenario into runnable code. It should be intentionally small, deterministic where possible, and easy to manipulate so that seeded failures are repeatable. The demo is not throwaway code; it is the first proving ground for instrumentation and views.

**Success looks like:** the example agent runs locally, exercises at least one tool path, can be forced into a loop-like behavior, and can carry version metadata through execution.

- [x] Create example LangGraph app folder under `examples/`
- [x] Add minimal graph workflow
- [x] Add at least one tool call path
- [x] Add at least one path that can loop under seeded conditions
- [x] Add version metadata injection for the example

### 1.3 Define demo datasets / fixtures

**Issue:** [#7](https://github.com/deghosal-2026/agent-exec-trace/issues/7) — **CLOSED**

This task makes the demo reproducible. The same inputs should create the same categories of runs often enough that tests, screenshots, and product validation are stable. This is also the beginning of the future demo workload pack.

**Success looks like:** there are named fixtures for success, loop, and high-cost cases, and a contributor can run them intentionally without guessing which inputs trigger which behavior.

- [x] Add sample inputs for success case
- [x] Add sample inputs for loop case
- [x] Add sample inputs for high-cost case
- [x] Add expected run outcomes doc

### 1.4 Build scenario matrix

**Issue:** [#8](https://github.com/deghosal-2026/agent-exec-trace/issues/8) — **CLOSED**

This task expands the demo from "a few example inputs" into a product validation matrix. The matrix should make it easy to see which scenarios exist, which detectors they exercise, and which views they are expected to populate.

**Success looks like:** there is a clear scenario table mapping each seeded run to its expected outcome, anomaly behavior, and UI surfaces.

- [x] Create scenario matrix doc in `docs/` or `examples/`
- [x] Map each scenario to expected run outcome
- [x] Map each scenario to expected anomaly types
- [x] Map each scenario to expected UI views that should show useful data

**Milestone 1 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 2: Python SDK Core

### 2.1 Package setup

**Issue:** [#9](https://github.com/deghosal-2026/agent-exec-trace/issues/9) — **CLOSED**

This creates the home for the instrumentation SDK. The goal is to make the package publishable later without overbuilding packaging today. Keep the layout conventional and easy to understand.

**Success looks like:** the SDK package can be installed locally, its source layout is conventional, and tests/docs can be added without moving files around later.

- [x] Create `packages/python-sdk/pyproject.toml`
- [x] Create package source layout
- [x] Add package README stub
- [x] Add unit test folder for SDK

### 2.2 Base tracing primitives

**Issue:** [#10](https://github.com/deghosal-2026/agent-exec-trace/issues/10) — **CLOSED**

This task creates the core building blocks everything else depends on: configuration, tracer bootstrap, run context, attribute mapping, and redaction support. These primitives should be small and boring because every adapter will lean on them.

**Success looks like:** later tasks can build adapters and spans using shared primitives instead of duplicating setup logic or ad hoc attribute formatting.

- [x] Create SDK config object
- [x] Create tracer initialization helper
- [x] Create run context model
- [x] Create helper for OTel attribute mapping
- [x] Create redaction configuration model

### 2.3 Root run instrumentation

**Issue:** [#11](https://github.com/deghosal-2026/agent-exec-trace/issues/11) — **CLOSED**

This is the first real product-critical SDK behavior. Every agent run must become a coherent root span with enough metadata to support run views, fleet views, and version comparisons later.

**Success looks like:** one agent run creates one stable root span with agent identity, version, runtime context, and run ID attached in a consistent way.

- [x] Implement root `invoke_agent` span creation
- [x] Attach agent name
- [x] Attach agent version when provided
- [x] Attach model/provider metadata when provided
- [x] Attach workload type when provided
- [x] Attach generated run ID

### 2.4 Nested behavior spans

**Issue:** [#12](https://github.com/deghosal-2026/agent-exec-trace/issues/12) — **CLOSED**

This task makes traces behaviorally meaningful. Without nested spans, the product collapses back into generic tracing. The helpers here should make planning, tool usage, retrieval, and memory behaviors first-class observability concepts.

**Success looks like:** a single run can express planning, tool execution, retrieval, and memory activity as a navigable span tree instead of one opaque root span.

- [x] Implement `plan` span helper
- [x] Implement `execute_tool` span helper
- [x] Implement `retrieval` span helper
- [x] Implement memory operation span helper
- [x] Implement generic event helper for warnings/notes

### 2.5 Raw Python adapter

**Issue:** [#13](https://github.com/deghosal-2026/agent-exec-trace/issues/13) — **CLOSED**

This task proves the product is not locked to one framework. The raw Python path should be easy to adopt for custom agents and should mirror the same semantic model used for LangGraph.

**Success looks like:** a plain Python agent can be instrumented with a decorator and helper contexts, and it produces traces that look structurally consistent with the framework adapter output.

- [x] Implement `@trace_agent` decorator
- [x] Implement nested helper context manager for tools
- [x] Implement nested helper context manager for planning
- [x] Implement nested helper context manager for retrieval
- [x] Add tests for decorator-based tracing

### 2.6 LangGraph adapter

**Issue:** [#14](https://github.com/deghosal-2026/agent-exec-trace/issues/14) — **CLOSED**

This is the first first-class framework integration and the most important one for `v0.1.0`. The adapter should preserve the LangGraph execution shape while expressing it in a stable OTel-first model.

**Success looks like:** the demo LangGraph workload emits a coherent run tree with root spans, nested behavior spans, and propagated metadata that later services can consume without graph-specific hacks.

- [x] Define LangGraph wrapper integration surface
- [x] Map graph lifecycle to run root span
- [x] Map graph planning step to `plan` span where possible
- [x] Map tool nodes to `execute_tool` spans
- [x] Propagate version and run metadata through execution
- [x] Add adapter tests against demo graph

### 2.7 Privacy defaults in SDK

**Issue:** [#15](https://github.com/deghosal-2026/agent-exec-trace/issues/15) — **CLOSED**

This task enforces the trust posture at the earliest possible boundary. Sensitive content decisions must happen in the SDK before data fans out into collectors, backends, databases, and UIs.

**Success looks like:** metadata-only mode is the default, unsafe content is absent unless explicitly enabled, and opt-in capture paths are configurable and documented.

- [x] Set metadata-only mode as default
- [x] Ensure prompts are not captured by default
- [x] Ensure tool args are not captured by default
- [x] Ensure memory content is not captured by default
- [x] Add opt-in config for truncated or hashed content capture

**Milestone 2 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 3: OTel Export and Jaeger Path

### 3.1 OTLP configuration

**Issue:** [#16](https://github.com/deghosal-2026/agent-exec-trace/issues/16) — **CLOSED**

This task makes the SDK operationally useful outside local function calls. The exporter path should stay standard and boring: OTLP first, backend-specific details hidden behind configuration.

**Success looks like:** an instrumented agent can emit traces through OTLP to either a collector or direct backend endpoint without code changes in the agent itself.

- [x] Add SDK exporter configuration for OTLP
- [x] Support collector endpoint configuration
- [x] Support direct Jaeger OTLP endpoint configuration
- [x] Document environment variables for exporter setup

### 3.2 Jaeger local stack

**Issue:** [#17](https://github.com/deghosal-2026/agent-exec-trace/issues/17) — **CLOSED**

This task creates the primary local proof path for `v0.1.0`. Jaeger is the first backend users should see in docs and local demos, so this setup must feel polished and dependable.

**Success looks like:** a contributor can run the local stack, execute the demo agent, and visibly inspect the generated traces in Jaeger without manual backend debugging.

- [x] Add Jaeger service to `docker-compose.yml`
- [x] Add collector service config
- [x] Validate SDK traces appear in Jaeger UI
- [x] Capture screenshot or validation note in docs

### 3.3 Tempo compatibility path

**Issue:** [#18](https://github.com/deghosal-2026/agent-exec-trace/issues/18) — **CLOSED**

This task preserves the long-term OTel positioning of the product. Even though Jaeger is first, Tempo compatibility must be real enough that the architecture does not become accidentally Jaeger-shaped.

**Success looks like:** the same trace data can be viewed in Tempo with only configuration changes, and compatibility notes are documented clearly.

- [x] Add optional Tempo service config
- [x] Validate same SDK traces can be viewed in Tempo
- [x] Document compatibility notes

### 3.4 Collector interoperability checks

**Issue:** [#19](https://github.com/deghosal-2026/agent-exec-trace/issues/19) — **CLOSED**

This task ensures the product stays OTel-first rather than backend-first. The collector path should be treated as a product contract, not just a local convenience layer.

**Success looks like:** the SDK can emit through the collector path cleanly, backend switching does not require code rewrites, and the collector setup is documented as a first-class integration path.

- [x] Add collector service to docker-compose
- [x] Add collector config forwarding to Jaeger
- [x] Validate collector-based OTLP export to Jaeger
- [x] Validate collector-based OTLP export to Tempo
- [x] Document collector config expectations
- [x] Document any backend-specific caveats discovered in testing

**Milestone 3 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

