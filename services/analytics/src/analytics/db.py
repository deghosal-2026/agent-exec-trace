"""asyncpg connection pool management for the analytics database.

Provides a lazily-initialized connection pool singleton, schema bootstrap,
and health-check utilities used by the worker, CLI, and API alike.

**Design decisions:**

- **Lazy initialization**: The pool is not created at import time.  ``get_pool()``
  creates it on first call, so the service can start without a database
  connection and only fails when actual work arrives.  This allows the CLI to
  display help without requiring a database.
- **Singleton pattern**: Using a module-level ``_pool`` variable means all
  callers share the same pool.  This is appropriate for a single-process
  service but would need rethinking in a multi-process (gunicorn/uwsgi)
  deployment.
- **No ORM**: Direct asyncpg queries are used throughout.  This keeps the
  service lightweight and avoids the overhead of SQLAlchemy for what are
  essentially simple CRUD operations.
"""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]
from asyncpg import Pool

from analytics.config import settings

# Module-level pool singleton.  Lazily initialized by ``get_pool()`` so the
# service can start without a database connection and only fails when work
# actually arrives.  Initialized as ``None``; becomes a ``Pool`` on first call.
_pool: Pool | None = None


async def get_pool() -> Pool:
    """Return the shared asyncpg connection pool, creating it if needed.

    The pool is sized according to ``settings.db_pool_min_size`` and
    ``settings.db_pool_max_size``.  This is a singleton: the pool is created
    once and reused for the lifetime of the process.

    Returns:
        An asyncpg ``Pool`` instance connected to the configured database.

    Raises:
        asyncpg.exceptions.InvalidPasswordError: if authentication fails.
        OSError: if the database host is unreachable.
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

    Safe to call multiple times; subsequent calls are no-ops once the
    pool is ``None``.  Should be called during graceful shutdown to
    prevent connection leaks.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def ensure_schema(pool: Pool) -> None:
    """Create the ``analytics`` schema if it does not exist.

    Called during worker startup so the service can create tables without
    an explicit migration step (development convenience).  Production
    deployments should manage schemas with a proper migration tool
    (e.g., Alembic) to track schema versions.

    Args:
        pool: an active asyncpg connection pool.

    Raises:
        asyncpg.exceptions.InsufficientPrivilegeError: if the database
            user lacks CREATE SCHEMA permission.
    """
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS analytics")


async def health_check(pool: Pool) -> bool:
    """Verify the database is reachable with a ``SELECT 1`` probe.

    This is the simplest possible health check: it verifies that a
    connection can be acquired and that the database responds to a
    trivial query.  It does NOT verify table existence or data integrity.

    Args:
        pool: an active asyncpg connection pool.

    Returns:
        ``True`` if the database responds to ``SELECT 1``, ``False`` on
        any error (connection failure, timeout, authentication error, etc.).
    """
    try:
        async with pool.acquire() as conn:
            val: object = await conn.fetchval("SELECT 1")
            return bool(val == 1)
    except Exception:
        return False
