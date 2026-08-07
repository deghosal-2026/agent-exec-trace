# agent-exec-trace-analytics

Behavior analytics service for `agent-exec-trace` — reads raw traces from Jaeger/Tempo via the collector, normalizes spans, runs 35+ deterministic and 5 LLM-augmented anomaly detectors, and writes run summaries and anomalies to a Postgres read model.

## Installation

```bash
pip install agent-exec-trace-analytics
```

Published on [PyPI](https://pypi.org/project/agent-exec-trace-analytics/).

Run with:

```bash
analytics
# or
python -m analytics
```

See the [top-level README](../README.md) and [docs/reference/configuration.md](../docs/reference/configuration.md) for installation and configuration.

## License

MIT — see [LICENSE](../LICENSE).