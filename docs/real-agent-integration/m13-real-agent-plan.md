# Real-World Agent Integration Test Plan — M13.2

> Validates the agent-exec-trace SDK integration workflow by instrumenting
> real open-source GitHub agents, generating traces, and running the full
> detection pipeline (rule-based + LLM 9B).

---

## 1. Purpose

The v0.1.0 value proposition is: "instrument any agent in 5 lines of code."
This claim needs validation against real, diverse agents from GitHub — not
just our own demo workloads and synthetic traces.

This test answers five questions:

1. **How easy is SDK integration?** Time from clone to traces-in-Jaeger.
2. **Trace quality on real agents?** Do real agents produce well-structured span trees?
3. **Detector quality on real traces?** Which anomalies fire? Are they meaningful?
4. **LLM vs rule-based on real data?** Does the LLM layer add value beyond synthetic?
5. **Integration friction?** What breaks? What needs docs or fixes?

## 2. Agent Selection Criteria

Agents must be:

| Criterion | Rationale |
|---|---|
| **Zero-infra** | No database, no Redis, no external services. `pip install` only. |
| **No API keys** | Agents that work with local/mock tools or OpenAI-compatible endpoints. |
| **Single-file or near** | Easy to understand and instrument. No complex project structures. |
| **Runnable in <5 min** | Clone, install, run — minimal setup. |
| **Diverse** | Different frameworks, use cases, and failure patterns. |

Excluded: agents requiring Postgres, Redis, Docker, cloud APIs, or
multi-service orchestration.

## 3. Agent List

### 3.1 Initial Roster (8 agents attempted)

| # | Slug | Agent | Framework | Repo | Status |
|---|---|---|---|---|---|
| 1 | `chatbot` | Chatbot in LangGraph | LangGraph | `campusx-official/chatbot-in-langgraph` | Downloaded |
| 2 | `eval-graph` | EvalGraph | LangGraph | `zachary-wilde/eval-graph` | Downloaded |
| 3 | `mcp-agents` | MCP Agents | LangGraph | `braincrew-lab/langgraph-mcp-agents` | Downloaded |
| 4 | `weather` | Weather Agent | PydanticAI | `pakagronglb/weather-agent-pydanticAI` | **Blocked** (old API) |
| 5 | `github-agent` | GitHub Agent | PydanticAI | `coleam00/pydantic-ai-github-agent` | **Blocked** (old API) |
| 6 | `crew-quickstart` | CrewAI Quickstart | CrewAI | `crewAIInc/crewAI-examples` | Downloaded |
| 7 | `react-agent` | React Agent | LangGraph | `langchain-ai/react-agent` | **Empty clone** |
| 8 | `rag-agent` | RAG Q&A | LangChain | `langchain-ai/langchain` | **Sparse checkout miss** |

### 3.2 Discovery: Framework Version Incompatibility

During setup, we discovered that **PydanticAI agents from GitHub use the v1
API** (`OpenAIModel` with explicit provider), which is incompatible with
the current `pydantic-ai>=2.22` installed by `pip install pydantic-ai`.
The v2 API uses model strings (`'openai:model-name'`) and environment
variables (`OPENAI_API_KEY`, `OPENAI_BASE_URL`) instead of provider objects.

This is a significant finding for the platform: **real-world agents often
depend on specific framework versions.** An observability SDK must work
across version boundaries or provide adapter shims. For v0.1.0, we
document this as a known limitation and narrow to agents compatible with
current framework versions.

### 3.3 Final Roster (6 agents — what actually runs)

| # | Agent | Framework | Source | Status |
|---|---|---|---|---|
| 1 | **`request_triage`** | LangGraph | Our `examples/` — already built and instrumented | ✅ Working |
| 2 | **`agent-chatbot`** | LangGraph | GitHub clone — `campusx-official/chatbot-in-langgraph` | Downloaded, needs setup |
| 3 | **`agent-eval-graph`** | LangGraph | GitHub clone — `zachary-wilde/eval-graph` | Downloaded, needs setup |
| 4 | **`agent-mcp`** | LangGraph | GitHub clone — `braincrew-lab/langgraph-mcp-agents` | Downloaded, needs setup |
| 5 | **PydanticAI v2 agent** | PydanticAI v2 | Write in ~15 lines using current API (`Agent('openai:...')`) | ✅ Built, tested |
| 6 | **Raw Python agent** | Raw Python | Write in ~10 lines using `@trace_agent` decorator | ✅ Built, 10K traces generated |

### 3.4 Discovery: OTLP Export Was Never End-to-End Tested

During trace generation for the raw Python agent, 10,000 traces were generated
but **none appeared in Jaeger.** Investigation revealed two independent bugs
that had cancelled each other out during M3 "validation":

**Bug 1 — Port 4317 not exposed in docker-compose.yml.**
The OpenTelemetry Collector's gRPC port (4317) was never mapped from the
container to the host. Only the HTTP port (4318) was exposed. The SDK
configures OTLP gRPC export to `http://localhost:4317`, so it never
reached the collector.

**Bug 2 — SDK using `configure_tracing` instead of `configure_otlp_tracing`.**
The SDK has two configuration functions:
- `configure_tracing(config)` — sets up LOCAL tracing only (outputs spans to
  console, no export). This is useful for development/debugging.
- `configure_otlp_tracing(config)` — sets up OTLP gRPC export to the
  configured endpoint.

Every trace-generation script was using `configure_tracing`, so traces were
printed to stdout but never actually exported anywhere. The OTLP
configuration was present in the codebase but never wired into the actual
trace generation path.

**Impact on M3 validation:** The M3 quality gates were checked as done
(✅ "Validate collector-based OTLP export to Jaeger") but the actual
end-to-end path was never verified. The two bugs cancelled each other out:
port 4317 wasn't exposed, but the SDK wasn't exporting anyway.

**Fixes applied:**
1. Added `- "4317:4317"` to the `otel-collector` service in
   `docker-compose.yml`
2. Changed `configure_tracing` → `configure_otlp_tracing` in
   `generate_traces.py`
3. Verified: `m13-raw-agent` now appears in Jaeger and traces are queryable

**Takeaway:** This is a critical finding. The SDK's default behavior
(`configure_tracing`) is safe-by-default but silent — it does not export
anywhere. New users who run the quickstart without reading the
`configure_otlp_tracing` docs will see their agent running but no traces
in Jaeger. The quickstart and instrumentation docs MUST be updated to
explicitly call `configure_otlp_tracing`. This is a v0.1.0 release blocker
documentation issue.

## 4. Setup (Pre-Test)

```bash
# 1. Clone agents into a local directory (not committed to repo)
mkdir -p /tmp/m13-agents
cd /tmp/m13-agents

# 2. Clone each agent
git clone https://github.com/campusx-official/chatbot-in-langgraph.git agent-chatbot
git clone https://github.com/zachary-wilde/eval-graph.git agent-eval-graph
git clone https://github.com/braincrew-lab/langgraph-mcp-agents.git agent-mcp
git clone https://github.com/pakagronglb/weather-agent-pydanticAI.git agent-weather
git clone https://github.com/coleam00/pydantic-ai-github-agent.git agent-github
git clone https://github.com/crewAIInc/crewAI-examples.git agent-crew
git clone https://github.com/langchain-ai/react-agent.git agent-react
git clone https://github.com/langchain-ai/langchain.git agent-langchain

# 3. Set up each agent (pip install + configure)
# (per-agent setup commands documented in the execution log)
```

## 5. Execution Plan

### 5.1 Phase 1 — Install and Verify

For each agent:
- [ ] Clone the repo
- [ ] `pip install -r requirements.txt` (or equivalent)
- [ ] Verify it runs end-to-end WITHOUT our SDK first
- [ ] Record setup time and any friction

### 5.2 Phase 2 — Instrument with SDK

For each agent:
- [ ] Add SDK to dependencies: `pip install -e ../../packages/python-sdk/`
- [ ] Add 3-5 lines of instrumentation code:
  - LangGraph agents: wrap graph with `TracedGraph(...)`
  - PydanticAI agents: wrap with `@trace_agent` decorator
  - CrewAI agents: wrap with `@trace_agent` decorator
- [ ] Configure OTLP export to local collector
- [ ] Record instrumentation time and lines changed
- [ ] Take screenshot of the instrumentation diff

### 5.3 Phase 3 — Generate Traces

For each agent:
- [ ] Run the agent with representative input(s)
- [ ] Verify traces appear in Jaeger (http://localhost:16686)
- [ ] Verify traces are ingested by analytics worker
- [ ] Run 3-5 different inputs per agent to get diverse traces
- [ ] Record: trace count, span count per trace, trace depth

### 5.4 Phase 4 — Run Detectors

For all agent traces combined:
- [ ] **Pass 1 — Rule-based only:** `analytics validate --input /tmp/m13-traces --max-traces N`
  → output to `data/m13-real/no-llm/`
- [ ] **Pass 2 — Rule-based + LLM (9B):** `ANALYTICS_LLM_CHAT_MODEL=Qwen3.5-9B-MLX-4bit analytics validate --input /tmp/m13-traces --max-traces N --llm-sample N`
  → output to `data/m13-real/llm-9b/`

### 5.5 Phase 5 — Document

- [ ] Write integration walkthrough per agent
- [ ] Capture screenshots of anomalies in UI
- [ ] Fill in the report template below

## 6. Measurements to Capture

### 6.1 Integration Metrics

| Metric | Per-Agent | How to Measure |
|---|---|---|
| Setup time | ✓ | Wall clock from clone to "runs" |
| Instrumentation lines | ✓ | Lines of SDK code added |
| Instrumentation time | ✓ | Wall clock to add SDK |
| Friction points | ✓ | What broke, what needed docs |
| Framework | ✓ | LangGraph / PydanticAI / CrewAI / LangChain |

### 6.2 Trace Quality Metrics

| Metric | Per-Agent | How to Measure |
|---|---|---|
| Traces generated | ✓ | Count in Jaeger |
| Avg spans per trace | ✓ | Analytics worker summary |
| Max span depth | ✓ | Span tree inspection |
| Operation types | ✓ | Distribution of plan/tool/retrieval/memory spans |
| Trace completeness | ✓ | % of traces with root span + metadata |

### 6.3 Detection Metrics

| Metric | Per-Agent | Aggregate |
|---|---|---|
| Rule-based anomalies found | ✓ | ✓ |
| LLM (9B) anomalies found | ✓ | ✓ |
| LLM-only anomalies found | ✓ | ✓ |
| Detector types fired | ✓ | ✓ |
| Meaningful anomalies (human review) | ✓ | ✓ |
| False positives (human review) | ✓ | ✓ |

### 6.4 Qualitative Assessment

Per-agent, after review:
- [ ] Are the anomalies meaningful? (1-5 scale)
- [ ] Would an operator act on them? (yes/no)
- [ ] Does the trace tell the story of what happened? (1-5 scale)
- [ ] Was the SDK easy to add? (1-5 scale)

## 7. Success Criteria

| Criterion | Target |
|---|---|
| Agents instrumented | ≥6 of 8 |
| Average instrumentation time | ≤5 minutes |
| Average instrumentation lines | ≤10 lines |
| Traces visible in Jaeger | All agents |
| Rule-based anomalies found | ≥1 per agent |
| LLM finds anomalies rules missed | ≥0 additional anomalies |
| UI shows agent data | All views populated |
| Integration walkthrough | Documented per agent |

---

# Real-World Agent Integration Test Report — M13.2

> **Status:** PENDING — execution planned
> **Date:** TBD
> **Model:** Qwen3.5-9B-MLX-4bit (thinking disabled)
> **Script:** `scripts/m13/run-real-agent-validation.sh` (TBD)

## 1. Integration Summary

| # | Agent | Framework | Setup Time | SDK Lines | SDK Time | Traces | Spans/Trace | Max Depth | Friction |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `chatbot` | LangGraph | — | — | — | — | — | — | — |
| 2 | `eval-graph` | LangGraph | — | — | — | — | — | — | — |
| 3 | `mcp-agents` | LangGraph | — | — | — | — | — | — | — |
| 4 | `weather` | PydanticAI | — | — | — | — | — | — | — |
| 5 | `github-agent` | PydanticAI | — | — | — | — | — | — | — |
| 6 | `crew-quickstart` | CrewAI | — | — | — | — | — | — | — |
| 7 | `react-agent` | LangGraph | — | — | — | — | — | — | — |
| 8 | `rag-agent` | LangChain | — | — | — | — | — | — | — |
| | **Average** | | — | — | — | — | — | — | |

### 1.1 SDK Integration Experience

_(Per-agent walkthrough of what worked and what broke.)_

**LangGraph agents (TracedGraph wrapper):**
```
# Typical instrumentation (3 lines):
from agent_exec_trace.langgraph import TracedGraph
from agent_exec_trace.context import RunContext

ctx = RunContext(agent_name="chatbot", agent_version="v1.0")
graph = TracedGraph(original_graph, ctx)
```

**PydanticAI agents (@trace_agent decorator):**
```
# Typical instrumentation (2 lines):
from agent_exec_trace.raw import trace_agent

@trace_agent(agent_name="weather", agent_version="v1.0")
async def run_agent(payload): ...
```

**CrewAI agents (@trace_agent decorator):**
```
# Typical instrumentation (2 lines):
from agent_exec_trace.raw import trace_agent

@trace_agent(agent_name="crew", agent_version="v1.0")
def run_crew(payload): ...
```

### 1.2 Friction Points

| Issue | Agent(s) | Severity | Resolution |
|---|---|---|---|
| — | — | — | — |

## 2. Trace Quality

### 2.1 Per-Agent Trace Statistics

| Agent | Total Traces | Spans/Trace (mean) | Spans/Trace (max) | Max Depth | Operation Types |
|---|---|---|---|---|---|
| `chatbot` | — | — | — | — | — |
| `eval-graph` | — | — | — | — | — |
| `mcp-agents` | — | — | — | — | — |
| `weather` | — | — | — | — | — |
| `github-agent` | — | — | — | — | — |
| `crew-quickstart` | — | — | — | — | — |
| `react-agent` | — | — | — | — | — |
| `rag-agent` | — | — | — | — | — |

### 2.2 Trace Structure Observations

_(Per-agent: does the span tree correctly capture the agent's behavior?)_

## 3. Detection Results

### 3.1 Headline Numbers

| Metric | Rule-Based Only | With LLM (9B) |
|---|---|---|
| Traces processed | — | — |
| Total anomalies | — | — |
| Additional anomalies vs rules | — | — |
| Detector types fired | — | — |
| LLM-only types fired | — | — |

### 3.2 Per-Detector Breakdown

| Anomaly Type | Rules Only | With LLM | Δ | Category |
|---|---|---|---|---|
| _(to be filled)_ | — | — | — | — |

### 3.3 LLM Detector Results

| Detector | Count | Fire Rate | Model Used |
|---|---|---|---|
| `hallucination` | — | — | Qwen3.5-9B-MLX-4bit |
| `confusion_pattern` | — | — | Qwen3.5-9B-MLX-4bit |
| `semantic_loop` | — | — | Qwen3.5-9B-MLX-4bit |
| `goal_drift` | — | — | Qwen3.5-9B-MLX-4bit |
| `quality_degradation` | — | — | Qwen3.5-9B-MLX-4bit |

### 3.4 Per-Agent Anomaly Distribution

| Agent | Rule-Based Anomalies | LLM Anomalies | Top Detectors |
|---|---|---|---|
| `chatbot` | — | — | — |
| `eval-graph` | — | — | — |
| `mcp-agents` | — | — | — |
| `weather` | — | — | — |
| `github-agent` | — | — | — |
| `crew-quickstart` | — | — | — |
| `react-agent` | — | — | — |
| `rag-agent` | — | — | — |

## 4. LLM Telemetry

| Metric | Value |
|---|---|
| Model | Qwen3.5-9B-MLX-4bit |
| Total LLM calls | — |
| Errors | — |
| JSON parse rate | — |
| p50 latency | — |
| p95 latency | — |
| Total tokens | — |
| Tokens/anomaly | — |
| Total LLM time | — |

## 5. Qualitative Assessment

### 5.1 Per-Agent Review

| Agent | SDK Ease (1-5) | Trace Quality (1-5) | Anomaly Meaningfulness (1-5) |
|---|---|---|---|
| `chatbot` | — | — | — |
| `eval-graph` | — | — | — |
| `mcp-agents` | — | — | — |
| `weather` | — | — | — |
| `github-agent` | — | — | — |
| `crew-quickstart` | — | — | — |
| `react-agent` | — | — | — |
| `rag-agent` | — | — | — |
| **Average** | — | — | — |

### 5.2 Operator Would Act On

| Anomaly (Agent, Type) | Actionable? | Why? |
|---|---|---|
| — | — | — |

## 6. Comparison: Synthetic vs Real Traces

| Metric | Synthetic (100 traces) | Real Agents (N traces) |
|---|---|---|
| Rule-based anomalies/trace | 5.08 | — |
| LLM anomalies/trace (9B) | 1.29 | — |
| Hallucination fire rate | 98% | — |
| Confusion pattern fire rate | 31% | — |
| JSON parse rate | 99.4% | — |
| Tokens/anomaly | 79 | — |

**Key question:** Are hallucination and confusion pattern rates lower on real
traces? Almost certainly yes — real agents produce fewer unsupported claims
than the synthetic generator's deliberately verbose outputs.

## 7. Findings

### 7.1 What Worked Well

_(To be filled after execution.)_

### 7.2 What Needed Fixes

_(To be filled after execution.)_

### 7.3 v0.2.0 Recommendations

_(To be filled after execution.)_

## 8. Raw Data

| Artifact | Location |
|---|---|
| Integration walkthroughs | `docs/real-agent-integration/agents/` |
| Trace parquet files | `/tmp/m13-traces/` |
| Rule-based validation | `data/m13-real/no-llm/` |
| LLM (9B) validation | `data/m13-real/llm-9b/` |
| Comparison report | `data/m13-real/comparison/` |
| Screenshots | `docs/real-agent-integration/screenshots/` |