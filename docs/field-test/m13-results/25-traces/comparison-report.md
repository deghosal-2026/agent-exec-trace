# M13.1 — 3-Way Comparison: No-LLM vs LLM-4B vs LLM-9B

**Traces sampled:** 25

| Metric | No LLM | LLM 4B | LLM 9B |
|---|---|---|---|
| Total anomalies | 117 | 142 | 153 |
| Types fired | 12 | 14 | 14 |
| LLM-only types fired | — | 2 | 2 |

## Per-Detector Breakdown

| Anomaly Type | No LLM | LLM 4B | LLM 9B | Δ 4B | Δ 9B | Category |
|---|---|---|---|---|---|---|
| `confusion_pattern` | 0 | 1 | 12 | +1 | +12 | llm-only |
| `cost_efficiency` | 3 | 3 | 3 | 0 | 0 | rule-based |
| `hallucination` | 0 | 24 | 24 | +24 | +24 | llm-only |
| `inactivity` | 24 | 24 | 24 | 0 | 0 | rule-based |
| `intervention_frequency` | 2 | 2 | 2 | 0 | 0 | rule-based |
| `loop` | 5 | 5 | 5 | 0 | 0 | rule-based |
| `low_output` | 9 | 9 | 9 | 0 | 0 | rule-based |
| `max_step_hit` | 5 | 5 | 5 | 0 | 0 | rule-based |
| `pattern_loop` | 0 | 0 | 0 | 0 | 0 | rule-based |
| `recovery_path` | 13 | 13 | 13 | 0 | 0 | rule-based |
| `retry_storm` | 10 | 10 | 10 | 0 | 0 | rule-based |
| `specific_tool_error` | 10 | 10 | 10 | 0 | 0 | rule-based |
| `step_efficiency` | 0 | 0 | 0 | 0 | 0 | rule-based |
| `tool_latency` | 6 | 6 | 6 | 0 | 0 | rule-based |
| `tool_timeout` | 16 | 16 | 16 | 0 | 0 | rule-based |
| `wasted_tool_calls` | 14 | 14 | 14 | 0 | 0 | rule-based |

_Report saved to `data/m13/comparison/comparison.json`_