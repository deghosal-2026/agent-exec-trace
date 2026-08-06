# agent-exec-trace v0.1.0 Work Breakdown Structure

> Checklist-style, granular, execution-oriented breakdown for `v0.1.0`.
> This file is the table of contents. Each part is a standalone document.

## Parts

| Part | Milestones | Focus |
|------|-----------|-------|
| [Part 1](wbs-v0.1.0-part1-foundation.md) | M0, M1, M2, M3 | Foundation, demo agent, Python SDK, OTel export |
| [Part 2](wbs-v0.1.0-part2-services.md) | M4, M5, M6, M7, M8 | Analytics service, materialization, anomaly engine, API, web UI |
| [Part 3](wbs-v0.1.0-part3-detection.md) | M8.6, M8.7, M8.8, M8.9, M9 | Robust detectors, LLM augmentation, trace datasets, field tests, compatibility |
| [Part 4](wbs-v0.1.0-part4-ship.md) | M10, M11, M12, M13, M14 | Local stack, e2e Playwright, docs/OSS, LLM validation + GitHub agent integration, release validation |

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
| Milestone 10 | local stack/demo + service-level testing issues ✅ |
| Milestone 11 | e2e Playwright testing and screenshot validation ✅ |
| Milestone 12 | documentation/OSS readiness issues ✅ |
| Milestone 13 | LLM validation on synthetic traces + GitHub agent SDK integration |
| Milestone 14 | release validation issues |

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

### Wave 4

- Milestone 8.8
- Milestone 8.9
- Milestone 9

### Wave 5

- Milestone 10
- Milestone 11
- Milestone 12
- Milestone 13

## Minimum Definition of Field Test

A field test is the structured execution of the anomaly detection pipeline against a representative corpus of real agent traces with documented ground-truth expectations. It validates that core detectors fire on known failure patterns, thresholds keep false positives manageable, and the system can process a high-volume trace set without data loss.

Key attributes:
- Uses real (not synthetic-only) traces from Hugging Face or similar corpora
- Documents detector fire rate and FP/TP classification for review
- Produces a report with the review sheet and a compatibility matrix
- Field tests must be reproducible and re-runnable

Seeded demo validation is necessary, but it does not count as the full field test.

## Release Blockers

Before declaring `v0.1.0` complete, these must be TRUE:

- `docker compose up -d --build` brings up all services with no errors
- Demo scenarios can be seeded and replayed
- All 35 rule-based detectors pass against synthetic traces
- At least one non-trivial external trace corpus has been validated
- The web UI displays anomalies, fleet rollup, and compare views
- The field-test plan is written and reviewable
- A field-test report exists with per-detector TP/FP analysis
- No known data-loss bugs in the ingestion pipeline

## Non-Functional Expectations

Throughout the WBS, all work should satisfy:

- **Deterministic:** Detector outputs must be reproducible given the same trace data and configuration (except where LLM detectors are enabled, where results are non-deterministic but degrade gracefully).
- **Explainable:** Every anomaly must carry a human-readable explanation in its evidence payload.
- **Testable:** Every detector must have at least one positive and one negative test case.
- **Configurable:** Thresholds are exposed via environment variables, not hardcoded magic numbers.
- **Observable:** The analytics worker exposes per-detector metrics and health signals.

## Trace Replay and Reprocessing Requirement

The analytics pipeline must support replay and reprocessing of traces. This is a design requirement, not a nice-to-have:

- seeded traces can be replayed intentionally
- processed traces can be re-processed after detector changes
- all reprocessed traces must produce matching results given the same detector code and configuration

## Known `v0.1.0` Limitation Tracking

Known limitations tracked for future:
- No streaming trace ingestion (batch-only via Jaeger polling)
- No distributed trace correlation across services
- No multi-tenant isolation
- LLM detectors are optional and not validated against production workloads
- field testing still pending beyond seeded demo validation
- Trace replay depends on Jaeger being available

## Demo Acceptance Bar

Before declaring the product complete for `v0.1.0`, all acceptance criteria from [Milestone 11 Part 4](wbs-v0.1.0-part4-ship.md) section 11.7 must pass.

## Docs Structure

```
docs/
├── wbs-v0.1.0.md                       ← this file (TOC)
├── architecture/                       ← architecture, spec, schema
│   ├── architecture-v0.1.0.md
│   ├── spec-v0.1.0.md
│   └── db-schema-sketch.md
├── design/                             ← PRD, agent designs, CLI plans
│   ├── prd.md
│   ├── synthetic-agent-design.md
│   ├── trace-dataset-sources.md
│   ├── validate-cli-design.md
│   ├── validate-cli-plan.md
│   └── demo-scenario.md
├── field-test/                         ← field-test plans and reports
│   ├── field-test-plan.md
│   ├── field-test-report-v1.md
│   ├── field-test-report-v2.md
│   ├── field-test-report-synthetic.md
│   └── anomaly-validation-matrix.md
├── reference/                          ← developer setup, config references
│   └── developer-setup.md
└── wbs/                                ← detailed WBS parts
    ├── wbs-v0.1.0-part1-foundation.md
    ├── wbs-v0.1.0-part2-services.md
    ├── wbs-v0.1.0-part3-detection.md
    └── wbs-v0.1.0-part4-ship.md
```