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
# actually arrives.  This avoids startup crashes when the DB container hasn't
# finished booting yet (common in Docker Compose orchestration).
_pool: Pool | None = None


async def get_pool() -> Pool:
    """Return the shared asyncpg connection pool, creating it if needed.

    The pool is sized according to ``settings.db_pool_min_size`` and
    ``settings.db_pool_max_size``.  This is a singleton: the pool is created
    once and reused for the lifetime of the process.

    Returns:
        The process-wide asyncpg connection pool instance.
    """
    global _pool
    if _pool is None:
        # Create pool with user-facing DSN string.  asyncpg accepts the full
        # DSN including username/password/dbname parameters.
        _pool = await asyncpg.create_pool(
            dsn=str(settings.db_dsn),
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
    return _pool


async def close_pool() -> None:
    """Close the shared connection pool and release all connections.

    Should be called during application shutdown (via FastAPI lifespan handler).
    After this call, ``get_pool()`` will create a fresh pool on the next request.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        # Reset to None so subsequent get_pool() calls re-create the pool
        # (useful in test teardown and hot-reload scenarios).
        _pool = None


async def health_check(pool: Pool) -> bool:
    """Verify the database is reachable with a ``SELECT 1`` probe.

    Args:
        pool: An active asyncpg connection pool.

    Returns:
        True if the database responds with 1, False on any connection or
        query error (timeout, auth failure, network drop, etc.).
    """
    try:
        async with pool.acquire() as conn:
            # ``fetchval`` returns a single scalar; we expect the int 1.
            # Cast to object because asyncpg is untyped.
            val: object = await conn.fetchval("SELECT 1")
            return bool(val == 1)
    except Exception:
        # Swallow any asyncpg exception (ConnectionError, InterfaceError, etc.)
        # so callers can log it and report degraded health without crashing.
        return False
