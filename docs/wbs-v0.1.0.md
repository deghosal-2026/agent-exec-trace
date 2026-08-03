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
| Milestone 9 | local stack/demo issues |
| Milestone 10 | testing/hardening issues |
| Milestone 11 | docs/OSS readiness issues |
| Milestone 12 | release validation issues |

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
- Milestone 9

### Wave 4

- Milestone 10
- Milestone 11
- Milestone 12

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
- [ ] Create `packages/python-sdk/`
- [ ] Create `services/api/`
- [ ] Create `services/analytics/`
- [ ] Create `apps/web/`
- [ ] Create `deploy/`
- [ ] Create `examples/`
- [ ] Create `tests/`

---

### Issue: Root project scaffolding

**Context:** Add root-level operating surface: README layout summary, gitignore, Makefile entrypoints, compose placeholder, developer setup doc.

**Dependencies:** monorepo skeleton.

**Suggested labels:** `infra`, `docs`

**Success criteria:**
- new contributor can open repo, understand layout from root README, see how local stack will work, understand workspace governance

**Checklist:**
- [ ] Add root `README.md` section for monorepo layout
- [ ] Update root `.gitignore` for monorepo paths
- [ ] Add root `Makefile` or task runner entrypoints
- [ ] Add root `docker-compose.yml` placeholder
- [ ] Add root developer setup doc

---

### Issue: Shared dev conventions

**Context:** Remove ambiguity about versions, formatting, and developer expectations. Keep setup light but lock enough that multi-service work does not drift immediately.

**Dependencies:** monorepo skeleton.

**Suggested labels:** `infra`

**Success criteria:**
- Python and web tooling are predictable
- local setup instructions match actual versions

**Checklist:**
- [ ] Define Python version target
- [ ] Define Node version target for web app
- [ ] Define formatting/lint tools for Python
- [ ] Define formatting/lint tools for web app
- [ ] Add pre-commit hooks

---

### Issue: Demo agent scenario definition

**Context:** This is the reality anchor for the whole product. Define one LangGraph agent with three paths: normal, loop, high-cost.

**Dependencies:** none.

**Suggested labels:** `demo`, `design-followup`

**Success criteria:**
- documented example scenario clearly explains happy path, bad path, and expensive path
- later SDK/UI/analytics work can reference this as truth

**Checklist:**
- [ ] Choose one LangGraph demo agent scenario
- [ ] Document what "bad run" looks like
- [ ] Document what normal run looks like
- [ ] Define one seeded loop scenario
- [ ] Define one seeded high-cost scenario

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
- [ ] Create example LangGraph app folder under `examples/`
- [ ] Add minimal graph workflow
- [ ] Add at least one tool call path
- [ ] Add at least one path that can loop under seeded conditions
- [ ] Add version metadata injection

---

### Issue: Demo datasets and fixtures

**Context:** Make the demo reproducible. Named fixtures for success, loop, and high-cost with expected outcomes.

**Dependencies:** demo agent skeleton.

**Suggested labels:** `demo`

**Success criteria:**
- named fixtures exist for all three cases
- contributor can run them intentionally and know what to expect

**Checklist:**
- [ ] Add sample inputs for success case
- [ ] Add sample inputs for loop case
- [ ] Add sample inputs for high-cost case
- [ ] Add expected run outcomes doc
- [ ] Create scenario matrix doc mapping inputs to expected anomalies and views

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
- [ ] Create `packages/python-sdk/pyproject.toml`
- [ ] Create package source layout
- [ ] Add package README stub
- [ ] Add unit test folder

---

### Issue: Base tracing primitives

**Context:** Core building blocks: config, tracer bootstrap, run context, attribute mapping, redaction support. Every adapter leans on these.

**Dependencies:** SDK package setup.

**Suggested labels:** `sdk`

**Success criteria:**
- later tasks can build adapters and spans using shared primitives
- no duplicated setup logic across adapters

**Checklist:**
- [ ] Create SDK config object
- [ ] Create tracer initialization helper
- [ ] Create run context model
- [ ] Create helper for OTel attribute mapping
- [ ] Create redaction configuration model

---

### Issue: Root run instrumentation

**Context:** Every agent run must become a coherent root span with enough metadata for run views, fleet views, and version comparisons.

**Dependencies:** base tracing primitives.

**Suggested labels:** `sdk`

**Success criteria:**
- one agent run creates one stable root span
- agent identity, version, runtime context, and run ID are attached consistently

**Checklist:**
- [ ] Implement root `invoke_agent` span creation
- [ ] Attach agent name
- [ ] Attach agent version when provided
- [ ] Attach model/provider metadata when provided
- [ ] Attach workload type when provided
- [ ] Attach generated run ID

---

### Issue: Nested behavior spans

**Context:** Make traces behaviorally meaningful. Planning, tool execution, retrieval, and memory become first-class observability concepts.

**Dependencies:** root run instrumentation.

**Suggested labels:** `sdk`

**Success criteria:**
- a single run can express its full behavior as a navigable span tree

**Checklist:**
- [ ] Implement `plan` span helper
- [ ] Implement `execute_tool` span helper
- [ ] Implement `retrieval` span helper
- [ ] Implement memory operation span helper
- [ ] Implement generic event helper

---

### Issue: Raw Python adapter

**Context:** Prove the product is not locked to one framework. Mirror the same semantic model used for LangGraph.

**Dependencies:** nested behavior spans.

**Suggested labels:** `sdk`, `adapter`

**Success criteria:**
- a plain Python agent can be instrumented with decorator and helpers
- traces look structurally consistent with LangGraph adapter output

**Checklist:**
- [ ] Implement `@trace_agent` decorator
- [ ] Implement nested helper context manager for tools
- [ ] Implement nested helper context manager for planning
- [ ] Implement nested helper context manager for retrieval
- [ ] Add tests for decorator-based tracing

---

### Issue: LangGraph adapter

**Context:** First first-class framework integration. Preserve LangGraph execution shape in OTel-first model.

**Dependencies:** nested behavior spans, demo agent skeleton.

**Suggested labels:** `sdk`, `adapter`

**Success criteria:**
- demo workload emits coherent run tree with root spans and nested behavior spans
- metadata is propagated without graph-specific hacks

**Checklist:**
- [ ] Define LangGraph wrapper integration surface
- [ ] Map graph lifecycle to run root span
- [ ] Map graph planning step to `plan` span
- [ ] Map tool nodes to `execute_tool` spans
- [ ] Propagate version and run metadata
- [ ] Add adapter tests against demo graph

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
- [ ] Set metadata-only mode as default
- [ ] Ensure prompts are not captured by default
- [ ] Ensure tool args are not captured by default
- [ ] Ensure memory content is not captured by default
- [ ] Add opt-in config for truncated or hashed content capture

---

### Issue: OTLP configuration

**Context:** Make SDK operationally useful outside local function calls. OTLP-first, backend details hidden behind config.

**Dependencies:** root run instrumentation.

**Suggested labels:** `sdk`, `backend`

**Success criteria:**
- instrumented agent can emit traces through OTLP to collector or direct backend without code changes

**Checklist:**
- [ ] Add SDK exporter configuration for OTLP
- [ ] Support collector endpoint configuration
- [ ] Support direct Jaeger OTLP endpoint configuration
- [ ] Document environment variables for exporter setup

---

### Issue: Jaeger local stack

**Context:** Primary local proof path. Jaeger is the first backend users should see in docs and demos.

**Dependencies:** OTLP configuration.

**Suggested labels:** `infra`, `backend`

**Success criteria:**
- contributor can run local stack, execute demo agent, inspect traces in Jaeger

**Checklist:**
- [ ] Add Jaeger service to `docker-compose.yml`
- [ ] Add collector service config
- [ ] Validate SDK traces appear in Jaeger UI
- [ ] Capture validation note in docs

---

### Issue: Tempo compatibility path

**Context:** Preserve long-term OTel positioning. Tempo compatibility must be real enough to prevent accidental Jaeger lock-in.

**Dependencies:** Jaeger local stack.

**Suggested labels:** `backend`, `interop`

**Success criteria:**
- same trace data viewable in Tempo with only config changes
- compatibility notes documented clearly

**Checklist:**
- [ ] Add optional Tempo service config
- [ ] Validate same SDK traces can be viewed in Tempo
- [ ] Document compatibility notes

---

### Issue: Collector interoperability

**Context:** Ensure the product stays OTel-first. Collector path treated as product contract, not local convenience.

**Dependencies:** Jaeger local stack, Tempo compatibility path.

**Suggested labels:** `interop`, `backend`

**Success criteria:**
- SDK emits through collector cleanly
- backend switching does not require code rewrites

**Checklist:**
- [ ] Validate collector-based OTLP export to Jaeger
- [ ] Validate collector-based OTLP export to Tempo
- [ ] Document collector config expectations
- [ ] Document backend-specific caveats

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

This task creates the physical shape of the product. The goal is not just folders; it is to make the repo reflect the product boundaries already locked in the architecture. A contributor should be able to tell where SDK work, API work, analytics work, and UI work belong without reading a long explanation.

**Success looks like:** the repo tree clearly matches the intended architecture, empty folders are replaced with minimal keep files or scaffold files where needed, and future work can be placed without restructuring the repository again.

- [ ] Create `packages/python-sdk/`
- [ ] Create `services/api/`
- [ ] Create `services/analytics/`
- [ ] Create `apps/web/`
- [ ] Create `deploy/`
- [ ] Create `examples/`
- [ ] Create `tests/`

### 0.2 Add root project scaffolding

This task establishes the root-level operating surface for the monorepo. It should give contributors one place to start, one place to read setup instructions, and one place to run the local stack. Keep it small, but make it real enough that implementation can begin immediately after scaffolding.

**Success looks like:** a new contributor can open the repo, understand the layout from the root README, see how local orchestration will work, and understand which top-level files govern the workspace.

- [ ] Add root `README.md` section for monorepo layout
- [ ] Add root `.gitignore` updates for monorepo paths
- [ ] Add root `Makefile` or task runner entrypoints
- [ ] Add root `docker-compose.yml` placeholder for local stack
- [ ] Add root developer setup doc in `docs/`

### 0.3 Choose and wire shared dev conventions

This task removes ambiguity early. The point is to avoid a repo where each service invents its own versions, formatting, and developer expectations. Keep the setup light, but lock enough conventions that multi-service work does not drift immediately.

**Success looks like:** Python and web tooling are predictable, local setup instructions match the actual versions used, and the project has one obvious lint/format/test baseline.

- [ ] Define Python version target
- [ ] Define Node version target for web app
- [ ] Define formatting/lint tools for Python
- [ ] Define formatting/lint tools for web app
- [ ] Add pre-commit or equivalent baseline hooks if desired

### 0.4 Record assumptions and open questions

This task keeps planning uncertainty visible instead of letting it disappear into implementation chatter. It should create an explicit place where contributors can see what is assumed, what is unresolved, and what may need revisiting.

**Success looks like:** assumptions and open questions from the spec are visible, current, and easy to convert into future issues if they become blockers.

- [ ] Link assumptions register from implementation-facing docs
- [ ] Link open questions register from implementation-facing docs
- [ ] Mark which open questions are safe to defer past `v0.1.0`

**Milestone 0 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 1: Demo-First Agent Workload

### 1.1 Create first demo agent scenario

This is the reality anchor for the whole product. The first agent scenario should be simple enough to run locally but rich enough to produce meaningful traces: one normal path, one loop path, and one high-cost path. The product should be designed around this lived behavior, not around abstract ideas of how agents might behave.

**Success looks like:** there is a documented example scenario that clearly explains the happy path, the bad path, and the expensive path, and later SDK/UI/analytics work can reference this scenario as the source of truth.

- [ ] Choose one LangGraph demo agent scenario
- [ ] Document what "bad run" looks like for this agent
- [ ] Document what normal run looks like for this agent
- [ ] Define one seeded loop scenario
- [ ] Define one seeded high-cost scenario

### 1.2 Implement demo agent skeleton

This task turns the scenario into runnable code. It should be intentionally small, deterministic where possible, and easy to manipulate so that seeded failures are repeatable. The demo is not throwaway code; it is the first proving ground for instrumentation and views.

**Success looks like:** the example agent runs locally, exercises at least one tool path, can be forced into a loop-like behavior, and can carry version metadata through execution.

- [ ] Create example LangGraph app folder under `examples/`
- [ ] Add minimal graph workflow
- [ ] Add at least one tool call path
- [ ] Add at least one path that can loop under seeded conditions
- [ ] Add version metadata injection for the example

### 1.3 Define demo datasets / fixtures

This task makes the demo reproducible. The same inputs should create the same categories of runs often enough that tests, screenshots, and product validation are stable. This is also the beginning of the future demo workload pack.

**Success looks like:** there are named fixtures for success, loop, and high-cost cases, and a contributor can run them intentionally without guessing which inputs trigger which behavior.

- [ ] Add sample inputs for success case
- [ ] Add sample inputs for loop case
- [ ] Add sample inputs for high-cost case
- [ ] Add expected run outcomes doc

### 1.4 Build scenario matrix

This task expands the demo from "a few example inputs" into a product validation matrix. The matrix should make it easy to see which scenarios exist, which detectors they exercise, and which views they are expected to populate.

**Success looks like:** there is a clear scenario table mapping each seeded run to its expected outcome, anomaly behavior, and UI surfaces.

- [ ] Create scenario matrix doc in `docs/` or `examples/`
- [ ] Map each scenario to expected run outcome
- [ ] Map each scenario to expected anomaly types
- [ ] Map each scenario to expected UI views that should show useful data

**Milestone 1 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 2: Python SDK Core

### 2.1 Package setup

This creates the home for the instrumentation SDK. The goal is to make the package publishable later without overbuilding packaging today. Keep the layout conventional and easy to understand.

**Success looks like:** the SDK package can be installed locally, its source layout is conventional, and tests/docs can be added without moving files around later.

- [ ] Create `packages/python-sdk/pyproject.toml`
- [ ] Create package source layout
- [ ] Add package README stub
- [ ] Add unit test folder for SDK

### 2.2 Base tracing primitives

This task creates the core building blocks everything else depends on: configuration, tracer bootstrap, run context, attribute mapping, and redaction support. These primitives should be small and boring because every adapter will lean on them.

**Success looks like:** later tasks can build adapters and spans using shared primitives instead of duplicating setup logic or ad hoc attribute formatting.

- [ ] Create SDK config object
- [ ] Create tracer initialization helper
- [ ] Create run context model
- [ ] Create helper for OTel attribute mapping
- [ ] Create redaction configuration model

### 2.3 Root run instrumentation

This is the first real product-critical SDK behavior. Every agent run must become a coherent root span with enough metadata to support run views, fleet views, and version comparisons later.

**Success looks like:** one agent run creates one stable root span with agent identity, version, runtime context, and run ID attached in a consistent way.

- [ ] Implement root `invoke_agent` span creation
- [ ] Attach agent name
- [ ] Attach agent version when provided
- [ ] Attach model/provider metadata when provided
- [ ] Attach workload type when provided
- [ ] Attach generated run ID

### 2.4 Nested behavior spans

This task makes traces behaviorally meaningful. Without nested spans, the product collapses back into generic tracing. The helpers here should make planning, tool usage, retrieval, and memory behaviors first-class observability concepts.

**Success looks like:** a single run can express planning, tool execution, retrieval, and memory activity as a navigable span tree instead of one opaque root span.

- [ ] Implement `plan` span helper
- [ ] Implement `execute_tool` span helper
- [ ] Implement `retrieval` span helper
- [ ] Implement memory operation span helper
- [ ] Implement generic event helper for warnings/notes

### 2.5 Raw Python adapter

This task proves the product is not locked to one framework. The raw Python path should be easy to adopt for custom agents and should mirror the same semantic model used for LangGraph.

**Success looks like:** a plain Python agent can be instrumented with a decorator and helper contexts, and it produces traces that look structurally consistent with the framework adapter output.

- [ ] Implement `@trace_agent` decorator
- [ ] Implement nested helper context manager for tools
- [ ] Implement nested helper context manager for planning
- [ ] Implement nested helper context manager for retrieval
- [ ] Add tests for decorator-based tracing

### 2.6 LangGraph adapter

This is the first first-class framework integration and the most important one for `v0.1.0`. The adapter should preserve the LangGraph execution shape while expressing it in a stable OTel-first model.

**Success looks like:** the demo LangGraph workload emits a coherent run tree with root spans, nested behavior spans, and propagated metadata that later services can consume without graph-specific hacks.

- [ ] Define LangGraph wrapper integration surface
- [ ] Map graph lifecycle to run root span
- [ ] Map graph planning step to `plan` span where possible
- [ ] Map tool nodes to `execute_tool` spans
- [ ] Propagate version and run metadata through execution
- [ ] Add adapter tests against demo graph

### 2.7 Privacy defaults in SDK

This task enforces the trust posture at the earliest possible boundary. Sensitive content decisions must happen in the SDK before data fans out into collectors, backends, databases, and UIs.

**Success looks like:** metadata-only mode is the default, unsafe content is absent unless explicitly enabled, and opt-in capture paths are configurable and documented.

- [ ] Set metadata-only mode as default
- [ ] Ensure prompts are not captured by default
- [ ] Ensure tool args are not captured by default
- [ ] Ensure memory content is not captured by default
- [ ] Add opt-in config for truncated or hashed content capture

**Milestone 2 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 3: OTel Export and Jaeger Path

### 3.1 OTLP configuration

This task makes the SDK operationally useful outside local function calls. The exporter path should stay standard and boring: OTLP first, backend-specific details hidden behind configuration.

**Success looks like:** an instrumented agent can emit traces through OTLP to either a collector or direct backend endpoint without code changes in the agent itself.

- [ ] Add SDK exporter configuration for OTLP
- [ ] Support collector endpoint configuration
- [ ] Support direct Jaeger OTLP endpoint configuration
- [ ] Document environment variables for exporter setup

### 3.2 Jaeger local stack

This task creates the primary local proof path for `v0.1.0`. Jaeger is the first backend users should see in docs and local demos, so this setup must feel polished and dependable.

**Success looks like:** a contributor can run the local stack, execute the demo agent, and visibly inspect the generated traces in Jaeger without manual backend debugging.

- [ ] Add Jaeger service to `docker-compose.yml`
- [ ] Add collector service config
- [ ] Validate SDK traces appear in Jaeger UI
- [ ] Capture screenshot or validation note in docs

### 3.3 Tempo compatibility path

This task preserves the long-term OTel positioning of the product. Even though Jaeger is first, Tempo compatibility must be real enough that the architecture does not become accidentally Jaeger-shaped.

**Success looks like:** the same trace data can be viewed in Tempo with only configuration changes, and compatibility notes are documented clearly.

- [ ] Add optional Tempo service config
- [ ] Validate same SDK traces can be viewed in Tempo
- [ ] Document compatibility notes

### 3.4 Collector interoperability checks

This task ensures the product stays OTel-first rather than backend-first. The collector path should be treated as a product contract, not just a local convenience layer.

**Success looks like:** the SDK can emit through the collector path cleanly, backend switching does not require code rewrites, and the collector setup is documented as a first-class integration path.

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

## Milestone 4: Analytics Service Skeleton

### 4.1 Service setup

This creates the service that turns traces into product value. It should start simple, but it must already look like a standalone service with its own config, logging, tests, and lifecycle.

**Success looks like:** analytics can run as its own service process, has a clean project shape, and is ready to own read-model materialization and anomaly logic.

- [ ] Create `services/analytics/pyproject.toml`
- [ ] Create analytics app entrypoint
- [ ] Create analytics config module
- [ ] Create analytics logging setup
- [ ] Add analytics unit test layout

### 4.2 Postgres setup

This task establishes the product read-model database. Because Postgres is the chosen path toward `1.0`, the setup should feel production-shaped even in local development.

**Success looks like:** Postgres runs in the local stack, migrations are wired, and analytics can create and evolve its schema predictably.

- [ ] Add Postgres service to compose stack
- [ ] Create analytics DB connection module
- [ ] Add migration tool setup
- [ ] Create initial schema migration

### 4.3 Read model tables

This task defines the first stable product storage layer. These tables should reflect product concepts, not raw tracing internals, so that the API and UI can work with clean entities.

**Success looks like:** the database has explicit tables for summaries and anomalies, indexes support key lookups, and the schema matches the product vocabulary from the PRD.

- [ ] Create `run_summaries` table
- [ ] Create `anomalies` table
- [ ] Create `fleet_rollups` table or equivalent summary structure
- [ ] Create `version_cohort_summaries` table
- [ ] Add indexes for run lookup and anomaly queries

### 4.4 Trace ingestion path

This task is the bridge between tracing infrastructure and product behavior. The goal is to read trace data once, normalize it cleanly, and stop making the rest of the product think in backend-native shapes.

**Success looks like:** traces from the demo workload can be fetched, parsed, normalized into internal models, and persisted as product-facing records.

- [ ] Decide trace read strategy from Jaeger/collector-accessible source
- [ ] Implement trace fetch/parse job
- [ ] Normalize root run data into internal models
- [ ] Normalize child spans into behavior segments
- [ ] Persist run summaries to Postgres

### 4.5 Background processing loop

This task makes analytics asynchronous and repeatable. It should support both live-ish processing for local use and controlled reprocessing for seeded demo runs and tests.

**Success looks like:** analytics can process new traces in the background, skip already-processed runs safely, and report its own health through logs/metrics.

- [ ] Create async worker loop
- [ ] Add polling or replay strategy for new traces
- [ ] Add idempotency guard for already-processed runs
- [ ] Add logging/metrics for processing success/failure

### 4.6 Reprocessing and rebuild support

This task makes the analytics service resilient to detector evolution. An observability product should be able to rebuild its summaries and anomaly records when logic changes, instead of treating the first computation as immutable truth.

**Success looks like:** a contributor can replay or reprocess stored trace inputs and rebuild materialized run summaries and anomaly records without hand-editing the database.

- [ ] Define reprocessing entrypoint or command
- [ ] Support rerunning summary materialization from trace truth
- [ ] Support rerunning anomaly detection from trace truth
- [ ] Document the rebuild workflow for developers

### 4.7 Analytics self-observability

This task makes the analytics service debuggable as a system in its own right. Since analytics is responsible for derived truth, it must emit enough signals that maintainers can tell whether it is healthy or stale.

**Success looks like:** maintainers can inspect worker lag, processing counts, duplicate-skip behavior, replay success, and read-model freshness without guessing.

- [ ] Emit processed-run counters
- [ ] Emit failed-run counters
- [ ] Emit duplicate-skip counters
- [ ] Emit replay/rebuild counters
- [ ] Record read-model freshness signal

**Milestone 4 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 5: Summary Materialization

### 5.1 Run summary model

This task creates the first product object users will actually feel. The run summary should answer the obvious first questions without forcing a user to inspect every span.

**Success looks like:** every processed run has a summary row with duration, cost, retries, tool counts, and other top-level values needed by both UI and anomaly logic.

- [ ] Define run summary fields
- [ ] Compute total duration
- [ ] Compute tool call count
- [ ] Compute retry count
- [ ] Compute intervention count
- [ ] Compute estimated cost field

### 5.2 Fleet rollups

This task turns isolated runs into fleet-level operational visibility. The rollups should be stable enough to support the fleet board without heavy per-request recomputation.

**Success looks like:** the analytics service materializes grouped summaries by agent/version/workload and those groups can power the fleet UI directly.

- [ ] Group summaries by agent
- [ ] Group summaries by version
- [ ] Group summaries by workload type
- [ ] Compute success/error counts
- [ ] Compute average cost per run
- [ ] Compute anomaly counts per grouping

### 5.3 Version cohort summaries

This task enables meaningful version comparison. The key is to define stable cohort semantics so that compare is not just two arbitrary lists of runs.

**Success looks like:** two versions can be compared through precomputed aggregates for cost, retries, outcomes, and tool usage without expensive ad hoc analysis.

- [ ] Define version comparison cohort inputs
- [ ] Materialize run counts by version
- [ ] Materialize cost aggregates by version
- [ ] Materialize retry aggregates by version
- [ ] Materialize top tool usage counts by version

### 5.4 Workload and cohort dimension support

This task protects the product from becoming too version-only in its thinking. Even in `v0.1.0`, the data model should leave room for meaningful workload and grouping dimensions.

**Success looks like:** summaries can be grouped by more than just agent name, and the fleet and compare views are not blocked from cohorting by workload type or environment.

- [ ] Define minimum cohort dimensions for `v0.1.0`
- [ ] Add workload-type grouping to summary materialization
- [ ] Add environment or deployment grouping if available
- [ ] Document which cohort dimensions are first-class in the first release

### 5.5 Database schema sketch review

This task gives the read-model layer enough explicit shape that future issues and migrations are not invented ad hoc. It is not the final migration set, but it should make the intended tables and lookup patterns concrete.

**Success looks like:** maintainers can point to a documented sketch of the core Postgres tables, their purpose, and their main lookup paths before schema work spreads across services.

- [ ] Document main read-model tables and their purpose
- [ ] Document primary lookup keys per table
- [ ] Document expected rebuild/recompute ownership for each table

**Milestone 5 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 6: Anomaly Engine

### 6.1 Loop detection rule

This is the first detector and the signature anomaly type for the product. It should be simple, explainable, and tied to visible evidence in the run timeline.

**Success looks like:** seeded loop scenarios are reliably detected, the anomaly is persisted, and the explanation clearly states why the run was considered a loop.

- [ ] Define configurable same-tool repetition threshold
- [ ] Detect repeated tool sequences inside a run
- [ ] Mark loop evidence in anomaly record
- [ ] Attach loop count to run summary
- [ ] Add tests with seeded loop demo case

### 6.2 Retry storm rule

This detector catches another common failure shape: agents repeatedly attempting recovery without converging. The rule should remain understandable to operators and not depend on opaque scoring.

**Success looks like:** runs that exceed retry thresholds are flagged with clear evidence and do not require manual counting to verify the detector result.

- [ ] Define retry threshold config
- [ ] Count retries per run
- [ ] Emit retry anomaly when threshold exceeded
- [ ] Add tests with seeded retry case

### 6.3 Cost spike rule

This detector connects observability to business value. It should make expensive runs visible whether they are absolutely expensive or only expensive relative to baseline behavior.

**Success looks like:** a seeded expensive run produces a cost anomaly with enough explanation for a user to understand both the amount and why it was considered unusual.

- [ ] Define absolute threshold config
- [ ] Define baseline-multiplier config
- [ ] Compare current run cost against threshold/baseline
- [ ] Emit cost anomaly record with explanation
- [ ] Add tests with seeded cost case

### 6.4 Anomaly persistence and lifecycle

This task makes anomalies durable product objects instead of transient log lines. The anomaly inbox, alerts, and future review workflows all depend on these records being well-shaped and linkable.

**Success looks like:** anomalies are stored with stable IDs, severity, explanation, timestamps, and run linkage so they can be queried and rendered consistently.

- [ ] Persist anomaly records to Postgres
- [ ] Link anomalies to run ID and agent name
- [ ] Store severity
- [ ] Store explanation text
- [ ] Store created timestamp

### 6.5 Alert output path

This task gives anomalies an outward operational path. Even if the first release keeps it simple, the alert shape should already look like something a real team could route and consume.

**Success looks like:** anomaly records can optionally emit webhook notifications with useful, trace-linked payloads and documented configuration.

- [ ] Define webhook payload shape
- [ ] Add optional webhook emitter
- [ ] Add retry/error handling for webhook delivery
- [ ] Document alert config

### 6.6 Define field-test handoff requirement

This task does not create the full field-test plan yet. It creates the explicit delivery requirement that `v0.1.0` anomaly work is incomplete until a separate field-testing plan exists and is executed later. The purpose is to prevent the team from treating seeded demo validation as sufficient evidence.

**Success looks like:** the WBS and release path explicitly call out that a separate field-test plan must be written later, and anomaly detection is treated as requiring post-implementation validation against broader workloads.

- [ ] Add a release note in docs that anomaly detection requires a dedicated field-test plan
- [ ] List minimum future field-test dimensions: multiple workloads, false positives, detector usefulness, operator feedback
- [ ] Mark field-test planning as a required follow-on artifact before final release confidence claims

### 6.7 Anomaly validation matrix

This task turns detector development into something reviewable. Each detector should have named scenarios it is expected to catch and scenarios it should ignore.

**Success looks like:** there is a detector-by-scenario matrix showing expected true positives and known non-goals, making false-positive discussions much easier later.

- [ ] Create detector validation matrix doc
- [ ] Map loop detector to seeded positive and negative cases
- [ ] Map retry detector to seeded positive and negative cases
- [ ] Map cost detector to seeded positive and negative cases
- [ ] Note known blind spots for each detector in `v0.1.0`

**Milestone 6 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 7: API Service

### 7.1 Service setup

This creates the stable read surface for the product. The service should be intentionally product-shaped rather than just proxying databases or trace backends.

**Success looks like:** the API service runs independently, connects to Postgres cleanly, and has a clear place for product endpoints and tests.

- [ ] Create `services/api/pyproject.toml`
- [ ] Create FastAPI app entrypoint
- [ ] Create DB access layer
- [ ] Create API config module
- [ ] Add API unit/integration test layout

### 7.2 Run timeline endpoint

This is the most important read endpoint in `v0.1.0`. It powers the first proof of value: understanding one broken or expensive run quickly.

**Success looks like:** the UI can request a run by ID and receive everything needed for the timeline, summary header, and anomaly markers in one coherent response model.

- [ ] Define endpoint path and response model
- [ ] Load run summary from Postgres
- [ ] Load trace-linked detail payload
- [ ] Return normalized span tree shape for UI
- [ ] Return anomaly markers for the run

### 7.3 Fleet health endpoint

This endpoint turns materialized summaries into an operator view of many agents at once. It should support the first level of grouping and triage without overcomplicating filtering.

**Success looks like:** the fleet view can load grouped rows with cost, outcome, and anomaly information directly from the API without custom client-side aggregation.

- [ ] Define endpoint path and response model
- [ ] Add agent/version/workload grouping filters
- [ ] Return aggregated fleet rows
- [ ] Add paging/sorting strategy if needed

### 7.4 Version compare endpoint

This endpoint should make version review feel like a first-class product capability rather than a future analytics experiment. The response shape should be intentionally compare-friendly.

**Success looks like:** two version cohorts can be requested and the API returns a stable, digestible set of deltas for cost, retries, tool usage, and outcomes.

- [ ] Define endpoint path and response model
- [ ] Accept version A / version B or cohort filters
- [ ] Return cost delta
- [ ] Return retry delta
- [ ] Return tool usage delta
- [ ] Return outcome counts

### 7.5 Anomaly inbox endpoint

This endpoint powers the triage surface. It should be simple to query, filter, and sort, because users will open it when they need to decide what to look at first.

**Success looks like:** the UI can list anomalies with filters and every anomaly contains enough context to jump straight into investigation.

- [ ] Define endpoint path and response model
- [ ] Return anomaly list
- [ ] Support severity/type/agent filtering
- [ ] Include run link fields

### 7.6 API issue templates for future integrations

This task prepares the API layer to be used beyond the first web app. Even if no public API strategy exists yet, the internal contracts should be explicit and test-friendly.

**Success looks like:** endpoint contracts are consistent enough that future CLI, automation, or external UI integrations would not require redesigning the response model.

- [ ] Document response contract conventions
- [ ] Document error payload conventions
- [ ] Document filtering and sorting conventions across endpoints

### 7.7 Endpoint example payload alignment

This task keeps the spec and implementation synchronized. Since the spec now includes example payloads, the API work should stay traceable to those shapes.

**Success looks like:** implemented endpoint models match or intentionally evolve the documented payload examples, and differences are captured explicitly rather than drifting silently.

- [ ] Cross-check run timeline response against spec example
- [ ] Cross-check fleet health response against spec example
- [ ] Cross-check version compare response against spec example
- [ ] Cross-check anomaly inbox response against spec example

**Milestone 7 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 8: React Web App

### 8.1 App setup

This task establishes the UI foundation for the product views. Keep the setup pragmatic, but make routing, API access, and layout strong enough that later views do not feel bolted on.

**Success looks like:** the web app runs locally, has navigable routes, can call the API, and has a stable foundation for all `v0.1.0` views.

- [ ] Create `apps/web/` app scaffold
- [ ] Add routing
- [ ] Add API client layer
- [ ] Add base layout/navigation
- [ ] Add lint/test baseline

### 8.2 Run timeline view

This is the flagship UI surface. It should make one run explainable quickly and visually, without depending on backend-native trace UIs.

**Success looks like:** a user can enter or open a run, see the summary, inspect the span tree, and identify the problematic section with anomaly markers and detail panels.

- [ ] Create run search/input entry
- [ ] Render run summary header
- [ ] Render span tree / timeline
- [ ] Render per-span detail panel
- [ ] Render anomaly markers in the timeline

### 8.2.1 Run timeline interaction details

This task makes the timeline truly operational rather than just visually interesting. The page should support the exact interactions an operator needs during a real investigation.

**Success looks like:** a user can expand/collapse spans, select a span, inspect summary details, and quickly identify where the run changed course.

- [ ] Add span expand/collapse behavior
- [ ] Add selected-span detail state
- [ ] Add clear display of timing and cost context per span
- [ ] Add visual emphasis for anomaly-linked spans

### 8.3 Fleet health view

This view proves the product is more than a single-trace debugger. It should make it obvious which agents or cohorts deserve attention next.

**Success looks like:** the page loads grouped fleet data, supports useful filters, and makes drill-down into related runs natural.

- [ ] Create fleet table/cards layout
- [ ] Add grouping/filter controls
- [ ] Display cost, success, anomaly counts
- [ ] Add drill-down action into related runs

### 8.3.1 Fleet dashboard detail design

This task specifies the information architecture of the fleet page. Since this is one of the core product views, the cards, columns, and filters should be intentional rather than improvised in implementation.

**Success looks like:** the fleet page has a clearly defined set of top-level cards, grouping controls, table columns, and drill-down actions that reflect the PRD's standard view model.

- [ ] Define top summary cards
- [ ] Define primary grouping controls
- [ ] Define required table columns
- [ ] Define default sort behavior

### 8.4 Version compare view

This view is where observability meets release review. It should help a team answer whether a change improved or degraded behavior without building a notebook.

**Success looks like:** two versions can be selected and the UI presents a clear delta story for cost, retries, tool usage, and outcomes.

- [ ] Create compare selection form
- [ ] Render version A vs B summary cards
- [ ] Render cost/retry/tool delta sections
- [ ] Add drill-down links into exemplar runs

### 8.4.1 Compare view interpretation aids

This task makes compare usable by normal engineers and managers, not only by people comfortable reading raw deltas. The UI should help explain what changed and whether that change likely matters.

**Success looks like:** compare output includes enough labeling, context, and interpretation hints that a reviewer can make a release decision without writing custom analysis.

- [ ] Add explicit "version A vs version B" framing
- [ ] Add positive/negative/neutral visual signals for deltas
- [ ] Add inline explanation labels for each metric block
- [ ] Add quick links to representative runs for both cohorts

### 8.5 Anomaly inbox view

This view should feel like an actionable inbox, not a generic error list. It must prioritize clarity, severity, and direct links into the run context.

**Success looks like:** users can filter anomalies, understand why each one fired, and open the exact run that needs investigation.

- [ ] Render anomaly list
- [ ] Add severity/type filters
- [ ] Show explanation text
- [ ] Link anomaly to run timeline page

### 8.5.1 Inbox triage ergonomics

This task keeps the anomaly inbox from becoming a generic list page. It should support real triage behavior: scan, filter, prioritize, and drill in fast.

**Success looks like:** a user can move from a broad list of anomalies to the one they should investigate next without confusion or extra navigation.

- [ ] Define default sort order for anomalies
- [ ] Add visible severity styling
- [ ] Add anomaly type badges
- [ ] Add one-click drill-down action

**Milestone 8 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 9: End-to-End Local Stack

### 9.1 Compose integration

This task assembles the product into one runnable local system. The compose stack is part of the OSS adoption strategy, so it should be treated like product surface, not internal plumbing.

**Success looks like:** one command (or a very small set of commands) brings up the complete local stack with all required services wired together.

- [ ] Add API service to compose
- [ ] Add analytics service to compose
- [ ] Add web app to compose
- [ ] Add Postgres to compose
- [ ] Add networking and env wiring

### 9.2 Seed and replay workflow

This task makes the local stack demonstrable and testable. A good OSS project should let users reproduce interesting behavior deliberately rather than waiting for it to happen by chance.

**Success looks like:** contributors can run scripts or commands that reliably generate the good run and bad run scenarios needed for demos and tests.

- [ ] Add script to run demo scenarios
- [ ] Add script to seed bad runs
- [ ] Add script or doc to replay traces into the stack

### 9.2.1 Replay acceptance requirement

This subtask makes replay a first-class requirement rather than a nice-to-have script. The product should be demonstrable repeatedly and should support debugging detector changes against stable evidence.

**Success looks like:** the same seeded traces or scenarios can be replayed multiple times to validate instrumentation, analytics, APIs, and UI behaviors predictably.

- [ ] Confirm replay works after clean database reset
- [ ] Confirm replay works after analytics code changes
- [ ] Confirm replay outcomes are documented for demo and test use

### 9.3 End-to-end validation

This task verifies the product loop, not just individual services. It should confirm that trace generation, storage, analytics, APIs, and UI all line up in the ways the PRD promises.

**Success looks like:** the demo scenarios are visible across the whole stack and the core `v0.1.0` views all show meaningful, non-empty data.

- [ ] Validate one normal run
- [ ] Validate one loop anomaly run
- [ ] Validate fleet view shows multiple runs/cohorts
- [ ] Validate version compare shows non-empty deltas

### 9.4 Interoperability smoke checks

This task checks whether the stack still behaves like an OTel-native product rather than a tightly coupled local demo. The goal is to catch hidden assumptions early.

**Success looks like:** the local reference stack proves Jaeger-first operation while preserving collector-first and Tempo-compatible behavior with documented caveats.

- [ ] Smoke test Jaeger-first stack
- [ ] Smoke test Tempo-compatible path
- [ ] Smoke test collector-mediated export
- [ ] Record interop findings in docs

### 9.5 Failure-recovery smoke checks

This task verifies that the chosen architecture can recover from predictable development-time failures. The goal is not full chaos engineering, just enough confidence that the system can be reset and rebuilt without heroics.

**Success looks like:** developers can recover from common failures such as Postgres resets or analytics reprocessing needs using documented workflows.

- [ ] Validate Postgres reset + rebuild flow
- [ ] Validate analytics reprocessing flow after detector changes
- [ ] Validate duplicate-run handling during replay
- [ ] Document known weak recovery paths in `v0.1.0`

**Milestone 9 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 10: Testing and Hardening

### 10.1 SDK tests

This task ensures the instrumentation layer is trustworthy. Since the whole product rests on trace correctness, the SDK must be tested more rigorously than a casual demo library.

**Success looks like:** root spans, nested spans, privacy defaults, and both adapters are covered by tests that catch regressions in trace shape and metadata.

- [ ] Unit tests for root span creation
- [ ] Unit tests for tool span creation
- [ ] Unit tests for privacy defaults
- [ ] Integration tests for LangGraph adapter
- [ ] Integration tests for raw Python decorator

### 10.2 Analytics tests

This task protects the product's interpretation layer. If summaries and anomalies are wrong, the UI can look polished while telling users the wrong story.

**Success looks like:** summary rollups, anomaly detection, and persistence logic are all validated against seeded scenarios and expected outputs.

- [ ] Unit tests for summary materialization
- [ ] Unit tests for loop detector
- [ ] Unit tests for retry detector
- [ ] Unit tests for cost detector
- [ ] Integration tests for Postgres persistence

### 10.3 API tests

This task locks the product contracts. The API should be treated as a stable surface for the UI and future integrations, so response shapes and filtering behavior should not drift silently.

**Success looks like:** each major endpoint has tests for shape, filtering, and representative payloads for the core product views.

- [ ] Test run timeline endpoint
- [ ] Test fleet health endpoint
- [ ] Test version compare endpoint
- [ ] Test anomaly inbox endpoint

### 10.4 Web tests

This task ensures the main views remain navigable and intelligible as the product evolves. Focus on the key interactions that express product value.

**Success looks like:** the main pages render, key filters and navigation work, and at least one end-to-end UI flow can be exercised with confidence.

- [ ] Render tests for key pages
- [ ] Interaction tests for filters/navigation
- [ ] End-to-end happy-path UI test if feasible

### 10.5 Acceptance scenario checks

This task ties tests back to product stories. It should validate not just technical correctness, but whether the product can actually support the main investigation workflows promised in the PRD.

**Success looks like:** at least one automated or semi-automated check exists for each `v0.1.0` standard view using seeded scenarios.

- [ ] Validate single bad run workflow
- [ ] Validate anomaly drill-down workflow
- [ ] Validate fleet triage workflow
- [ ] Validate version compare workflow

### 10.6 Service readiness checks

This task splits release thinking by service so one polished area does not hide another weak one. Each service should have its own readiness signal before overall release validation begins.

**Success looks like:** SDK, analytics, API, web, and docs each have explicit readiness checks and no major service is assumed ready by association.

- [ ] Confirm SDK readiness
- [ ] Confirm analytics service readiness
- [ ] Confirm API service readiness
- [ ] Confirm web app readiness
- [ ] Confirm docs/OSS readiness

**Milestone 10 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 11: Documentation and OSS Readiness

### 11.1 Developer docs

This task turns the internal architecture into something another engineer can actually use. Docs should make the first local success path obvious and reduce hidden setup friction.

**Success looks like:** a new developer can set up the stack, instrument the demo, and understand the service layout by following docs alone.

- [ ] Add local setup doc
- [ ] Add architecture summary doc links
- [ ] Add instrumentation quickstart
- [ ] Add privacy/configuration doc

### 11.1.1 Configuration documentation

This task turns the configuration surface into something maintainable. Since the product spans SDK, analytics, API, and web, configuration drift would otherwise become a hidden source of failure.

**Success looks like:** contributors can find one clear place that lists all major config knobs and understands which service owns each one.

- [ ] Document SDK configuration surface
- [ ] Document analytics configuration surface
- [ ] Document API configuration surface
- [ ] Document web app configuration surface

### 11.2 Product docs

This task explains the product surfaces in user terms. The documentation should help people interpret what they are seeing, not just launch the software.

**Success looks like:** users can understand what each view is for, what an anomaly means, and how to interpret version comparison output.

- [ ] Add "what each view means" doc
- [ ] Add anomaly explanation doc
- [ ] Add version compare interpretation doc

### 11.2.1 Versioning rules documentation

This task makes the compare model understandable. Since version comparison is a product feature, the project should document what counts as a version and how optional version dimensions are expected to behave.

**Success looks like:** users can read one doc and understand the required `agent_version` field, optional secondary version dimensions, and how compare cohorts are formed.

- [ ] Document required `agent_version`
- [ ] Document optional prompt/model/tool-schema version dimensions
- [ ] Document compare cohort expectations and caveats

### 11.3 OSS readiness

This task prepares the repo to receive outside contributors. The goal is to make it obvious where help is welcome and how the monorepo is organized.

**Success looks like:** contribution paths are visible, roadmap context is easy to find, and the repo feels intentionally open rather than merely public.

- [ ] Add contribution guidance for monorepo layout
- [ ] Add contribution areas for adapters/detectors/views
- [ ] Add issue templates if desired
- [ ] Add roadmap reference to PRD/docs

### 11.4 OSS community scaffolding

This task prepares the repo to behave like a serious OSS project instead of a private build log that happens to be public. The goal is to reduce friction for first-time contributors and make the repo legible to people evaluating whether the project is real.

**Success looks like:** the repository has the minimum community and governance surfaces expected of a credible OSS project, and a new visitor can understand how to participate.

- [ ] Add `CODE_OF_CONDUCT.md`
- [ ] Add or refine `CONTRIBUTING.md`
- [ ] Add issue templates for bug, feature request, and adapter proposal
- [ ] Add pull request template
- [ ] Add `SECURITY.md`

### 11.5 OSS maintainer guidance

This task creates the basic maintainer-facing operational layer. It should make it easier to accept contributions, review issues, and explain the project roadmap without improvising policy later.

**Success looks like:** the repo documents who the project is for, what contribution seams are welcomed, how roadmap work is organized, and how maintainers should evaluate incoming changes.

- [ ] Add maintainer notes or `MAINTAINERS.md` if desired
- [ ] Document supported contribution seams: adapters, detectors, views, docs, demo workloads
- [ ] Document how semconv extension proposals should be discussed and tracked
- [ ] Add a short roadmap snapshot for `v0.1.0` and `v0.2.0`

### 11.6 OSS release packaging

This task makes the first public release consumable. It covers the presentation and packaging details that often determine whether an OSS project feels usable or unfinished.

**Success looks like:** the release includes clear install/run instructions, visible screenshots or demo references, and enough packaging polish that someone can evaluate the project without reading the full codebase.

- [ ] Add screenshots or animated captures for key views
- [ ] Add quickstart section for running the local stack
- [ ] Add SDK quickstart for instrumenting one demo agent
- [ ] Add release notes draft for the first OSS release
- [ ] Add known limitations section for `v0.1.0`

### 11.7 GitHub issue generation prep

This task makes the planning docs ready to turn into tracked work items. Since each WBS subsection is intended to become one issue, the repo should have enough structure to make that conversion straightforward.

**Success looks like:** maintainers can lift a subsection into a GitHub issue with minimal rewriting and consistent metadata.

- [ ] Add suggested labels to issue conversion guidance
- [ ] Add dependency notation guidance
- [ ] Add example issue body template in docs if helpful
- [ ] Identify milestone subsections that should become the first issue batch

**Milestone 11 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [ ] Ruff: zero violations (`ruff check .`)
- [ ] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [ ] Tests pass: all unit/integration tests green (`pytest`)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 12: Release Validation

### 12.1 Release criteria check

This task maps the implementation back to the PRD promises. The release should not be considered complete because components exist; it is complete when the core operator outcomes are visibly true.

**Success looks like:** each `v0.1.0` promise can be demonstrated with the local stack using the seeded scenarios and standard views.

- [ ] Confirm one real agent is easier to debug here than with logs alone
- [ ] Confirm run timeline works end-to-end
- [ ] Confirm fleet board works end-to-end
- [ ] Confirm anomaly inbox works end-to-end
- [ ] Confirm version compare works end-to-end
- [ ] Confirm the need for a separate field-test plan is documented and tracked as a required follow-on before stronger production confidence claims

### 12.1.1 Demo acceptance verification

This task explicitly checks the demo acceptance bar instead of assuming it is implied by other validations. Since demo-first is a design choice, the release should prove the demo is actually strong.

**Success looks like:** the product can be shown cleanly through the minimum demo scenarios and each standard view contributes something meaningful to that demonstration.

- [ ] Validate one normal run demo
- [ ] Validate one loop anomaly demo
- [ ] Validate one cost spike anomaly demo
- [ ] Validate one fleet grouping demo
- [ ] Validate one version compare demo

### 12.2 Final packaging

This task makes sure the repo is coherent as a releasable OSS artifact. The main concern is that docs, commands, package layout, and stack orchestration all agree with reality.

**Success looks like:** a clean clone of the repo can boot the stack, install the SDK, and follow the docs without hidden tribal knowledge.

- [ ] Confirm compose stack boots cleanly
- [ ] Confirm SDK package installs locally
- [ ] Confirm docs match actual commands and paths
- [ ] Confirm repo structure is reflected in README

### 12.3 Launch prep

This task prepares the project to be shown and evaluated as a real OSS release. It is about making the first external impression legible and honest.

**Success looks like:** screenshots or demos exist, near-term roadmap items are visible, and `v0.1.0` limitations are written down instead of hidden.

- [ ] Capture screenshots or demo artifacts
- [ ] Prepare initial issues for `v0.2.0`
- [ ] Prepare known limitations doc for `v0.1.0`

### 12.4 Post-release follow-on tracking

This task prevents `v0.1.0` from ending with undocumented next steps. It should capture the immediate follow-ons that are already known from the PRD and WBS.

**Success looks like:** the project has a visible and honest follow-on list covering field testing, additional adapters, richer anomaly work, and deeper interop tasks.

- [ ] Track separate field-test plan as follow-on work
- [ ] Track PydanticAI adapter as follow-on work
- [ ] Track memory review and policy overlay as follow-on work
- [ ] Track `v0.2.0` issue creation as a next step

**Milestone 12 Quality Gates:**
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
