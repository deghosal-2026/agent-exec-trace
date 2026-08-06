# agent-exec-trace v0.1.0 WBS — Part 2-services

> [← Back to WBS Table of Contents](wbs-v0.1.0.md)


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

