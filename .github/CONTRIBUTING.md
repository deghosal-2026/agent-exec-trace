# Contributing to agent-exec-trace

Thanks for your interest in contributing! agent-exec-trace provides
OpenTelemetry-based observability for AI agent workflows — tracing tool calls,
sub-agent invocations, guardrail checks, and state transitions across
frameworks like LangGraph and CrewAI.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code. Please report
unacceptable behavior to deghosal@gmail.com.

## Ways to Contribute

- **Adapters** — Add instrumentation for a new agent framework
  (e.g. AutoGen, Semantic Kernel, LlamaIndex agents).
- **Detectors** — Implement new anomaly detection algorithms or heuristics
  (e.g. looping agents, tool call storms, stale state).
- **Views** — Build or improve dashboard views in the web app.
- **Docs** — Improve documentation, add examples, fix typos.
- **Demo Workloads** — Contribute realistic agent workflow traces for
  testing and benchmarking.

## Development Setup

```bash
make setup       # install dependencies, pre-commit hooks
make stack-up    # start local services (collector, DB, web app)
make test        # run the full test suite
```

Requires Python 3.11+ and Docker.

## Quality Gates

Before opening a pull request, ensure:

- `ruff check` passes with zero warnings
- `mypy --strict` passes with zero errors
- `pytest` is green
- Test coverage is above 90%

## Testing Policy

New features and major functionality changes must include tests added to the
automated test suite (`pytest`). Bug fixes should include a regression test
that reproduces the bug. All tests and coverage checks run automatically
via GitHub Actions on every push and pull request.

## Pull Request Process

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/my-thing`).
3. Make your changes and write tests.
4. Run the quality gates locally (`make test`).
5. Open a pull request against `main`.
6. A maintainer will review. Address feedback and the PR will be merged.

## Monorepo Layout

```
agent-exec-trace/
├── sdk/                  # Python SDK — core instrumentation
├── adapters/             # Framework-specific instrumentation
│   ├── langgraph/        #   LangGraph adapter
│   └── crewai/           #   CrewAI adapter
├── services/             # Backend collector and processor
├── web/                  # Web dashboard (React / FastAPI)
├── docs/                 # Documentation and architecture decisions
│   └── architecture/     #   Decision records and proposals
├── tests/                # Cross-package integration tests
└── demos/                # Demo workloads and traces
```

## Style Guide

- Follow existing patterns in the codebase. Look at adjacent modules for
  conventions on naming, structure, and error handling.
- No magic numbers. Use named constants or configuration.
- Configuration comes from environment variables, never hard-coded.
- Type annotations are required. All new code must pass `mypy --strict`.
- Use `ruff` for formatting and linting (default configuration in
  `pyproject.toml`).

## Issue Tracking

We use labels to organize issues:

| Label         | Purpose                                      |
| ------------- | -------------------------------------------- |
| `bug`         | Something is broken                          |
| `enhancement` | A new feature or improvement                 |
| `adapter`     | A request or proposal for a new adapter      |
| `docs`        | Documentation changes                        |
| `good first issue` | Accessible entry points for new contributors |

Use issue templates when available — they help us triage faster.
