#!/usr/bin/env python3
"""Run the demo agent with OTLP export to a local Jaeger / Tempo backend.

= Purpose
Executes a single scenario of the deterministic request-triage demo agent with
OpenTelemetry tracing enabled.  Traces are exported via OTLP gRPC to a local
Jaeger or Tempo instance, where they can be inspected in the Jaeger UI.

= Architecture overview
1. Configure OTLP tracing to export spans to a local backend (Jaeger/Tempo).
2. Import and build the LangGraph from ``request_triage.graph.build_graph()``.
3. Wrap the compiled graph with ``trace_graph()`` from the agent-exec-trace SDK.
   This injects span instrumentation at each LangGraph node boundary.
4. Invoke the graph with a seeded scenario input (``seeds.all_requests()``).
5. Print the outcome, step count, cost estimate, and tool log to stdout.

= Scenarios
* ``normal``     -- Healthy request: account exists, KB has an answer ->
                    resolves in 2 steps.
* ``loop``       -- Missing account: lookups keep failing, searches keep missing
                    -> hits the MAX_STEPS cap and escalates.
* ``high_cost``  -- Open-ended intent: many KB searches across turns ->
                    high step count, high estimated cost.

= Usage
    python run_demo.py [--scenario normal|loop|high_cost] [--endpoint http://localhost:4317]

= Prerequisites
    - docker compose up -d jaeger  (or ``docker compose --profile tempo up -d``)
    - pip install "agent-exec-trace[otlp]"  (from the SDK package)
"""

from __future__ import annotations

import argparse
import os
import sys

# Make the demo agent package importable from the examples directory.
# ``src/`` is one level below ``run_demo.py`` and contains the
# ``request_triage`` package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from agent_exec_trace.config import SDKConfig
from agent_exec_trace.langgraph import trace_graph
from agent_exec_trace.tracer import configure_otlp_tracing

from request_triage.graph import DEFAULT_VERSION, build_graph
from request_triage.seeds import all_requests


def main() -> None:
    """Parse CLI args, configure tracing, run the seeded scenario, and print results."""
    parser = argparse.ArgumentParser(
        description="Run the request-triage demo agent with OTLP tracing"
    )
    parser.add_argument(
        "--scenario", choices=("normal", "loop", "high_cost"), default="normal"
    )
    parser.add_argument("--endpoint", default="http://localhost:4317")
    args = parser.parse_args()

    # 1. Configure tracing with OTLP export to the local backend.
    #    The service name appears in Jaeger's service dropdown.
    #    ``endpoint`` is the OTLP gRPC receiver address (Jaeger default: 4317).
    cfg = SDKConfig(service_name="request-triage-demo")
    configure_otlp_tracing(cfg, endpoint=args.endpoint)

    # 2. Build and wrap the graph.
    #    ``build_graph()`` returns a compiled LangGraph state graph (4 nodes:
    #    planner, run_tool, resolve, escalate).
    #    ``trace_graph()`` wraps it with OTel span instrumentation around each
    #    node, so every planner/tool/resolve transition creates a trace span.
    graph = build_graph()
    traced = trace_graph(
        graph,
        agent_name="request-triage",
        agent_version=DEFAULT_VERSION,
    )

    # 3. Run the seeded scenario.
    #    ``all_requests()[args.scenario]`` returns a TriageState dict with the
    #    scenario/account/intent fields pre-configured for that scenario.
    seed = all_requests()[args.scenario]
    print(f"Running scenario: {args.scenario}")
    result = traced.invoke(seed)

    # Print key fields from the final state so the user sees the run outcome.
    print(f"  Outcome: {result.get('outcome')} / {result.get('status')}")
    print(f"  Steps:   {result.get('step')}")
    print(f"  Cost:    {result.get('estimated_cost')}")
    print(f"  Tool log: {result.get('tool_log')}")

    # Direct the user to the Jaeger UI for trace inspection.
    print("View trace in Jaeger at http://localhost:16686/search?service=request-triage-demo")


if __name__ == "__main__":
    main()