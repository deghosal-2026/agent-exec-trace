# Issue Conversion Guide

How to convert WBS subsections into trackable GitHub issues, sourced from the
conversion notes in `docs/wbs/wbs-v0.1.0.md`.

## Issue body template

Each WBS subsection maps to one GitHub issue (not one checkbox per issue).
Use this body shape:

```markdown
## Context
<!-- Why this work matters and what problem it solves. -->

## Checklist
<!-- Task-level breakdown. Copy the WBS checkboxes here. -->

- [ ] ...
- [ ] ...

## Success Criteria
<!-- What "done" looks like. Concrete, verifiable outcomes. -->

- [ ] ...

## Dependencies
<!-- Blocking issues or prerequisites. -->

Depends on: #123, #456

## Suggested Labels
<!-- Label families from the taxonomy below. -->

sdk, wbs-v0.2.0
```

## Label families

Apply one or more of these labels to every issue:

| Label | Scope |
|---|---|
| `sdk` | Python SDK, adapters, instrumentation |
| `analytics` | Analytics pipeline, detectors, materializers |
| `api` | REST API endpoints, query layer |
| `web` | Web UI, frontend components |
| `infra` | Docker, CI, local stack, deployment |
| `docs` | Documentation, guides, reference files |
| `oss` | OSS readiness, licensing, community prep |
| `field-test` | Field test execution and reporting |
| `demo` | Demo agent scenarios and seed data |

Specialised type labels (can overlap with family labels):

| Label | Scope |
|---|---|
| `adapter` | New framework/runtime adapter |
| `detector` | New or improved anomaly detector |
| `view` | New UI view or major feature |
| `backend` | Backend service work |
| `interop` | Cross-framework or cross-service compatibility |
| `db` | Schema changes, migrations |
| `design-followup` | Design debt or deferred decisions |

**Milestone tracking**: add the `wbs-v0.2.0` label to every issue targeting
the `v0.2.0` release so they can be filtered as a group.

## Dependency notation

Declare dependencies at the bottom of the issue body:

```
Depends on: #123, #456
```

Do not use GitHub's "blocked by" linked-issue field; keep dependencies
readable in plain text. The notation supports multiple issue references.
If an issue has no dependencies, omit the section.

## Suggested ownership buckets

Assign each issue to one of these ownership areas:

| Bucket | Typical scope |
|---|---|
| **SDK** | Python SDK, adapters (LangGraph, PydanticAI, raw), config |
| **Analytics** | Pipeline, detectors, materializers, anomaly engine |
| **API** | FastAPI routes, query layer, response models |
| **Web** | React UI, views, components |
| **Infra** | Docker Compose, CI, seed scripts, local stack |
| **Docs / OSS** | Documentation, README, changelog, licensing |

## First batch: v0.2.0 issues

The following issues are the initial batch for `v0.2.0`, derived from the
v0.1.0 WBS follow-on tracking and from known limitations in
`docs/reference/limitations.md`.

### PydanticAI adapter

- **Bucket:** SDK
- **Labels:** `sdk`, `adapter`, `wbs-v0.2.0`
- **Context:** The SDK currently supports LangGraph and raw Python only.
  PydanticAI users must use manual instrumentation. A first-class adapter
  validates that the span schema is truly framework-agnostic and unblocks a
  growing framework community.
- **Depends on:** none

### Span tree materialization in API

- **Bucket:** API
- **Labels:** `api`, `backend`, `interop`, `wbs-v0.2.0`
- **Context:** Seeded e2e data includes run summaries and anomalies but span
  trees are empty. Real span trees require live traces in Jaeger processed by
  the analytics worker. This issue covers materialising span trees from live
  traces into the API response.
- **Depends on:** none

### Cross-browser Playwright smoke

- **Bucket:** Infra
- **Labels:** `infra`, `web`, `wbs-v0.2.0`
- **Context:** Current Playwright tests run Chromium only. A cross-browser
  smoke test (Firefox, WebKit) ensures no rendering regressions on other
  engines. Full parity is not required — a smoke is sufficient.
- **Depends on:** none

### CI integration for e2e

- **Bucket:** Infra
- **Labels:** `infra`, `wbs-v0.2.0`
- **Context:** Add a CI job that gates merges on e2e test pass. Non-blocking
  on optional cross-browser results.
- **Depends on:** Cross-browser Playwright smoke

### Policy overlay view

- **Bucket:** Web
- **Labels:** `web`, `view`, `wbs-v0.2.0`
- **Context:** No UI surface exists for reviewing policy evaluations
  (guardrail checks, content filters, approval rules) against agent traces.
  Operators cannot audit which policies fired on which runs.
- **Depends on:** none

### Memory audit UI

- **Bucket:** Web
- **Labels:** `web`, `view`, `wbs-v0.2.0`
- **Context:** The SDK can emit `memory` spans but there is no dedicated view
  for reviewing agent memory state. Operators cannot debug memory corruption,
  stale context, or unintended persistence through the UI.
- **Depends on:** none

### LLM detector production validation

- **Bucket:** Analytics
- **Labels:** `analytics`, `detector`, `field-test`, `wbs-v0.2.0`
- **Context:** LLM detectors were deferred from v0.1.0 because model response
  quality was insufficient for structured JSON judging. Code and
  instrumentation are in place. This issue covers switching to a capable
  model, tightening prompts, and validating against production-like workloads.
- **Depends on:** none

### Streaming trace ingestion

- **Bucket:** Analytics
- **Labels:** `analytics`, `backend`, `wbs-v0.2.0`
- **Context:** Traces are ingested via batch polling only (default 30s
  interval). Real-time streaming ingestion via OTLP directly into the
  analytics pipeline is needed for sub-second alerting.
- **Depends on:** none