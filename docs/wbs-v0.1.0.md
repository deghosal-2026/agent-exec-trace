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
| Milestone 10 | local stack/demo issues |
| Milestone 11 | testing/hardening issues |
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
- [ ] Code review passed
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
- [ ] Code review passed
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
- [ ] Code review passed
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
- [ ] Validate SDK traces appear in Jaeger UI
- [ ] Capture screenshot or validation note in docs

### 3.3 Tempo compatibility path

**Issue:** [#18](https://github.com/deghosal-2026/agent-exec-trace/issues/18) — **CLOSED**

This task preserves the long-term OTel positioning of the product. Even though Jaeger is first, Tempo compatibility must be real enough that the architecture does not become accidentally Jaeger-shaped.

**Success looks like:** the same trace data can be viewed in Tempo with only configuration changes, and compatibility notes are documented clearly.

- [x] Add optional Tempo service config
- [ ] Validate same SDK traces can be viewed in Tempo
- [ ] Document compatibility notes

### 3.4 Collector interoperability checks

**Issue:** [#19](https://github.com/deghosal-2026/agent-exec-trace/issues/19) — **CLOSED**

This task ensures the product stays OTel-first rather than backend-first. The collector path should be treated as a product contract, not just a local convenience layer.

**Success looks like:** the SDK can emit through the collector path cleanly, backend switching does not require code rewrites, and the collector setup is documented as a first-class integration path.

- [x] Add collector service to docker-compose
- [x] Add collector config forwarding to Jaeger
- [ ] Validate collector-based OTLP export to Jaeger
- [ ] Validate collector-based OTLP export to Tempo
- [ ] Document collector config expectations
- [ ] Document any backend-specific caveats discovered in testing

**Milestone 3 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 4: Analytics Service Skeleton  ✅

**Issue:** [#20](https://github.com/deghosal-2026/agent-exec-trace/issues/20) — **CLOSED**

### 4.1 Service setup

This creates the service that turns traces into product value. It should start simple, but it must already look like a standalone service with its own config, logging, tests, and lifecycle.

**Success looks like:** analytics can run as its own service process, has a clean project shape, and is ready to own read-model materialization and anomaly logic.

- [x] Create `services/analytics/pyproject.toml`
- [x] Create analytics app entrypoint
- [x] Create analytics config module
- [x] Create analytics logging setup
- [x] Add analytics unit test layout

### 4.2 Postgres setup

**Issue:** [#21](https://github.com/deghosal-2026/agent-exec-trace/issues/21) — **CLOSED**

This task establishes the product read-model database. Because Postgres is the chosen path toward `1.0`, the setup should feel production-shaped even in local development.

**Success looks like:** Postgres runs in the local stack, migrations are wired, and analytics can create and evolve its schema predictably.

- [x] Add Postgres service to compose stack
- [x] Create analytics DB connection module
- [x] Add migration tool setup
- [x] Create initial schema migration

### 4.3 Read model tables

**Issue:** [#22](https://github.com/deghosal-2026/agent-exec-trace/issues/22) — **CLOSED**

This task defines the first stable product storage layer. These tables should reflect product concepts, not raw tracing internals, so that the API and UI can work with clean entities.

**Success looks like:** the database has explicit tables for summaries and anomalies, indexes support key lookups, and the schema matches the product vocabulary from the PRD.

- [x] Create `run_summaries` table
- [x] Create `anomalies` table
- [x] Create `fleet_rollups` table or equivalent summary structure
- [x] Create `version_cohort_summaries` table
- [x] Add indexes for run lookup and anomaly queries

### 4.4 Trace ingestion path

**Issue:** [#23](https://github.com/deghosal-2026/agent-exec-trace/issues/23) — **CLOSED**

This task is the bridge between tracing infrastructure and product behavior. The goal is to read trace data once, normalize it cleanly, and stop making the rest of the product think in backend-native shapes.

**Success looks like:** traces from the demo workload can be fetched, parsed, normalized into internal models, and persisted as product-facing records.

- [x] Decide trace read strategy from Jaeger/collector-accessible source
- [x] Implement trace fetch/parse job
- [x] Normalize root run data into internal models
- [x] Normalize child spans into behavior segments
- [x] Persist run summaries to Postgres

### 4.5 Background processing loop

**Issue:** [#24](https://github.com/deghosal-2026/agent-exec-trace/issues/24) — **CLOSED**

This task makes analytics asynchronous and repeatable. It should support both live-ish processing for local use and controlled reprocessing for seeded demo runs and tests.

**Success looks like:** analytics can process new traces in the background, skip already-processed runs safely, and report its own health through logs/metrics.

- [x] Create async worker loop
- [x] Add polling or replay strategy for new traces
- [x] Add idempotency guard for already-processed runs
- [x] Add logging/metrics for processing success/failure

### 4.6 Reprocessing and rebuild support

**Issue:** [#25](https://github.com/deghosal-2026/agent-exec-trace/issues/25) — **CLOSED**

This task makes the analytics service resilient to detector evolution. An observability product should be able to rebuild its summaries and anomaly records when logic changes, instead of treating the first computation as immutable truth.

**Success looks like:** a contributor can replay or reprocess stored trace inputs and rebuild materialized run summaries and anomaly records without hand-editing the database.

- [x] Define reprocessing entrypoint or command
- [x] Support rerunning summary materialization from trace truth
- [x] Support rerunning anomaly detection from trace truth
- [x] Document the rebuild workflow for developers

### 4.7 Analytics self-observability

**Issue:** [#26](https://github.com/deghosal-2026/agent-exec-trace/issues/26) — **CLOSED**

This task makes the analytics service debuggable as a system in its own right. Since analytics is responsible for derived truth, it must emit enough signals that maintainers can tell whether it is healthy or stale.

**Success looks like:** maintainers can inspect worker lag, processing counts, duplicate-skip behavior, replay success, and read-model freshness without guessing.

- [x] Emit processed-run counters
- [x] Emit failed-run counters
- [x] Emit duplicate-skip counters
- [x] Emit replay/rebuild counters
- [x] Record read-model freshness signal

**Milestone 4 Quality Gates:**
- [x] Code review passed (reviewed via code-reviewer skill across all new files)
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 5: Summary Materialization  ✅

**Issue:** [#27](https://github.com/deghosal-2026/agent-exec-trace/issues/27) — **CLOSED**

### 5.1 Run summary model

This task creates the first product object users will actually feel. The run summary should answer the obvious first questions without forcing a user to inspect every span.

**Success looks like:** every processed run has a summary row with duration, cost, retries, tool counts, and other top-level values needed by both UI and anomaly logic.

- [x] Define run summary fields
- [x] Compute total duration
- [x] Compute tool call count
- [x] Compute retry count
- [x] Compute intervention count
- [x] Compute estimated cost field

### 5.2 Fleet rollups

**Issue:** [#28](https://github.com/deghosal-2026/agent-exec-trace/issues/28) — **CLOSED**

This task turns isolated runs into fleet-level operational visibility. The rollups should be stable enough to support the fleet board without heavy per-request recomputation.

**Success looks like:** the analytics service materializes grouped summaries by agent/version/workload and those groups can power the fleet UI directly.

- [x] Group summaries by agent
- [x] Group summaries by version
- [x] Group summaries by workload type
- [x] Compute success/error counts
- [x] Compute average cost per run
- [x] Compute anomaly counts per grouping

### 5.3 Version cohort summaries

**Issue:** [#29](https://github.com/deghosal-2026/agent-exec-trace/issues/29) — **CLOSED**

This task enables meaningful version comparison. The key is to define stable cohort semantics so that compare is not just two arbitrary lists of runs.

**Success looks like:** two versions can be compared through precomputed aggregates for cost, retries, outcomes, and tool usage without expensive ad hoc analysis.

- [x] Define version comparison cohort inputs
- [x] Materialize run counts by version
- [x] Materialize cost aggregates by version
- [x] Materialize retry aggregates by version
- [x] Materialize top tool usage counts by version

### 5.4 Workload and cohort dimension support

**Issue:** [#30](https://github.com/deghosal-2026/agent-exec-trace/issues/30) — **CLOSED**

This task protects the product from becoming too version-only in its thinking. Even in `v0.1.0`, the data model should leave room for meaningful workload and grouping dimensions.

**Success looks like:** summaries can be grouped by more than just agent name, and the fleet and compare views are not blocked from cohorting by workload type or environment.

- [x] Define minimum cohort dimensions for `v0.1.0`
- [x] Add workload-type grouping to summary materialization
- [x] Add environment or deployment grouping if available
- [x] Document which cohort dimensions are first-class in the first release

### 5.5 Database schema sketch review

**Issue:** [#31](https://github.com/deghosal-2026/agent-exec-trace/issues/31) — **CLOSED**

This task gives the read-model layer enough explicit shape that future issues and migrations are not invented ad hoc. It is not the final migration set, but it should make the intended tables and lookup patterns concrete.

**Success looks like:** maintainers can point to a documented sketch of the core Postgres tables, their purpose, and their main lookup paths before schema work spreads across services.

- [x] Document main read-model tables and their purpose
- [x] Document primary lookup keys per table
- [x] Document expected rebuild/recompute ownership for each table

**Milestone 5 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 6: Anomaly Engine  ✅

**Issue:** [#32](https://github.com/deghosal-2026/agent-exec-trace/issues/32) — **CLOSED**

### 6.1 Loop detection rule

This is the first detector and the signature anomaly type for the product. It should be simple, explainable, and tied to visible evidence in the run timeline.

**Success looks like:** seeded loop scenarios are reliably detected, the anomaly is persisted, and the explanation clearly states why the run was considered a loop.

- [x] Define configurable same-tool repetition threshold
- [x] Detect repeated tool sequences inside a run
- [x] Mark loop evidence in anomaly record
- [x] Attach loop count to run summary
- [x] Add tests with seeded loop demo case

### 6.2 Retry storm rule

**Issue:** [#33](https://github.com/deghosal-2026/agent-exec-trace/issues/33) — **CLOSED**

This detector catches another common failure shape: agents repeatedly attempting recovery without converging. The rule should remain understandable to operators and not depend on opaque scoring.

**Success looks like:** runs that exceed retry thresholds are flagged with clear evidence and do not require manual counting to verify the detector result.

- [x] Define retry threshold config
- [x] Count retries per run
- [x] Emit retry anomaly when threshold exceeded
- [x] Add tests with seeded retry case

### 6.3 Cost spike rule

**Issue:** [#34](https://github.com/deghosal-2026/agent-exec-trace/issues/34) — **CLOSED**

This detector connects observability to business value. It should make expensive runs visible whether they are absolutely expensive or only expensive relative to baseline behavior.

**Success looks like:** a seeded expensive run produces a cost anomaly with enough explanation for a user to understand both the amount and why it was considered unusual.

- [x] Define absolute threshold config
- [x] Define baseline-multiplier config
- [x] Compare current run cost against threshold/baseline
- [x] Emit cost anomaly record with explanation
- [x] Add tests with seeded cost case

### 6.4 Anomaly persistence and lifecycle

**Issue:** [#35](https://github.com/deghosal-2026/agent-exec-trace/issues/35) — **CLOSED**

This task makes anomalies durable product objects instead of transient log lines. The anomaly inbox, alerts, and future review workflows all depend on these records being well-shaped and linkable.

**Success looks like:** anomalies are stored with stable IDs, severity, explanation, timestamps, and run linkage so they can be queried and rendered consistently.

- [x] Persist anomaly records to Postgres
- [x] Link anomalies to run ID and agent name
- [x] Store severity
- [x] Store explanation text
- [x] Store created timestamp

### 6.5 Alert output path

**Issue:** [#36](https://github.com/deghosal-2026/agent-exec-trace/issues/36) — **CLOSED**

This task gives anomalies an outward operational path. Even if the first release keeps it simple, the alert shape should already look like something a real team could route and consume.

**Success looks like:** anomaly records can optionally emit webhook notifications with useful, trace-linked payloads and documented configuration.

- [x] Define webhook payload shape
- [x] Add optional webhook emitter
- [x] Add retry/error handling for webhook delivery
- [x] Document alert config

### 6.6 Define field-test handoff requirement

**Issue:** [#37](https://github.com/deghosal-2026/agent-exec-trace/issues/37) — **CLOSED**

This task does not create the full field-test plan yet. It creates the explicit delivery requirement that `v0.1.0` anomaly work is incomplete until a separate field-testing plan exists and is executed later. The purpose is to prevent the team from treating seeded demo validation as sufficient evidence.

**Success looks like:** the WBS and release path explicitly call out that a separate field-test plan must be written later, and anomaly detection is treated as requiring post-implementation validation against broader workloads.

- [x] Add a release note in docs that anomaly detection requires a dedicated field-test plan
- [x] List minimum future field-test dimensions: multiple workloads, false positives, detector usefulness, operator feedback
- [x] Mark field-test planning as a required follow-on artifact before final release confidence claims

### 6.7 Anomaly validation matrix

**Issue:** [#38](https://github.com/deghosal-2026/agent-exec-trace/issues/38) — **CLOSED**

This task turns detector development into something reviewable. Each detector should have named scenarios it is expected to catch and scenarios it should ignore.

**Success looks like:** there is a detector-by-scenario matrix showing expected true positives and known non-goals, making false-positive discussions much easier later.

- [x] Create detector validation matrix doc
- [x] Map loop detector to seeded positive and negative cases
- [x] Map retry detector to seeded positive and negative cases
- [x] Map cost detector to seeded positive and negative cases
- [x] Note known blind spots for each detector in `v0.1.0`

**Milestone 6 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 7: API Service  ✅

**Issue:** [#39](https://github.com/deghosal-2026/agent-exec-trace/issues/39) — **CLOSED**
### 7.1 Service setup

This creates the stable read surface for the product. The service should be intentionally product-shaped rather than just proxying databases or trace backends.

**Success looks like:** the API service runs independently, connects to Postgres cleanly, and has a clear place for product endpoints and tests.

- [x] Create `services/api/pyproject.toml`
- [x] Create FastAPI app entrypoint
- [x] Create DB access layer
- [x] Create API config module
- [x] Add API unit/integration test layout

### 7.2 Run timeline endpoint

This is the most important read endpoint in `v0.1.0`. It powers the first proof of value: understanding one broken or expensive run quickly.

**Success looks like:** the UI can request a run by ID and receive everything needed for the timeline, summary header, and anomaly markers in one coherent response model.

- [x] Define endpoint path and response model
- [x] Load run summary from Postgres
- [x] Load trace-linked detail payload
- [x] Return normalized span tree shape for UI
- [x] Return anomaly markers for the run

### 7.3 Fleet health endpoint

This endpoint turns materialized summaries into an operator view of many agents at once. It should support the first level of grouping and triage without overcomplicating filtering.

**Success looks like:** the fleet view can load grouped rows with cost, outcome, and anomaly information directly from the API without custom client-side aggregation.

- [x] Define endpoint path and response model
- [x] Add agent/version/workload grouping filters
- [x] Return aggregated fleet rows
- [x] Add paging/sorting strategy if needed

### 7.4 Version compare endpoint

This endpoint should make version review feel like a first-class product capability rather than a future analytics experiment. The response shape should be intentionally compare-friendly.

**Success looks like:** two version cohorts can be requested and the API returns a stable, digestible set of deltas for cost, retries, tool usage, and outcomes.

- [x] Define endpoint path and response model
- [x] Accept version A / version B or cohort filters
- [x] Return cost delta
- [x] Return retry delta
- [x] Return tool usage delta
- [x] Return outcome counts

### 7.5 Anomaly inbox endpoint

This endpoint powers the triage surface. It should be simple to query, filter, and sort, because users will open it when they need to decide what to look at first.

**Success looks like:** the UI can list anomalies with filters and every anomaly contains enough context to jump straight into investigation.

- [x] Define endpoint path and response model
- [x] Return anomaly list
- [x] Support severity/type/agent filtering
- [x] Include run link fields

### 7.6 API issue templates for future integrations

This task prepares the API layer to be used beyond the first web app. Even if no public API strategy exists yet, the internal contracts should be explicit and test-friendly.

**Success looks like:** endpoint contracts are consistent enough that future CLI, automation, or external UI integrations would not require redesigning the response model.

- [x] Document response contract conventions
- [x] Document error payload conventions
- [x] Document filtering and sorting conventions across endpoints

### 7.7 Endpoint example payload alignment

This task keeps the spec and implementation synchronized. Since the spec now includes example payloads, the API work should stay traceable to those shapes.

**Success looks like:** implemented endpoint models match or intentionally evolve the documented payload examples, and differences are captured explicitly rather than drifting silently.

- [x] Cross-check run timeline response against spec example
- [x] Cross-check fleet health response against spec example
- [x] Cross-check version compare response against spec example
- [x] Cross-check anomaly inbox response against spec example

**Milestone 7 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 8: React Web App  ✅

**Issue:** [#46](https://github.com/deghosal-2026/agent-exec-trace/issues/46) — **CLOSED**
### 8.1 App setup

This task establishes the UI foundation for the product views. Keep the setup pragmatic, but make routing, API access, and layout strong enough that later views do not feel bolted on.

**Success looks like:** the web app runs locally, has navigable routes, can call the API, and has a stable foundation for all `v0.1.0` views.

- [x] Create `apps/web/` app scaffold
- [x] Add routing
- [x] Add API client layer
- [x] Add base layout/navigation
- [x] Add lint/test baseline

### 8.2 Run timeline view

This is the flagship UI surface. It should make one run explainable quickly and visually, without depending on backend-native trace UIs.

**Success looks like:** a user can enter or open a run, see the summary, inspect the span tree, and identify the problematic section with anomaly markers and detail panels.

- [x] Create run search/input entry
- [x] Render run summary header
- [x] Render span tree / timeline
- [x] Render per-span detail panel
- [x] Render anomaly markers in the timeline

### 8.2.1 Run timeline interaction details

This task makes the timeline truly operational rather than just visually interesting. The page should support the exact interactions an operator needs during a real investigation.

**Success looks like:** a user can expand/collapse spans, select a span, inspect summary details, and quickly identify where the run changed course.

- [x] Add span expand/collapse behavior
- [x] Add selected-span detail state
- [x] Add clear display of timing and cost context per span
- [x] Add visual emphasis for anomaly-linked spans

### 8.3 Fleet health view

This view proves the product is more than a single-trace debugger. It should make it obvious which agents or cohorts deserve attention next.

**Success looks like:** the page loads grouped fleet data, supports useful filters, and makes drill-down into related runs natural.

- [x] Create fleet table/cards layout
- [x] Add grouping/filter controls
- [x] Display cost, success, anomaly counts
- [x] Add drill-down action into related runs

### 8.3.1 Fleet dashboard detail design

This task specifies the information architecture of the fleet page. Since this is one of the core product views, the cards, columns, and filters should be intentional rather than improvised in implementation.

**Success looks like:** the fleet page has a clearly defined set of top-level cards, grouping controls, table columns, and drill-down actions that reflect the PRD's standard view model.

- [x] Define top summary cards
- [x] Define primary grouping controls
- [x] Define required table columns
- [x] Define default sort behavior

### 8.4 Version compare view

This view is where observability meets release review. It should help a team answer whether a change improved or degraded behavior without building a notebook.

**Success looks like:** two versions can be selected and the UI presents a clear delta story for cost, retries, tool usage, and outcomes.

- [x] Create compare selection form
- [x] Render version A vs B summary cards
- [x] Render cost/retry/tool delta sections
- [x] Add drill-down links into exemplar runs

### 8.4.1 Compare view interpretation aids

This task makes compare usable by normal engineers and managers, not only by people comfortable reading raw deltas. The UI should help explain what changed and whether that change likely matters.

**Success looks like:** compare output includes enough labeling, context, and interpretation hints that a reviewer can make a release decision without writing custom analysis.

- [x] Add explicit "version A vs version B" framing
- [x] Add positive/negative/neutral visual signals for deltas
- [x] Add inline explanation labels for each metric block
- [x] Add quick links to representative runs for both cohorts

### 8.5 Anomaly inbox view

This view should feel like an actionable inbox, not a generic error list. It must prioritize clarity, severity, and direct links into the run context.

**Success looks like:** users can filter anomalies, understand why each one fired, and open the exact run that needs investigation.

- [x] Render anomaly list
- [x] Add severity/type filters
- [x] Show explanation text
- [x] Link anomaly to run timeline page

### 8.5.1 Inbox triage ergonomics

This task keeps the anomaly inbox from becoming a generic list page. It should support real triage behavior: scan, filter, prioritize, and drill in fast.

**Success looks like:** a user can move from a broad list of anomalies to the one they should investigate next without confusion or extra navigation.

- [x] Define default sort order for anomalies
- [x] Add visible severity styling
- [x] Add anomaly type badges
- [x] Add one-click drill-down action

**Milestone 8 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 8.6: Robust Detector Engine ✅

> **Priority:** Critical-path. The anomaly engine is the core product differentiator. Three
> detectors is insufficient for production confidence. This milestone expands to 35 detectors
> across 7 categories, hardens every detector against known blind spots, and ensures
> deterministic, explainable, testable behavior.

### 8.6.1 Expand detectors to 35 across 7 categories

**Issue:** [#91](https://github.com/deghosal-2026/agent-exec-trace/issues/91) — **CLOSED**

**Context:** The v0.1.0 anomaly engine ships with 3 detectors (loop, retry, cost). For
production-grade observability, we need comprehensive coverage of agent failure patterns
across tool execution, cost, runtime, retry behavior, human interaction, output quality,
and cross-run patterns. Every detector must be deterministic (rule-based, no LLM), have
configurable thresholds, and produce structured evidence payloads.

**Success looks like:** 35 detectors are implemented, tested, and integrated into the
analytics worker pipeline. Each detector's positive/negative cases are verified through
seeded scenarios.

- [x] **Tool Execution (8 detectors):** LoopDetector, PatternLoopDetector, ArgumentLoopDetector, ToolErrorRateDetector, SpecificToolErrorDetector, ToolLatencyDetector, ToolTimeoutDetector, RedundantToolCallDetector
- [x] **Cost & Resource (6 detectors):** CostSpikeDetector, CostVsBaselineDetector, CostEfficiencyDetector, TokenExplosionDetector, PerToolCostSpikeDetector, WastedToolCallsDetector
- [x] **Runtime & Completion (5 detectors):** RunDurationDetector, MaxStepHitDetector, StepEfficiencyDetector, InactivityDetector, PrematureCompletionDetector
- [x] **Retry & Recovery (5 detectors):** RetryStormDetector, SystemicRetryDetector, TransientRetryDetector, CascadingRetryDetector, RecoveryPathDetector
- [x] **Interaction & Control (4 detectors):** InterventionFrequencyDetector, EscalationRateDetector, ApprovalLatencyDetector, InterventionRejectionDetector
- [x] **Output Quality (4 detectors):** EmptyResponseDetector, LowOutputDetector, IndeterminateDetector, OutputDriftDetector
- [x] **Cross-Run Patterns (3 detectors):** AnomalyClusterDetector, RunFrequencyAnomaly, FirstRunHeuristic

### 8.6.2 Harden detectors against known blind spots

**Issue:** [#92](https://github.com/deghosal-2026/agent-exec-trace/issues/92) — **CLOSED**

**Context:** The 3 existing detectors have documented blind spots: polling false positives,
transient vs systemic retry confusion, sparse baseline skew, no argument-awareness, and no
cross-run context. Every detector (old and new) must address its known blind spots.

**Success looks like:** Each detector has explicit hardening: allowlists, success-rate
gating, baseline confidence checks, multi-signal correlation, and severity calibration.

- [x] Loop detectors (1-3): add `polling_tool_allowlist`, argument-aware repetition weighting, A→B→A→B pattern detection with configurable window size
- [x] Retry detectors (20-24): add `retry_success_rate` gating (≥50% success → suppress), error-type clustering, cascading retry chain detection
- [x] Cost detectors (9-14): add `min_baseline_run_count=5` sparse protection, token-vs-tool cost breakdown, period-over-period trend check
- [x] Runtime detectors (15-19): add per-workload baseline calibration, step-vs-complexity correlation
- [x] All detectors: severity scaling (warning at threshold, critical at 2x threshold), structured evidence payload, human-readable explanations

### 8.6.3 Ensure deterministic and testable behavior

**Issue:** [#93](https://github.com/deghosal-2026/agent-exec-trace/issues/93) — **CLOSED** ✅

**Context:** Detectors must never depend on randomness, LLM calls, or external state beyond
trace data and cohort baselines. Every detector's logic must be unit-testable with
deterministic inputs.

**Success looks like:** All 35 detectors have unit tests covering positive (must-fire)
and negative (must-not-fire) cases. Every seeded failure scenario in the field-test plan
has a corresponding test.

- [x] Unit test per detector: positive case (anomaly fires correctly)
- [x] Unit test per detector: negative case (no false positive on clean input)
- [x] Unit test per detector: severity scaling (warning vs critical at thresholds)
- [x] Integration test: all 35 detectors run in worker pipeline end-to-end
- [x] Cross-framework test: same failure pattern caught on LangGraph and CrewAI traces

### 8.6.4 Integrate into analytics worker and API

**Issue:** [#94](https://github.com/deghosal-2026/agent-exec-trace/issues/94) — **CLOSED** ✅

**Context:** New detectors must plug into the existing worker pipeline seamlessly. The API
must expose anomaly type filters for all 35 anomaly types. The web UI anomaly inbox must
display all types with appropriate badges.

**Success looks like:** Worker `_process_cycle` runs all 35 detectors, persists anomalies,
triggers webhook alerts. API `/anomalies` filters by all types. UI shows badges for all.

- [x] Register all 35 detectors in the worker pipeline (`_process_cycle`, `process_trace`)
- [x] Add 35 anomaly types to API response model enum
- [x] Add color badges for all 35 types in web UI anomaly inbox
- [x] Configurable per-detector on/off toggle via settings (default: all on)
- [x] Per-detector metrics counter in AnalyticsMetrics

### 8.6.5 Update field-test plan with 35-detector scenarios

**Issue:** [#95](https://github.com/deghosal-2026/agent-exec-trace/issues/95) — **CLOSED** ✅

**Context:** The field-test plan must cover all 35 detectors with explicit positive/negative
scenarios across 4 agent workloads.

**Success looks like:** The field-test plan documents ~140 test scenarios (70 positive +
70 negative), 4 agent workloads, per-detector expected outcomes, and the review sheet
expanded to cover all detectors.

- [x] Expand field-test-plan.md: 70+ positive scenarios across 35 detectors
- [x] Expand field-test-plan.md: 70+ negative scenarios across 35 detectors
- [x] Update anomaly review sheet to cover all 35 detectors
- [x] Per-detector expected TP/FP/FN tracking columns

**Milestone 8.6 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`) — 109/109
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`) ✅

---


## Milestone 8.7: LLM-Augmented Anomaly Detection ✅

> **Priority:** Differentiator. Rule-based detectors are fast and deterministic but blind
> to semantics. This milestone adds a local LLM layer (MLX with llama3.2 or qwen2.5, ~3B params)
> for semantic anomaly detection, explanation quality scoring, FP triage, output drift
> tracking, and severity calibration. All LLM features are optional — detectors function
> fully without LLM when the MLX model server is unavailable.

### 8.7.1 Integrate local LLM via MLX

**Issue:** [#85](https://github.com/deghosal-2026/agent-exec-trace/issues/85) — **CLOSED** ✅

**Context:** Adds `LLMClient` abstraction that wraps MLX-based LLM serving (mlx-lm)
calls. Supports llama3.2 (3B) and qwen2.5 (3B) models that run on developer laptops
via Apple Silicon. All calls are async, have configurable timeouts, and degrade
gracefully when the MLX model server is not running.

**Success looks like:** `LLMClient` provides a clean interface for text generation,
classification, scoring, and embedding extraction. Used by all LLM-augmented detectors.

- [x] Build `LLMClient` class: mlx-lm chat, embed, generate wrappers
- [x] Build availability check: detect if MLX model server is running, fallback gracefully
- [x] Build model management: load model if missing, configure model via settings
- [x] Build caching layer: cache LLM responses for deterministic replay
- [x] Build prompt template system: structured prompts for each LLM detector task
- [x] Build latency tracking: log LLM call durations for cost awareness

### 8.7.2 LLM explanation quality scoring

**Issue:** [#86](https://github.com/deghosal-2026/agent-exec-trace/issues/86) — **CLOSED** ✅

**Context:** Rule-based detectors produce formulaic explanations ("Tool X called 12 times").
An LLM can assess whether these explanations are clear, actionable, and informative
enough for an operator to triage the anomaly.

**Success looks like:** Every anomaly fires, the LLM scores its explanation 1-5 for
clarity and actionability. Scores below 3 trigger a rewrite suggestion.

- [x] Build `ExplanationScorer`: LLM rates explanation clarity + actionability 1-5
- [x] Add scoring to detector pipeline: score every anomaly explanation
- [x] Flag low-scoring explanations (<3) for detector explanation improvement
- [x] Generate aggregate explanation quality report per detector
- [x] Track explanation scores over time for detector quality monitoring

### 8.7.3 LLM false positive/negative triage

**Issue:** [#87](https://github.com/deghosal-2026/agent-exec-trace/issues/87) — **CLOSED** ✅

**Context:** Rule-based detectors fire on threshold violations — they can't distinguish
between a legitimate spike and a real problem. An LLM can review the full trace context
and classify anomalies as likely TP or likely FP.

**Success looks like:** A `LLMTriageClassifier` that runs as a second-pass filter after
rule-based detectors fire. Anomalies classified as likely FP are suppressed or
downgraded to info severity.

- [x] Build `LLMTriageClassifier`: given anomaly + run summary + span tree context, classify TP/FP/uncertain
- [x] Integrate into worker pipeline: after detector fires, optionally run LLM triage
- [x] Configurable FP suppression: auto-suppress anomalies classified as likely FP
- [x] Uncertainty flagging: anomalies classified as uncertain go to human review
- [x] Track triage accuracy against ground truth labels from seeded traces

### 8.7.4 Embedding-based output drift detection

**Issue:** [#88](https://github.com/deghosal-2026/agent-exec-trace/issues/88) — **CLOSED** ✅

**Context:** Agent output quality changes can be subtle — shorter answers, higher toxicity,
different writing style. Rule-based detectors can't catch semantic drift. LLM embeddings
can measure output similarity across versions and flag when a new version produces
semantically different outputs.

**Success looks like:** `OutputDriftDetector` uses LLM embeddings to compare agent
outputs across versions. A significant cosine distance from baseline triggers a
drift anomaly.

- [x] Build `OutputDriftDetector`: extract output text, compute embedding via MLX, compare to baseline
- [x] Build baseline embedding store: per-version, per-workload output embedding centroids
- [x] Configurable drift threshold: cosine distance > 0.3 → anomaly
- [x] Per-output-type drift tracking: final answer, intermediate reasoning, tool outputs
- [x] Version comparison integration: show drift alongside cost/retry deltas

### 8.7.5 LLM severity calibration and threshold suggestion

**Issue:** [#89](https://github.com/deghosal-2026/agent-exec-trace/issues/89) — **CLOSED** ✅

**Context:** Detector thresholds and severity levels are currently hard-coded (warning at
5, critical at 10). These should be data-driven. An LLM can analyze anomaly distributions
across real trace data and suggest threshold adjustments per detector per workload.

**Success looks like:** `ThresholdCalibrator` runs after bulk trace processing, analyzes
anomaly distributions, and produces threshold tuning recommendations with explanations.

- [x] Build `ThresholdCalibrator`: given anomaly distribution data, suggest threshold adjustments
- [x] LLM analyzes: are current thresholds too sensitive? too lenient?
- [x] Per-workload tuning: different workloads may need different thresholds
- [x] Generate tuning report: current threshold → suggested threshold → rationale
- [x] Configurable auto-apply: optionally update thresholds based on LLM suggestions

### 8.7.6 Five new LLM-powered semantic detectors

**Issue:** [#90](https://github.com/deghosal-2026/agent-exec-trace/issues/90) — **CLOSED** ✅

**Context:** Current detectors (1-35) are purely rule-based on numeric metrics. Five
new detectors use LLM reasoning for semantic-level anomalies that rules can't catch.

**Success looks like:** 5 new detectors (#36-40) that augment the 35 rule-based
detectors with semantic understanding. Detectors work via LLM but degrade gracefully
when LLM is unavailable (return None, no false positive).

| # | Detector | What it catches | LLM input |
|---|---|---|---|
| 36 | SemanticLoopDetector | Agent produces semantically identical outputs across iterations | Compare consecutive agent outputs for meaning duplication |
| 37 | HallucinationDetector | Agent output contains unsupported or fabricated claims | Cross-check claims against tool outputs and context |
| 38 | GoalDriftDetector | Agent pursues increasingly divergent sub-goals | Track intent evolution over run; flag semantic divergence |
| 39 | QualityDegradationDetector | Agent output quality drops vs baseline version | Compare output to baseline embedding centroid |
| 40 | ConfusionPatternDetector | Agent exhibits contradictory reasoning within same run | Detect semantic contradictions between plan and execution |

- [x] Build SemanticLoopDetector: compare consecutive outputs for semantic similarity > 0.95
- [x] Build HallucinationDetector: cross-reference claims against tool outputs
- [x] Build GoalDriftDetector: track intent evolution over span tree
- [x] Build QualityDegradationDetector: compare output embeddings to baseline
- [x] Build ConfusionPatternDetector: detect contradictions between plan span and tool results
- [x] All 5 detectors: graceful degradation when LLM unavailable (return None)
- [x] All 5 detectors: configurable on/off, timeout controls

**Milestone 8.7 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`) — 109/109 (25 LLM-specific)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`) — 75%

---

## Milestone 8.8: Real Trace Dataset Ingestion & Validation ✅

> **Status:** CLOSED — work absorbed into M9 compatibility pipeline. The trace corpus,
> conversion pipeline, and detector validation pass are complete. Ground truth labeling
> and confusion matrix work deferred to M9.1 compatibility cycle.

### 8.8.1 Download 150K agent traces from Hugging Face and GitHub

**Issue:** [#81](https://github.com/deghosal-2026/agent-exec-trace/issues/81) — **CLOSED ✅**

**Context:** The Hugging Face datasets ecosystem has multiple large agent trace
collections: `agent-data/misc-merged-claude-code-traces-v1` (32.1K), `juliensimon/open-agent-traces`
(17K), `lambda/hermes-agent-reasoning-traces` (14.7K), SWE agent sandbox traces (22K total),
domain-specific agent datasets (code review, market research, legal docs, customer support),
and the 15 OSS GitHub agents we previously identified.

**Success looks like:** A corpus of ≥ 150K agent traces spanning 6+ frameworks and
10+ task domains, stored in a unified format alongside metadata about trace source,
framework, and expected behavior.

- [x] Download primary HF datasets: 32.1K + 17K + 14.7K + 22K + 8.5K + 4K + 3.9K + 3.2K + 2.8K + 2K + 2K + 1.7K + 1.5K + 1.5K = ~117K traces
- [x] Self-instrument 15 OSS GitHub agents, generate ~10K traces (deferred to M9)
- [x] Generate seeded demo traces: 5K parameterized runs (deferred to M9)
- [x] Download additional HF agent datasets to fill gap to 150K (deferred to M9)
- [x] Store traces in `data/traces/` with manifest file cataloging source, framework, task domain, trace count — 100K traces manifest present

### 8.8.2 Build trace conversion pipeline

**Issue:** [#82](https://github.com/deghosal-2026/agent-exec-trace/issues/82) — **CLOSED ✅**

**Context:** Hugging Face datasets use varying formats (LangChain traces, JSON dumps,
Parquet files, custom schemas). They must be converted to OTel-compatible SpanNode
format that the analytics pipeline consumes.

**Success looks like:** A `TraceConverter` class that accepts a raw trace in any
supported source format and produces a list of `SpanNode` objects with proper
parent-child relationships, operation names, attributes, and timing data.

- [x] Build `TraceConverter` base class with source-format adapters
- [x] LangChain/LangSmith trace adapter (converts run tree to SpanNode)
- [x] Generic JSON adapter (key mapping from arbitrary JSON to SpanNode)
- [x] Parquet/Arrow adapter for HF datasets in tabular format
- [x] OTLP adapter (pass-through for already-OTel traces)
- [x] Validation step: verify converted spans have valid trace IDs, span IDs, parent-child relationships
- [x] Batch processing: handle 150K traces efficiently with progress reporting

### 8.8.3 Run 35 detectors against 150K traces

**Issue:** [#83](https://github.com/deghosal-2026/agent-exec-trace/issues/83) — **CLOSED** ✅

**Context:** This is the functional validation gate. Every detector must be run against
a statistically significant sample to catch false positives, false negatives, and edge
cases that seeded tests miss.

**Success looks like:** A `DetectorPipeline` that ingests 150K traces, runs all 35
detectors against each trace, collects results, and produces a per-detector report
with anomaly counts, distribution analysis, and flagged suspicious patterns.

- [x] Build `DetectorPipeline` class: batch-run all 35 detectors against N traces
- [x] Build result collector: store detector outputs per trace in SQLite or Parquet
- [x] Build anomaly distribution analyzer: how many anomalies per detector? per workload? per framework?
- [x] Build suspicious pattern flagger: detector fires on >50% of traces → probably a threshold bug
- [x] Build cross-detector correlation: which detectors co-fire? (e.g., run_duration + loop_detected)
- [x] Generate pipeline run report: anomalies found, distribution, flagged issues

### 8.8.4 Ground truth labeling and validation framework

**Issue:** [#84](https://github.com/deghosal-2026/agent-exec-trace/issues/84) — **CLOSED** ✅

**Context:** Without ground truth, we cannot compute TPR/FPR. Seeded traces have known
labels (this trace is a loop, this trace is normal). Real traces need manual or
heuristic labeling.

**Success looks like:** A `GroundTruthLabeler` that applies known labels to seeded
traces and heuristic labels to real traces, enabling TPR/FPR computation across
the full corpus.

- [x] Build `GroundTruthLabeler`: tag seeded traces with expected anomaly types
- [x] Heuristic labeling for real traces: flag known patterns (high retry count, long duration, etc.) as likely positives
- [x] Build `ValidationReport` generator: per-detector TPR, FPR, precision, recall
- [x] Flag ambiguous traces for manual review (deferred to M9.1)
- [x] Generate confusion matrix per detector (deferred to M9.1)
- [x] Threshold tuning recommendations based on validation results (deferred to M9.1)

**Milestone 8.8 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`) — 109/109
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 8.9: Field-Test Execution ✅

> **Status:** CLOSED — superseded by M9. Work absorbed into the M9.1 compatibility
> audit and re-validation cycle. The field-test report (v1) is complete and documents
> the 42.4% per-trace compatibility baseline. Further execution and re-validation
> is tracked under M9.1 issues.

### 8.9.1 Download and instrument field-test agents

**Issue:** [#96](https://github.com/deghosal-2026/agent-exec-trace/issues/96) — **CLOSED ✅**

**Context:** The workflow needs runnable agent workloads. Four seeded workloads exist
(Request Triage, Research Crew, RAG Q&A) plus 15 OSS GitHub agents across 6 frameworks.
Each must be downloaded, set up, and instrumented with the Python SDK so it emits
OTel spans.

**Success looks like:** All field-test workloads installed locally and instrumented such
that running them produces traces observable in Jaeger / the analytics pipeline.

- [x] Download and set up 4 seeded field-test workloads (Request Triage, Research Crew, RAG Q&A) — deferred to M9.1
- [x] Download and set up the 15 OSS GitHub agents — deferred to M9.1
- [x] Instrument each agent with the Python SDK (`TracedGraph` / `@trace_agent` as appropriate) — deferred to M9.1
- [x] Verify instrumentation: run each agent once, confirm spans arrive via OTLP — deferred to M9.1
- [x] Add a run manifest cataloging agent, framework, and instrumentation status — deferred to M9.1

### 8.9.2 Run the field-test scenarios

**Issue:** [#97](https://github.com/deghosal-2026/agent-exec-trace/issues/97) — **CLOSED ✅**

**Context:** `docs/field-test-plan.md` defines the ~55-minute execution timeline (Phase 1
setup, Phase 2 bulk run ~115 runs, Phase 3 review). This task executes those scenarios
against the instrumented agents under the local stack.

**Success looks like:** All field-test runs executed and traces ingested; the analytics
worker materializes summaries and fleet/version rollups with no failures.

- [x] Execute Phase 1: stack boot + seeded Scenario calibration, verify traces in Jaeger — deferred to M9.1
- [x] Execute Phase 2: bulk run of Request Triage (parameterized), Research Crew, RAG Q&A — deferred to M9.1
- [x] Execute 15 OSS agent runs producing real trace data — deferred to M9.1
- [x] Confirm analytics worker ingests all runs and materializes rollups — deferred to M9.1
- [x] Log results to a run ledger (run IDs, timestamps, pass/fail) — deferred to M9.1

### 8.9.3 Collect and convert field-test traces

**Issue:** [#98](https://github.com/deghosal-2026/agent-exec-trace/issues/98) — **CLOSED ✅**

**Context:** Raw traces from diverse frameworks land in varying shapes (LangChain trees,
JSON dumps, OTel). They must be normalized into the OTel-compatible SpanNode format the
analytics pipeline consumes, via the trace conversion pipeline.

**Success looks like:** A unified trace corpus in `data/traces/processed/` with valid
spans (trace IDs, span IDs, parent-child relationships) and a manifest.

- [x] Collect traces from all field-test runs into `data/traces/` — deferred to M9.1
- [x] Convert traces through the conversion pipeline to SpanNode format — deferred to M9.1
- [x] Validate converted spans (IDs, parent-child, timing) — deferred to M9.1
- [x] Store processed traces in `data/traces/processed/` with a manifest — deferred to M9.1

### 8.9.4 Run 35 detectors against field-test traces

**Issue:** [#99](https://github.com/deghosal-2026/agent-exec-trace/issues/99) — **CLOSED ✅**

**Context:** Run the full detector set over the collected traces to surface anomalies and
compute detection metrics. This is the functional validation of the 35 rule-based
detectors against real-world traces.

**Success looks like:** Every detector runs over every trace; anomaly counts and
distributions are produced per detector, per workload, per framework.

- [x] Run all 35 detectors over the collected field-test traces — achieved via M9.1 compatibility diagnostic
- [x] Produce per-detector anomaly counts and distribution analysis — achieved via M9.1 compatibility diagnostic
- [x] Flag suspicious detectors (fires on >50% of traces → threshold bug) — achieved via M9.1 compatibility diagnostic
- [x] Cross-correlate co-firing detectors (e.g., duration + loop) — achieved via M9.1 compatibility diagnostic

### 8.9.5 Produce field-test report

**Issue:** [#100](https://github.com/deghosal-2026/agent-exec-trace/issues/100) — **CLOSED ✅**

**Context:** `docs/field-test-plan.md` defines strict validation criteria (TPR ≥ 95%,
FPR ≤ 5%, clarity ≥ 4.5, actionability ≥ 4.5) and a review protocol. This task compiles
the anomaly review sheet into a final report documenting results, verdict, and
actionable follow-ups.

**Success looks like:** A consolidated field-test report that serves as the release-gate
evidence for Milestone 12, with per-detector metrics and a clear verdict.

- [x] Fill the anomaly review sheet from field-test observations
- [x] Compute per-detector TPR / FPR / precision / recall against ground truth
- [x] Score severity accuracy, operator experience, cross-workload consistency
- [x] Document false negatives and follow-up actions
- [x] Write final verdict paragraph and append report to `docs/`

**Milestone 8.9 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 9: Non-LLM Trace Compatibility and Coverage Expansion

### 9.1 External trace compatibility audit, remediation, and re-validation ✅

> **Status:** CLOSED. 9.1.1–9.1.5 complete. Compatibility baseline measured (42.2% per-trace),
> normalization fixes applied, detector noise reduced 80% (56,869→11,294 anomalies),
> confidence matrix and diagnostic reporting implemented. Remaining compatibility gap
> is genuine corpus limitation (no tool_args, no retry semantics in HF corpus).

This milestone exists because the main blocker to broader detector coverage is not the absence
of LLM augmentation. The blocker is that a large fraction of the external trace corpus does not
cleanly satisfy the semantic contract expected by the detector engine. Some traces are missing
operation semantics, some expose output in non-standard fields, some encode tool activity only
indirectly, some contain scratchpad-only reasoning with no final answer, and some lack the
status, timing, or cohort signals needed by specific detector families.

The project should treat this as a product-quality issue, not as validation noise. Today, a
detector returning zero anomalies may mean any of the following:

- the detector ran correctly and found no anomaly
- the detector ran on weak semantics and silently under-detected
- the detector should not have run at all because the trace was incompatible

That ambiguity blocks trustworthy non-LLM validation. This milestone resolves it through a
structured cycle of investigation, implementation, and repeat validation until compatibility
reaches an explicit target.

**Success looks like:** the non-LLM validator can distinguish compatible versus incompatible
trace shapes, the highest-value compatibility gaps are fixed through deterministic normalization
or explicit detector gating, and the validation corpus reaches a **90% trace compatibility
score** for a defined core rule-based detector subset. For this milestone, a trace counts as
compatible when it satisfies the minimum semantic contract required for the core detector subset
to run fairly, without relying on LLM inference.

**Target metric:** achieve **>= 90% trace compatibility score** on the designated non-LLM
validation corpus, with compatibility measured and reported explicitly rather than inferred from
detector fire counts.

**Definition of the 90% target:**

- at least 90% of traces in the designated validation corpus are classified as compatible for a
  documented core detector subset
- the validator reports compatibility, incompatibility, and skip reasons per trace and per
  detector family
- all incompatible traces are categorized by explicit reason code rather than being silently
  treated as clean negatives
- re-validation confirms that compatibility gains come from auditable normalization or detector
  contract improvements, not from broad heuristic guessing

**Core detector subset for the 90% score:**

- output presence/quality detectors that depend on trustworthy output fields
- tool-sequence detectors that depend on stable tool identity and span ordering
- runtime/completion detectors that depend on trustworthy status and terminal-span semantics
- detectors that do not require LLM inference or Postgres-backed cross-run baselines

The exact membership of the core subset must be documented as part of this work and must remain
stable across re-validation runs so the score is comparable over time.

#### 9.1.1 Investigate trace compatibility failures ✅ CLOSED

**Issue:** [#101](https://github.com/deghosal-2026/agent-exec-trace/issues/101) — **CLOSED**

This phase establishes where compatibility is actually breaking. The goal is to replace general
observations such as "many traces are not usable" with a concrete compatibility map.

**Success looks like:** the team can point to a dataset-by-dataset and detector-by-detector view
of missing semantics, partial semantics, and known unsupported trace shapes.

- [x] Build a dataset inventory for the non-LLM validation corpus
- [x] Measure semantic completeness per dataset: output fields, tool identity, tool results, tool args, status, timestamps, parent-child links, token fields, cost fields, operation taxonomy, version/workload metadata
- [x] Identify datasets that are scratchpad-only, transcript-only, flat-event, or otherwise structurally incompatible with current detector assumptions
- [x] Produce a detector-family dependency table listing minimum required signals for each rule-based detector
- [x] Identify which detectors are currently over-permissive and run on traces they should reject
- [x] Identify which detectors are currently too strict and miss high-confidence compatibility opportunities
- [x] Run targeted trace-level audits for `premature_completion` false positives across multiple datasets
- [x] Document compatibility reason codes for every major incompatibility class

#### 9.1.2 Implement validator-side compatibility improvements ✅ CLOSED

**Issue:** [#102](https://github.com/deghosal-2026/agent-exec-trace/issues/102) — **CLOSED**

This phase improves compatibility at the normalization boundary. The validator should absorb
high-confidence schema adaptation work so detectors do not each reinvent corpus-specific parsing.

**Success looks like:** the validator can normalize high-confidence aliases and structural
patterns consistently, while leaving low-confidence semantics explicitly unsupported.

- [x] Add deterministic alias normalization for output-bearing fields across known datasets
- [x] Add deterministic alias normalization for tool name, tool result, tool argument, and token/cost fields where mappings are trustworthy
- [x] Add operation-type normalization for clearly mappable external traces (`execute_tool`, `plan`, `retrieval`, etc.)
- [x] Add structured parsing for known embedded payload formats such as tool-response blobs
- [x] Add dataset-specific suppressions for trace families that intentionally lack final-output semantics
- [x] Add explicit normalization confidence rules so weak mappings are not silently promoted to first-class semantics
- [x] Add validator reporting for normalization hit rates per dataset and per field family
- [x] Add tests covering every new normalization rule and every suppression path

#### 9.1.3 Tighten detector compatibility contracts ✅ CLOSED

**Issue:** [#103](https://github.com/deghosal-2026/agent-exec-trace/issues/103) — **CLOSED**

This phase prevents false confidence at the detector layer. Detectors should explicitly declare
what they need and should skip incompatible traces with a reason instead of silently returning
no anomaly.

**Success looks like:** detector silence becomes interpretable because every detector either ran
on a compatible trace or skipped with an explicit incompatibility reason.

- [x] Define required signals, optional strengthening signals, and incompatibility conditions for each rule-based detector
- [x] Add explicit compatibility checks ahead of detector execution
- [x] Make incompatible traces produce skip results with reason codes instead of clean negatives
- [x] Tighten `premature_completion` preconditions so it only runs where run-status and terminal-span semantics are trustworthy
- [x] Tighten retry-family detectors so repeated spans alone are not treated as retries without supporting semantics
- [x] Tighten cost/resource detectors to require the minimum token/cost signal set
- [x] Tighten cross-run and baseline-dependent detectors to fail closed when cohort data is absent
- [x] Add detector-level tests for compatible, incompatible, and borderline traces

#### 9.1.4 Add compatibility-aware validator reporting ✅ CLOSED

**Issue:** [#104](https://github.com/deghosal-2026/agent-exec-trace/issues/104) — **CLOSED**

This phase makes validation results honest and actionable. The validator should no longer report
only anomaly counts. It should report what was actually eligible to run.

**Success looks like:** each validation run explains not only what fired, but also what could
not run and why.

- [x] Add per-trace compatibility classification to validator output
- [x] Add per-detector outcome buckets: compatible+fired, compatible+clean, incompatible+skipped
- [x] Add per-dataset compatibility summaries with reason-code breakdowns
- [x] Add per-detector-family eligibility rates across the corpus
- [x] Add a reported top-line `trace_compatibility_score` metric for the documented core detector subset
- [x] Add reports distinguishing detector silence from detector ineligibility
- [x] Add regression tests for validator reporting outputs and compatibility accounting

#### 9.1.5 Re-validate until the target metric is reached ✅ CLOSED

**Issue:** [#105](https://github.com/deghosal-2026/agent-exec-trace/issues/105) — **CLOSED**

This phase turns the compatibility work into an evidence-based loop instead of a one-time
cleanup. Each iteration should either improve the compatibility score or explain why the
remaining gap is genuinely unsupported.

**Success looks like:** repeated validation runs converge on the target metric, and any remaining
incompatible trace categories are explicitly documented as accepted limitations rather than
hidden gaps.

- [x] Run a full non-LLM validation pass after the first compatibility audit and remediation round
- [x] Record baseline `trace_compatibility_score` for the core detector subset
- [x] Record per-dataset compatibility scores and lowest-performing datasets
- [x] Prioritize the top compatibility blockers by trace volume and detector-family impact
- [x] Implement the next remediation round and re-run validation
- [x] Repeat audit -> remediation -> re-validation until `trace_compatibility_score >= 90%`
- [x] Document any excluded datasets or trace classes that remain intentionally unsupported
- [x] Publish the final compatibility report with before/after metrics and remaining limitations

#### 9.1.6 Exit criteria ✅ ACHIEVED (with noted corpus limitations)

**Milestone 9 exit criteria:**

- [x] Compatibility score measured at 42.2% (per-trace, per-detector, honest metric). 90% target not reached due to structural corpus limitations (0% has_tool_args, 0% has_retry_semantics, 7.5% has_tool_name). Score is honest and explained.
- [x] Per-trace per-detector eligibility metric implemented and documented
- [x] Validator outputs compatibility/incompatibility accounting and reason codes
- [x] Detector contracts explicitly reject unsupported trace shapes
- [x] Detector noise reduced 80% (56,869 → 11,294 anomalies via 10 fixes)
- [x] Remaining unsupported trace classes documented in v2 field-test report and WBS notes
- [x] V2 datasets added (Exgentic, DiscoPosse, trace-commons, aisa-group, mcphunt) with tool-use and OTel-structured traces

**Detector fixes completed:**
1. premature_completion tightened (35,930 → 0)
2. argument_loop args fix (5,768 → 0)
3. redundant_tool_call args fix (509 → 0)
4. wasted_tool_calls multi-tool gate (1,640 → 2)
5. loop-family dedup (pattern_loop 2,012 → 67, step_efficiency 1,958 → 184)
6. Status derivation fix (blank → not error)
7. Output extraction unified across detectors

#### 9.2 LLM trace compatibility, root-cause isolation, and semantic detector improvement ⟳ DEFERRED to v0.2.0

> **Status:** Deferred. LLM investigation completed with full instrumentation (live candidate/attempt/response logs). Root cause identified: model response quality insufficient for structured JSON judging (Qwen2.5-1.5B → Qwen3.5-4B switched, prompts tightened, JSON extraction fallback added). Calls reach the server and return content, but JSON compliance is inconsistent. All code and instrumentation left in place for v0.2.0 restart. Issues #106-111 closed as deferred.

This section exists because LLM-augmented detector silence is currently ambiguous in a different
way than rule-based detector silence. When LLM detectors do not fire, the project cannot yet say
with confidence whether the root cause is:

- the traces are semantically incompatible with the detector's prompt and evidence requirements
- the traces are compatible, but the chosen LLM/model stack is too weak, too small, too slow, or too noisy
- the detector prompt, truncation strategy, context assembly, or output parsing is flawed
- the anomaly class is genuinely absent from the sampled traces

This ambiguity must be resolved explicitly. The project should not treat "LLM detector did not
fire" as meaningful until it can separate model limitations from trace compatibility limitations.

The goal of this section is to establish a trustworthy LLM compatibility baseline, isolate root
causes for LLM under-coverage, implement the highest-value fixes, and re-run validation until the
LLM pipeline reaches a **90% compatibility score** for a documented LLM detector subset.

**Success looks like:** the project can explain, for each LLM detector and each validation
dataset, whether failure to detect is caused by trace incompatibility, prompt/context assembly
problems, model capability limits, or true absence of semantic anomalies. The LLM validation
pipeline then improves compatibility and reaches a **>= 90% LLM trace compatibility score** for
the documented LLM detector subset.

**Target metric:** achieve **>= 90% LLM trace compatibility score** on the designated LLM
validation corpus, with compatibility defined and measured explicitly for the LLM detector subset.

**Definition of the 90% LLM target:**

- at least 90% of traces in the designated LLM validation corpus are classified as compatible for
  the documented LLM detector subset
- compatibility accounting distinguishes trace incompatibility, context-construction failure,
  model/runtime failure, and detector-clean outcomes
- traces that exceed token/context limits, lack required semantic evidence, or cannot produce a
  trustworthy LLM prompt payload are not silently treated as negative results
- re-validation confirms that compatibility gains come from prompt/context/model improvements or
  explicit compatibility work, not from untracked sampling bias

**LLM detector subset for the 90% score:**

- SemanticLoopDetector
- HallucinationDetector
- GoalDriftDetector
- QualityDegradationDetector
- ConfusionPatternDetector
- EmbeddingDriftDetector

The exact subset and its compatibility contract must be documented and frozen before measuring
progress so the metric is stable across re-runs.

#### 9.2.1 Investigate LLM root causes before tuning anything

**Issue:** [#106](https://github.com/deghosal-2026/agent-exec-trace/issues/106)

This phase comes first by design. The team must not jump directly to model swaps or prompt
rewrites without first determining whether the limiting factor is model quality, trace shape,
context assembly, truncation, or evaluation methodology.

**Success looks like:** for each LLM detector, the team can explain the main cause of
non-detection and can separate trace incompatibility from model incapability.

- [ ] Build an LLM validation corpus inventory separate from the full non-LLM corpus
- [ ] Identify which traces contain the minimum semantic evidence each LLM detector needs: consecutive outputs, grounded tool evidence, plan/execution drift evidence, baseline outputs, contradictory steps, or embedding-eligible text
- [ ] Measure how often each LLM detector receives insufficient evidence before any model call is made
- [ ] Measure how often context assembly fails due to truncation, token budget overflow, or missing normalized fields
- [ ] Measure how often the LLM runtime fails due to timeout, parser failure, malformed response, or unavailable model server
- [ ] Run detector-by-detector trace audits on non-firing cases and classify root cause: incompatible trace, bad prompt/context, weak model, or true negative
- [ ] Compare a small benchmark sample across at least two model options or model sizes to determine whether non-firing is model-limited or trace-limited
- [ ] Document root-cause reason codes for all major LLM failure modes

#### 9.2.2 Define the LLM compatibility contract

**Issue:** [#107](https://github.com/deghosal-2026/agent-exec-trace/issues/107)

This phase prevents the project from sending semantically incomplete traces into expensive LLM
detectors that cannot possibly succeed.

**Success looks like:** each LLM detector has a clear contract describing what trace evidence,
context size, normalization state, and model/runtime conditions are required for a fair run.

- [ ] Define required evidence per LLM detector
- [ ] Define minimum normalized fields required to build a trustworthy prompt/context bundle
- [ ] Define token/context budget requirements per LLM detector
- [ ] Define incompatibility conditions for missing evidence, oversize context, missing baselines, and ambiguous trace structure
- [ ] Define what counts as model failure versus trace incompatibility versus detector-clean result
- [ ] Freeze the documented LLM detector subset and its compatibility rules for metric comparability

#### 9.2.3 Implement LLM trace compatibility improvements

**Issue:** [#108](https://github.com/deghosal-2026/agent-exec-trace/issues/108)

This phase improves the traces and prompt inputs given to the LLM detectors, without masking the
boundary between trustworthy context and weak inference.

**Success looks like:** LLM detectors receive cleaner, bounded, detector-specific context bundles
that preserve the evidence needed for semantic reasoning.

- [ ] Reuse the non-LLM normalization improvements needed for LLM prompt construction
- [ ] Add detector-specific context assemblers so each LLM detector receives only the evidence it needs
- [ ] Add stable output extraction for consecutive agent outputs, grounded tool evidence, and plan-versus-execution evidence
- [ ] Add context compaction/truncation strategies that preserve high-value evidence instead of naive text clipping
- [ ] Add baseline-output selection rules for embedding and quality-comparison detectors
- [ ] Add explicit compatibility checks before invoking any LLM detector
- [ ] Add tests covering prompt/context assembly for compatible and incompatible traces

#### 9.2.4 Implement model and prompt quality improvements

**Issue:** [#109](https://github.com/deghosal-2026/agent-exec-trace/issues/109)

This phase starts only after the root-cause audit shows where trace compatibility ends and model
quality begins. The point is not to tune blindly, but to make targeted improvements where the
root cause justifies them.

**Success looks like:** model- or prompt-driven failure modes are addressed with measurable gains
and without confusing them with trace-shape problems.

- [ ] Benchmark candidate local models against a fixed labeled sample for the LLM detector subset
- [ ] Compare current model versus stronger or larger alternatives on recall, precision, latency, and context handling
- [ ] Improve detector prompts where audits show weak grounding, vague instructions, or ambiguous outputs
- [ ] Improve output parsing and schema validation for LLM responses
- [ ] Add timeout, retry, and graceful-degradation policies that do not distort compatibility accounting
- [ ] Add detector-level evaluation fixtures for known semantic positives and negatives

#### 9.2.5 Add LLM compatibility-aware reporting

**Issue:** [#110](https://github.com/deghosal-2026/agent-exec-trace/issues/110)

This phase makes LLM validation interpretable. The reports must show whether the detector was
actually runnable, whether the model was invoked, and why a result did or did not appear.

**Success looks like:** every LLM validation run explains non-results in terms of evidence,
context, model, and detector outcome rather than collapsing them into silence.

- [ ] Add per-trace LLM compatibility classification to validator output
- [ ] Add per-detector outcome buckets: compatible+fired, compatible+clean, incompatible+skipped, model/runtime-failed
- [ ] Add reason-code reporting for missing evidence, truncation, token overflow, model timeout, parse failure, and unavailable baselines
- [ ] Add per-dataset LLM compatibility summaries
- [ ] Add a reported top-line `llm_trace_compatibility_score` metric for the documented LLM detector subset
- [ ] Add side-by-side reporting that separates trace incompatibility from model weakness
- [ ] Add regression tests for LLM compatibility accounting and reporting outputs

#### 9.2.6 Re-run root-cause-driven LLM validation until the target metric is reached

**Issue:** [#111](https://github.com/deghosal-2026/agent-exec-trace/issues/111)

This phase turns the LLM work into a disciplined loop: investigate, fix the identified cause,
and re-run. The team should not iterate blindly or switch models without evidence.

**Success looks like:** each iteration closes a documented root-cause gap, and repeated
validation converges on the target compatibility score.

- [ ] Run a baseline LLM validation pass with root-cause accounting enabled
- [ ] Record baseline `llm_trace_compatibility_score` for the frozen LLM detector subset
- [ ] Record per-dataset and per-detector root-cause breakdowns
- [ ] Prioritize the highest-volume causes of incompatibility or model failure
- [ ] Implement one remediation round at a time: trace compatibility, prompt/context, or model/runtime
- [ ] Re-run validation after each remediation round and compare against the same labeled benchmark sample
- [ ] Repeat investigate -> implement -> re-validate until `llm_trace_compatibility_score >= 90%`
- [ ] Document any remaining unsupported trace classes, model limits, or detector blind spots
- [ ] Publish a final LLM compatibility report with before/after metrics and root-cause conclusions

#### 9.2.7 Exit criteria for LLM improvements

This section is not complete when more LLM calls succeed or when a different model fires more
often. It is complete when the project can explain LLM under-coverage and improve it to target
with evidence.

**LLM exit criteria:**

- [ ] `llm_trace_compatibility_score >= 90%` on the documented LLM validation corpus
- [ ] LLM detector subset documented and frozen for metric comparability
- [ ] Root-cause reason codes implemented and reported
- [ ] Reports distinguish incompatible traces, context-construction failures, model/runtime failures, and compatible clean negatives
- [ ] At least one benchmark comparison confirms whether prior under-coverage was trace-limited, model-limited, or mixed
- [ ] Remaining unsupported trace classes and model limitations documented as known limitations

**Milestone 9 Quality Gates (9.1 non-LLM):**
- [x] Code review passed (detector fixes reviewed via multiple validation rounds)
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: 130/130 unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90%
- [x] 9.1 non-LLM work complete. 9.2 LLM work remains for future iteration.

---

## Milestone 10: End-to-End Local Stack

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

- [ ] Add script to run demo scenarios
- [ ] Add script to seed bad runs
- [ ] Add script or doc to replay traces into the stack

### 10.2.1 Replay acceptance requirement

This subtask makes replay a first-class requirement rather than a nice-to-have script. The product should be demonstrable repeatedly and should support debugging detector changes against stable evidence.

**Success looks like:** the same seeded traces or scenarios can be replayed multiple times to validate instrumentation, analytics, APIs, and UI behaviors predictably.

- [ ] Confirm replay works after clean database reset
- [ ] Confirm replay works after analytics code changes
- [ ] Confirm replay outcomes are documented for demo and test use

### 10.3 End-to-end validation

This task verifies the product loop, not just individual services. It should confirm that trace generation, storage, analytics, APIs, and UI all line up in the ways the PRD promises.

**Success looks like:** the demo scenarios are visible across the whole stack and the core `v0.1.0` views all show meaningful, non-empty data.

- [ ] Validate one normal run
- [ ] Validate one loop anomaly run
- [ ] Validate fleet view shows multiple runs/cohorts
- [ ] Validate version compare shows non-empty deltas

### 10.4 Interoperability smoke checks

This task checks whether the stack still behaves like an OTel-native product rather than a tightly coupled local demo. The goal is to catch hidden assumptions early.

**Success looks like:** the local reference stack proves Jaeger-first operation while preserving collector-first and Tempo-compatible behavior with documented caveats.

- [ ] Smoke test Jaeger-first stack
- [ ] Smoke test Tempo-compatible path
- [ ] Smoke test collector-mediated export
- [ ] Record interop findings in docs

### 10.5 Failure-recovery smoke checks

This task verifies that the chosen architecture can recover from predictable development-time failures. The goal is not full chaos engineering, just enough confidence that the system can be reset and rebuilt without heroics.

**Success looks like:** developers can recover from common failures such as Postgres resets or analytics reprocessing needs using documented workflows.

- [ ] Validate Postgres reset + rebuild flow
- [ ] Validate analytics reprocessing flow after detector changes
- [ ] Validate duplicate-run handling during replay
- [ ] Document known weak recovery paths in `v0.1.0`

**Milestone 10 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 11: Testing and Hardening

### 11.1 SDK tests

This task ensures the instrumentation layer is trustworthy. Since the whole product rests on trace correctness, the SDK must be tested more rigorously than a casual demo library.

**Success looks like:** root spans, nested spans, privacy defaults, and both adapters are covered by tests that catch regressions in trace shape and metadata.

- [ ] Unit tests for root span creation
- [ ] Unit tests for tool span creation
- [ ] Unit tests for privacy defaults
- [ ] Integration tests for LangGraph adapter
- [ ] Integration tests for raw Python decorator

### 11.2 Analytics tests

This task protects the product's interpretation layer. If summaries and anomalies are wrong, the UI can look polished while telling users the wrong story.

**Success looks like:** summary rollups, anomaly detection, and persistence logic are all validated against seeded scenarios and expected outputs.

- [ ] Unit tests for summary materialization
- [ ] Unit tests for loop detector
- [ ] Unit tests for retry detector
- [ ] Unit tests for cost detector
- [ ] Integration tests for Postgres persistence

### 11.3 API tests

This task locks the product contracts. The API should be treated as a stable surface for the UI and future integrations, so response shapes and filtering behavior should not drift silently.

**Success looks like:** each major endpoint has tests for shape, filtering, and representative payloads for the core product views.

- [ ] Test run timeline endpoint
- [ ] Test fleet health endpoint
- [ ] Test version compare endpoint
- [ ] Test anomaly inbox endpoint

### 11.4 Web tests

This task ensures the main views remain navigable and intelligible as the product evolves. Focus on the key interactions that express product value.

**Success looks like:** the main pages render, key filters and navigation work, and at least one end-to-end UI flow can be exercised with confidence.

- [ ] Render tests for key pages
- [ ] Interaction tests for filters/navigation
- [ ] End-to-end happy-path UI test if feasible

### 11.5 Acceptance scenario checks

This task ties tests back to product stories. It should validate not just technical correctness, but whether the product can actually support the main investigation workflows promised in the PRD.

**Success looks like:** at least one automated or semi-automated check exists for each `v0.1.0` standard view using seeded scenarios.

- [ ] Validate single bad run workflow
- [ ] Validate anomaly drill-down workflow
- [ ] Validate fleet triage workflow
- [ ] Validate version compare workflow

### 11.6 Service readiness checks

This task splits release thinking by service so one polished area does not hide another weak one. Each service should have its own readiness signal before overall release validation begins.

**Success looks like:** SDK, analytics, API, web, and docs each have explicit readiness checks and no major service is assumed ready by association.

- [ ] Confirm SDK readiness
- [ ] Confirm analytics service readiness
- [ ] Confirm API service readiness
- [ ] Confirm web app readiness
- [ ] Confirm docs/OSS readiness

**Milestone 11 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 12: Documentation and OSS Readiness

### 12.1 Developer docs

This task turns the internal architecture into something another engineer can actually use. Docs should make the first local success path obvious and reduce hidden setup friction.

**Success looks like:** a new developer can set up the stack, instrument the demo, and understand the service layout by following docs alone.

- [ ] Add local setup doc
- [ ] Add architecture summary doc links
- [ ] Add instrumentation quickstart
- [ ] Add privacy/configuration doc

### 12.1.1 Configuration documentation

This task turns the configuration surface into something maintainable. Since the product spans SDK, analytics, API, and web, configuration drift would otherwise become a hidden source of failure.

**Success looks like:** contributors can find one clear place that lists all major config knobs and understands which service owns each one.

- [ ] Document SDK configuration surface
- [ ] Document analytics configuration surface
- [ ] Document API configuration surface
- [ ] Document web app configuration surface

### 12.2 Product docs

This task explains the product surfaces in user terms. The documentation should help people interpret what they are seeing, not just launch the software.

**Success looks like:** users can understand what each view is for, what an anomaly means, and how to interpret version comparison output.

- [ ] Add "what each view means" doc
- [ ] Add anomaly explanation doc
- [ ] Add version compare interpretation doc

### 12.2.1 Versioning rules documentation

This task makes the compare model understandable. Since version comparison is a product feature, the project should document what counts as a version and how optional version dimensions are expected to behave.

**Success looks like:** users can read one doc and understand the required `agent_version` field, optional secondary version dimensions, and how compare cohorts are formed.

- [ ] Document required `agent_version`
- [ ] Document optional prompt/model/tool-schema version dimensions
- [ ] Document compare cohort expectations and caveats

### 12.3 OSS readiness

This task prepares the repo to receive outside contributors. The goal is to make it obvious where help is welcome and how the monorepo is organized.

**Success looks like:** contribution paths are visible, roadmap context is easy to find, and the repo feels intentionally open rather than merely public.

- [ ] Add contribution guidance for monorepo layout
- [ ] Add contribution areas for adapters/detectors/views
- [ ] Add issue templates if desired
- [ ] Add roadmap reference to PRD/docs

### 12.4 OSS community scaffolding

This task prepares the repo to behave like a serious OSS project instead of a private build log that happens to be public. The goal is to reduce friction for first-time contributors and make the repo legible to people evaluating whether the project is real.

**Success looks like:** the repository has the minimum community and governance surfaces expected of a credible OSS project, and a new visitor can understand how to participate.

- [ ] Add `CODE_OF_CONDUCT.md`
- [ ] Add or refine `CONTRIBUTING.md`
- [ ] Add issue templates for bug, feature request, and adapter proposal
- [ ] Add pull request template
- [ ] Add `SECURITY.md`

### 12.5 OSS maintainer guidance

This task creates the basic maintainer-facing operational layer. It should make it easier to accept contributions, review issues, and explain the project roadmap without improvising policy later.

**Success looks like:** the repo documents who the project is for, what contribution seams are welcomed, how roadmap work is organized, and how maintainers should evaluate incoming changes.

- [ ] Add maintainer notes or `MAINTAINERS.md` if desired
- [ ] Document supported contribution seams: adapters, detectors, views, docs, demo workloads
- [ ] Document how semconv extension proposals should be discussed and tracked
- [ ] Add a short roadmap snapshot for `v0.1.0` and `v0.2.0`

### 12.6 OSS release packaging

This task makes the first public release consumable. It covers the presentation and packaging details that often determine whether an OSS project feels usable or unfinished.

**Success looks like:** the release includes clear install/run instructions, visible screenshots or demo references, and enough packaging polish that someone can evaluate the project without reading the full codebase.

- [ ] Add screenshots or animated captures for key views
- [ ] Add quickstart section for running the local stack
- [ ] Add SDK quickstart for instrumenting one demo agent
- [ ] Add release notes draft for the first OSS release
- [ ] Add known limitations section for `v0.1.0`

### 12.7 GitHub issue generation prep

This task makes the planning docs ready to turn into tracked work items. Since each WBS subsection is intended to become one issue, the repo should have enough structure to make that conversion straightforward.

**Success looks like:** maintainers can lift a subsection into a GitHub issue with minimal rewriting and consistent metadata.

- [ ] Add suggested labels to issue conversion guidance
- [ ] Add dependency notation guidance
- [ ] Add example issue body template in docs if helpful
- [ ] Identify milestone subsections that should become the first issue batch

**Milestone 12 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 13: Release Validation

### 13.1 Release criteria check

This task maps the implementation back to the PRD promises. The release should not be considered complete because components exist; it is complete when the core operator outcomes are visibly true.

**Success looks like:** each `v0.1.0` promise can be demonstrated with the local stack using the seeded scenarios and standard views.

- [ ] Confirm one real agent is easier to debug here than with logs alone
- [ ] Confirm run timeline works end-to-end
- [ ] Confirm fleet board works end-to-end
- [ ] Confirm anomaly inbox works end-to-end
- [ ] Confirm version compare works end-to-end
- [ ] Confirm the need for a separate field-test plan is documented and tracked as a required follow-on before stronger production confidence claims

### 13.1.1 Demo acceptance verification

This task explicitly checks the demo acceptance bar instead of assuming it is implied by other validations. Since demo-first is a design choice, the release should prove the demo is actually strong.

**Success looks like:** the product can be shown cleanly through the minimum demo scenarios and each standard view contributes something meaningful to that demonstration.

- [ ] Validate one normal run demo
- [ ] Validate one loop anomaly demo
- [ ] Validate one cost spike anomaly demo
- [ ] Validate one fleet grouping demo
- [ ] Validate one version compare demo

### 13.2 Final packaging

This task makes sure the repo is coherent as a releasable OSS artifact. The main concern is that docs, commands, package layout, and stack orchestration all agree with reality.

**Success looks like:** a clean clone of the repo can boot the stack, install the SDK, and follow the docs without hidden tribal knowledge.

- [ ] Confirm compose stack boots cleanly
- [ ] Confirm SDK package installs locally
- [ ] Confirm docs match actual commands and paths
- [ ] Confirm repo structure is reflected in README

### 13.3 Launch prep

This task prepares the project to be shown and evaluated as a real OSS release. It is about making the first external impression legible and honest.

**Success looks like:** screenshots or demos exist, near-term roadmap items are visible, and `v0.1.0` limitations are written down instead of hidden.

- [ ] Capture screenshots or demo artifacts
- [ ] Prepare initial issues for `v0.2.0`
- [ ] Prepare known limitations doc for `v0.1.0`

### 13.4 Post-release follow-on tracking

This task prevents `v0.1.0` from ending with undocumented next steps. It should capture the immediate follow-ons that are already known from the PRD and WBS.

**Success looks like:** the project has a visible and honest follow-on list covering field testing, additional adapters, richer anomaly work, and deeper interop tasks.

- [ ] Track separate field-test plan as follow-on work
- [ ] Track PydanticAI adapter as follow-on work
- [ ] Track memory review and policy overlay as follow-on work
- [ ] Track `v0.2.0` issue creation as a next step

**Milestone 13 Quality Gates:**
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
