"""asyncpg connection pool management for the API database.

Provides a lazily-initialized connection pool singleton and health-check utility
shared across all API routes.
"""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]
from asyncpg import Pool

from api.config import settings

# Module-level pool singleton. Lazily initialized by ``get_pool()`` so the API
# server can start without a database connection and only fails when a request
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
    """Close the shared connection pool and release all connections."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def health_check(pool: Pool) -> bool:
    """Verify the database is reachable with a ``SELECT 1`` probe.

    Returns True if the database responds, False on any error.
    """
    try:
        async with pool.acquire() as conn:
            val: object = await conn.fetchval("SELECT 1")
            return bool(val == 1)
    except Exception:
        return False