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
    """
    pool = await get_pool()
    db_ok = await health_check(pool)
    if db_ok:
        logger.info("Database connection established")
    else:
        logger.warning("Database not available at startup")
    yield
    await close_pool()
    logger.info("Database pool closed")


app = FastAPI(
    title="agent-exec-trace API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow the Vite dev server (port 5173) and any production build origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def run() -> None:
    """Start the uvicorn server with the configured host, port, and log level."""
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()