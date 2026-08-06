#!/usr/bin/env python3
"""Generate diverse synthetic agent traces for detector validation.

10 distinct agent profiles with different tools, failure modes, costs, and retry patterns.
Outputs parquet files the validator consumes directly.
import pyarrow as pa
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any


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


def _span(
    sid: str, tid: str, pid: str | None, op: str,
    attrs: dict[str, object], t0: float, dur: float, status: str = "ok",
) -> dict[str, Any]:
    return {
        "span_id": sid, "trace_id": tid, "parent_span_id": pid,
        "operation_name": op,
        "start_time": f"2026-08-04T12:00:{t0/1000:07.3f}",
        "end_time": f"2026-08-04T12:00:{(t0+dur)/1000:07.3f}",
        "duration_ms": int(dur),
        "attributes_json": json.dumps(attrs),
        "status": status,
        "source_dataset": "synthetic", "source_row_idx": 0,
    }


def _gen(agent: dict, scenario: str, idx: int) -> list[dict[str, Any]]:
    tid = f"syn_{agent['name']}_{scenario}_{idx:04d}"
    tools = agent["tools"]
    rows: list[dict[str, Any]] = []
    t = 0.0
    cost = random.uniform(0.01, 0.20)

    # Root
    content = {"normal": "Resolved", "loop": "Escalated – max steps hit",
                "high_cost": "Completed with high cost", "retry_storm": "Failed after retries"}[scenario]
    root_a: dict[str, object] = {
        "gen_ai.agent.name": agent["name"],
        "gen_ai.agent.version": agent["version"],
        "gen_ai.agent.workload.type": scenario,
        "gen_ai.agent.run.id": tid,
        "gen_ai.response.content": content,
        "gen_ai.agent.run.cost.total": round(cost, 4),
        "gen_ai.usage.prompt_tokens": random.randint(50, 200),
        "gen_ai.usage.completion_tokens": random.randint(20, 100),
    }
    rows.append(_span(f"{tid}_root", tid, None, "invoke_agent", root_a, t, 400, "success"))

    # Plan
    t += 10
    plan_a: dict[str, object] = {
        "gen_ai.response.content": f"Plan: {scenario} scenario for {agent['name']}",
        "gen_ai.usage.prompt_tokens": random.randint(30, 100),
        "gen_ai.usage.completion_tokens": random.randint(10, 50),
    }
    rows.append(_span(f"{tid}_plan", tid, f"{tid}_root", "plan", plan_a, t, 150, "ok"))

    # Tools
    its = {"normal": 3, "loop": 20, "high_cost": 12, "retry_storm": 18}[scenario]
    for i in range(its):
        t += random.uniform(20, 80)
        tn = random.choice(tools)
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
        if scenario in ("loop", "retry_storm") and i > 8:
            cost += random.uniform(0.05, 0.30)
            ta["gen_ai.agent.run.cost.total"] = round(cost, 4)
        if scenario == "retry_storm" and i > 3:
            ta["retry"] = "true"
            ta["error.code"] = f"ERR_{random.choice(['TIMEOUT','NOT_FOUND','RATE_LIMIT'])}"
            st = "error" if i > 12 else "ok"
        rows.append(_span(f"{tid}_t{i}", tid, f"{tid}_root", "execute_tool", ta, t, dur, st))

    return rows


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/traces2/seeded")
    out.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    batch: list[dict[str, Any]] = []
    bi = total = 0
    for a in AGENTS:
        for s in a["scenarios"]:
            for i in range(a["runs_per"]):
                batch.extend(_gen(a, s, i))
                total += 1
                if len(batch) >= 5000:
                    import pyarrow.parquet as pq
                    t = pa.Table.from_pylist(batch)  # type: ignore
                    pq.write_table(t, str(out / f"traces-{bi:04d}.parquet"))
                    print(f"  batch {bi}: {len(batch)} rows ({total} traces)")
                    batch, bi = [], bi + 1
    if batch:
        import pyarrow.parquet as pq
        t = pa.Table.from_pylist(batch)  # type: ignore
        pq.write_table(t, str(out / f"traces-{bi:04d}.parquet"))
        print(f"  final batch {bi}: {len(batch)} rows")

    print(f"\n{total} traces in {out}")
    print(f"python3 -m analytics.main validate --input {out} --diagnose")


if __name__ == "__main__":
    main()
