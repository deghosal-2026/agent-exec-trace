"""API package for the agent-exec-trace REST service.

Provides the FastAPI application, Pydantic models, database queries, and route
handlers that serve the web frontend's data needs: run timeline details, fleet
health aggregates, version comparison, and anomaly inbox.

Exports nothing -- consumers import directly from the submodules they need.
"""
