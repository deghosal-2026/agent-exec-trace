#!/usr/bin/env python3
"""Generate synthetic agent traces — 1M+ traces with randomized behaviors.

Usage:
  python3 generate_bulk_traces.py
  python3 generate_bulk_traces.py --num-traces 50000 --phase-timer 15 --output-dir ./my-traces
  python3 generate_bulk_traces.py --num-traces 100000 --agents BlipZorp FizzNark WobbleFlarp --seed 99
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate synthetic agent traces with timer-driven behavior phases."
    )
    p.add_argument("--num-traces", type=int, default=1_000_000)
    p.add_argument("--agents", nargs="*", default=None,
                   help="Agent names to use (default: all 10)")
    p.add_argument("--phase-timer", type=int, default=10,
                   help="Seconds per behavior phase (default: 10)")
    p.add_argument("--batch-size", type=int, default=10_000,
                   help="Traces per parquet file (default: 10000)")
    p.add_argument("--output-dir", type=str, default="data/traces/synthetic")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


# ── Tools (shared by all agents) ──────────────────────────────────────────────

TOOLS = [
    # name,              span_type,        base_cost, base_latency_ms, is_expensive
    ("search_kb",        "retrieval",      0.002,     100,              False),
    ("lookup_account",   "execute_tool",   0.005,      80,              False),
    ("analyze_data",     "execute_tool",   0.010,     200,              False),
    ("generate_report",  "execute_tool",   0.020,     350,              True),
    ("send_alert",       "execute_tool",   0.003,      50,              False),
    ("escalate_human",   "execute_tool",   0.050,     500,              True),
    ("fetch_metrics",    "retrieval",      0.002,     120,              False),
    ("scan_deps",        "execute_tool",   0.015,     400,              False),
    ("deploy_service",   "execute_tool",   0.080,    2000,              True),
    ("create_memory",    "create_memory",  0.001,      30,              False),
    ("search_memory",    "search_memory",  0.001,      30,              False),
    ("update_memory",    "update_memory",  0.001,      30,              False),
    ("delete_memory",    "delete_memory",  0.001,      30,              False),
    ("await_approval",   "execute_tool",   0.050,   60000,              True),   # human intervention
]

ERRORS = ["TIMEOUT", "NOT_FOUND", "RATE_LIMIT", "PERMISSION_DENIED", "INTERNAL"]
WORKLOADS = ["triage", "code_review", "deployment", "research", "monitoring", "support"]
MODELS = ["gpt-4o", "claude-3.5-sonnet", "gemini-1.5-pro", "llama-3.1-70b"]
PROVIDERS = ["openai", "anthropic", "google", "meta"]

OUTCOME_POOL = [
    (200, "",          "success"),   # empty response
    (300, "OK",        "success"),
    (150, "Done.",     "success"),
    (100, "Error.",    "error"),
    (50,  "Failed.",   "error"),
    (800, "Task completed successfully. Processed {tc} tool calls across {ph} phases. "
           "Key findings: {f} issues found, {c} critical. Outcome: {o}.", "success"),
    (400, "Partial success — {d} of {tc} steps completed. {ph} phases executed.", "success"),
    (300, "Escalated to human operator after {ph} phases. Awaiting review.", "error"),
    (250, "Operation failed after {tc} steps. Error: {e}. {ph} phases attempted.", "error"),
]

ALL_AGENTS = [
    "BlipZorp", "SnarfBlat", "CrunkWumpus", "FizzNark", "GloopWrangler",
    "ZorchSqueegee", "PlibbleDash", "NarfKnuckle", "SkronkMuppet", "WobbleFlarp",
]

# ── Span builder ──────────────────────────────────────────────────────────────

def _span(
    sid: str, tid: str, pid: str | None, op: str,
    attrs: dict[str, Any], t0: datetime, dur_ms: int, status: str = "ok",
) -> dict[str, Any]:
    return {
        "span_id": sid,
        "trace_id": tid,
        "parent_span_id": pid,
        "operation_name": op,
        "start_time": t0.isoformat(timespec="milliseconds"),
        "end_time": (t0 + timedelta(milliseconds=dur_ms)).isoformat(timespec="milliseconds"),
        "duration_ms": dur_ms,
        "attributes_json": json.dumps(attrs),
        "status": status,
        "source_dataset": "synthetic",
        "source_row_idx": 0,
    }


def _jitter(base: float, pct: float = 0.35) -> float:
    return base * (1.0 + random.uniform(-pct, pct))


def _pick_tool(rng: random.Random) -> dict[str, Any]:
    """Random tool with slight bias toward cheaper tools (more realistic)."""
    weights = [5 if not t[3] else 1 for t in TOOLS]  # is_expensive at index 3
    picked = rng.choices(TOOLS, weights=weights, k=1)[0]
    return {
        "name": picked[0],
        "span_type": picked[1],
        "cost": _jitter(picked[2]),
        "latency_ms": int(_jitter(picked[3])),
        "expensive": picked[3],
    }


# ── Trace generator ───────────────────────────────────────────────────────────

def _gen_trace(
    agent_name: str, trace_idx: int, phase_secs: int, rng: random.Random,
) -> list[dict[str, Any]]:
    tid = f"s_{agent_name}_{trace_idx:06d}"
    rows: list[dict[str, Any]] = []
    t0 = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)

    # ── randomize trace-level params ──
    dur_s = rng.randint(20, 180)
    num_phases = max(2, dur_s // phase_secs)
    sparse = rng.random() < 0.12
    version = rng.choices(["v1.0", "v2.0", "v3.0"], weights=[65, 25, 10], k=1)[0]
    model = rng.choice(MODELS)
    provider = rng.choice(PROVIDERS)
    workload = rng.choice(WORKLOADS)

    cost = 0.0
    tool_count = 0
    retry_count = 0
    intervention_count = 0
    error_count = 0
    span_n = 0
    elapsed = 0

    # ── root span ──
    root_sid = f"{tid}_r"
    rows.append(_span(root_sid, tid, None, "invoke_agent", {
        "gen_ai.agent.name": agent_name,
        "gen_ai.agent.version": version,
        "gen_ai.agent.run.id": tid,
        "gen_ai.agent.workload.type": workload,
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
        "gen_ai.agent.run.cost.total": 0.0,
    }, t0, 0, "success"))
    elapsed += 5

    # ── per-phase randomization weights ──
    # Each phase draws a fresh set of behavior toggles → maximum variety
    for ph in range(num_phases):
        # ── plan ──
        plan_dur = rng.randint(20, 180)
        rows.append(_span(f"{tid}_p{ph}", tid, root_sid, "plan", {
            "gen_ai.response.content": f"Phase {ph} plan for {agent_name}",
            "gen_ai.usage.prompt_tokens": rng.randint(10, 120),
            "gen_ai.usage.completion_tokens": rng.randint(5, 60),
        }, t0 + timedelta(milliseconds=elapsed), plan_dur, "ok"))
        elapsed += plan_dur + rng.randint(3, 25)

        # ── randomize this phase's behavior pattern ──
        warmup = (ph == 0)
        n_calls = rng.randint(1, 3) if warmup else rng.randint(3, 10)

        gap = rng.random() < 0.08 and not warmup          # inactivity gap
        loop = rng.random() < 0.06 and not warmup          # same-tool loop
        error_phase = rng.random() < 0.10 and not warmup   # error-heavy phase
        retry_phase = rng.random() < 0.08 and not warmup   # retry-heavy phase
        intervention = rng.random() < 0.04 and not warmup  # human approval
        memory_blitz = rng.random() < 0.07 and not warmup  # memory CRUD spike
        token_boom = rng.random() < 0.06 and ph > num_phases // 2  # late-phase token explosion

        if gap:
            elapsed += rng.randint(10_000, 60_000)  # 10-60s gap

        if loop:
            t = _pick_tool(rng)
            reps = rng.randint(5, 18)
            for i in range(reps):
                span_n += 1; tool_count += 1
                c = _jitter(t["cost"]); cost += c
                lat = int(_jitter(t["latency_ms"]))

                is_err = error_phase and rng.random() < 0.35
                is_retry = retry_phase and rng.random() < 0.25
                if is_err: error_count += 1
                if is_retry: retry_count += 1

                attrs = {
                    "gen_ai.tool.name": t["name"],
                    "gen_ai.tool.args": json.dumps({"q": f"l_{tid}_{i}", "n": i}),
                    "gen_ai.tool.result": json.dumps({"status": "error" if is_err else "ok", "hits": rng.randint(0, 10)}),
                    "gen_ai.usage.prompt_tokens": rng.randint(15, 80),
                    "gen_ai.usage.completion_tokens": rng.randint(5, 40),
                    "gen_ai.agent.run.cost.total": round(cost, 4),
                }
                if is_err: attrs["error.code"] = rng.choice(ERRORS)
                if is_retry: attrs["retry"] = "true"

                rows.append(_span(f"{tid}_s{span_n}", tid, root_sid, t["span_type"],
                                  attrs, t0 + timedelta(milliseconds=elapsed), lat,
                                  "error" if is_err else "ok"))
                elapsed += lat + rng.randint(2, 15)
                if is_err and i > reps // 2 and rng.random() < 0.3:
                    break  # bail out mid-loop
            continue  # skip normal tool calls for this phase

        # ── normal / mixed tool calls ──
        for i in range(n_calls):
            span_n += 1; tool_count += 1
            t = _pick_tool(rng)
            c = _jitter(t["cost"]); cost += c
            lat = int(_jitter(t["latency_ms"]))

            # random mutations
            is_err = (not warmup) and rng.random() < 0.08
            is_retry = (not warmup) and rng.random() < 0.06
            is_timeout = (not warmup) and rng.random() < 0.03
            if is_err: error_count += 1
            if is_retry: retry_count += 1
            if is_timeout: lat = rng.randint(65_000, 200_000)

            tp = rng.randint(150, 2500) if token_boom else rng.randint(15, 300)
            tc = rng.randint(80, 1500) if token_boom else rng.randint(5, 200)

            attrs = {
                "gen_ai.tool.name": t["name"],
                "gen_ai.tool.args": json.dumps({"q": f"q_{tid}_{ph}_{i}", "lim": rng.randint(1, 50), "f": rng.choice(["active", "all", "recent"])}),
                "gen_ai.tool.result": json.dumps({"status": "error" if is_err else "ok", "r": rng.randint(0, 20)}),
                "gen_ai.usage.prompt_tokens": tp,
                "gen_ai.usage.completion_tokens": tc,
                "gen_ai.agent.run.cost.total": round(cost, 4),
            }
            if is_err: attrs["error.code"] = rng.choice(ERRORS)
            if is_retry: attrs["retry"] = "true"
            if is_timeout: attrs["timeout"] = "true"

            rows.append(_span(f"{tid}_s{span_n}", tid, root_sid, t["span_type"],
                              attrs, t0 + timedelta(milliseconds=elapsed), lat,
                              "error" if is_err else "ok"))
            elapsed += lat + rng.randint(2, 18)

        # ── memory blitz ──
        if memory_blitz and not warmup:
            for _ in range(rng.randint(2, 5)):
                span_n += 1
                mop = rng.choice(["create_memory", "search_memory", "update_memory", "delete_memory"])
                cost += 0.001
                rows.append(_span(f"{tid}_s{span_n}", tid, root_sid, mop, {
                    "gen_ai.tool.name": mop,
                    "gen_ai.tool.args": json.dumps({"k": f"m_{tid}_{span_n}", "v": f"v{rng.randint(0,9999)}"}),
                    "gen_ai.tool.result": json.dumps({"status": "ok", "ver": rng.randint(1,10)}),
                    "gen_ai.agent.run.cost.total": round(cost, 4),
                }, t0 + timedelta(milliseconds=elapsed), rng.randint(10, 50), "ok"))
                elapsed += rng.randint(15, 60)

        # ── human intervention ──
        if intervention and not warmup:
            for _ in range(rng.randint(1, 3)):
                span_n += 1; intervention_count += 1
                approval_ms = rng.randint(30_000, 150_000)
                rejected = rng.random() < 0.35
                rows.append(_span(f"{tid}_s{span_n}", tid, root_sid, "execute_tool", {
                    "gen_ai.tool.name": "await_approval",
                    "gen_ai.tool.args": json.dumps({"reason": rng.choice(["cost_threshold", "prod_write", "schema_change"])}),
                    "gen_ai.tool.result": json.dumps({"status": "rejected" if rejected else "approved"}),
                    "gen_ai.agent.run.cost.total": round(cost + 0.05, 4),
                }, t0 + timedelta(milliseconds=elapsed), approval_ms,
                   "error" if rejected else "ok"))
                elapsed += approval_ms + rng.randint(50, 300)

    # ── finalize root ──
    run_status = "error" if error_count > max(1, tool_count * 0.35) else "success"

    weights, texts, statuses = zip(*OUTCOME_POOL) if OUTCOME_POOL else ([1], [""], ["success"])
    tmpl = rng.choices(list(zip(texts, statuses)), weights=list(weights), k=1)[0]
    outcome_text = tmpl[0].format(
        tc=tool_count, ph=num_phases,
        f=rng.randint(1, 20), c=rng.randint(0, 5),
        o=rng.choice(["successful", "failed", "pending"]),
        d=rng.randint(1, max(1, tool_count)),
        e=rng.choice(ERRORS),
    )
    outcome_text = outcome_text * rng.randint(1, 3) if rng.random() < 0.04 else outcome_text

    root = json.loads(rows[0]["attributes_json"])
    root.update({
        "gen_ai.response.content": outcome_text,
        "gen_ai.agent.run.cost.total": round(cost, 4),
        "gen_ai.agent.retry.count": retry_count,
        "gen_ai.agent.intervention.count": intervention_count,
        "gen_ai.agent.loop.count": retry_count,
        "gen_ai.usage.prompt_tokens": rng.randint(80, 6000),
        "gen_ai.usage.completion_tokens": rng.randint(30, 4000),
    })
    if error_count:
        root["error.count"] = error_count
    rows[0]["attributes_json"] = json.dumps(root)
    rows[0]["status"] = run_status
    rows[0]["duration_ms"] = elapsed
    rows[0]["end_time"] = (t0 + timedelta(milliseconds=elapsed)).isoformat(timespec="milliseconds")

    # ── sparse trace pruning ──
    if sparse:
        keep_every = max(1, len(rows) // 4)
        rows = [rows[0]] + rows[1::keep_every]
        for row in rows[1:]:
            a = json.loads(row["attributes_json"])
            if rng.random() < 0.5: a.pop("gen_ai.tool.args", None)
            if rng.random() < 0.4: a.pop("gen_ai.usage.prompt_tokens", None)
            if rng.random() < 0.4: a.pop("gen_ai.usage.completion_tokens", None)
            row["attributes_json"] = json.dumps(a)

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    agents = args.agents if args.agents else ALL_AGENTS
    num_agents = len(agents)

    per_agent = args.num_traces // num_agents
    rem = args.num_traces % num_agents

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)

    print(f"Agents:      {', '.join(agents)}")
    print(f"Traces:      {args.num_traces:,} (~{per_agent:,}/agent)")
    print(f"Phase timer: {args.phase_timer}s")
    print(f"Output:      {out.resolve()}")
    print()

    batch: list[dict[str, Any]] = []
    bi = 0
    total = 0
    span_est = 25  # avg spans per trace

    for ai, name in enumerate(agents):
        n = per_agent + (1 if ai < rem else 0)
        agent_rng = random.Random(args.seed + ai * 1_000_000)

        for ti in range(n):
            tr_rng = random.Random(args.seed + ai * 1_000_000 + ti)
            spans = _gen_trace(name, total, args.phase_timer, tr_rng)
            batch.extend(spans)
            total += 1

            if len(batch) >= args.batch_size * span_est:
                _write(batch, out, bi)
                print(f"  [{total:>10,}] -> traces-{bi:04d}.parquet")
                batch, bi = [], bi + 1

    if batch:
        _write(batch, out, bi)
        print(f"  [{total:>10,}] -> traces-{bi:04d}.parquet (final)")

    print(f"\nDone: {total:,} traces, {bi + 1} parquet files -> {out.resolve()}")


def _write(batch: list[dict[str, Any]], out: Path, idx: int) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(batch), str(out / f"traces-{idx:04d}.parquet"))


if __name__ == "__main__":
    main()