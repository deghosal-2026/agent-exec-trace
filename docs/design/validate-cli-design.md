# #83 — `validate` CLI design

New `validate` command in `analytics.main` for batch detector validation against 150K traces.

## Two modes

```
analytics validate --input data/traces/processed
analytics validate --input data/traces/processed --llm-sample 1000
```

## Components

- `trace_pipeline/validator.py` — `Validator` class: load parquet, run detectors, build reports
- `main.py` — wire `validate` Click command
- Output: `data/traces/validations/without-llm/` and `with-llm/`
  - `summary.json`, `correlation.json`, `traces.json`

## Reports

- Anomaly distribution per detector
- Suspicious-pattern flag (>50% fire rate)
- Cross-detector co-fire matrix
- LLM-vs-rule-based comparison (when --llm-sample used)
