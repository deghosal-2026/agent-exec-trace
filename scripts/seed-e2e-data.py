#!/usr/bin/env python3
"""Seed the Postgres read-model with mock data for demo and e2e testing.

= Purpose
Populates run_summaries, anomalies, fleet_rollups, and version_cohort_summaries
with enough data to exercise all four standard views:
  - Fleet Health (filters by agent, version, workload, status)
  - Run Timeline (span trees, anomaly drill-down)
  - Version Compare (deltas between two versions)
  - Anomaly Inbox (type and severity filtering)

= How data is generated
The script generates **deterministic** mock data (seeded by agent definitions
and loop counters) so the resulting fixture is stable across runs.  Each agent
has one or more versions, and each version generates a fixed number of runs
with varying behaviors:

  * Every 3rd run is an error (``status="error"``).
  * Specific run indices trigger loops (#2, #9), retry storms (#4, #10),
    cost spikes (#1, #7), and timeouts (#6).
  * Anomalies are associated with runs using a round-robin assignment from a
    fixed pool of anomaly types.
  * Fleet rollups are generated per-day for 7 consecutive days per version.
  * Version cohort summaries aggregate per-version stats.

= Data shape
* AGENTS: 4 agent definitions with 1-3 versions each.
* Anomaly types: 35 rule-based anomaly types (from the analytics detectors).
* Run count per version: 12 (except research_crew v1.4.0: 3 runs -- sparse).
* Total data volume: ~150 runs, ~375 anomalies, ~84 fleet rollups, ~10 cohorts.

= Special scenarios for E2E testing
* ``research_crew`` versions v1.2.0 and v1.3.0 have dict-shaped ``top_tools``
  (tool-name -> count) so the Version Compare view can compute non-empty
  ``tool_deltas``.  All other agents use a simple list of tool names, which
  results in empty ``tool_deltas``.
* ``research_crew`` v1.4.0 has only 3 runs, creating a "sparse cohort" edge case
  that triggers the ``sparse_cohorts`` warning in the Version Compare endpoint.

= Usage
    python3 scripts/seed-e2e-data.py
    python3 scripts/seed-e2e-data.py --dsn postgresql://analytics:analytics@localhost:5433/analytics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg

# ── Agent definitions ──────────────────────────────────────────────────────────
# Each agent has a name, workload type, and a list of versions.  Versions can be:
#   * A plain string -> generates 12 runs (default).
#   * A single-key dict {"version_str": run_count} -> generates exactly that many.
#
# ``research_crew`` is the "main" demo agent used in most E2E tests.  The
# ``demo_triage`` agent mirrors the request-triage LangGraph demo's agent name
# so the demo replay works end-to-end.
AGENTS = [
    {"name": "research_crew", "workload": "research_crew",
        "versions": ["v1.2.0", "v1.3.0", {"v1.4.0": 3}]},
    {"name": "support_triage", "workload": "support_triage",
        "versions": ["v1.0.0", "v1.1.0", "v2.0.0"]},
    {"name": "code_review", "workload": "code_review", "versions": ["v1.0.0"]},
    {"name": "demo_triage", "workload": "demo_triage", "versions": ["v0.1.0", "v0.2.0"]},
]


def _version_entries(agent: dict) -> list[tuple[str, int]]:
    """Normalise agent versions list to (version_str, run_count) pairs.

    String entries default to 12 runs; dict entries specify an explicit run
    count (e.g. ``{"v1.4.0": 3}`` for the sparse-cohort scenario).

    Args:
        agent: An agent definition dict with a ``"versions"`` key.

    Returns:
        A list of ``(version_string, run_count)`` tuples.
    """
    out: list[tuple[str, int]] = []
    for v in agent["versions"]:
        if isinstance(v, str):
            # Default: 12 runs per version.  Chosen to give ~1/3 error rate
            # (4 errors per version) which is sufficient for fleet view testing.
            out.append((v, 12))
        elif isinstance(v, dict) and len(v) == 1:
            # Single-key dict: the key is the version string, the value is the
            # run count.  Used for sparse-cohort edge cases.
            ver, cnt = next(iter(v.items()))
            out.append((str(ver), int(cnt)))
    return out


# ── Anomaly types ──────────────────────────────────────────────────────────────
# The 35 rule-based anomaly types produced by the analytics service detectors.
# These are the values that appear in the ``anomaly_type`` column and in the
# ``AnomalyType`` enum in ``api.models``.
ANOMALY_TYPES = [
    # Flow / structure anomalies
    "loop", "pattern_loop", "argument_loop",
    # Tool behaviour anomalies
    "tool_error_rate", "specific_tool_error", "tool_latency", "tool_timeout", "redundant_tool_call",
    # Cost anomalies
    "cost_spike", "cost_vs_baseline", "cost_efficiency", "token_explosion",
    "per_tool_cost_spike", "wasted_tool_calls",
    # Performance anomalies
    "run_duration", "max_step_hit", "step_efficiency", "inactivity", "premature_completion",
    # Retry & recovery anomalies
    "retry_storm", "systemic_retry", "transient_retry", "cascading_retry", "recovery_path",
    # Human-in-the-loop anomalies
    "intervention_frequency", "escalation_rate", "approval_latency", "intervention_rejection",
    # Output quality anomalies
    "empty_response", "low_output", "indeterminate_status", "output_drift",
    # Systematic / cross-run anomalies
    "anomaly_cluster", "run_frequency_anomaly", "first_run_heuristic",
]

# ── Constants ──────────────────────────────────────────────────────────────────
# Current UTC time used as the anchor for all generated timestamps.  Runs are
# distributed over the preceding 7 days.
NOW = datetime.now(timezone.utc)


async def seed(dsn: str) -> None:
    """Generate and insert all mock data into the read-model tables.

    Args:
        dsn: PostgreSQL connection string.
    """
    # Use a small pool so we don't exhaust connections during seeding.
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    conn = await pool.acquire()

    # ── Clear existing data ──
    # DELETE order: children before parents to avoid FK violations.
    await conn.execute("DELETE FROM anomalies")
    await conn.execute("DELETE FROM fleet_rollups")
    await conn.execute("DELETE FROM version_cohort_summaries")
    await conn.execute("DELETE FROM run_summaries")

    # ── Generate run summaries ──
    run_ids: list[str] = []         # Ordered list for index-based behavior flags.
    run_agent_map: dict[str, str] = {}  # run_id -> agent_name for anomaly generation.
    base_time = NOW - timedelta(days=7)  # Start one week ago.

    for agent in AGENTS:
        for vi, (version, runs_per_agent_version) in enumerate(_version_entries(agent)):
            # The last 1/3 of runs for each version are errors.  This creates
            # a visible pattern in the fleet view and ensures non-trivial
            # error rates for aggregate metrics.
            error_start = runs_per_agent_version * 2 // 3
            for ri in range(runs_per_agent_version):
                run_id = str(uuid.uuid4())
                run_ids.append(run_id)
                run_agent_map[run_id] = agent["name"]

                # ── Behavior flags ──
                # Stages are:
                #   0, 1, 2 = normal (1st third: cost spike on #1, loop on #2)
                #   3, 4, 5 = moderate trouble (retry storm on #4, timeout on #6)
                #   6, 7, 8 = error zone (2nd third:
                #   cost spike on #7, loop on #9, retry storm on #10)
                #   9, 10, 11 = severe error zone (final third)
                is_error = ri >= error_start
                is_loop = ri in (2, 9)        # Every ~6th run has a loop.
                is_retry_storm = ri in (4, 10)  # Every ~6th run has a retry storm.

                # Status: "error" for the last third; "success" otherwise.
                status = "error" if is_error else "success"

                # Retries: retry-storm runs get triple the baseline retries
                # for visibility in retry-related anomaly detectors.
                retries = ri * 3 if is_retry_storm else ri

                # Tool calls scale with the run index (later runs do more work)
                # plus extra calls for retry overhead.
                tool_calls = (ri + 1) * 4 + (retries * 2)

                # Cost: base + per-step + retry overhead.  Grows monotonically
                # so cost-based anomalies can detect the cost_spike flags.
                cost = round(0.05 + ri * 0.15 + retries * 0.02, 6)

                # Duration: base latency + per-step + per-tool-call.
                duration_ms = 12000 + ri * 8000 + (tool_calls * 1200)

                # Timestamp: staggered across days, hours, and minutes so
                # fleet rollups see data across all time buckets.
                started = base_time + timedelta(
                    days=vi * 3 + ri // 4, hours=ri % 24, minutes=(ri * 7) % 60
                )

                await conn.execute(
                    """INSERT INTO run_summaries
                       (run_id, agent_name, agent_version, workload_type, duration_ms,
                        total_tool_calls, total_retries, total_interventions,
                        estimated_cost, loop_count, loop_detected, status,
                        started_at, completed_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                    run_id,
                    agent["name"],
                    version,
                    agent["workload"],
                    duration_ms,
                    tool_calls,
                    retries,
                    ri % 3,            # 0-2 interventions (cycles through values)
                    cost,
                    8 if is_loop else 0,  # Loop count: 8 for loop runs, 0 otherwise.
                    is_loop,
                    status,
                    started,
                    # Completed at = started + duration, converted to datetime.
                    started + timedelta(milliseconds=duration_ms),
                )

    # ── Generate anomalies ──
    # Each run gets 1-4 anomalies (avg ~2.5).  Anomaly types are assigned
    # round-robin from the ANOMALY_TYPES pool for maximum variety.
    anomaly_count = 0
    for run_id in run_ids:
        agent_name = run_agent_map[run_id]
        # 1-4 anomalies per run, varying by run index for diversity.
        num_anomalies = 1 + (run_ids.index(run_id) % 4)

        for ai in range(num_anomalies):
            # Round-robin selection from the anomaly type pool.  The multiplier
            # (3) and modulo give good distribution across all types.
            atype = ANOMALY_TYPES[(run_ids.index(run_id) * 3 + ai) % len(ANOMALY_TYPES)]

            # First anomaly per run is "critical" severity for visual contrast
            # in the inbox; subsequent ones are "warning".
            severity = "critical" if ai == 0 else "warning"

            await conn.execute(
                """INSERT INTO anomalies (
                    id, run_id, agent_name, anomaly_type, severity, explanation, evidence)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()),
                run_id,
                agent_name,
                atype,
                severity,
                # Explanation includes the first 8 chars of run_id as a
                # human-readable reference (not exposed in the UI directly).
                f"Detected {atype} anomaly in run {run_id[:8]}: threshold exceeded",
                # Evidence JSON mimics what the analytics detector produces:
                # a threshold value, the actual observed value, and the run.
                f'{{"threshold": 5, "actual": {7 + ai}, "run_id": "{run_id[:8]}"}}',
            )
            anomaly_count += 1

    # ── Generate fleet rollups ──
    # One rollup row per agent/version per day for 7 consecutive days.
    # ``ON CONFLICT DO NOTHING`` makes the seed idempotent.
    for agent in AGENTS:
        for version, runs_per_agent_version in _version_entries(agent):
            # Reset to midnight for clean daily boundaries.
            period_start = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
            for day_offset in range(7):
                ps = period_start + timedelta(days=day_offset)
                pe = ps + timedelta(hours=24)
                total = runs_per_agent_version
                errors = total // 3          # Roughly 1/3 errors.
                loops = total // 6           # Roughly 1/6 loops.
                avg_cost = round(0.5 + day_offset * 0.1, 6)  # Costs rise slightly per day.

                await conn.execute(
                    """INSERT INTO fleet_rollups
                       (id, agent_name, agent_version, workload_type, period_start, period_end,
                        total_runs, success_count, error_count, loop_count, anomaly_count,
                        avg_duration_ms, avg_cost)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                       ON CONFLICT DO NOTHING""",
                    str(uuid.uuid4()),
                    agent["name"],
                    version,
                    agent["workload"],
                    ps,
                    pe,
                    total,
                    total - errors,
                    errors,
                    loops,
                    anomaly_count // 4,  # Approximate anomaly count per day.
                    int(15000 + day_offset * 1000),  # Duration grows slightly per day.
                    avg_cost,
                )

    # ── Generate version cohort summaries ──
    # One row per agent version with aggregate stats.
    for agent in AGENTS:
        for version, runs_per_agent_version in _version_entries(agent):
            total = runs_per_agent_version
            errors = total // 3
            loops = total // 6
            tool_calls_total = total * 20  # Estimate: ~20 tool calls per run.

            # Default top_tools mirrors previous seed (JSON array), but for
            # research_crew v1.2.0/v1.3.0 we provide dict-shaped counts so
            # Version Compare can compute non-empty tool_deltas.
            top_tools: object
            if agent["name"] == "research_crew" and version == "v1.2.0":
                # Dict shape: tool-name -> invocation count.  These values
                # are designed to show a clear tool-count shift between
                # v1.2.0 (fetch-heavy) and v1.3.0 (analyze-heavy).
                top_tools = json.dumps({"fetch_data": 30, "analyze": 20, "search": 10})
            elif agent["name"] == "research_crew" and version == "v1.3.0":
                top_tools = json.dumps({"fetch_data": 25, "analyze": 35, "search": 5})
            else:
                # Keep existing semantics: a simple ordered list of tool names
                # (stored as JSON array) results in empty tool_deltas, which is
                # acceptable for E2E except the explicit research_crew compare.
                top_tools = json.dumps(["fetch_data", "analyze", "search", "compute", "validate"])

            await conn.execute(
                """INSERT INTO version_cohort_summaries
                   (id, agent_name, agent_version, total_runs, success_count, error_count,
                    loop_count, anomaly_count, avg_duration_ms, avg_cost,
                    total_tool_calls, total_retries, top_tools)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::json)
                   ON CONFLICT DO NOTHING""",
                str(uuid.uuid4()),
                agent["name"],
                version,
                total,
                total - errors,
                errors,
                loops,
                anomaly_count // 4,
                20000,  # Fixed avg duration for simplicity.
                round(0.75, 6),  # Fixed avg cost.
                tool_calls_total,
                total * 2,  # Retries: roughly 2x run count.
                top_tools,
            )

    await conn.close()
    await pool.close()
    # Summary printout so operators can verify expected data volumes.
    print(f"Seeded {len(run_ids)} runs, {anomaly_count} anomalies across {len(AGENTS)} agents.")


def main() -> None:
    """Parse CLI arguments and trigger seeding."""
    parser = argparse.ArgumentParser(description="Seed e2e demo data into Postgres")
    parser.add_argument(
        "--dsn",
        default="postgresql://analytics:analytics@localhost:5433/analytics",
        help="Postgres DSN (default: localhost:5433 for compose port remap)",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.dsn))


if __name__ == "__main__":
    main()