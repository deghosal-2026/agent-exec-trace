#!/usr/bin/env python3
"""Create read-model tables in Postgres (synchronous alternative to Alembic).

Usage:
    make migrate-db
    python3 scripts/migrate-db.py --dsn postgresql://analytics:analytics@localhost:5433/analytics
"""

from __future__ import annotations

import argparse
import asyncio
import asyncpg


SQL = """
CREATE TABLE IF NOT EXISTS run_summaries (
    run_id VARCHAR(255) PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    agent_version VARCHAR(50),
    workload_type VARCHAR(100),
    duration_ms BIGINT,
    total_tool_calls INTEGER DEFAULT 0,
    total_retries INTEGER DEFAULT 0,
    total_interventions INTEGER DEFAULT 0,
    estimated_cost NUMERIC(10,6),
    loop_count INTEGER DEFAULT 0,
    loop_detected BOOLEAN DEFAULT false,
    status VARCHAR(50),
    root_span_id VARCHAR(255),
    trace_id VARCHAR(255),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS anomalies (
    id VARCHAR(255) PRIMARY KEY,
    run_id VARCHAR(255) REFERENCES run_summaries(run_id),
    agent_name VARCHAR(255) NOT NULL,
    anomaly_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'warning',
    explanation TEXT,
    evidence JSON,
    detected_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fleet_rollups (
    id VARCHAR(255) PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    agent_version VARCHAR(50),
    workload_type VARCHAR(100),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    total_runs INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    loop_count INTEGER DEFAULT 0,
    anomaly_count INTEGER DEFAULT 0,
    avg_duration_ms BIGINT,
    avg_cost NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(agent_name, agent_version, workload_type, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS version_cohort_summaries (
    id VARCHAR(255) PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    agent_version VARCHAR(50) NOT NULL,
    total_runs INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    loop_count INTEGER DEFAULT 0,
    anomaly_count INTEGER DEFAULT 0,
    avg_duration_ms BIGINT,
    avg_cost NUMERIC(10,6),
    total_tool_calls INTEGER DEFAULT 0,
    total_retries INTEGER DEFAULT 0,
    top_tools JSON,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(agent_name, agent_version)
);

CREATE INDEX IF NOT EXISTS idx_run_summaries_agent ON run_summaries(agent_name);
CREATE INDEX IF NOT EXISTS idx_run_summaries_version ON run_summaries(agent_version);
CREATE INDEX IF NOT EXISTS idx_run_summaries_started_at ON run_summaries(started_at);
CREATE INDEX IF NOT EXISTS idx_anomalies_run_id ON anomalies(run_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_fleet_rollups_agent ON fleet_rollups(agent_name);
"""


async def migrate(dsn: str) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    for stmt in SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            await conn.execute(stmt)
    await conn.close()
    print("Migration complete: all read-model tables created.")


def main() -> None:
    p = argparse.ArgumentParser(description="Create read-model tables")
    p.add_argument(
        "--dsn",
        default="postgresql://analytics:analytics@localhost:5433/analytics",
        help="Postgres DSN",
    )
    args = p.parse_args()
    asyncio.run(migrate(args.dsn))


if __name__ == "__main__":
    main()