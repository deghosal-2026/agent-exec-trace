#!/usr/bin/env python3
"""Run the demo agent with OTLP export to a local Jaeger / Tempo backend.

Usage:
    python run_demo.py [--scenario normal|loop|high_cost] [--endpoint http://localhost:4317]

Prerequisites:
    - docker compose up -d jaeger  (or ``docker compose --profile tempo up -d``)
    - pip install "agent-exec-trace[otlp]"  (from the SDK package)
"""

from __future__ import annotations

import argparse
import os
import sys

# Make the demo agent package importable from the examples directory.
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
    cfg = SDKConfig(service_name="request-triage-demo")
    configure_otlp_tracing(cfg, endpoint=args.endpoint)

    # 2. Build and wrap the graph.
    graph = build_graph()
    traced = trace_graph(
        graph,
        agent_name="request-triage",
        agent_version=DEFAULT_VERSION,
    )

    # 3. Run the seeded scenario.
    seed = all_requests()[args.scenario]
    print(f"Running scenario: {args.scenario}")
    result = traced.invoke(seed)
    print(f"  Outcome: {result.get('outcome')} / {result.get('status')}")
    print(f"  Steps:   {result.get('step')}")
    print(f"  Cost:    {result.get('estimated_cost')}")
    print(f"  Tool log: {result.get('tool_log')}")
    print("View trace in Jaeger at http://localhost:16686/search?service=request-triage-demo")


if __name__ == "__main__":
    main()