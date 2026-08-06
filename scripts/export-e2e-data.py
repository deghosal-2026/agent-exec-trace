#!/usr/bin/env python3
"""Export seeded E2E data from Postgres into docs/fixtures/e2e-seed.

= What this script does
Dumps four read-model tables from the analytics Postgres database into JSON
fixture files that serve as the canonical E2E seed data for the web frontend.
The output directory is ``docs/fixtures/e2e-seed/`` by default.

= Output files
* run_summaries.json     -- All run summary rows with full column data.
* anomalies.json         -- All anomaly rows linked to runs via run_id.
* fleet_rollups.json     -- Fleet health rollup rows (agent/version/workload/time).
* version_cohort_summaries.json -- Pre-aggregated per-version cohort stats.
* manifest.json          -- A simple table-name -> row-count mapping.

= Usage
    python3 scripts/export-e2e-data.py
    python3 scripts/export-e2e-data.py --dsn postgresql://analytics:analytics@localhost:5433/analytics

= Companion scripts
* seed-e2e-data.py      -- Generates mock data into the database.
* reload-e2e-data.py    -- Imports exported fixtures back into the database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg

# Tables are exported in this order so child tables (anomalies referencing
# run_summaries via foreign key) are dumped after their parents.  This ordering
# is also used by reload-e2e-data.py for consistent round-tripping.
TABLES = [
    "run_summaries",
    "anomalies",
    "fleet_rollups",
    "version_cohort_summaries",
]


def _json_default(value: Any) -> Any:
    """Custom JSON serializer for types that ``json.dumps`` can't handle natively.

    Handles:
        * Decimal -> float (PostgreSQL NUMERIC columns).
        * datetime/date -> ISO-8601 string (PostgreSQL TIMESTAMPTZ/DATE columns).

    Raises:
        TypeError: If the value type is not explicitly handled.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"Unsupported type: {type(value).__name__}")


async def export_data(dsn: str, output_dir: Path) -> None:
    """Connect to Postgres, dump all tables as JSON fixtures, and write a manifest.

    Args:
        dsn: PostgreSQL connection string (asyncpg DSN format).
        output_dir: Directory to write JSON fixture files into.
            Created if it doesn't exist.
    """
    # Ensure the output directory exists so the first write succeeds.
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        manifest: dict[str, int] = {}
        for table in TABLES:
            # ``SELECT *`` dumps all columns.  For small E2E datasets (hundreds
            # of rows) this is fast and avoids hardcoding column names.
            rows = await conn.fetch(f"SELECT * FROM {table}")

            # Convert each asyncpg Record to a plain dict so json.dumps works.
            payload = [dict(row) for row in rows]

            # Write as pretty-printed JSON (indent=2) for human readability in
            # code review.  Trailing newline ensures POSIX line-ending convention
            # and avoids diffs when editors strip trailing whitespace.
            (output_dir / f"{table}.json").write_text(
                json.dumps(payload, indent=2, default=_json_default) + "\n",
                encoding="utf-8",
            )
            manifest[table] = len(payload)

        # Write a small manifest file listing row counts per table so CI and
        # E2E test scripts can assert expected data volumes at a glance.
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        # Always close the connection to avoid resource leaks even on error.
        await conn.close()


def main() -> None:
    """Parse CLI arguments and trigger the export."""
    parser = argparse.ArgumentParser(description="Export seeded e2e data from Postgres")
    parser.add_argument(
        "--dsn",
        default="postgresql://analytics:analytics@localhost:5433/analytics",
        help="Postgres DSN",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/fixtures/e2e-seed",
        help="Directory for exported JSON fixtures",
    )
    args = parser.parse_args()
    asyncio.run(export_data(args.dsn, Path(args.output_dir)))


if __name__ == "__main__":
    main()