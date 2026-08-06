#!/usr/bin/env python3
"""Seed the Postgres read-model with mock data for demo and e2e testing.

Populates run_summaries, anomalies, fleet_rollups, and version_cohort_summaries
with enough data to exercise all four standard views:
  - Fleet Health (filters by agent, version, workload, status)
  - Run Timeline (span trees, anomaly drill-down)
  - Version Compare (deltas between two versions)
  - Anomaly Inbox (type and severity filtering)

Usage:
    python3 scripts/seed-e2e-data.py
    python3 scripts/seed-e2e-data.py --dsn postgresql://analytics:analytics@localhost:5433/analytics
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg

AGENTS = [
    {"name": "research_crew", "workload": "research_crew", "versions": ["v1.2.0", "v1.3.0"]},
    {"name": "support_triage", "workload": "support_triage", "versions": ["v1.0.0", "v1.1.0", "v2.0.0"]},
    {"name": "code_review", "workload": "code_review", "versions": ["v1.0.0"]},
    {"name": "demo_triage", "workload": "demo_triage", "versions": ["v0.1.0", "v0.2.0"]},
]

ANOMALY_TYPES = [
    "loop", "pattern_loop", "argument_loop",
    "tool_error_rate", "specific_tool_error", "tool_latency", "tool_timeout", "redundant_tool_call",
    "cost_spike", "cost_vs_baseline", "cost_efficiency", "token_explosion",
    "per_tool_cost_spike", "wasted_tool_calls",
    "run_duration", "max_step_hit", "step_efficiency", "inactivity", "premature_completion",
    "retry_storm", "systemic_retry", "transient_retry", "cascading_retry", "recovery_path",
    "intervention_frequency", "escalation_rate", "approval_latency", "intervention_rejection",
    "empty_response", "low_output", "indeterminate_status", "output_drift",
    "anomaly_cluster", "run_frequency_anomaly", "first_run_heuristic",
]

NOW = datetime.now(timezone.utc)


async def seed(dsn: str) -> None:
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    conn = await pool.acquire()

    await conn.execute("DELETE FROM anomalies")
    await conn.execute("DELETE FROM fleet_rollups")
    await conn.execute("DELETE FROM version_cohort_summaries")
    await conn.execute("DELETE FROM run_summaries")

    run_ids: list[str] = []
    runs_per_agent_version = 12
    base_time = NOW - timedelta(days=7)

    for agent in AGENTS:
        for vi, version in enumerate(agent["versions"]):
            for ri in range(runs_per_agent_version):
                run_id = str(uuid.uuid4())
                run_ids.append(run_id)

                is_error = ri >= 8
                is_loop = ri in (2, 9)
                is_retry_storm = ri in (4, 10)
                is_cost_spike = ri in (1, 7)
                is_timeout = ri == 6

                status = "error" if is_error else "success"
                retries = ri * 3 if is_retry_storm else ri
                tool_calls = (ri + 1) * 4 + (retries * 2)
                cost = round(0.05 + ri * 0.15 + retries * 0.02, 6)
                duration_ms = 12000 + ri * 8000 + (tool_calls * 1200)

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
                    ri % 3,
                    cost,
                    8 if is_loop else 0,
                    is_loop,
                    status,
                    started,
                    started + timedelta(milliseconds=duration_ms),
                )

    anomaly_count = 0
    for run_id in run_ids:
        agent_info = AGENTS[run_ids.index(run_id) % len(AGENTS)]
        num_anomalies = 1 + (run_ids.index(run_id) % 4)

        for ai in range(num_anomalies):
            atype = ANOMALY_TYPES[(run_ids.index(run_id) * 3 + ai) % len(ANOMALY_TYPES)]
            severity = "critical" if ai == 0 else "warning"

            await conn.execute(
                """INSERT INTO anomalies (id, run_id, agent_name, anomaly_type, severity, explanation, evidence)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()),
                run_id,
                agent_info["name"],
                atype,
                severity,
                f"Detected {atype} anomaly in run {run_id[:8]}: threshold exceeded",
                f'{{"threshold": 5, "actual": {7 + ai}, "run_id": "{run_id[:8]}"}}',
            )
            anomaly_count += 1

    for agent in AGENTS:
        for version in agent["versions"]:
            period_start = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
            for day_offset in range(7):
                ps = period_start + timedelta(days=day_offset)
                pe = ps + timedelta(hours=24)
                total = runs_per_agent_version
                errors = total // 3
                loops = total // 6
                avg_cost = round(0.5 + day_offset * 0.1, 6)

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
                    anomaly_count // 4,
                    int(15000 + day_offset * 1000),
                    avg_cost,
                )

    for agent in AGENTS:
        for version in agent["versions"]:
            total = runs_per_agent_version
            errors = total // 3
            loops = total // 6
            tool_calls_total = total * 20

            await conn.execute(
                """INSERT INTO version_cohort_summaries
                   (id, agent_name, agent_version, total_runs, success_count, error_count,
                    loop_count, anomaly_count, avg_duration_ms, avg_cost,
                    total_tool_calls, total_retries, top_tools)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                   ON CONFLICT DO NOTHING""",
                str(uuid.uuid4()),
                agent["name"],
                version,
                total,
                total - errors,
                errors,
                loops,
                anomaly_count // 4,
                20000,
                round(0.75, 6),
                tool_calls_total,
                total * 2,
                '["fetch_data", "analyze", "search", "compute", "validate"]',
            )

    await conn.close()
    await pool.close()
    print(f"Seeded {len(run_ids)} runs, {anomaly_count} anomalies across {len(AGENTS)} agents.")


def main() -> None:
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