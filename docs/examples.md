# Examples

Ready-to-run examples showing how to instrument agents with the `agent-exec-trace` SDK.

---

## Demo agent (`examples/demo-agent/`)

A deterministic request-triage agent built with LangGraph, instrumented end-to-end with the SDK. Three scenarios produce different behavior patterns (normal, loop, high-cost) so you can see anomalies materialize in the UI.

### Run it

```bash
# 1. Boot the stack (Jaeger + Postgres + API + Analytics + Web)
make stack-up

# 2. Install the SDK with OTLP export extras
pip install "agent-exec-trace[otlp]"

# 3. Run a scenario
cd examples/demo-agent
python run_demo.py --scenario loop --endpoint http://localhost:4317

# 4. View the trace
open http://localhost:16686      # Jaeger UI
open http://localhost:5173       # operator UI (after analytics polls, ~30s)
```

### Scenarios

| Scenario | Behavior | Expected anomalies |
|---|---|---|
| `normal` | Healthy request, resolves in 2 steps | None |
| `loop` | Missing account, lookups keep failing | `loop`, `tool_loop`, `step_exhaustion` |
| `high_cost` | Open-ended intent, many KB searches | `cost_spike`, `token_explosion`, `wasted_tool_calls` |

### Bulk trace generation

Generate many traces at once to populate the fleet dashboard:

```bash
python generate_traces.py --count 50 --scenario loop
python generate_bulk_traces.py
```

See `examples/demo-agent/scenario-matrix.md` for the full scenario catalog.

---

## Instrumenting your own agent

### Raw Python agent

```python
from agent_exec_trace import AgentTracer, trace_agent, tool_span

# Configure OTLP export once at startup
AgentTracer.setup(otlp_endpoint="http://localhost:4317", service_name="my-agent")

@trace_agent(agent_name="my-agent", agent_version="1.0.0", workload_type="support")
def handle_request(query: str) -> str:
    with tool_span("search_kb", tool_args={"q": query}):
        result = search(query)
    return result
```

### Async agent

```python
@trace_agent(agent_name="my-agent", agent_version="1.0.0")
async def handle_request(query: str) -> str:
    with tool_span("search_kb", tool_args={"q": query}):
        result = await search(query)
    return result
```

### LangGraph agent

```python
from agent_exec_trace import AgentTracer, TracedGraph

AgentTracer.setup(otlp_endpoint="http://localhost:4317")

graph = build_graph().compile()
traced = TracedGraph(graph, agent_name="my-langgraph-agent", agent_version="1.0.0")
result = traced.invoke({"query": "reset password"})
```

See the [Instrumentation Guide](reference/instrumentation.md) for full details including privacy modes, version metadata, and all span types.

---

## Privacy modes

Control what data is captured in spans:

| Mode | Behavior |
|---|---|
| `METADATA_ONLY` (default) | Span structure + counts, no argument content |
| `TRUNCATED` | Truncated argument values |
| `HASHED` | Hashed argument values (length-preserving) |
| `FULL` | Full argument content (use with care) |

```python
from agent_exec_trace import RedactionConfig, PrivacyMode

config = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)
```
