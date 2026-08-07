#!/usr/bin/env python3
"""Generate synthetic agent traces — 1M+ traces with randomized behaviors.

= Purpose
Generates a large-scale synthetic trace dataset (default: 1 million traces) that
exercises every edge case in the analytics service's anomaly detection pipeline.
Each trace has deeply randomized behavior patterns per phase, making this dataset
suitable for stress-testing, benchmarking, and soaking the full pipeline.

= Behavior randomization (per phase)
Every phase within a trace draws fresh random toggles:
* ``warmup``         -- Phase 0 gets simplified behavior (fewer calls).
* ``gap``            -- 10-60s inactivity gaps (exercises the ``inactivity`` detector).
* ``loop``           -- Same tool called 5-18 times in a row (exercises all loop detectors).
* ``error_phase``    -- 35% of calls in this phase fail.
* ``retry_phase``    -- 25% of calls have retry flags.
* ``intervention``   -- Human-approval flows (exercises intervention_frequency,
                         escalation_rate, approval_latency, intervention_rejection).
* ``memory_blitz``   -- Burst of 2-5 memory CRUD operations.
* ``token_boom``     -- Late-phase token spike (exercises token_explosion, cost_spike).

= Trace shape
* Root span with full run metadata (agent name, version, model, provider, status).
* One plan span per phase with LLM planning content and token counts.
* N tool spans per phase with randomized tools, errors, retries, timeouts.
* Optional memory CRUD spans and human intervention spans.
* ~12% of traces are ``sparse`` (every 4th span kept, some attributes dropped)
  to exercise the low_output, empty_response, and sparse-data edge cases.

= Agent pool
10 agents with whimsical names (default can be overridden via ``--agents``):
  BlipZorp, SnarfBlat, CrunkWumpus, FizzNark, GloopWrangler,
  ZorchSqueegee, PlibbleDash, NarfKnuckle, SkronkMuppet, WobbleFlarp

= Tools (14 shared across all agents)
search_kb, lookup_account, analyze_data, generate_report, send_alert,
escalate_human, fetch_metrics, scan_deps, deploy_service,
create_memory, search_memory, update_memory, delete_memory, await_approval

Tools are weighted so cheaper tools (non-expensive) are 5x more likely to be
selected, producing realistic cost distributions.

= Output
Parquet files in ``data/traces/synthetic/`` (configurable).  Files are batched
at ~250K span rows (~10K traces) each.  With 1M traces, expect ~40 files.

= Usage
    python3 generate_bulk_traces.py
    python3 generate_bulk_traces.py --num-traces 50000 --phase-timer 15 --output-dir ./my-traces
    python3 generate_bulk_traces.py --num-traces 100000 \
        --agents BlipZorp FizzNark WobbleFlarp --seed 99
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── CLI ────────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for trace generation.

    Returns:
        A namespace with: num_traces, agents, phase_timer, batch_size,
        output_dir, seed.
    """
    p = argparse.ArgumentParser(
        description="Generate synthetic agent traces with timer-driven behavior phases."
    )
    p.add_argument("--num-traces", type=int, default=1_000_000)
    p.add_argument("--agents", nargs="*", default=None, help="Agent names to use (default: all 10)")
    p.add_argument(
        "--phase-timer", type=int, default=10, help="Seconds per behavior phase (default: 10)"
    )
    p.add_argument(
        "--batch-size", type=int, default=10_000, help="Traces per parquet file (default: 10000)"
    )
    p.add_argument("--output-dir", type=str, default="data/traces/synthetic")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


# ── Tools (shared by all agents) ───────────────────────────────────────────────
# Each tool tuple: (name, span_type, base_cost, base_latency_ms, is_expensive).
# ``is_expensive`` controls the random weighting: expensive tools are chosen 5x
# less frequently than cheap tools, producing realistic cost distributions where
# most calls are to low-cost retrieval/light-execute tools.

TOOLS = [
    # name,              span_type,        base_cost, base_latency_ms, is_expensive
    ("search_kb", "retrieval", 0.002, 100, False),
    ("lookup_account", "execute_tool", 0.005, 80, False),
    ("analyze_data", "execute_tool", 0.010, 200, False),
    ("generate_report", "execute_tool", 0.020, 350, True),
    ("send_alert", "execute_tool", 0.003, 50, False),
    ("escalate_human", "execute_tool", 0.050, 500, True),
    ("fetch_metrics", "retrieval", 0.002, 120, False),
    ("scan_deps", "execute_tool", 0.015, 400, False),
    ("deploy_service", "execute_tool", 0.080, 2000, True),
    ("create_memory", "create_memory", 0.001, 30, False),
    ("search_memory", "search_memory", 0.001, 30, False),
    ("update_memory", "update_memory", 0.001, 30, False),
    ("delete_memory", "delete_memory", 0.001, 30, False),
    ("await_approval", "execute_tool", 0.050, 60000, True),  # human intervention
]

# ── Shared randomness pools ────────────────────────────────────────────────────
# These are drawn from randomly per trace or per call to maximize variety.

ERRORS = ["TIMEOUT", "NOT_FOUND", "RATE_LIMIT", "PERMISSION_DENIED", "INTERNAL"]
WORKLOADS = ["triage", "code_review", "deployment", "research", "monitoring", "support"]
MODELS = ["gpt-4o", "claude-3.5-sonnet", "gemini-1.5-pro", "llama-3.1-70b"]
PROVIDERS = ["openai", "anthropic", "google", "meta"]

# Outcome pool: weighted response templates paired with success/error flags.
# ``(weight, template, status)`` -- templates use format() with keys:
#   tc = tool_count, ph = num_phases, f = findings, c = critical,
#   o = outcome word, d = completed steps, e = error code.
# Weights are chosen to give ~60% success, ~30% error, ~10% partial/other.
OUTCOME_POOL = [
    (200, "", "success"),  # empty response
    (300, "OK", "success"),
    (150, "Done.", "success"),
    (100, "Error.", "error"),
    (50, "Failed.", "error"),
    (
        800,
        "Task completed successfully. Processed {tc} tool calls across {ph} phases. "
        "Key findings: {f} issues found, {c} critical. Outcome: {o}.",
        "success",
    ),
    (400, "Partial success — {d} of {tc} steps completed. {ph} phases executed.", "success"),
    (300, "Escalated to human operator after {ph} phases. Awaiting review.", "error"),
    (250, "Operation failed after {tc} steps. Error: {e}. {ph} phases attempted.", "error"),
]

# Default agent pool: 10 whimsical names to avoid conflating with real agent names
# in test environments.  Override with ``--agents``.
ALL_AGENTS = [
    "BlipZorp",
    "SnarfBlat",
    "CrunkWumpus",
    "FizzNark",
    "GloopWrangler",
    "ZorchSqueegee",
    "PlibbleDash",
    "NarfKnuckle",
    "SkronkMuppet",
    "WobbleFlarp",
]


# ── Span builder ───────────────────────────────────────────────────────────────


def _span(
    sid: str,
    tid: str,
    pid: str | None,
    op: str,
    attrs: dict[str, Any],
    t0: datetime,
    dur_ms: int,
    status: str = "ok",
) -> dict[str, Any]:
    """Build a single synthetic span row dict with absolute timestamps.

    Args:
        sid: Span ID (unique within the trace).
        tid: Trace ID (groups spans).
        pid: Parent span ID, or None for root spans.
        op: Operation name.
        attrs: Key-value attributes (will be JSON-serialized).
        t0: Absolute base datetime for timestamps.
        dur_ms: Duration in milliseconds.
        status: Span status.

    Returns:
        A dict matching the parquet schema.
    """
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
    """Apply random jitter (default ±35%) to a numeric value.

    Args:
        base: The base value to jitter.
        pct: Jitter percentage as a decimal (0.35 = ±35%).

    Returns:
        The jittered value.  Always positive (strictly > 0) for costs/latencies.
    """
    return base * (1.0 + random.uniform(-pct, pct))


def _pick_tool(rng: random.Random) -> dict[str, Any]:
    """Random tool with slight bias toward cheaper tools (more realistic).

    Cheap tools (is_expensive=False) are weighted 5:1 vs expensive tools,
    so the cost distribution mimics real agent workloads where most calls
    are cheap lookups/retrievals and only a few are expensive operations.

    Args:
        rng: A seeded Random instance for reproducibility.

    Returns:
        A dict with tool metadata: ``name``, ``span_type``, ``cost``,
        ``latency_ms``, ``expensive``.
    """
    weights = [5 if not t[3] else 1 for t in TOOLS]  # is_expensive at index 3
    picked = rng.choices(TOOLS, weights=weights, k=1)[0]
    return {
        "name": picked[0],
        "span_type": picked[1],
        "cost": _jitter(picked[2]),
        "latency_ms": int(_jitter(picked[3])),
        "expensive": picked[3],
    }


# ── Trace generator ────────────────────────────────────────────────────────────


def _gen_trace(
    agent_name: str,
    trace_idx: int,
    phase_secs: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate one complete synthetic trace with deeply randomized behavior.

    Args:
        agent_name: The agent's display name.
        trace_idx: 0-based global trace index (used for uniqueness in trace_id).
        phase_secs: Seconds per behavior phase (controls granularity).
        rng: Seeded Random instance for reproducible randomness.

    Returns:
        A list of span row dicts forming one complete trace.
    """
    tid = f"s_{agent_name}_{trace_idx:06d}"  # Global unique trace ID.
    rows: list[dict[str, Any]] = []
    t0 = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)

    # ── randomize trace-level params ──
    # Duration: 20-180 seconds; phase count is derived from duration.
    dur_s = rng.randint(20, 180)
    num_phases = max(2, dur_s // phase_secs)

    # 12% of traces are sparse: only every 4th span is kept and some attributes
    # are dropped.  This exercises the low_output, empty_response, and
    # sparse-data detection paths.
    sparse = rng.random() < 0.12

    # Version distribution: 65% v1.0, 25% v2.0, 10% v3.0 (mirrors a realistic
    # adoption curve where most agents run the stable v1 release).
    version = rng.choices(["v1.0", "v2.0", "v3.0"], weights=[65, 25, 10], k=1)[0]
    model = rng.choice(MODELS)
    provider = rng.choice(PROVIDERS)
    workload = rng.choice(WORKLOADS)

    # Running accumulators for the root span's final metadata.
    cost = 0.0
    tool_count = 0
    retry_count = 0
    intervention_count = 0
    error_count = 0
    span_n = 0  # Per-trace span sequence number for unique span IDs.
    elapsed = 0  # Accumulated elapsed time in ms.

    # ── root span ──
    root_sid = f"{tid}_r"
    rows.append(
        _span(
            root_sid,
            tid,
            None,
            "invoke_agent",
            {
                "gen_ai.agent.name": agent_name,
                "gen_ai.agent.version": version,
                "gen_ai.agent.run.id": tid,
                "gen_ai.agent.workload.type": workload,
                "gen_ai.provider.name": provider,
                "gen_ai.request.model": model,
                "gen_ai.agent.run.cost.total": 0.0,
            },
            t0,
            0,
            "success",
        )
    )  # Root starts with duration=0; finalized at end.
    elapsed += 5  # Small gap after root creation.

    # ── per-phase randomization ──
    # Each phase independently draws its behavior pattern, producing extreme
    # variety across the dataset.
    for ph in range(num_phases):
        # ── plan ──
        plan_dur = rng.randint(20, 180)
        rows.append(
            _span(
                f"{tid}_p{ph}",
                tid,
                root_sid,
                "plan",
                {
                    "gen_ai.response.content": f"Phase {ph} plan for {agent_name}",
                    "gen_ai.usage.prompt_tokens": rng.randint(10, 120),
                    "gen_ai.usage.completion_tokens": rng.randint(5, 60),
                },
                t0 + timedelta(milliseconds=elapsed),
                plan_dur,
                "ok",
            )
        )
        elapsed += plan_dur + rng.randint(3, 25)  # Inter-phase gap.

        # ── randomize this phase's behavior pattern ──
        warmup = ph == 0
        n_calls = rng.randint(1, 3) if warmup else rng.randint(3, 10)

        # Each toggle is independently randomized.  A single phase may have
        # multiple toggles active, producing compound failure modes that
        # exercise multiple detectors simultaneously.
        gap = rng.random() < 0.08 and not warmup  # inactivity gap (10-60s)
        loop = rng.random() < 0.06 and not warmup  # same-tool loop (5-18 reps)
        error_phase = rng.random() < 0.10 and not warmup  # error-heavy (35% fail rate)
        retry_phase = rng.random() < 0.08 and not warmup  # retry-heavy (25% retry rate)
        intervention = rng.random() < 0.04 and not warmup  # human approval flow
        memory_blitz = rng.random() < 0.07 and not warmup  # memory CRUD spike (2-5 ops)
        token_boom = rng.random() < 0.06 and ph > num_phases // 2  # late-phase token explosion

        # Inactivity gap: add 10-60 seconds of idle time.  Exercises the
        # ``inactivity`` detector which flags runs with long idle periods.
        if gap:
            elapsed += rng.randint(10_000, 60_000)

        # ── Loop mode ──
        # When loop is active, pick one tool and call it repeatedly (5-18 times).
        # This exercises loop, pattern_loop, argument_loop detectors.
        if loop:
            t = _pick_tool(rng)
            reps = rng.randint(5, 18)
            for i in range(reps):
                span_n += 1
                tool_count += 1
                c = _jitter(t["cost"])
                cost += c
                lat = int(_jitter(t["latency_ms"]))

                is_err = error_phase and rng.random() < 0.35
                is_retry = retry_phase and rng.random() < 0.25
                if is_err:
                    error_count += 1
                if is_retry:
                    retry_count += 1

                attrs = {
                    "gen_ai.tool.name": t["name"],
                    "gen_ai.tool.args": json.dumps({"q": f"l_{tid}_{i}", "n": i}),
                    "gen_ai.tool.result": json.dumps(
                        {"status": "error" if is_err else "ok", "hits": rng.randint(0, 10)}
                    ),
                    "gen_ai.usage.prompt_tokens": rng.randint(15, 80),
                    "gen_ai.usage.completion_tokens": rng.randint(5, 40),
                    "gen_ai.agent.run.cost.total": round(cost, 4),
                }
                if is_err:
                    attrs["error.code"] = rng.choice(ERRORS)
                if is_retry:
                    attrs["retry"] = "true"

                rows.append(
                    _span(
                        f"{tid}_s{span_n}",
                        tid,
                        root_sid,
                        t["span_type"],
                        attrs,
                        t0 + timedelta(milliseconds=elapsed),
                        lat,
                        "error" if is_err else "ok",
                    )
                )
                elapsed += lat + rng.randint(2, 15)

                # Mid-loop bailout: 30% chance to exit after the halfway point
                # if we hit an error.  This creates truncated loops that exercise
                # the premature_completion detector.
                if is_err and i > reps // 2 and rng.random() < 0.3:
                    break
            continue  # Skip normal tool calls for this phase (loop supersedes).

        # ── normal / mixed tool calls ──
        for i in range(n_calls):
            span_n += 1
            tool_count += 1
            t = _pick_tool(rng)
            c = _jitter(t["cost"])
            cost += c
            lat = int(_jitter(t["latency_ms"]))

            # Random mutations per tool call.  Multiple mutations may apply
            # simultaneously (e.g., an error that also times out).
            is_err = (not warmup) and rng.random() < 0.08
            is_retry = (not warmup) and rng.random() < 0.06
            is_timeout = (not warmup) and rng.random() < 0.03
            if is_err:
                error_count += 1
            if is_retry:
                retry_count += 1
            if is_timeout:
                # Timeouts have extreme latency (65-200 seconds) to trigger
                # the tool_timeout, run_duration, and cost_spike detectors.
                lat = rng.randint(65_000, 200_000)

            # Token explosion: prompt tokens jump to 150-2500, completion to 80-1500.
            # This exercises token_explosion and cost_spike (token-based).
            tp = rng.randint(150, 2500) if token_boom else rng.randint(15, 300)
            tc = rng.randint(80, 1500) if token_boom else rng.randint(5, 200)

            attrs = {
                "gen_ai.tool.name": t["name"],
                "gen_ai.tool.args": json.dumps(
                    {
                        "q": f"q_{tid}_{ph}_{i}",
                        "lim": rng.randint(1, 50),
                        "f": rng.choice(["active", "all", "recent"]),
                    }
                ),
                "gen_ai.tool.result": json.dumps(
                    {"status": "error" if is_err else "ok", "r": rng.randint(0, 20)}
                ),
                "gen_ai.usage.prompt_tokens": tp,
                "gen_ai.usage.completion_tokens": tc,
                "gen_ai.agent.run.cost.total": round(cost, 4),
            }
            if is_err:
                attrs["error.code"] = rng.choice(ERRORS)
            if is_retry:
                attrs["retry"] = "true"
            if is_timeout:
                attrs["timeout"] = "true"

            rows.append(
                _span(
                    f"{tid}_s{span_n}",
                    tid,
                    root_sid,
                    t["span_type"],
                    attrs,
                    t0 + timedelta(milliseconds=elapsed),
                    lat,
                    "error" if is_err else "ok",
                )
            )
            elapsed += lat + rng.randint(2, 18)

        # ── memory blitz ──
        # Burst of 2-5 memory CRUD operations with tiny cost.  Exercises the
        # waste_detectors and creates realistic memory-tool usage patterns.
        if memory_blitz and not warmup:
            for _ in range(rng.randint(2, 5)):
                span_n += 1
                mop = rng.choice(
                    ["create_memory", "search_memory", "update_memory", "delete_memory"]
                )
                cost += 0.001  # Memory ops are trivially cheap.
                rows.append(
                    _span(
                        f"{tid}_s{span_n}",
                        tid,
                        root_sid,
                        mop,
                        {
                            "gen_ai.tool.name": mop,
                            "gen_ai.tool.args": json.dumps(
                                {"k": f"m_{tid}_{span_n}", "v": f"v{rng.randint(0, 9999)}"}
                            ),
                            "gen_ai.tool.result": json.dumps(
                                {"status": "ok", "ver": rng.randint(1, 10)}
                            ),
                            "gen_ai.agent.run.cost.total": round(cost, 4),
                        },
                        t0 + timedelta(milliseconds=elapsed),
                        rng.randint(10, 50),
                        "ok",
                    )
                )
                elapsed += rng.randint(15, 60)

        # ── human intervention ──
        # 1-3 "await_approval" calls.  35% chance of rejection.  Latency is
        # 30-150 seconds (simulates human response time).  Exercises
        # intervention_frequency, escalation_rate, approval_latency,
        # intervention_rejection detectors.
        if intervention and not warmup:
            for _ in range(rng.randint(1, 3)):
                span_n += 1
                intervention_count += 1
                approval_ms = rng.randint(30_000, 150_000)
                rejected = rng.random() < 0.35
                rows.append(
                    _span(
                        f"{tid}_s{span_n}",
                        tid,
                        root_sid,
                        "execute_tool",
                        {
                            "gen_ai.tool.name": "await_approval",
                            "gen_ai.tool.args": json.dumps(
                                {
                                    "reason": rng.choice(
                                        ["cost_threshold", "prod_write", "schema_change"]
                                    )
                                }
                            ),
                            "gen_ai.tool.result": json.dumps(
                                {"status": "rejected" if rejected else "approved"}
                            ),
                            "gen_ai.agent.run.cost.total": round(cost + 0.05, 4),
                        },
                        t0 + timedelta(milliseconds=elapsed),
                        approval_ms,
                        "error" if rejected else "ok",
                    )
                )
                elapsed += approval_ms + rng.randint(50, 300)

    # ── finalize root span ──
    # Run status: "error" if >35% of tool calls failed; otherwise "success".
    # The 35% threshold is high enough that a few random errors don't mark
    # the entire run as failed.
    run_status = "error" if error_count > max(1, tool_count * 0.35) else "success"

    # Pick an outcome template weighted by the OUTCOME_POOL.
    weights, texts, statuses = zip(*OUTCOME_POOL, strict=False) \
        if OUTCOME_POOL \
        else ([1], [""], ["success"])
    tmpl = rng.choices(list(zip(texts, statuses, strict=False)), weights=list(weights), k=1)[0]
    outcome_text = tmpl[0].format(
        tc=tool_count,
        ph=num_phases,
        f=rng.randint(1, 20),
        c=rng.randint(0, 5),
        o=rng.choice(["successful", "failed", "pending"]),
        d=rng.randint(1, max(1, tool_count)),
        e=rng.choice(ERRORS),
    )
    # 4% chance to repeat the outcome text 2-3 times (exercises output_drift
    # and quality_degradation detectors which look for repetitive outputs).
    outcome_text = outcome_text * rng.randint(1, 3) if rng.random() < 0.04 else outcome_text

    # Update the root span's attributes_json with final accumulated values.
    root = json.loads(rows[0]["attributes_json"])
    root.update(
        {
            "gen_ai.response.content": outcome_text,
            "gen_ai.agent.run.cost.total": round(cost, 4),
            "gen_ai.agent.retry.count": retry_count,
            "gen_ai.agent.intervention.count": intervention_count,
            "gen_ai.agent.loop.count": retry_count,
            "gen_ai.usage.prompt_tokens": rng.randint(80, 6000),
            "gen_ai.usage.completion_tokens": rng.randint(30, 4000),
        }
    )
    if error_count:
        root["error.count"] = error_count
    rows[0]["attributes_json"] = json.dumps(root)
    rows[0]["status"] = run_status
    rows[0]["duration_ms"] = elapsed
    rows[0]["end_time"] = (t0 + timedelta(milliseconds=elapsed)).isoformat(timespec="milliseconds")

    # ── Sparse trace pruning ──
    # Keep only the root + every 4th span, and randomly drop some attributes.
    # This creates traces that look incomplete -- exercising the low_output,
    # empty_response, and sparse-data edge cases.
    if sparse:
        keep_every = max(1, len(rows) // 4)
        rows = [rows[0]] + rows[1::keep_every]  # Always keep root, then every Nth.
        for row in rows[1:]:
            a = json.loads(row["attributes_json"])
            # Drop args/tokens with 50%/40%/40% probability respectively.
            if rng.random() < 0.5:
                a.pop("gen_ai.tool.args", None)
            if rng.random() < 0.4:
                a.pop("gen_ai.usage.prompt_tokens", None)
            if rng.random() < 0.4:
                a.pop("gen_ai.usage.completion_tokens", None)
            row["attributes_json"] = json.dumps(a)

    return rows


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse args, generate all traces, and write batched parquet files."""
    args = _parse_args()
    agents = args.agents if args.agents else ALL_AGENTS
    num_agents = len(agents)

    # Distribute traces evenly across agents, with remainder going to first N agents.
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
    span_est = 25  # Estimated average spans per trace (used to size batches).

    for ai, name in enumerate(agents):
        n = per_agent + (1 if ai < rem else 0)  # Distribute remainder.
        # Each agent gets its own seeded RNG for deterministic reproducibility.
        random.Random(args.seed + ai * 1_000_000)

        for ti in range(n):
            # Per-trace RNG seeded from agent offset + trace index.
            tr_rng = random.Random(args.seed + ai * 1_000_000 + ti)
            spans = _gen_trace(name, total, args.phase_timer, tr_rng)
            batch.extend(spans)
            total += 1

            # Flush to parquet when the batch is roughly full.
            # ``batch_size * span_est`` is an approximate target; actual
            # sizes will vary because traces have variable span counts.
            if len(batch) >= args.batch_size * span_est:
                _write(batch, out, bi)
                print(f"  [{total:>10,}] -> traces-{bi:04d}.parquet")
                batch, bi = [], bi + 1

    # Flush the final partial batch.
    if batch:
        _write(batch, out, bi)
        print(f"  [{total:>10,}] -> traces-{bi:04d}.parquet (final)")

    print(f"\nDone: {total:,} traces, {bi + 1} parquet files -> {out.resolve()}")


def _write(batch: list[dict[str, Any]], out: Path, idx: int) -> None:
    """Write a batch of span rows to a numbered parquet file.

    Args:
        batch: List of span row dicts to write.
        out: Output directory.
        idx: Batch index (embedded in filename).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    # ``Table.from_pylist`` infers the schema from the data automatically.
    pq.write_table(pa.Table.from_pylist(batch), str(out / f"traces-{idx:04d}.parquet"))


if __name__ == "__main__":
    main()
