# Synthetic Agent Trace Generator — Design

**Status:** Implemented  
**Target:** 1,000,000 synthetic agent traces  
**Output:** `agent-exec-trace/data/traces/synthetic/*.parquet`  
**Script:** `agent-exec-trace/examples/demo-agent/generate_bulk_traces.py`

---

## 1. Approach

A single monolithic Python script that directly generates parquet trace files. No actual agent runtime, no OTLP export — pure deterministic randomization producing OTel-semconv-compliant span rows.

**CLI:**
```bash
python3 generate_bulk_traces.py                                            # 1M traces, 10 agents
python3 generate_bulk_traces.py --num-traces 50000 --phase-timer 15
python3 generate_bulk_traces.py --agents BlipZorp FizzNark WobbleFlarp
```

| Flag | Default | Description |
|------|---------|-------------|
| `--num-traces` | 1,000,000 | Total traces to generate |
| `--agents` | all 10 | Which agent names to use |
| `--phase-timer` | 10 | Seconds per behavior phase |
| `--batch-size` | 10,000 | Traces per parquet file |
| `--output-dir` | `data/traces/synthetic` | Output directory |
| `--seed` | 42 | Random seed |

---

## 2. Output Format

Parquet schema compatible with the existing analytics validator (`generate_traces.py`):

| Column | Description |
|--------|-------------|
| `span_id` | Unique per span |
| `trace_id` | Shared by all spans in one trace |
| `parent_span_id` | `null` for root, otherwise parent span_id |
| `operation_name` | `invoke_agent`, `plan`, `execute_tool`, `retrieval`, `create_memory`, `search_memory`, `update_memory`, `delete_memory` |
| `start_time` / `end_time` | ISO 8601 |
| `duration_ms` | Span duration in ms |
| `attributes_json` | JSON string of OTel attributes |
| `status` | `ok`, `error`, `success` |

Batched: 10,000 traces per parquet file → ~100 files for 1M traces.

---

## 3. The 10 Agents (Funky Names)

| # | Agent Name | Flavor |
|---|-----------|--------|
| 1 | **BlipZorp** | Overthinker |
| 2 | **SnarfBlat** | Retry addict |
| 3 | **CrunkWumpus** | Money burner |
| 4 | **FizzNark** | Flakey failure |
| 5 | **GloopWrangler** | Human-needy |
| 6 | **ZorchSqueegee** | Lazy quitter |
| 7 | **PlibbleDash** | Speed demon |
| 8 | **NarfKnuckle** | Memory hoarder |
| 9 | **SkronkMuppet** | Drift king |
| 10 | **WobbleFlarp** | Balanced chaos |

All agents use the same toolkit. Variety comes from **per-phase randomization**, not agent-specific code. Every agent gets equal opportunity for every behavior pattern.

---

## 4. Shared Toolkit (14 Tools)

| Tool | Span Type | Base Cost | Base Latency |
|------|-----------|-----------|--------------|
| `search_kb` | `retrieval` | $0.002 | 100ms |
| `lookup_account` | `execute_tool` | $0.005 | 80ms |
| `analyze_data` | `execute_tool` | $0.010 | 200ms |
| `generate_report` | `execute_tool` | $0.020 | 350ms |
| `send_alert` | `execute_tool` | $0.003 | 50ms |
| `escalate_human` | `execute_tool` | $0.050 | 500ms |
| `fetch_metrics` | `retrieval` | $0.002 | 120ms |
| `scan_deps` | `execute_tool` | $0.015 | 400ms |
| `deploy_service` | `execute_tool` | $0.080 | 2000ms |
| `create_memory` | `create_memory` | $0.001 | 30ms |
| `search_memory` | `search_memory` | $0.001 | 30ms |
| `update_memory` | `update_memory` | $0.001 | 30ms |
| `delete_memory` | `delete_memory` | $0.001 | 30ms |
| `await_approval` | `execute_tool` | $0.050 | 60s (avg) |

Cost and latency jitter ±35% per call.

---

## 5. Trace Structure: Timer-Driven Phases

Each trace has a randomized duration (20-180s), divided into **10-second phases**:

```
│ Phase 0 (0-10s) │ Phase 1 (10-20s) │ Phase 2 (20-30s) │ ... │ Phase N │
│     warmup       │   random behavior │  random behavior  │     │  wrap   │
```

- **Phase 0 (warmup)**: 1-3 simple tool calls, no errors/retries/interventions. Every trace starts clean.
- **Phases 1+**: Each phase randomly activates 0-3 of these behavior modes:
  - **Loop** (6% chance): Same tool called 5-18 times consecutively → exercises LoopDetector, PatternLoopDetector, ArgumentLoopDetector
  - **Error phase** (10% chance): 35% of tool calls error → ToolErrorRateDetector, SpecificToolErrorDetector
  - **Retry phase** (8% chance): 25% of spans get `retry=true` → RetryStormDetector, SystemicRetryDetector, CascadingRetryDetector
  - **Timeout** (3% per call): 65-200s tool latency → ToolTimeoutDetector
  - **Inactivity gap** (8% chance): 10-60s gap inserted → InactivityDetector
  - **Token explosion** (6% late-phase chance): Token counts jump 10x → TokenExplosionDetector
  - **Memory blitz** (7% chance): 2-5 memory CRUD spans → exercises memory detectors
  - **Human intervention** (4% chance): 1-3 `await_approval` calls, 30-150s approval waits, 35% rejection rate → InterventionFrequencyDetector, EscalationRateDetector, ApprovalLatencyDetector, InterventionRejectionDetector
- **Sparsity** (12% of traces): 75% of spans pruned, some attributes dropped → tests detector resilience

### Span Tree (per trace)
```
invoke_agent (root)    ← run-level metadata, output, cost, retry/intervention counts
├── plan               ← one per phase
├── execute_tool: X    ← 2-10 calls per phase (random)
├── execute_tool: Y
├── retrieval: Z
├── [memory ops]       ← random per-phase
├── [await_approval]   ← random per-phase
├── plan               ← next phase
├── ...
```

---

## 6. Randomization Strategy

**Per-trace:** Duration (20-180s), version (70/20/10 v1/v2/v3), model, provider, workload type.

**Per-phase:** Tool count (3-10), which behavior modes activate, tool selection (weighted toward cheaper tools), error/retry/timeout probabilities.

**Per-span:** Token counts jittered, tool args unique per call, tool results vary by outcome, latency jitter ±35%.

**Root span**: Accumulated cost, retry count, intervention count, loop count, error count, output text (empty/short/normal/drifted), run status.

---

## 7. Detector Coverage

| Category | Detectors | How Exercised |
|----------|-----------|---------------|
| Tool Execution (8) | Loop, PatternLoop, ArgumentLoop, ToolErrorRate, SpecificToolError, ToolLatency, ToolTimeout, RedundantToolCall | Loop phases, error phases, timeout calls, jittered latency, repeated expensive tools |
| Cost & Resource (6) | CostSpike, CostVsBaseline, CostEfficiency, TokenExplosion, PerToolCostSpike, WastedToolCalls | Expensive tool loops, token explosion phases, accumulated cost, version cohorts (v1/v2/v3) |
| Runtime & Completion (5) | RunDuration, MaxStepHit, StepEfficiency, Inactivity, PrematureCompletion | 20-180s durations, inactivity gaps, early exits on error |
| Retry & Recovery (5) | RetryStorm, SystemicRetry, TransientRetry, CascadingRetry, RecoveryPath | Retry phases, retry+error combos |
| Interaction & Control (4) | InterventionFrequency, EscalationRate, ApprovalLatency, InterventionRejection | `await_approval` spans, rejection flags |
| Output Quality (4) | EmptyResponse, LowOutput, Indeterminate, OutputDrift | Empty/short/drifted outputs, error statuses |
| Cross-Run (3) | AnomalyCluster, RunFrequencyAnomaly, FirstRunHeuristic | Multi-anomaly traces, version transitions |

---

## 8. Runtime

- **Expected spans**: 40-90 per trace (avg ~65)
- **Expected total spans**: ~65M for 1M traces
- **Expected parquet size**: ~25-40 GB
- **Expected generation time**: 15-30 min on M3 Mac
- **100 output files**: `traces-0000.parquet` through `traces-0099.parquet`
