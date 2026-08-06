# Instrumentation Guide

How to instrument your own agent with the `agent-exec-trace` Python SDK.
Covers both the raw Python decorator and the LangGraph adapter, span structure,
metadata propagation, and privacy control.

## Option 1 — Raw Python decorator

Use the `@trace_agent` decorator with `plan_span` and `tool_span` context
managers for any Python agent.

```python
from agent_exec_trace import trace_agent, plan_span, tool_span

@trace_agent(
    agent_name="support-triage",
    agent_version="1.2.0",
    workload_type="support",
)
def run_agent(query: str, account_id: str) -> dict:
    with plan_span("identify_intent"):
        intent = classify(query)

    results = []
    with tool_span("search_kb", tool_input={"query": query}):
        results = search_kb(query)

    with tool_span("lookup_account", tool_input={"account_id": account_id}):
        account = lookup_account(account_id)

    return {"intent": intent, "results": results, "account": account}
```

### Span context managers

| Manager | Use for |
|---|---|
| `plan_span(name)` | Reasoning/planning steps (agent deciding what to do) |
| `tool_span(name, tool_input=...)` | Tool invocations with structured input |
| `retrieval_span(name, query=...)` | Knowledge retrieval (RAG lookups, search) |
| `memory_span(name)` | Memory read/write operations |
| `approval_span(name)` | Human-in-the-loop approval gates |

Each context manager sets the OpenTelemetry span name and attributes
automatically. Exceptions raised inside a span are recorded as span events.

## Option 2 — LangGraph adapter

Wrap your compiled LangGraph graph with `TracedGraph` for automatic
instrumentation of every node.

```python
from agent_exec_trace.langgraph import TracedGraph
from agent_exec_trace.config import Config

config = Config(
    agent_name="support-triage",
    agent_version="1.2.0",
    workload_type="support",
    otlp_endpoint="http://localhost:4317",
)

# Build your LangGraph graph as usual
graph = builder.compile()

# Wrap it — every node invocation becomes a span
traced = TracedGraph(graph, config=config)

# Run normally — traces flow to OTLP automatically
result = traced.invoke({"query": "reset password", "account_id": "acct-001"})
```

### What TracedGraph instruments

| LangGraph event | Span created |
|---|---|
| Graph invocation start | Root `invoke_agent` span |
| Each node execution | `plan` / `execute_tool` / `retrieval` span (auto-detected from node name conventions) |
| Node errors | Span events with exception details |
| Graph completion | Span status + outcome |

Nodes named with `search_`, `lookup_`, `call_`, or `invoke_` prefixes are
classified as tool spans. Nodes with `plan_`, `think_`, or `reason_` prefixes
are classified as plan spans.

## Option 3 — Direct OTLP export

For advanced use, construct spans manually via the exporter:

```python
from agent_exec_trace.tracer import AgentTracer
from agent_exec_trace.config import Config

tracer = AgentTracer(
    Config(
        agent_name="my-agent",
        agent_version="0.1.0",
        workload_type="batch-job",
        otlp_endpoint="http://localhost:4317",
    )
)

with tracer.root_span("handle_request") as root:
    with tracer.child_span("plan", name="decide_action") as plan:
        plan.set_attribute("agent.plan.intent", "lookup")
    with tracer.child_span("execute_tool", name="search_kb") as tool:
        tool.set_attribute("agent.tool.name", "search_kb")
```

## How traces flow

```
┌─────────────────────┐
│  Your Agent (SDK)   │  @trace_agent / TracedGraph
│  emits OTel spans   │
└────────┬────────────┘
         │ OTLP gRPC (:4317) or HTTP (:4318)
         ▼
┌─────────────────────┐
│  Jaeger / Tempo     │  Trace storage + query
└────────┬────────────┘
         │ Analytics worker polls Jaeger API
         ▼
┌─────────────────────┐
│  Analytics Worker   │  Runs 35 detectors, computes summaries
│  → Postgres         │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  FastAPI (read API) │  /api/runs, /api/fleet, /api/compare, /api/anomalies
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  React Web UI       │  Fleet Health, Run Timeline, Version Compare, Anomaly Inbox
└─────────────────────┘
```

## Expected span structure

Every instrumented run produces this hierarchy:

```
invoke_agent (root)                        agent_name, agent_version, workload_type
├── plan: "identify_intent"                agent.plan.name
├── execute_tool: "search_kb"              agent.tool.name, agent.tool.input.*
├── retrieval: "kb_lookup"                 agent.retrieval.query, agent.retrieval.source
├── approval: "confirm_escalation"         agent.approval.actor
├── memory: "write_session"                agent.memory.operation
└── plan: "decide_outcome"                 agent.plan.name
```

Spans carry OpenTelemetry GenAI semantic convention attributes where
applicable, plus custom `agent.*` attributes for behavior-specific data.

## Metadata propagation

Every root span carries these metadata attributes:

| Attribute | Description | Required |
|---|---|---|
| `agent.name` | Logical agent name (e.g. `support-triage`) | Yes |
| `agent.version` | Agent version string (e.g. `1.2.0`) | Yes |
| `agent.workload_type` | Workload category (e.g. `support`, `batch`, `interactive`) | Yes |
| `agent.prompt_version` | Optional prompt template version | No |
| `agent.model_version` | Optional model identifier | No |
| `agent.tool_schema_version` | Optional tool schema version | No |

Version metadata is critical for the fleet health and version compare views.
Every run with the same `agent_name` and `agent_version` is grouped into a
cohort for comparison and anomaly baseline calculation.

## Privacy control

The SDK supports four content-capture modes to control what tool inputs,
outputs, and plan details appear in traces.

| Mode | What's captured | Use case |
|---|---|---|
| **Metadata-only** (default) | Span names, tool names, durations, outcomes. No payload content. | Production: maximum safety. |
| **Truncated** | First 256 characters of tool I/O and plan text. | Development: partial context. |
| **Hashed** | SHA-256 hash of content for integrity checks without exposing payload. | Audit: verify content hasn't changed. |
| **Full** | Complete tool inputs, outputs, and plan details. | Debugging: full trace fidelity. |

Configure via `Config`:

```python
from agent_exec_trace.config import Config, PrivacyMode

config = Config(
    agent_name="support-triage",
    agent_version="1.2.0",
    privacy_mode=PrivacyMode.TRUNCATED,
)
```

The default `Metadata-only` mode means traces show *what tools were called* and
*how long they took*, but not *what data passed through them*. This is the safe
default for production workloads.

## Configuration surface

```python
from agent_exec_trace.config import Config, PrivacyMode

config = Config(
    # Required
    agent_name="support-triage",
    agent_version="1.2.0",

    # Optional
    workload_type="support",
    otlp_endpoint="http://localhost:4317",
    otlp_insecure=True,
    privacy_mode=PrivacyMode.METADATA_ONLY,
    service_name="agent-exec-trace",

    # Version dimensions (optional, enables richer compare views)
    prompt_version="v3",
    model_version="gpt-4o-2024-08-06",
    tool_schema_version="1.0.0",
)
```

## Verifying instrumentation

After running your agent, check Jaeger at `http://localhost:16686`:

1. Select `agent-exec-trace` from the service dropdown
2. Click **Find Traces**
3. Confirm your root span has `agent.name` and `agent.version` tags
4. Drill into the trace to verify child span hierarchy

Then check the web UI at `http://localhost:5173` — your agent should appear
in the Fleet Health view after the analytics worker processes the trace
(typically 15–30 seconds).
