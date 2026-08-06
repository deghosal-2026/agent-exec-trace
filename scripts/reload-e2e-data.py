#!/usr/bin/env python3
"""Reload exported E2E fixture data from docs/fixtures/e2e-seed into Postgres.

Usage:
    python3 scripts/reload-e2e-data.py
    python3 scripts/reload-e2e-data.py --dsn postgresql://analytics:analytics@localhost:5433/analytics
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

import asyncpg


TABLES = [
    "run_summaries",
    "anomalies",
    "fleet_rollups",
    "version_cohort_summaries",
]

DATETIME_COLUMNS = {
    "run_summaries": {"started_at", "completed_at", "created_at", "updated_at"},
    "anomalies": {"detected_at", "created_at"},
    "fleet_rollups": {"period_start", "period_end", "created_at"},
    "version_cohort_summaries": {"created_at"},
}


def _coerce_value(table: str, column: str, value: object) -> object:
    if value is None:
        return None
    if column in DATETIME_COLUMNS.get(table, set()) and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


async def reload_data(dsn: str, input_dir: Path) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute("DELETE FROM anomalies")
        await conn.execute("DELETE FROM fleet_rollups")
        await conn.execute("DELETE FROM version_cohort_summaries")
        await conn.execute("DELETE FROM run_summaries")

        for table in TABLES:
            rows = json.loads((input_dir / f"{table}.json").read_text(encoding="utf-8"))
            if not rows:
                continue

            columns = list(rows[0].keys())
            placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

            for row in rows:
                values = [_coerce_value(table, col, row[col]) for col in columns]
                await conn.execute(query, *values)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reload exported e2e data into Postgres")
    parser.add_argument(
        "--dsn",
        default="postgresql://analytics:analytics@localhost:5433/analytics",
        help="Postgres DSN",
    )
    parser.add_argument(
        "--input-dir",
        default="docs/fixtures/e2e-seed",
        help="Directory containing exported JSON fixtures",
    )
    args = parser.parse_args()
    asyncio.run(reload_data(args.dsn, Path(args.input_dir)))


if __name__ == "__main__":
    main()
