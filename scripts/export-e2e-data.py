#!/usr/bin/env python3
"""Export seeded E2E data from Postgres into docs/fixtures/e2e-seed.

Usage:
    python3 scripts/export-e2e-data.py
    python3 scripts/export-e2e-data.py --dsn postgresql://analytics:analytics@localhost:5433/analytics
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


TABLES = [
    "run_summaries",
    "anomalies",
    "fleet_rollups",
    "version_cohort_summaries",
]


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"Unsupported type: {type(value).__name__}")


async def export_data(dsn: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        manifest: dict[str, int] = {}
        for table in TABLES:
            rows = await conn.fetch(f"SELECT * FROM {table}")
            payload = [dict(row) for row in rows]
            (output_dir / f"{table}.json").write_text(
                json.dumps(payload, indent=2, default=_json_default) + "\n",
                encoding="utf-8",
            )
            manifest[table] = len(payload)

        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        await conn.close()


def main() -> None:
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
