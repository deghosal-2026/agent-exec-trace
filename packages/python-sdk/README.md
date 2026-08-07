# agent-exec-trace SDK

Instrumentation SDK for `agent-exec-trace`: OpenTelemetry-style observability for AI
agent workflows.

## Installation

```bash
pip install agent-exec-trace
```

Add optional extras for LangGraph integration or OTLP export:

```bash
pip install agent-exec-trace[langgraph]   # LangGraph adapter
pip install agent-exec-trace[otlp]        # OTLP export extras
```

Published on [PyPI](https://pypi.org/project/agent-exec-trace/).

## Overview

The SDK turns agent behavior into OpenTelemetry spans and attributes so runs can be
inspected in Jaeger, Tempo, or any OTLP-compatible backend, then analyzed by the
`agent-exec-trace` analytics service.

## Status

Under active development for `v0.1.0`. Milestones tracked in `docs/wbs-v0.1.0.md`.
