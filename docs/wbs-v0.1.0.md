# agent-exec-trace v0.1.0 Work Breakdown Structure

> Checklist-style, granular, execution-oriented breakdown for `v0.1.0`.

## Milestone 0: Foundation and Repo Layout

### 0.1 Create monorepo skeleton
- [ ] Create `packages/python-sdk/`
- [ ] Create `services/api/`
- [ ] Create `services/analytics/`
- [ ] Create `apps/web/`
- [ ] Create `deploy/`
- [ ] Create `examples/`
- [ ] Create `tests/`

### 0.2 Add root project scaffolding
- [ ] Add root `README.md` section for monorepo layout
- [ ] Add root `.gitignore` updates for monorepo paths
- [ ] Add root `Makefile` or task runner entrypoints
- [ ] Add root `docker-compose.yml` placeholder for local stack
- [ ] Add root developer setup doc in `docs/`

### 0.3 Choose and wire shared dev conventions
- [ ] Define Python version target
- [ ] Define Node version target for web app
- [ ] Define formatting/lint tools for Python
- [ ] Define formatting/lint tools for web app
- [ ] Add pre-commit or equivalent baseline hooks if desired

---

## Milestone 1: Demo-First Agent Workload

### 1.1 Create first demo agent scenario
- [ ] Choose one LangGraph demo agent scenario
- [ ] Document what "bad run" looks like for this agent
- [ ] Document what normal run looks like for this agent
- [ ] Define one seeded loop scenario
- [ ] Define one seeded high-cost scenario

### 1.2 Implement demo agent skeleton
- [ ] Create example LangGraph app folder under `examples/`
- [ ] Add minimal graph workflow
- [ ] Add at least one tool call path
- [ ] Add at least one path that can loop under seeded conditions
- [ ] Add version metadata injection for the example

### 1.3 Define demo datasets / fixtures
- [ ] Add sample inputs for success case
- [ ] Add sample inputs for loop case
- [ ] Add sample inputs for high-cost case
- [ ] Add expected run outcomes doc

---

## Milestone 2: Python SDK Core

### 2.1 Package setup
- [ ] Create `packages/python-sdk/pyproject.toml`
- [ ] Create package source layout
- [ ] Add package README stub
- [ ] Add unit test folder for SDK

### 2.2 Base tracing primitives
- [ ] Create SDK config object
- [ ] Create tracer initialization helper
- [ ] Create run context model
- [ ] Create helper for OTel attribute mapping
- [ ] Create redaction configuration model

### 2.3 Root run instrumentation
- [ ] Implement root `invoke_agent` span creation
- [ ] Attach agent name
- [ ] Attach agent version when provided
- [ ] Attach model/provider metadata when provided
- [ ] Attach workload type when provided
- [ ] Attach generated run ID

### 2.4 Nested behavior spans
- [ ] Implement `plan` span helper
- [ ] Implement `execute_tool` span helper
- [ ] Implement `retrieval` span helper
- [ ] Implement memory operation span helper
- [ ] Implement generic event helper for warnings/notes

### 2.5 Raw Python adapter
- [ ] Implement `@trace_agent` decorator
- [ ] Implement nested helper context manager for tools
- [ ] Implement nested helper context manager for planning
- [ ] Implement nested helper context manager for retrieval
- [ ] Add tests for decorator-based tracing

### 2.6 LangGraph adapter
- [ ] Define LangGraph wrapper integration surface
- [ ] Map graph lifecycle to run root span
- [ ] Map graph planning step to `plan` span where possible
- [ ] Map tool nodes to `execute_tool` spans
- [ ] Propagate version and run metadata through execution
- [ ] Add adapter tests against demo graph

### 2.7 Privacy defaults in SDK
- [ ] Set metadata-only mode as default
- [ ] Ensure prompts are not captured by default
- [ ] Ensure tool args are not captured by default
- [ ] Ensure memory content is not captured by default
- [ ] Add opt-in config for truncated or hashed content capture

---

## Milestone 3: OTel Export and Jaeger Path

### 3.1 OTLP configuration
- [ ] Add SDK exporter configuration for OTLP
- [ ] Support collector endpoint configuration
- [ ] Support direct Jaeger OTLP endpoint configuration
- [ ] Document environment variables for exporter setup

### 3.2 Jaeger local stack
- [ ] Add Jaeger service to `docker-compose.yml`
- [ ] Add collector service config
- [ ] Validate SDK traces appear in Jaeger UI
- [ ] Capture screenshot or validation note in docs

### 3.3 Tempo compatibility path
- [ ] Add optional Tempo service config
- [ ] Validate same SDK traces can be viewed in Tempo
- [ ] Document compatibility notes

---

## Milestone 4: Analytics Service Skeleton

### 4.1 Service setup
- [ ] Create `services/analytics/pyproject.toml`
- [ ] Create analytics app entrypoint
- [ ] Create analytics config module
- [ ] Create analytics logging setup
- [ ] Add analytics unit test layout

### 4.2 Postgres setup
- [ ] Add Postgres service to compose stack
- [ ] Create analytics DB connection module
- [ ] Add migration tool setup
- [ ] Create initial schema migration

### 4.3 Read model tables
- [ ] Create `run_summaries` table
- [ ] Create `anomalies` table
- [ ] Create `fleet_rollups` table or equivalent summary structure
- [ ] Create `version_cohort_summaries` table
- [ ] Add indexes for run lookup and anomaly queries

### 4.4 Trace ingestion path
- [ ] Decide trace read strategy from Jaeger/collector-accessible source
- [ ] Implement trace fetch/parse job
- [ ] Normalize root run data into internal models
- [ ] Normalize child spans into behavior segments
- [ ] Persist run summaries to Postgres

### 4.5 Background processing loop
- [ ] Create async worker loop
- [ ] Add polling or replay strategy for new traces
- [ ] Add idempotency guard for already-processed runs
- [ ] Add logging/metrics for processing success/failure

---

## Milestone 5: Summary Materialization

### 5.1 Run summary model
- [ ] Define run summary fields
- [ ] Compute total duration
- [ ] Compute tool call count
- [ ] Compute retry count
- [ ] Compute intervention count
- [ ] Compute estimated cost field

### 5.2 Fleet rollups
- [ ] Group summaries by agent
- [ ] Group summaries by version
- [ ] Group summaries by workload type
- [ ] Compute success/error counts
- [ ] Compute average cost per run
- [ ] Compute anomaly counts per grouping

### 5.3 Version cohort summaries
- [ ] Define version comparison cohort inputs
- [ ] Materialize run counts by version
- [ ] Materialize cost aggregates by version
- [ ] Materialize retry aggregates by version
- [ ] Materialize top tool usage counts by version

---

## Milestone 6: Anomaly Engine

### 6.1 Loop detection rule
- [ ] Define configurable same-tool repetition threshold
- [ ] Detect repeated tool sequences inside a run
- [ ] Mark loop evidence in anomaly record
- [ ] Attach loop count to run summary
- [ ] Add tests with seeded loop demo case

### 6.2 Retry storm rule
- [ ] Define retry threshold config
- [ ] Count retries per run
- [ ] Emit retry anomaly when threshold exceeded
- [ ] Add tests with seeded retry case

### 6.3 Cost spike rule
- [ ] Define absolute threshold config
- [ ] Define baseline-multiplier config
- [ ] Compare current run cost against threshold/baseline
- [ ] Emit cost anomaly record with explanation
- [ ] Add tests with seeded cost case

### 6.4 Anomaly persistence and lifecycle
- [ ] Persist anomaly records to Postgres
- [ ] Link anomalies to run ID and agent name
- [ ] Store severity
- [ ] Store explanation text
- [ ] Store created timestamp

### 6.5 Alert output path
- [ ] Define webhook payload shape
- [ ] Add optional webhook emitter
- [ ] Add retry/error handling for webhook delivery
- [ ] Document alert config

---

## Milestone 7: API Service

### 7.1 Service setup
- [ ] Create `services/api/pyproject.toml`
- [ ] Create FastAPI app entrypoint
- [ ] Create DB access layer
- [ ] Create API config module
- [ ] Add API unit/integration test layout

### 7.2 Run timeline endpoint
- [ ] Define endpoint path and response model
- [ ] Load run summary from Postgres
- [ ] Load trace-linked detail payload
- [ ] Return normalized span tree shape for UI
- [ ] Return anomaly markers for the run

### 7.3 Fleet health endpoint
- [ ] Define endpoint path and response model
- [ ] Add agent/version/workload grouping filters
- [ ] Return aggregated fleet rows
- [ ] Add paging/sorting strategy if needed

### 7.4 Version compare endpoint
- [ ] Define endpoint path and response model
- [ ] Accept version A / version B or cohort filters
- [ ] Return cost delta
- [ ] Return retry delta
- [ ] Return tool usage delta
- [ ] Return outcome counts

### 7.5 Anomaly inbox endpoint
- [ ] Define endpoint path and response model
- [ ] Return anomaly list
- [ ] Support severity/type/agent filtering
- [ ] Include run link fields

---

## Milestone 8: React Web App

### 8.1 App setup
- [ ] Create `apps/web/` app scaffold
- [ ] Add routing
- [ ] Add API client layer
- [ ] Add base layout/navigation
- [ ] Add lint/test baseline

### 8.2 Run timeline view
- [ ] Create run search/input entry
- [ ] Render run summary header
- [ ] Render span tree / timeline
- [ ] Render per-span detail panel
- [ ] Render anomaly markers in the timeline

### 8.3 Fleet health view
- [ ] Create fleet table/cards layout
- [ ] Add grouping/filter controls
- [ ] Display cost, success, anomaly counts
- [ ] Add drill-down action into related runs

### 8.4 Version compare view
- [ ] Create compare selection form
- [ ] Render version A vs B summary cards
- [ ] Render cost/retry/tool delta sections
- [ ] Add drill-down links into exemplar runs

### 8.5 Anomaly inbox view
- [ ] Render anomaly list
- [ ] Add severity/type filters
- [ ] Show explanation text
- [ ] Link anomaly to run timeline page

---

## Milestone 9: End-to-End Local Stack

### 9.1 Compose integration
- [ ] Add API service to compose
- [ ] Add analytics service to compose
- [ ] Add web app to compose
- [ ] Add Postgres to compose
- [ ] Add networking and env wiring

### 9.2 Seed and replay workflow
- [ ] Add script to run demo scenarios
- [ ] Add script to seed bad runs
- [ ] Add script or doc to replay traces into the stack

### 9.3 End-to-end validation
- [ ] Validate one normal run
- [ ] Validate one loop anomaly run
- [ ] Validate fleet view shows multiple runs/cohorts
- [ ] Validate version compare shows non-empty deltas

---

## Milestone 10: Testing and Hardening

### 10.1 SDK tests
- [ ] Unit tests for root span creation
- [ ] Unit tests for tool span creation
- [ ] Unit tests for privacy defaults
- [ ] Integration tests for LangGraph adapter
- [ ] Integration tests for raw Python decorator

### 10.2 Analytics tests
- [ ] Unit tests for summary materialization
- [ ] Unit tests for loop detector
- [ ] Unit tests for retry detector
- [ ] Unit tests for cost detector
- [ ] Integration tests for Postgres persistence

### 10.3 API tests
- [ ] Test run timeline endpoint
- [ ] Test fleet health endpoint
- [ ] Test version compare endpoint
- [ ] Test anomaly inbox endpoint

### 10.4 Web tests
- [ ] Render tests for key pages
- [ ] Interaction tests for filters/navigation
- [ ] End-to-end happy-path UI test if feasible

---

## Milestone 11: Documentation and OSS Readiness

### 11.1 Developer docs
- [ ] Add local setup doc
- [ ] Add architecture summary doc links
- [ ] Add instrumentation quickstart
- [ ] Add privacy/configuration doc

### 11.2 Product docs
- [ ] Add "what each view means" doc
- [ ] Add anomaly explanation doc
- [ ] Add version compare interpretation doc

### 11.3 OSS readiness
- [ ] Add contribution guidance for monorepo layout
- [ ] Add contribution areas for adapters/detectors/views
- [ ] Add issue templates if desired
- [ ] Add roadmap reference to PRD/docs

---

## Milestone 12: Release Validation

### 12.1 Release criteria check
- [ ] Confirm one real agent is easier to debug here than with logs alone
- [ ] Confirm run timeline works end-to-end
- [ ] Confirm fleet board works end-to-end
- [ ] Confirm anomaly inbox works end-to-end
- [ ] Confirm version compare works end-to-end

### 12.2 Final packaging
- [ ] Confirm compose stack boots cleanly
- [ ] Confirm SDK package installs locally
- [ ] Confirm docs match actual commands and paths
- [ ] Confirm repo structure is reflected in README

### 12.3 Launch prep
- [ ] Capture screenshots or demo artifacts
- [ ] Prepare initial issues for `v0.2.0`
- [ ] Prepare known limitations doc for `v0.1.0`

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
