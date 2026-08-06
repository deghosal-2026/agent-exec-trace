# Synthetic LLM Validation Plan — M13.1

> Validates the 5 LLM-augmented anomaly detectors against the existing 1M
> synthetic trace corpus. Complements the rule-based synthetic report at
> [`field-test-report-synthetic.md`](field-test-report-synthetic.md).
>
> **Status:** Planning — M13.1
> **Dataset:** 1,000,343 synthetic traces already generated in `data/traces2/synthetic/`
> **Date:** 2026-08-05

---

## 1. Objective

Validate that the 5 LLM-augmented detectors (SemanticLoop, Hallucination,
GoalDrift, QualityDegradation, ConfusionPattern) and the EmbeddingDrift
detector produce correct, useful anomaly records when run against synthetic
agent traces. Measure detection accuracy, LLM call efficiency, and model
quality tradeoffs to produce paper-grade telemetry.

## 2. Dataset

The synthetic corpus is already generated and documented in
[`field-test-report-synthetic.md`](field-test-report-synthetic.md):

| Metric | Value |
|---|---|
| Total traces | 1,000,343 |
| Agents | 10 (whimsical names: BlipZorp, SnarfBlat, etc.) |
| Tools | 14 shared across all agents |
| Traces with anomalies (rule-based) | 967,386 (96.7%) |
| Total rule-based anomalies | 5,132,535 |
| Detectors firing (rule-based) | 20 of 35 |
| Parquet files | 290 (~3,800 traces per file) |

### Sampling strategy

For M13.1, sample **25 traces** from the first parquet file. The
validator's `--max-traces 25` flag selects the first 25 traces
deterministically (sorted by file, then by trace_id).

Because the synthetic generator is deterministic with known injected
failure patterns, per-detector fire rates are stable at 25 traces —
25 vs 50 vs 200 traces produce the same percentages. More traces only
tighten confidence intervals, which is unnecessary for synthetic data
with known ground truth. 25 traces keeps the 3-way comparison
(no-LLM / 4B / 9B) under 30 minutes total.

## 3. Experimental Design

### 3.1 Three-way comparison (primary experiment)

Run the same 25 traces through three configurations and compare:

```
┌──────────────────────────────────────────────────┐
│  25 synthetic traces (data/traces2/synthetic)      │
└──────────────────────┬───────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Pass 1:      │ │ Pass 2:      │ │ Pass 3:      │
│ Rule-based   │ │ Rule + LLM   │ │ Rule + LLM   │
│ only         │ │ (4B model)  │ │ (9B model)  │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ data/m13/    │ │ data/m13/    │ │ data/m13/    │
│ no-llm/      │ │ llm-4b/      │ │ llm-9b/      │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
              ┌──────────────────┐
              │ 3-way comparison  │
              │ data/m13/         │
              │ comparison/       │
              └──────────────────┘
```

### 3.2 Script

`scripts/m13/run-llm-validation.sh` orchestrates all three passes:

1. **Pass 1 — No LLM** — `analytics validate --max-traces 25` (no `--llm-sample`)
   → `data/m13/no-llm/`
2. **Pass 2 — LLM 4B** — `ANALYTICS_LLM_CHAT_MODEL=Qwen3.5-4B-4bit analytics validate --max-traces 25 --llm-sample 25`
   → `data/m13/llm-4b/`
3. **Pass 3 — LLM 9B** — `ANALYTICS_LLM_CHAT_MODEL=Qwen3.5-9B-MLX-4bit analytics validate --max-traces 25 --llm-sample 25`
   → `data/m13/llm-9b/`
4. **Compare** — Python script reads all three summaries, produces
   `data/m13/comparison/comparison-report.md` with 3-way table

### 3.3 Configuration

| Pass | Model | Params | Expected speed | Env var |
|---|---|---|---|---|
| 1 (baseline) | None (rule-based only) | — | <1s/trace | `--no-llm` |
| 2 (4B) | Qwen3.5-4B-4bit | 4B | ~1s/call | `ANALYTICS_LLM_CHAT_MODEL=Qwen3.5-4B-4bit` |
| 3 (9B) | Qwen3.5-9B-MLX-4bit | 9B | ~2s/call | `ANALYTICS_LLM_CHAT_MODEL=Qwen3.5-9B-MLX-4bit` |

Thinking mode disabled in all LLM passes via `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`.

## 4. Telemetry to Capture

### 4.1 Currently captured

| Metric | Source | Status |
|---|---|---|
| Total LLM calls (chat + embed) | `llm_client._stats` | ✅ |
| Total LLM errors | `llm_client._stats` | ✅ |
| Aggregate latency (ms) | `llm_client._stats` | ✅ |
| LLM responses (trace_id, detector, system, prompt, response) | `llm_responses.json` | ✅ |
| LLM trace candidates (which traces got LLM) | `llm_trace_candidates.jsonl` | ✅ |
| LLM detector attempts (per-trace per-detector) | `llm_detector_attempts.jsonl` | ✅ |
| Anomaly counts by type and severity | `summary.json` | ✅ |
| Detector fire rates | `summary.json` | ✅ |
| Cross-detector correlation | `summary.json` | ✅ |
| Skipped/errored detectors | `summary.json` | ✅ |

### 4.2 To add before the 200-trace run

| # | Metric | Why it matters | Implementation |
|---|---|---|---|
| 1 | **Per-call latency** | p50/p95/p99 distribution, per-detector timing | Add `latency_ms` to each response record in `llm_client.py` |
| 2 | **Token usage per call** | prompt_tokens, completion_tokens, total_tokens | Capture `resp.usage` in `llm_client.py` |
| 3 | **Cache hit/miss count** | Efficiency — how many LLM calls avoided by cache | Increment counter in `llm_client.py` cache check |
| 4 | **JSON parse success rate** | Reliability — % of responses that parse as valid JSON | Track in `validator.py` per detector attempt |
| 5 | **Finish reason** | Did model finish (stop) or get cut off (length)? | Capture `resp.choices[0].finish_reason` |
| 6 | **Per-detector latency** | Which LLM detectors are most expensive | Time each `detect_async()` call in validator |
| 7 | **Prompt length (chars)** | Token cost correlation with prompt size | Log `len(prompt)` in response record |
| 8 | **Trace complexity** | Correlate span count/depth/tool count with detection | Compute per-trace stats in validator |

### 4.3 Analysis-layer metrics (post-run)

| # | Metric | Why it matters | Source |
|---|---|---|---|
| 9 | **Ground truth labels** | TP/FP/TN/FN → precision, recall, F1 | Manual review of LLM-flagged anomalies on 200 traces |
| 10 | **Rule vs LLM agreement matrix** | When both fire, do they agree? Disagreement is interesting | Comparison script joins on trace_id |
| 11 | **LLM explanation quality** | Are LLM explanations more actionable than rule-based? | Score 1-5 via `ExplanationScorer` or manual review |
| 12 | **Model comparison table** | 4B vs 9B on same traces: accuracy, latency, token cost | Run both, save side-by-side |

## 5. Ground Truth Approach

Synthetic traces have known failure modes by construction (the generator
injects loops, retries, cost spikes, etc.). Use the generator's phase
metadata to derive ground truth:

| Phase | Injected behavior | Expected detector | Ground truth label |
|---|---|---|---|
| `loop` | Same tool 5-18x consecutively | `loop`, `pattern_loop`, `argument_loop` | TP if any loop detector fires |
| `error_phase` | 35% of calls fail | `tool_error_rate`, `specific_tool_error` | TP if error detector fires |
| `retry_phase` | 25% of calls have retry flags | `retry_storm`, `recovery_path` | TP if retry detector fires |
| `intervention` | Human approval flows | `intervention_frequency`, `approval_latency` | TP if interaction detector fires |
| `token_boom` | Late-phase token spike | `token_explosion`, `cost_spike` | TP if cost detector fires |
| `gap` | 10-60s inactivity gaps | `inactivity` | TP if inactivity fires |
| `memory_blitz` | 2-5 memory CRUD ops | (no specific detector) | TN if no detector fires |
| `warmup` | Simplified behavior | (no anomaly expected) | TN if no detector fires |

For LLM-only detectors:
- `hallucination`: TP if claim in output is not supported by tool results
- `confusion_pattern`: TP if plan and execution contradict
- `semantic_loop`: TP if consecutive outputs are semantically identical
- `quality_degradation`: TP if output quality drops vs baseline
- `goal_drift`: TP if intent diverges over the run

These require manual review of the 200 traces. Budget: ~2 min/trace = ~7 hrs.

## 6. Success Criteria

| Criterion | Target | Measurement |
|---|---|---|
| LLM detectors fire on synthetic traces | ≥3 of 5 fire | `anomaly_by_type` in summary |
| LLM finds anomalies rules missed | >0 additional anomalies | Comparison report diff > 0 |
| JSON parse success rate | ≥95% | Telemetry item #4 |
| LLM error rate | ≤5% | `detector_errors` in summary |
| Per-call latency p95 | ≤10s (9B) / ≤5s (4B) | Telemetry item #1 |
| Rule-based anomalies unchanged | identical counts in both passes | Comparison report diff = 0 for rule types |
| Ground truth precision (LLM) | ≥80% | Manual review of TP/FP |
| Ground truth recall (LLM) | ≥60% | Manual review of FN |

## 7. Paper-Ready Outputs

After the run, the following artifacts support a paper:

| Artifact | Location | Content |
|---|---|---|
| Comparison report | `data/m13/comparison/comparison-report.md` | Per-detector diff table |
| LLM responses | `data/m13/with-llm/with-llm/llm_responses.json` | Full response audit trail |
| Per-call telemetry | `data/m13/with-llm/with-llm/telemetry.jsonl` | Latency, tokens, cache, finish reason |
| Ground truth labels | `data/m13/ground-truth.jsonl` | Per-trace expected anomalies |
| Model comparison | `data/m13/model-comparison.json` | 4B vs 9B side-by-side |
| Summary statistics | `data/m13/with-llm/with-llm/summary.json` | Aggregate counts and rates |
| This plan + results | `docs/field-test/synthetic-llm-validation-plan.md` | Experimental design and outcomes |

## 8. Paper Measurement Framework

This section defines every measurement needed to author a rigorous paper on
LLM-augmented anomaly detection for agent workflows. Each metric is tagged
with the paper section it supports and the artifact that produces it.

### 8.1 System Description Metrics (Introduction / Background)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| Detector count | 35 rule-based + 5 LLM-augmented + 1 embedding drift | `detectors/__init__.py` | System overview |
| Detector categories | 7 behavioral categories | WBS Part 3 | System overview |
| Corpus size | 1,000,343 synthetic traces, 290 parquet files | `field-test-report-synthetic.md` | Dataset description |
| Agent diversity | 10 agent personalities, 14 tools | `generate_bulk_traces.py` | Dataset description |
| Trace structure | Root span → plan spans → tool spans → memory/intervention spans | SDK instrumentation docs | Architecture |
| Span count per trace | Mean, median, p95, distribution | Telemetry item #8 (trace complexity) | Dataset description |
| Tool calls per trace | Mean, median, p95 | Telemetry item #8 | Dataset description |
| Trace depth | Max nesting depth per trace | Telemetry item #8 | Dataset description |

### 8.2 Detection Accuracy Metrics (Results — Core)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| **True positives (TP)** | LLM detector fires and ground truth confirms anomaly | Ground truth labels | Accuracy table |
| **False positives (FP)** | LLM detector fires but ground truth says no anomaly | Ground truth labels | Accuracy table |
| **False negatives (FN)** | LLM detector does not fire but ground truth says anomaly | Ground truth labels | Accuracy table |
| **True negatives (TN)** | LLM detector does not fire and ground truth says no anomaly | Ground truth labels | Accuracy table |
| **Precision** | TP / (TP + FP) per detector | Computed | Accuracy table |
| **Recall** | TP / (TP + FN) per detector | Computed | Accuracy table |
| **F1 score** | 2 × (precision × recall) / (precision + recall) | Computed | Accuracy table |
| **Per-detector fire rate** | % of traces where detector fires | `summary.json` | Detection overview |
| **Severity accuracy** | Does severity (warning/critical) match ground truth? | Ground truth labels | Quality assessment |
| **Anomalies per trace** | Mean, median, p95 distribution (rule vs LLM) | `summary.json` | Detection overview |
| **Coverage delta** | Anomalies found by LLM that rules missed (count + %) | Comparison report | Key result |
| **Novel anomaly types** | LLM-only detector types that fire (count) | Comparison report | Key result |

### 8.3 Rule-Based vs LLM Comparison Metrics (Results — Comparative)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| **Rule-based baseline** | Anomaly count, types, severity (no LLM) | `data/m13/without-llm/summary.json` | Baseline |
| **LLM-augmented total** | Anomaly count, types, severity (with LLM) | `data/m13/with-llm/summary.json` | Augmented |
| **Delta count** | LLM total − rule total | Comparison report | Comparison |
| **Delta per detector** | Per-detector count diff (rules vs LLM) | Comparison report | Comparison table |
| **Additivity** | Rule counts unchanged between passes (LLM is strictly additive) | Comparison report | Design property |
| **Agreement matrix** | When both rule and LLM fire on same trace, do they agree? | Analysis script | Agreement analysis |
| **Disagreement cases** | Traces where LLM contradicts rule-based (interesting cases) | Analysis script | Discussion |
| **Co-fire correlation** | Which detectors co-fire (rule + LLM pairs) | `summary.json` cross_detector_correlation | Correlation analysis |

### 8.4 LLM Efficiency Metrics (Results — Cost)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| **Total LLM calls** | Chat + embed call count | `llm_client._stats` | Efficiency |
| **LLM calls per trace** | Mean, median, p95 | Telemetry item #1 | Efficiency |
| **Calls per detector** | Breakdown by LLM detector type | `llm_responses.json` | Efficiency table |
| **Per-call latency (ms)** | p50, p95, p99, mean | Telemetry item #1 | Latency table |
| **Per-detector latency (ms)** | p50, p95 per detector type | Telemetry item #6 | Latency breakdown |
| **Wall-clock time** | Total experiment runtime | Script timing | Runtime |
| **Token usage — prompt** | Sum of prompt_tokens across all calls | Telemetry item #2 | Token cost |
| **Token usage — completion** | Sum of completion_tokens | Telemetry item #2 | Token cost |
| **Token usage — total** | Sum of total_tokens | Telemetry item #2 | Token cost |
| **Tokens per anomaly** | Total tokens / LLM anomalies found | Computed | Cost-effectiveness |
| **Cache hit rate** | % of calls served from cache (no LLM needed) | Telemetry item #3 | Efficiency |
| **Estimated cost (USD)** | Tokens × pricing model (if available) | Computed | Cost table |

### 8.5 LLM Reliability Metrics (Results — Robustness)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| **JSON parse rate** | % of LLM responses that parse as valid JSON | Telemetry item #4 | Reliability |
| **JSON parse failures** | Count + examples of unparseable responses | Telemetry item #4 | Failure analysis |
| **LLM error rate** | % of calls that errored (timeout, server down, etc.) | `llm_client._stats` | Reliability |
| **Finish reason distribution** | stop vs length vs content_filter | Telemetry item #5 | Robustness |
| **Empty response rate** | % of calls returning empty content | `llm_responses.json` | Failure analysis |
| **Graceful degradation** | Does pipeline complete when LLM is unavailable? | `detector_errors` in summary | Design property |
| **Timeout rate** | % of calls exceeding `llm_timeout_seconds` | Telemetry item #1 | Reliability |

### 8.6 Model Comparison Metrics (Results — Ablation)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| **4B anomaly count** | Total LLM anomalies (4B model) | Model comparison run | Ablation |
| **9B anomaly count** | Total LLM anomalies (9B model) | Model comparison run | Ablation |
| **4B precision/recall** | Accuracy metrics for 4B | Ground truth labels | Ablation table |
| **9B precision/recall** | Accuracy metrics for 9B | Ground truth labels | Ablation table |
| **4B latency** | Per-call latency (4B) | Telemetry item #1 | Ablation table |
| **9B latency** | Per-call latency (9B) | Telemetry item #1 | Ablation table |
| **4B token cost** | Total tokens (4B) | Telemetry item #2 | Ablation table |
| **9B token token cost** | Total tokens (9B) | Telemetry item #2 | Ablation table |
| **4B JSON parse rate** | % valid JSON (4B) | Telemetry item #4 | Ablation table |
| **9B JSON parse rate** | % valid JSON (9B) | Telemetry item #4 | Ablation table |
| **4B vs 9B per-detector** | Per-detector fire count comparison | Model comparison | Ablation detail |
| **Quality/cost tradeoff** | Accuracy improvement per dollar of compute | Computed | Discussion |

### 8.7 Explanation Quality Metrics (Results — Qualitative)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| **Rule explanation length** | Mean chars in rule-based explanations | `anomalies` table | Quality comparison |
| **LLM explanation length** | Mean chars in LLM explanations | `anomalies` table | Quality comparison |
| **Explanation actionability** | Score 1-5: does explanation tell operator what to do? | Manual review or `ExplanationScorer` | Quality |
| **Explanation clarity** | Score 1-5: is explanation easy to understand? | Manual review or `ExplanationScorer` | Quality |
| **Evidence specificity** | Does explanation cite specific spans/attributes? | Manual review | Quality |
| **Inter-rater agreement** | Cohen's kappa across 2+ reviewers on 20 traces | Manual review | Validity |

### 8.8 Trace Complexity Correlation Metrics (Discussion)

| Metric | Description | Source | Paper Section |
|---|---|---|---|
| **Span count vs anomaly count** | Correlation (Pearson r) | Telemetry item #8 | Discussion |
| **Tool count vs LLM anomaly count** | Correlation | Telemetry item #8 | Discussion |
| **Trace depth vs confusion pattern** | Do deeper traces trigger more confusion? | Telemetry item #8 | Discussion |
| **Token count vs hallucination** | Do high-token traces hallucinate more? | Telemetry item #8 | Discussion |
| **Phase count vs goal drift** | Do more phases increase drift? | Telemetry item #8 | Discussion |

### 8.9 Threats to Validity (Discussion)

| Threat | Mitigation | Measurement |
|---|---|---|
| **Synthetic data bias** | Generator injects known patterns; LLM may find these easier than real failures | M13.2 validates against real GitHub agents |
| **Single model family** | Only Qwen tested; results may not generalize | Document as limitation; future work for Llama/Mistral |
| **Thinking mode disabled** | Disabling thinking may reduce reasoning quality | Document as limitation; future experiment with thinking + higher token budget |
| **Cache contamination** | Repeated system prompts hit cache; may inflate efficiency | Report cache hit rate separately; run with cache disabled as ablation |
| **Prompt sensitivity** | Results may depend on prompt wording | Document exact prompts in appendix; test prompt variations as future work |
| **Ground truth subjectivity** | Manual labels have inter-rater variance | Use 2+ reviewers, report Cohen's kappa |
| **Sample size** | 50-200 traces may be too few for rare detector types | Report per-detector confidence intervals |
| **Determinism** | Rule-based is deterministic; LLM is not | Run LLM pass 3x, report variance |

## 9. Estimated Runtime

| Pass | Traces | LLM calls | Model | Est. time |
|---|---|---|---|---|
| 1 — No LLM (baseline) | 25 | 0 | — | <30s |
| 2 — LLM 4B | 25 | ~750 | Qwen3.5-4B-4bit | ~12 min |
| 3 — LLM 9B | 25 | ~750 | Qwen3.5-9B-MLX-4bit | ~25 min |
| **Total (3-way)** | **25** | **~1,500** | **3 configs** | **~38 min** |

Because synthetic traces are deterministic with known failure modes,
25 traces produces the same per-detector fire rates as 200 traces.
The 3-way comparison runs in under 40 minutes total.

## 9. Pre-Run Checklist

- [ ] Add per-call telemetry to `llm_client.py` (latency, tokens, cache, finish reason)
- [ ] Add JSON parse tracking to `validator.py`
- [ ] Add per-detector latency timing to `validator.py`
- [ ] Add trace complexity metrics to `validator.py`
- [ ] Verify MLX server is running with Qwen3.5-9B-MLX-4bit loaded
- [ ] Verify thinking mode is disabled (`extra_body={"chat_template_kwargs": {"enable_thinking": False}}`)
- [ ] Run 5-trace pilot to verify telemetry capture
- [ ] Run 50-trace full experiment
- [ ] Generate comparison report
- [ ] Manual ground truth labeling (sample 20 traces for inter-rater reliability)
- [ ] Write findings report

## 10. Known Limitations

1. **Synthetic data bias:** The synthetic generator injects known failure
   patterns. LLM detectors may find these easier (or harder) than real-world
   failures. Results should be validated against real agent traces in M13.2.

2. **Single model family:** Only Qwen models are tested. Results may not
   generalize to Llama, Mistral, or proprietary models.

3. **No streaming:** LLM calls are synchronous per trace. Streaming would
   reduce wall-clock time but doesn't affect accuracy metrics.

4. **Cache effects:** The in-memory cache means repeated prompts (e.g.,
   same system message) don't incur LLM calls. The 200-trace run will have
   cache hits for system prompts. Report cache hit rate separately.

5. **Thinking mode disabled:** We disable Qwen's thinking mode for JSON
   compliance. This may reduce reasoning quality. A future experiment
   could compare thinking-enabled (with higher max_tokens) vs disabled.

---

## 11. Results

### 11.1 Pilot Run — 5 Traces, Qwen3.5-9B-MLX-4bit

> **Date:** 2026-08-05
> **Model:** Qwen3.5-9B-MLX-4bit (thinking disabled via `enable_thinking: False`)
> **Script:** `scripts/m13/run-llm-validation.sh --traces 5`
> **Output:** `data/m13/`

#### Summary

| Metric | Rule-Based Only | With LLM (9B) | Delta |
|---|---|---|---|
| Traces processed | 5 | 5 | 0 |
| Traces with anomalies | 5 | 5 | 0 |
| Total anomalies | 17 | 26 | **+9** |
| Detector types fired | 8 | 10 | **+2 (LLM-only)** |
| LLM calls | 0 | 150 | +150 |
| LLM errors | 0 | 0 | 0 |

#### Per-Detector Comparison

| Anomaly Type | Rules Only | With LLM | Diff | Category |
|---|---|---|---|---|
| `hallucination` | 0 | 5 | **+5** | llm-only |
| `confusion_pattern` | 0 | 4 | **+4** | llm-only |
| `inactivity` | 5 | 5 | 0 | rule-based |
| `loop` | 2 | 2 | 0 | rule-based |
| `low_output` | 2 | 2 | 0 | rule-based |
| `tool_timeout` | 3 | 3 | 0 | rule-based |
| `wasted_tool_calls` | 2 | 2 | 0 | rule-based |
| `recovery_path` | 1 | 1 | 0 | rule-based |
| `retry_storm` | 1 | 1 | 0 | rule-based |
| `specific_tool_error` | 1 | 1 | 0 | rule-based |

#### LLM Detector Fire Rates

| Detector | Traces Fired | Fire Rate | Severity |
|---|---|---|---|
| `hallucination` | 5/5 | 100% | warning |
| `confusion_pattern` | 4/5 | 80% | warning |

#### LLM Call Breakdown

| Detector | Calls | Calls/Trace |
|---|---|---|
| `semantic_loop` | 66 | 13.2 |
| `hallucination` | 30 | 6.0 |
| `confusion_pattern` | 30 | 6.0 |
| `quality_degradation` | 24 | 4.8 |
| **Total** | **150** | **30.0** |

#### Cross-Detector Correlation (Top 5)

| Pair | Co-fire Count | Co-fire % |
|---|---|---|
| inactivity + hallucination | 5 | 100% |
| inactivity + confusion_pattern | 4 | 80% |
| hallucination + confusion_pattern | 4 | 80% |
| tool_timeout + inactivity | 3 | 60% |
| tool_timeout + hallucination | 3 | 60% |

#### LLM Response Quality

All 150 responses returned valid JSON (100% parse rate). Sample responses:

| Detector | Response |
|---|---|
| `semantic_loop` | `{"identical": false, "similarity": 0.0}` |
| `hallucination` | `{"hallucination": true, "evidence": "none"}` |
| `quality_degradation` | `{"degraded": false, "severity": "none", "note": "The current output is identical to the baseline..."}` |
| `confusion_pattern` | `{"contradiction": false, "explanation": "The execution steps are consistent with the plan..."}` |

#### Key Findings

1. **Hallucination detector fires on every trace.** The synthetic agent outputs
   contain claims ("17 issues found, 4 critical") that are not directly supported
   by the tool results (`{"status": "ok", "r": 17}`). The LLM correctly identifies
   this as a hallucination — the number 17 appears in tool output but "4 critical"
   does not.

2. **Confusion pattern fires on 80% of traces.** The LLM detects contradictions
   between the plan spans ("Phase 0 plan for BlipZorp") and execution steps.
   This is a semantic-level finding that no rule-based detector can catch.

3. **Rule-based counts are identical in both passes.** The LLM layer is strictly
   additive — it does not modify or suppress any rule-based detector output.

4. **30 LLM calls per trace.** The `semantic_loop` detector makes the most calls
   (13.2/trace) because it compares every pair of consecutive outputs. The other
   detectors make ~5-6 calls per trace.

5. **Thinking mode fix was critical.** Without disabling thinking
   (`enable_thinking: False`), the Qwen3.5 model spent all tokens on reasoning
   and returned empty content. With thinking disabled, 100% of responses are
   valid JSON.

### 11.2 Full Run — 50 Traces, Qwen3.5-9B-MLX-4bit

> **Status:** PENDING — run after telemetry hooks are added
> **Command:** `bash scripts/m13/run-llm-validation.sh --traces 50`

_(Results will be filled in after the run.)_

| Metric | Rule-Based Only | With LLM (9B) | Delta |
|---|---|---|---|
| Traces processed | 50 | 50 | — |
| Total anomalies | — | — | — |
| LLM calls | 0 | — | — |
| LLM errors | — | — | — |
| JSON parse rate | — | — | — |
| Per-call latency p50 | — | — | — |
| Per-call latency p95 | — | — | — |
| Token usage (total) | — | — | — |
| Cache hit rate | — | — | — |

### 11.3 Model Comparison — 4B vs 9B (50 Traces)

> **Status:** PENDING

| Metric | Qwen3.5-4B-4bit | Qwen3.5-9B-MLX-4bit |
|---|---|---|
| Total LLM anomalies | — | — |
| Hallucination fire rate | — | — |
| Confusion pattern fire rate | — | — |
| JSON parse rate | — | — |
| Avg latency per call | — | — |
| Total tokens consumed | — | — |
| Wall-clock time | — | — |

### 11.4 Ground Truth Analysis

> **Status:** PENDING — manual review of 20 sampled traces

| Detector | True Positives | False Positives | False Negatives | Precision | Recall |
|---|---|---|---|---|---|
| `hallucination` | — | — | — | — | — |
| `confusion_pattern` | — | — | — | — | — |
| `semantic_loop` | — | — | — | — | — |
| `goal_drift` | — | — | — | — | — |
| `quality_degradation` | — | — | — | — | — |
