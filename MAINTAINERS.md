# Maintainers

## Current Maintainer

- **deghosal** — deghosal@gmail.com

## What Maintainers Do

- **Review PRs** — Ensure contributions meet quality gates (ruff, mypy, pytest,
  coverage) and align with the project's design philosophy.
- **Triage Issues** — Label, prioritize, and respond to bug reports, feature
  requests, and adapter proposals.
- **Guide the Roadmap** — Decide which adapters to prioritize, which detectors
  to ship, and when to cut releases.

## Contribution Seams

Maintainers actively review and support contributions in these areas:

| Seam           | Description                                          |
| -------------- | ---------------------------------------------------- |
| Adapters       | Instrumentation for new agent frameworks (LangGraph, CrewAI, etc.) |
| Detectors      | New anomaly detection algorithms and heuristics      |
| Views          | Dashboard and visualization improvements             |
| Docs           | Guides, examples, architecture records               |
| Demo Workloads | Realistic agent traces for testing and benchmarking  |

## Becoming a Maintainer

Maintainers are contributors who have demonstrated:

- A track record of **sustained, high-quality contributions** (code, reviews,
  docs).
- **Domain expertise** in one or more areas: OpenTelemetry, agent frameworks,
  observability systems, or anomaly detection.
- Good judgment and constructive communication in discussions.

If that sounds like you, reach out to an existing maintainer. There is no
formal application — it starts with doing the work.

## Decision Log

Proposals that affect the semantic conventions (new span types, attribute keys,
operation names) are discussed in GitHub issues and must be accepted before
implementation. Accepted decisions are documented in `docs/architecture/`.

## Roadmap Snapshot

| Version | Focus                                                        |
| ------- | ------------------------------------------------------------ |
| v0.1.0  | Core SDK, LangGraph adapter, CrewAI adapter, basic detectors |
| v0.2.0  | PydanticAI adapter, memory/policy overlay, field tests       |

The roadmap is a living document. Priorities shift based on community needs.

## Semantic Convention Extensions

To propose a new span type, attribute key, or operation name:

1. Open an issue with the `adapter` or `enhancement` label.
2. Describe the use case and why existing conventions do not cover it.
3. Propose the new key names, value types, and expected cardinality.
4. Reference any relevant OpenTelemetry semantic conventions.

Proposals are discussed openly and become part of the project's semconv
extensions once a maintainer approves them. Finalized extensions are
documented in `docs/architecture/semconv-extensions.md`.
