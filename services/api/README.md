# agent-exec-trace-api

Read API service for `agent-exec-trace` — serves product-facing views (run timeline, fleet health, version compare, anomaly inbox) from the normalized Postgres read model.

## Installation

```bash
pip install agent-exec-trace-api
```

Published on [PyPI](https://pypi.org/project/agent-exec-trace-api/).

Run with:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

See the [top-level README](../README.md) and [docs/reference/configuration.md](../docs/reference/configuration.md) for installation and configuration.

## License

MIT — see [LICENSE](../LICENSE).