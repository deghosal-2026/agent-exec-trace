# M13.1 — 3-Way Comparison: No-LLM vs LLM-4B vs LLM-9B

**Traces sampled:** 100

| Metric | No LLM | LLM 4B | LLM 9B |
|---|---|---|---|
| Total anomalies | 508 | 610 | 637 |
| Types fired | 15 | 18 | 17 |
| LLM-only types fired | — | 3 | 2 |

## Per-Detector Breakdown

| Anomaly Type | No LLM | LLM 4B | LLM 9B | Δ 4B | Δ 9B | Category |
|---|---|---|---|---|---|---|
| `argument_loop` | 1 | 1 | 1 | 0 | 0 | rule-based |
| `confusion_pattern` | 0 | 3 | 31 | +3 | +31 | llm-only |
| `cost_efficiency` | 4 | 4 | 4 | 0 | 0 | rule-based |
| `hallucination` | 0 | 98 | 98 | +98 | +98 | llm-only |
| `inactivity` | 95 | 95 | 95 | 0 | 0 | rule-based |
| `intervention_frequency` | 9 | 9 | 9 | 0 | 0 | rule-based |
| `loop` | 26 | 26 | 26 | 0 | 0 | rule-based |
| `low_output` | 37 | 37 | 37 | 0 | 0 | rule-based |
| `max_step_hit` | 22 | 22 | 22 | 0 | 0 | rule-based |
| `pattern_loop` | 1 | 1 | 1 | 0 | 0 | rule-based |
| `quality_degradation` | 0 | 1 | 0 | +1 | 0 | llm-only |
| `recovery_path` | 64 | 64 | 64 | 0 | 0 | rule-based |
| `retry_storm` | 25 | 25 | 25 | 0 | 0 | rule-based |
| `specific_tool_error` | 43 | 43 | 43 | 0 | 0 | rule-based |
| `step_efficiency` | 0 | 0 | 0 | 0 | 0 | rule-based |
| `token_explosion` | 1 | 1 | 1 | 0 | 0 | rule-based |
| `tool_latency` | 37 | 37 | 37 | 0 | 0 | rule-based |
| `tool_timeout` | 78 | 78 | 78 | 0 | 0 | rule-based |
| `wasted_tool_calls` | 65 | 65 | 65 | 0 | 0 | rule-based |

_Report saved to `data/m13/comparison/comparison.json`_