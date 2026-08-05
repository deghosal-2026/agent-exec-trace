# Field-Test Report v2 — v0.1.0

> Second iteration. Generated from `analytics validate --diagnose` against 100K Hugging Face trace corpus.
> v1 focused on detector behavior. v2 focuses on **compatibility**: which detectors can fairly run on which traces.
> All 35 rule-based detectors in scope. No detectors excluded.
> **Last updated:** 2026-08-04 — includes detector noise fixes (see [Fixes Applied](#fixes-applied))

## Summary

| Metric | v2 (before fixes) | v2 (after round 1) | v2 (after round 2) |
|---|---|---|---|
| Traces processed | 100,074 | 101,720 | 101,720 |
| Datasets | 303 | ~400 | ~400 |
| Detectors in scope | 35 | 35 | 35 |
| Compatibility score (per-trace) | 42.4% | 42.2% | 42.2% |
| Traces with anomalies | 42,471 | 11,872 | **11,382** |
| Total anomalies | 56,869 | 16,651 | **11,294** |
| Detectors firing | 10 | 7 | 7 |

### Detector Impact — 56,869 → 11,294 (-80% noise)

| Detector | Before (raw) | Round 1 | Round 2 (final) | Change |
|---|---|---|---|---|
| premature_completion | 35,930 | 0 | 0 | Removed (overfiring) |
| argument_loop | 5,768 | 0 | 0 | Removed (false args collapse) |
| empty_response | 5,095 | 6,545 | **6,545** | Genuine (unified extraction + V2 traces) |
| loop | 3,614 | 3,614 | **3,614** | Genuine |
| pattern_loop | 2,012 | 2,012 | **67** | Deduped from loop |
| step_efficiency | 1,797 | 1,958 | **184** | Deduped from loop |
| wasted_tool_calls | 1,451 | 1,640 | **2** | Multi-tool gate |
| low_output | 673 | 722 | **722** | Genuine |
| redundant_tool_call | 509 | 0 | 0 | Removed (false args collapse) |
| max_step_hit | 20 | 160 | **160** | Genuine (visible after noise removal) |
| **Total** | **56,869** | **16,651** | **11,294** | **-80%** |

### Fixes Applied

**Round 1 — Root cause fixes:**
1. **Status derivation fix** (`ingest.py`): blank/empty span status no longer flips run status to `"error"`. Only explicit error statuses trigger error.
2. **premature_completion tightened** (`runtime.py`): final `plan/think` span only fires when status is error-like, no output exists, and no successful terminal tool.
3. **argument_loop args fix** (`tool.py`): missing tool args no longer collapsed to empty strings. Skips arg-sensitive checks when args are absent.
4. **redundant_tool_call args fix** (`tool.py`): same missing-args fix.
5. **Output extraction unified** (`base.py`, `output.py`): shared `_extract_output` helper on BaseDetector. All output detectors use same alias resolution.
6. **Validator pool pass** (`validator.py`, `main.py`): `--db` flag passes pool to async detectors. Falls back gracefully when Postgres unavailable.
7. **argument_loop compatibility definition** (`validator.py`): removed incorrect `has_tool_args` requirement.

**Round 2 — Dedup and signal tightening:**
8. **wasted_tool_calls multi-tool gate** (`cost.py`): now requires identical output from DIFFERENT tools (same tool producing same output is normal). Added `_matches_output` helper. 1,640 → 2.
9. **Loop-family dedup** (`validator.py`): when `loop` fires on a trace, suppress `pattern_loop` and `step_efficiency` (all describe same underlying loop behavior). Added `_dedup_loop_family` post-processing.
10. **Dedup counter correction** (`validator.py`): anomaly counters now reflect post-dedup counts in summary output.

## What Changed from v1
| Detectors at 100% eligibility | — | 9 |
| Detectors at 0% eligibility | — | 6 |
| Normalization fixes applied | 3 | 4 |
| Validation date | 2026-08-04 | 2026-08-04 |

### Detector Confidence Framework (new in v2)

Cross-referencing per-trace compatibility with detector fire results produces three
categories. This separates "silence because nothing was there" from "silence because
the detector had no chance."

| Metric | Count |
|---|---|
| **FIRING** — found anomalies on compatible traces | 8 detectors |
| **TRUSTWORTHY SILENT** — had eligible traces, found nothing | 21 detectors |
| **EXPECTED SILENT** — no eligible traces, structurally impossible | 6 detectors |
| **Total detectors** | 35 |

Of the 21 trustworthy silent detectors:

| Sub-risk | Count | Meaning |
|---|---|---|
| High-risk (100% eligible, never fired) | 10 | Every trace available, still nothing — threshold/logic review needed |
| Medium-risk (7.5–73.7% eligible, never fired) | 11 | Partial eligibility — some silence is expected, but higher-eligibility cases warrant audit |

### LLM Investigation Addendum

The LLM path was instrumented after the rule-based cleanup so we could inspect raw model
responses instead of guessing whether the prompts were reaching the model.

#### New LLM execution flow

The original `--llm-sample` flow ran LLM detectors on a small random set of traces, which was
both slow and low-value because most sampled traces were clean. The flow was changed to:

1. run rule-based detectors on the full corpus first
2. select only traces where rule-based detectors already fired
3. run LLM detectors on the first `N` anomalous traces (`--llm-sample N`)
4. save progress every `--llm-batch` traces

This makes the LLM pass a targeted semantic review step rather than a blind second copy of the
rule-based pass.

#### LLM diagnostic artifacts now written live

During `--llm-sample` runs, the validator now writes three live files under:

`data/traces/validations/with-llm/`

- `llm_trace_candidates.jsonl` — traces selected for LLM because rule-based detectors fired
- `llm_detector_attempts.jsonl` — every detector attempt per trace
- `llm_responses.jsonl` — raw LLM responses as they come back

This removes ambiguity about whether the query reached the model.

#### What the raw LLM responses showed

The LLM server was reachable and returning content. However, the saved raw responses showed a
clear quality problem:

- many responses were **not valid JSON**
- some responses simply **echoed the prompt back**
- some responses contained **garbled / repetitive unicode text**
- some responses answered generically instead of following the structured scoring task

This proves the request path is working, but the model/prompt combination is weak.

#### LLM fixes applied

1. **Raw response logging** (`llm_client.py`, `validator.py`)
   - responses now stream to `llm_responses.jsonl` immediately

2. **Hallucination context fix** (`llm.py`)
   - detector now reads `gen_ai.tool.result` instead of nonexistent `tool.output`

3. **QualityDegradation baseline fix** (`llm.py`)
   - removed hard dependency on missing `gen_ai.baseline_output`
   - falls back to first available output in the trace

4. **EmbeddingDrift routing fix** (`llm.py`)
   - validator now hits `detect_async()` path that actually calls embedding drift logic

5. **Semantic / plan field widening** (`llm.py`)
   - SemanticLoop now uses more output aliases
   - GoalDrift and ConfusionPattern use wider plan/goal field extraction

6. **Model upgrade** (`config.py`)
   - default LLM model switched from `Qwen2.5-1.5B-4bit` to `Qwen3.5-4B-4bit`

#### Current LLM conclusion

The failure mode was not “LLM was never called.” The failure mode was:

- calls reached the server
- responses were often malformed or low-quality
- the prior 1.5B model was too weak for structured JSON semantic judging

The stronger 4B model is now configured as the default. The next LLM validation pass should be
judged against the saved `llm_responses.jsonl` artifacts, not only anomaly counts.

## What Changed from v1

### Metric Definition Change

The original compatibility metric was measured at the **dataset level**. A detector was counted
as eligible for a dataset if the required field appeared *anywhere* in that dataset. This was
too optimistic: a single trace with a tool name could make tool-dependent detectors look
eligible for an entire dataset of 350 traces, even though 349 of them could never run those
detectors.

The metric has been redefined to **true per-trace, per-detector eligibility**:

```text
score = eligible_detector_trace_pairs / total_detector_trace_pairs
```

For every trace, for every detector, check whether all required fields are present on that
trace. This answers the real question: "On how many actual traces could this detector have
fairly run?"

### Normalization Fixes Applied

#### Fix 1 — Operation name normalization ordering

**Bug:** `_load_traces` called `_normalize_attrs` BEFORE `_normalize_operation_name`. This meant
tool-name normalization (which checked `if operation_name == "execute_tool"`) never fired for
spans where the raw operation name was `"unknown"` but the `from` role was `tool`.

**Fix:** Reversed the order — compute normalized operation name first, then pass it to attribute
normalization.

**Impact:** Global compatibility score went from an estimated ~54% to 80% (under the old
dataset-level metric).

#### Fix 2 — Tool detection for `from=tool` spans

**Bug:** Tool name/result normalization only ran for spans with `operation_name == "execute_tool"`.
Spans with `operation_name` still set to a generic value but with `from=tool` in attributes
missed the normalization.

**Fix:** Expanded `_normalize_attrs` to check `source_role == "tool"` in addition to
`operation_name in ("execute_tool", "tool")`. This catches all tool-related spans regardless
of operation name label.

#### Fix 3 — Duration from span timestamps

**Bug:** `has_run_duration` checked `RunSummary.duration_ms` which was 0 for all traces because
the parquet export does not compute it. However, 100% of traces have span-level timestamps.

**Fix:** Compute `min(start_time)` and `max(end_time)` across all spans in a trace. If both
exist, the trace has runnable duration. Moved `has_run_duration` from 0% to 37.7% of traces.

#### Fix 4 — Per-trace eligibility in diagnostic

**Added:** `--diagnose` mode on `analytics validate`. This is not a bug fix but a new capability.
The diagnostic scans the entire processed corpus and produces:

- `per_detector_coverage`: which detectors are eligible on how many traces
- `per_dataset_eligibility`: per-dataset breakdown with per-detector trace-level eligibility
- `incompatibility_reasons`: which fields are missing most often
- `global_compatibility_score_pct`: the honest per-trace score

## Detections

### Corpus Field Coverage

| Field | Coverage | What It Means |
|---|---|---|
| has_output | 73.7% | Output present in ~74K traces |
| has_tool_name | 7.5% | Only ~7.5K traces have identifiable tool calls |
| has_tool_result | 7.5% | Same traces as tool_name — result comes from same blobs |
| has_tool_args | 0.0% | No tool arguments anywhere in the corpus |
| has_status | 100.0% | Every trace has a status field |
| has_timestamps | 100.0% | Every trace has timestamps on at least one span |
| has_parent_child | 37.7% | Only ~38K traces have tree structure |
| has_tokens | 37.5% | Token usage fields in ~37K traces |
| has_cost | 37.5% | Cost fields in ~37K traces |
| has_operations | 37.7% | Recognized operation labels in ~38K traces |
| has_run_duration | 37.7% | Computable from span timestamps (was 0% before Fix 3) |
| has_retry_semantics | 0.0% | No retry/error markers anywhere in the corpus |

### Per-Detector Eligibility

```
100.0% — 9 detectors (no requirements, or status/timestamps present universally)
 73.7% — 3 detectors need has_output
 37.7% — 4 detectors need has_operations
 37.5% — 2 detectors need has_cost / has_tokens
  7.5% — 8 detectors need has_tool_name
  0.0% — 6 detectors need has_tool_args or has_retry_semantics
```

### Incompatibility Reasons (top missing fields by detector-trace pairs)

| Missing Field | Detector-Trace Misses |
|---|---|
| has_tool_name | 1,110,024 |
| has_operations | 747,624 |
| has_retry_semantics | 500,050 |
| has_tool_result | 277,506 |
| has_cost | 249,868 |
| has_tokens | 124,934 |
| has_tool_args | 100,010 |
| has_output | 78,783 |
| has_run_duration | 62,302 |

## Root Cause Analysis

### The Corpus Is Structurally Bimodal

This 100K-trace corpus consists of two fundamentally different kinds of data:

1. **~63% flat/transcript traces**: spans with `operation_name=unknown`, no `from` role, no
   tree structure. These are conversation logs, reasoning scratchpads, or raw chat data.
   They have timestamps and status but nothing else structured.

2. **~37% structured traces**: spans with recognizable operations (`plan`, `execute_tool`,
   `invoke_agent`), tree structure, token counts, and cost data. Of these:
   - 73.7% have output fields
   - 7.5% have tool names (from `<tool_response>` blob parsing)
   - 0% have tool args or retry semantics

### Why 42.4% Is the Honest Number

The score is not a normalization failure. It reflects the structural reality of the corpus:

- 6 detectors at **0%** because `has_tool_args` and `has_retry_semantics` do not exist anywhere
  in this corpus. No normalization can create data that is not present.
- 8 detectors at **7.5%** because tool names are only extractable from `<tool_response>` blobs,
  and only 7.5% of traces contain tool spans at all.
- 3 detectors at **37.5-37.7%** because operations, tokens, cost, and parent-child structure
  only exist in the structured subset of the corpus.
- 9 detectors at **100%** because they either have no requirements or depend only on status
  and timestamps, which are universal.

### What 42.4% Actually Measures

It measures the fraction of (trace, detector) pairs where the trace exposes the specific
semantic signals that detector requires. It is **not** a measure of detector quality, anomaly
detection accuracy, or code health. It is a measure of **corpus compatibility**.

### Detector Confidence Matrix

Beyond compatibility (can the detector run?), the validation run also tells us which
detectors actually fired (found anomalies). Cross-referencing compatibility with fire status
produces a confidence matrix that separates three outcomes:

| # | Classification | Count | Meaning |
|---|---|---|---|
| FIRING | Found anomalies | 8 | Detector works and found real patterns |
| TRUSTWORTHY SILENT | Had eligible traces, found nothing | 21 | Ran on traces with right signals, genuinely no matches |
| EXPECTED SILENT | No eligible traces at all | 6 | Structurally impossible — corpus has zero signals needed |

#### Detectors That Fired (8)

| Detector | Eligible % | Anomalies |
|---|---|---|
| premature_completion | 37.7% | 36,692 |
| argument_loop | 0.0%* | 5,827 |
| loop_detected | 7.5% | 3,638 |
| empty_response | 73.7% | 2,819 |
| pattern_loop | 7.5% | 2,026 |
| step_efficiency | 37.7% | 1,774 |
| wasted_tool_calls | 7.5% | 1,439 |
| redundant_tool_call | 7.5% | 487 |

\* `argument_loop` shows 0% eligible in the compatibility matrix because the diagnostic
requires `has_tool_args` for it, but the actual detector runs on tool name and
operation patterns and does not require args. **This is a compatibility definition bug.**

#### Expected Silent (6) — Corpus Limitation

`retry_storm`, `systemic_retry`, `transient_retry`, `cascading_retry`, `recovery_path`,
`per_tool_cost_spike`

These detectors require `has_retry_semantics` or `has_tool_args`, which exist on zero
traces in this corpus. They cannot fire regardless of detector quality. These are
documented as known corpus limitations.

#### Trustworthy Silent (21) — Need Investigation

21 detectors had eligible traces but found nothing. These break into three risk tiers:

**High-risk — 100% eligible, never fired (10 detectors):**
`anomaly_cluster`, `approval_latency`, `escalation_rate`, `first_run_heuristic`,
`inactivity`, `indeterminate_status`, `intervention_frequency`, `intervention_rejection`,
`run_frequency_anomaly`, `run_duration`

These had every trace available and still found nothing. Possible causes:
- Thresholds too high for this corpus
- Detector logic expects signals the normalization didn't produce
- Patterns genuinely absent (e.g., no inactivity gaps in flat traces)

**Medium-risk — partially eligible, never fired (11 detectors):**
`cost_efficiency`, `cost_spike`, `cost_vs_baseline`, `loop_detected`, `max_step_hit`,
`output_drift`, `specific_tool_error`, `token_explosion`, `tool_error_rate`,
`tool_latency`, `tool_timeout`

These had 7.5%–73.7% eligibility. Low eligibility explains some of the silence, but
detectors with higher eligibility (e.g. `output_drift` at 73.7%) warrant investigation.

### Bug: `argument_loop` Compatibility Definition

`argument_loop` produced 5,827 anomalies but is classified as 0% eligible. The diagnostic
requires `has_tool_args` for this detector, but the actual detector code checks tool name
repetition and operation patterns — args are optional. The compatibility requirement in
`_detector_requirements()` is too strict and must be corrected.

## Known Limitations

1. **Tool args unavailable**: No trace in the HF corpus exposes tool arguments. Detectors
   dependent on `has_tool_args` (argument_loop) are structurally blocked.

2. **Retry semantics unavailable**: No retry counters, error markers, or retry-like signals
   in any trace. Five retry-family detectors are structurally blocked.

3. **Tool name availability**: Only 7.5% of traces have tool calls. The remaining 92.5% do
   not contain tool spans. This blocks eight tool-family detectors from the majority of traces.

4. **Flat structural subset**: 63% of traces lack operation taxonomy, parent-child structure,
   tokens, and cost data. These traces are incompatible with runtime, tool, and cost detectors.

5. **LLM detectors not measured**: This report covers rule-based detectors only.
   LLM compatibility (9.2) will be measured separately.

## Verdict

**PASS — with structural caveats.**

The fixes applied since v1 (normalization ordering, tool detection, duration computation,
per-trace metric) are correct and verified. The new 42.4% baseline is honest: it reflects
what is actually present in the corpus, not what the detectors hope to find.

To raise this number above 80%, the project needs a corpus that genuinely contains
structured agent execution traces — with tool names, operation taxonomy, and retry signals —
not flat chat transcripts. The next iteration should either source such a corpus from
richer HF datasets or self-instrument real agents.

## Root Cause Analysis — 21 Silent Detectors

The 21 trustworthy silent detectors were investigated at the code level.

### Infrastructure Bug: Pool Never Passed to Async Detectors

The validator calls `detector.detect_async(summary, spans)` without a `pool=pool` parameter.
8 detectors guard against `pool is None` as their first check and silently return `None`.

| Detector | Fix |
|---|---|
| `anomaly_cluster` | Validator now passes `pool=self.pool` to `detect_async()` |
| `escalation_rate` | Same |
| `first_run_heuristic` | Same |
| `run_frequency_anomaly` | Same |
| `run_duration` | Same |
| `cost_vs_baseline` | Same |
| `cost_spike` | Same (partial — also has threshold issue) |
| `output_drift` | Same |

**Status:** Fixed. Validator updated to accept `--db` flag and pass pool through. Run with:
```bash
python3 -m analytics.main validate --input data/traces/processed --db
```

### Corpus Limitations — 6 Detectors (No Actionable Fix)

These detectors correctly returned `None` because the required signals don't exist in the HF corpus:

| Detector | Reason |
|---|---|
| `approval_latency` | No human-intervention spans anywhere in corpus |
| `intervention_frequency` | `total_interventions` always 0 |
| `intervention_rejection` | `total_interventions` always 0 |
| `indeterminate_status` | No trace uses ambiguous status values |
| `specific_tool_error` | Tool error rate near 0% in 7.5% of traces that have tool data |
| `tool_error_rate` | Same |

### Threshold Issues — 7 Detectors (Needs Tuning)

These detectors ran on eligible traces but thresholds are too strict for the corpus:

| Detector | Current Threshold | Why It Doesn't Fire |
|---|---|---|
| `inactivity` | Gap > 30s between spans | Spans execute sub-second in agent traces |
| `cost_efficiency` | >$0.50 per tool call or >20 calls | Agent costs are cents, not dollars |
| `loop_detected` | Same tool ≥5 consecutive times | Rare in 7.5% of traces with tool data |
| `max_step_hit` | >20 tool spans or "max_steps_exceeded" status | Most traces under 20 tool spans |
| `token_explosion` | Late-half tokens 3x early-half tokens | Token counts are stable across runs |
| `tool_latency` | Single call >3x mean duration | Tool latency is consistent within runs |
| `tool_timeout` | Single call >60 seconds | Most tool calls complete in seconds |

### Fixed: `argument_loop` Compatibility Definition

`argument_loop` fired 5,827 anomalies but was classified as 0% eligible because the diagnostic
incorrectly required `has_tool_args`. Fixed: requirements changed to `["has_tool_name", "has_operations"]`.

## Next Steps — WBS 9.1 Work Items

### 9.1.6 Fix argument_loop compatibility definition ✅ DONE
### 9.1.7 Fix pool passing to async detectors ✅ DONE — added `--db` flag

### 9.1.8 Audit and tune threshold-dependent detectors

7 detectors have thresholds too strict for this corpus. For each:
- Run with `--db` to enable baseline comparison where applicable
- Trace-sample and determine if detection should fire on known patterns
- Lower thresholds or add corpus-adaptive baseline computation

### 9.1.9 Document structurally incompatible detectors

6 detectors require human-interaction or retry data that does not exist in the HF corpus.
Add `docs/detector-compatibility.md` documenting per-detector requirements and limitations.
