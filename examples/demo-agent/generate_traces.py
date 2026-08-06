#!/usr/bin/env python3
"""Generate diverse synthetic agent traces for detector validation.

= Purpose
Generates parquet files containing synthetic OTel trace data for 10 distinct
agent profiles.  Each agent produces runs across 4 scenarios (normal, loop,
high_cost, retry_storm), creating a rich dataset for validating the analytics
service's anomaly detectors across all 35+ detection rules.

= Agent profiles
10 agents with different tool sets and realistic behavior patterns:
  request_triage, code_reviewer, data_pipeline, research_assistant,
  cicd_orchestrator, security_scanner, customer_support, monitoring_agent,
  documentation_writer, price_optimizer.

= Scenarios (per agent, 40 runs each)
* ``normal``      -- 3 tool calls, no failures.  Baseline for success-rate
                      and cost detectors.
* ``loop``        -- 20 tool calls in a tight repeated pattern.  Exercises
                      loop/anomaly/pattern-loop/argument-loop detectors.
* ``high_cost``   -- 12 tool calls with escalating costs.  Exercises cost_spike,
                      cost_efficiency, token_explosion detectors.
* ``retry_storm`` -- 18 tool calls with error codes, retry flags, and escalating
                      costs after step 8.  Exercises retry_storm, systemic_retry,
                      transient_retry, cascading_retry, recovery_path.

= Trace shape
Each trace contains:
* 1 root ``invoke_agent`` span with agent metadata, status, and cost.
* 1 ``plan`` span (child of root) with the LLM planning phase.
* N ``execute_tool`` spans (children of root) with tool name, args, result,
  token usage, and optional error/tool flags.

All spans carry synthetic but realistic attributes matching the OTel semantic
conventions for generative AI: ``gen_ai.agent.name``, ``gen_ai.tool.name``,
``gen_ai.usage.prompt_tokens``, etc.

= Output
Parquet files in ``data/traces2/seeded/`` (or a custom directory passed as
the first CLI argument).  Each parquet file contains up to 5000 span rows.

= Usage
    python3 generate_traces.py
    python3 generate_traces.py data/my-traces
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

# ── Agent definitions ──────────────────────────────────────────────────────────
# Each agent has a name, version, tool list, scenarios to generate, and runs per
# scenario.  The total traces = sum(runs_per * len(scenarios)) across all agents
# = 10 * 4 * 40 = 1600 traces, ~22,000 span rows.

AGENTS = [
    {
        "name": "request_triage",
        "version": "v1.0",
        "tools": ["lookup_account", "search_kb", "escalate"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "code_reviewer",
        "version": "v1.0",
        "tools": ["read_file", "analyze_code", "lint_check", "suggest_fix"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "data_pipeline",
        "version": "v1.0",
        "tools": ["fetch_data", "validate_schema", "transform", "load_db"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "research_assistant",
        "version": "v1.0",
        "tools": ["search_web", "extract_content", "summarize", "cite_sources"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "cicd_orchestrator",
        "version": "v1.0",
        "tools": ["checkout_code", "run_tests", "build_image", "deploy", "rollback"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "security_scanner",
        "version": "v1.0",
        "tools": ["scan_deps", "check_cve", "assess_risk", "generate_report"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "customer_support",
        "version": "v1.0",
        "tools": ["classify_intent", "search_docs", "draft_response", "escalate_human"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "monitoring_agent",
        "version": "v1.0",
        "tools": ["check_metrics", "query_logs", "create_alert", "notify_oncall"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "documentation_writer",
        "version": "v1.0",
        "tools": ["read_source", "extract_docstrings", "generate_markdown", "publish_docs"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
    {
        "name": "price_optimizer",
        "version": "v1.0",
        "tools": ["fetch_market_data", "analyze_competitors", "compute_elasticity", "recommend_price"],
        "scenarios": ["normal", "loop", "high_cost", "retry_storm"],
        "runs_per": 40,
    },
]


# ── Span builder ───────────────────────────────────────────────────────────────


def _span(
    sid: str, tid: str, pid: str | None, op: str,
    attrs: dict[str, object], t0: float, dur: float, status: str = "ok",
) -> dict[str, Any]:
    """Build a single synthetic span row dict.

    Args:
        sid: Span ID (must be unique within the trace).
        tid: Trace ID (groups spans into a trace).
        pid: Parent span ID, or None for root spans.
        op: Operation name (``"invoke_agent"``, ``"plan"``, ``"execute_tool"``).
        attrs: Key-value attributes dictionary (will be JSON-serialized).
        t0: Start time as a float offset (added to a base timestamp).
        dur: Duration in milliseconds.
        status: Span status (``"ok"``, ``"error"``, ``"success"``).

    Returns:
        A dict with all the fields expected by the parquet schema.
    """
    return {
        "span_id": sid,
        "trace_id": tid,
        "parent_span_id": pid,
        "operation_name": op,
        # Timestamps are relative to 2026-08-04T12:00:00; the float offset is
        # divided by 1000 to convert ms -> seconds for the ISO timestamp.
        "start_time": f"2026-08-04T12:00:{t0/1000:07.3f}",
        "end_time": f"2026-08-04T12:00:{(t0+dur)/1000:07.3f}",
        "duration_ms": int(dur),
        # Attributes are stored as a JSON string to match the analytics
        # service's expected parquet schema format.
        "attributes_json": json.dumps(attrs),
        "status": status,
        "source_dataset": "synthetic",
        "source_row_idx": 0,
    }


# ── Trace generator ────────────────────────────────────────────────────────────


def _gen(agent: dict, scenario: str, idx: int) -> list[dict[str, Any]]:
    """Generate a single synthetic trace with spans for one agent run.

    Args:
        agent: Agent definition dict with ``name``, ``version``, ``tools`` keys.
        scenario: Behavior scenario (``"normal"``, ``"loop"``, ``"high_cost"``,
            ``"retry_storm"``).
        idx: 0-based run index (used in trace_id for uniqueness).

    Returns:
        A list of span row dicts forming one complete trace.
    """
    # Trace ID: ``syn_{agent}_{scenario}_{idx:04d}`` ensures uniqueness across
    # all runs while being human-readable.
    tid = f"syn_{agent['name']}_{scenario}_{idx:04d}"
    tools = agent["tools"]
    rows: list[dict[str, Any]] = []
    t = 0.0  # Running time offset in milliseconds.
    cost = random.uniform(0.01, 0.20)  # Initial cost (varies per trace).

    # ── Root span ──
    # Outcome text varies by scenario to give the semantic_loop and
    # output_drift detectors realistic content to analyze.
    content = {
        "normal": "Resolved",
        "loop": "Escalated – max steps hit",
        "high_cost": "Completed with high cost",
        "retry_storm": "Failed after retries",
    }[scenario]
    root_a: dict[str, object] = {
        "gen_ai.agent.name": agent["name"],
        "gen_ai.agent.version": agent["version"],
        "gen_ai.agent.workload.type": scenario,  # Scenario = workload type for simplicity.
        "gen_ai.agent.run.id": tid,
        "gen_ai.response.content": content,
        "gen_ai.agent.run.cost.total": round(cost, 4),
        "gen_ai.usage.prompt_tokens": random.randint(50, 200),
        "gen_ai.usage.completion_tokens": random.randint(20, 100),
    }
    rows.append(_span(f"{tid}_root", tid, None, "invoke_agent", root_a, t, 400, "success"))

    # ── Plan span ──
    # Every trace has a planning phase that generates a strategy text.
    # Token counts simulate LLM input/output tokenization.
    t += 10  # Small gap after root start.
    plan_a: dict[str, object] = {
        "gen_ai.response.content": f"Plan: {scenario} scenario for {agent['name']}",
        "gen_ai.usage.prompt_tokens": random.randint(30, 100),
        "gen_ai.usage.completion_tokens": random.randint(10, 50),
    }
    rows.append(_span(f"{tid}_plan", tid, f"{tid}_root", "plan", plan_a, t, 150, "ok"))

    # ── Tool spans ──
    # Number of tool iterations varies by scenario:
    #   normal: 3 calls    -> always converges quickly.
    #   loop: 20 calls     -> repeated tool calls for loop detectors.
    #   high_cost: 12 calls -> more calls = higher cost for cost detectors.
    #   retry_storm: 18 calls -> many retries for retry detectors.
    its = {"normal": 3, "loop": 20, "high_cost": 12, "retry_storm": 18}[scenario]
    for i in range(its):
        t += random.uniform(20, 80)  # Gap between tool calls.
        tn = random.choice(tools)  # Pick a random tool from the agent's set.
        result = f"result_{scenario}_{tid}_{i}"
        ta: dict[str, object] = {
            "gen_ai.tool.name": tn,
            "gen_ai.tool.result": result,
            "gen_ai.tool.args": json.dumps({"param": i, "scenario": scenario}),
            "gen_ai.usage.prompt_tokens": random.randint(5, 40),
            "gen_ai.usage.completion_tokens": random.randint(3, 20),
        }
        dur = random.uniform(30, 400)
        st = "ok"

        # Loop and retry_storm scenarios accumulate extra cost after step 8
        # to trigger cost_spike and cost_efficiency detectors.
        if scenario in ("loop", "retry_storm") and i > 8:
            cost += random.uniform(0.05, 0.30)
            ta["gen_ai.agent.run.cost.total"] = round(cost, 4)

        # Retry_storm scenario: after step 3, add retry flags and error codes.
        # After step 12, tool calls start failing (status="error") to exercise
        # the retry_storm, systemic_retry, and cascading_retry detectors.
        if scenario == "retry_storm" and i > 3:
            ta["retry"] = "true"
            ta["error.code"] = f"ERR_{random.choice(['TIMEOUT','NOT_FOUND','RATE_LIMIT'])}"
            st = "error" if i > 12 else "ok"

        rows.append(_span(f"{tid}_t{i}", tid, f"{tid}_root", "execute_tool", ta, t, dur, st))

    return rows


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    """Generate all traces and write them as parquet files.

    Traces are batched into parquet files of ~5000 span rows each to keep file
    sizes manageable and enable partial processing by the analytics pipeline.
    """
    # Output directory: first CLI argument or default.
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/traces2/seeded")
    out.mkdir(parents=True, exist_ok=True)

    # Fixed seed for reproducibility across runs.
    random.seed(42)

    batch: list[dict[str, Any]] = []
    bi = total = 0  # bi = batch index, total = trace count.

    for a in AGENTS:
        for s in a["scenarios"]:
            for i in range(a["runs_per"]):
                # Generate all spans for this trace and add to batch.
                batch.extend(_gen(a, s, i))
                total += 1

                # Flush to parquet when the batch exceeds 5000 span rows.
                # This keeps individual parquet files small (~few MB) and
                # avoids memory issues with the full 1.6M trace dataset.
                if len(batch) >= 5000:
                    import pyarrow as pa
                    import pyarrow.parquet as pq
                    t = pa.Table.from_pylist(batch)  # type: ignore
                    pq.write_table(t, str(out / f"traces-{bi:04d}.parquet"))
                    print(f"  batch {bi}: {len(batch)} rows ({total} traces)")
                    batch, bi = [], bi + 1

    # Flush any remaining rows in the final partial batch.
    if batch:
        import pyarrow as pa
        import pyarrow.parquet as pq
        t = pa.Table.from_pylist(batch)  # type: ignore
        pq.write_table(t, str(out / f"traces-{bi:04d}.parquet"))
        print(f"  final batch {bi}: {len(batch)} rows")

    print(f"\n{total} traces in {out}")
    # Print the validation command for convenience.
    print(f"python3 -m analytics.main validate --input {out} --diagnose")


if __name__ == "__main__":
    main()