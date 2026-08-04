"""asyncpg connection pool management for the analytics database.

Provides a lazily-initialized connection pool singleton, schema bootstrap,
and health-check utilities used by the worker, CLI, and API alike.
"""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]
from asyncpg import Pool

from analytics.config import settings

# Module-level pool singleton. Lazily initialized by ``get_pool()`` so the
# service can start without a database connection and only fails when work
# actually arrives.
_pool: Pool | None = None


async def get_pool() -> Pool:
    """Return the shared asyncpg connection pool, creating it if needed.

    The pool is sized according to ``settings.db_pool_min_size`` and
    ``settings.db_pool_max_size``.  This is a singleton: the pool is created
    once and reused for the lifetime of the process.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=str(settings.db_dsn),
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
    return _pool


async def close_pool() -> None:
    """Close the shared connection pool and release all connections.

    Safe to call multiple times; subsequent calls are no-ops once the pool is ``None``.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def ensure_schema(pool: Pool) -> None:
    """Create the ``analytics`` schema if it does not exist.

    Called during worker startup so the service can create tables without an
    explicit migration step (development convenience).  Production deployments
    should manage schemas with a proper migration tool.
    """
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS analytics")


async def health_check(pool: Pool) -> bool:
    """Verify the database is reachable with a ``SELECT 1`` probe.

    Returns True if the database responds, False on any error (connection
    failure, timeout, etc.).
    """
    try:
        async with pool.acquire() as conn:
            val: object = await conn.fetchval("SELECT 1")
            return bool(val == 1)
    except Exception:
        return False