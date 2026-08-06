#!/usr/bin/env python3
"""Reload exported E2E fixture data from docs/fixtures/e2e-seed into Postgres.

= Purpose
Imports JSON fixture files produced by ``export-e2e-data.py`` back into the
four read-model tables.  This supports an "export then re-import" workflow for:
* Reproducing known-good fixture states in CI.
* Migrating seed data between Postgres instances.
* Round-trip testing of the export format.

= Data flow
1. Read JSON files from the input directory.
2. DELETE all rows from all four tables (order matters: child tables first to
   avoid FK constraint violations).
3. INSERT rows using dynamically-built INSERT statements that adapt to the
   column set in the JSON data.

= Datetime coercion
JSON serializes timestamps as ISO-8601 strings.  This script detects known
datetime columns per table and converts strings back to Python ``datetime``
objects so asyncpg can bind them correctly.

= Usage
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

# Table export/reload order: child tables first (anomalies references
# run_summaries via FK), so we DELETE children before parents.
TABLES = [
    "run_summaries",
    "anomalies",
    "fleet_rollups",
    "version_cohort_summaries",
]

# Map each table to the set of columns that store timestamp data.  When a
# column is in this set and the JSON value is a string, it gets parsed back
# to a datetime object.  All other values pass through unchanged.
DATETIME_COLUMNS = {
    "run_summaries": {"started_at", "completed_at", "created_at", "updated_at"},
    "anomalies": {"detected_at", "created_at"},
    "fleet_rollups": {"period_start", "period_end", "created_at"},
    "version_cohort_summaries": {"created_at"},
}


def _coerce_value(table: str, column: str, value: object) -> object:
    """Convert JSON-serialized values back to Python-native types for asyncpg.

    Specifically, ISO-8601 datetime strings in known timestamp columns are
    parsed back using ``datetime.fromisoformat()``.  All other values
    (including None) pass through unchanged.

    Args:
        table: The table name (used to look up known datetime columns).
        column: The column name being processed.
        value: The JSON-deserialized value for this column.

    Returns:
        A Python value suitable for asyncpg bind parameters.
    """
    if value is None:
        return None
    # Check if this column is a known datetime column in this table.
    if column in DATETIME_COLUMNS.get(table, set()) and isinstance(value, str):
        # ``fromisoformat`` handles ISO-8601 with and without timezone info.
        return datetime.fromisoformat(value)
    return value


async def reload_data(dsn: str, input_dir: Path) -> None:
    """Delete all existing data and reload from JSON fixtures.

    Args:
        dsn: PostgreSQL connection string.
        input_dir: Directory containing the JSON fixture files.
    """
    conn = await asyncpg.connect(dsn=dsn)
    try:
        # DELETE order: child tables first to avoid foreign-key violations.
        # (anomalies references run_summaries via FK).
        await conn.execute("DELETE FROM anomalies")
        await conn.execute("DELETE FROM fleet_rollups")
        await conn.execute("DELETE FROM version_cohort_summaries")
        await conn.execute("DELETE FROM run_summaries")

        for table in TABLES:
            # Load the JSON fixture for this table.
            rows = json.loads((input_dir / f"{table}.json").read_text(encoding="utf-8"))
            if not rows:
                continue  # Skip empty tables (no rows to insert).

            # Infer the column list from the first row's keys.  This makes the
            # script resilient to schema evolution (new columns in the JSON are
            # automatically included).
            columns = list(rows[0].keys())

            # Build parameterized INSERT: ``($1, $2, $3, ...)`` with one
            # placeholder per column.
            placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

            for row in rows:
                # Apply datetime coercion to each value before binding.
                values = [_coerce_value(table, col, row[col]) for col in columns]
                await conn.execute(query, *values)
    finally:
        await conn.close()


def main() -> None:
    """Parse CLI arguments and trigger the reload."""
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