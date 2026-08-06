"""FastAPI application entry point for the agent-exec-trace REST API.

Provides the HTTP server that serves the web frontend's data needs: run timeline
details, fleet health aggregates, version comparison, and anomaly inbox.  The
server uses CORS middleware to allow the Vite dev server and production builds
to make cross-origin requests.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.db import close_pool, get_pool, health_check
from api.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler: initializes and tears down the DB pool.

    The pool is created on startup and closed on shutdown.  A health check runs
    at startup so the log shows whether the database is reachable.

    Args:
        app: The FastAPI application instance (unused parameter, required by
            the FastAPI lifespan protocol signature).
    """
    # Eagerly initialize the pool so the first request doesn't pay the
    # connection-establishment latency.  If the DB is down at startup,
    # the server still starts but logs a warning so operators know.
    pool = await get_pool()
    db_ok = await health_check(pool)
    if db_ok:
        logger.info("Database connection established")
    else:
        logger.warning("Database not available at startup")
    yield  # Application runs here; teardown below runs after shutdown signal.
    await close_pool()
    logger.info("Database pool closed")


# Construct the FastAPI application with OpenAPI metadata.
# Lifespan handles startup/shutdown; version is hardcoded for now until
# there's a proper release process.
app = FastAPI(
    title="agent-exec-trace API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow the Vite dev server (port 5173) and any production build origin.
# ``allow_methods=["*"]`` and ``allow_headers=["*"]`` are permissive defaults
# suitable for internal/admin tools.  Tighten for public-facing deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routes under the shared router (prefix: /api/v1).
app.include_router(router)


def run() -> None:
    """Start the uvicorn server with the configured host, port, and log level.

    This is the entry point used by ``python -m api.main`` and the Docker
    CMD.  We import uvicorn lazily here to avoid an import-time dependency
    on the web server when the module is used purely for its ``app`` object
    (e.g. in tests via TestClient).
    """
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


# Direct execution (``python api/main.py``) starts the server.
# For production, use ``python -m api.main`` or the ``run()`` entry in Docker.
if __name__ == "__main__":
    run()
