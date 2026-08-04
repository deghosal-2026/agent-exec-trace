from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_mock_pool(mock_conn: AsyncMock | None = None) -> AsyncMock:
    if mock_conn is None:
        mock_conn = AsyncMock()
    pool = AsyncMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = Mock(return_value=acquire_cm)
    return pool


def _make_run_row(
    run_id: str = "run_123",
    agent_name: str = "demo-agent",
    agent_version: str = "v1",
    status: str = "error",
    estimated_cost: float = 1.82,
    total_retries: int = 3,
    total_interventions: int = 0,
    total_tool_calls: int = 9,
    loop_detected: bool = True,
    duration_ms: int = 18420,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "agent_name": agent_name,
        "agent_version": agent_version,
        "workload_type": "code-review",
        "duration_ms": duration_ms,
        "total_tool_calls": total_tool_calls,
        "total_retries": total_retries,
        "total_interventions": total_interventions,
        "estimated_cost": estimated_cost,
        "loop_count": 1,
        "loop_detected": loop_detected,
        "status": status,
        "root_span_id": "span_root",
        "trace_id": "trace_123",
        "started_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 1, 1, 12, 0, 18, tzinfo=timezone.utc),
    }


def _make_anomaly_row(
    anomaly_id: str = "anom_1",
    run_id: str = "run_123",
    agent_name: str = "demo-agent",
    anomaly_type: str = "loop",
    severity: str = "high",
    explanation: str = "Same tool executed repeatedly",
) -> dict[str, Any]:
    return {
        "id": anomaly_id,
        "run_id": run_id,
        "agent_name": agent_name,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "explanation": explanation,
        "evidence": None,
        "detected_at": datetime(2026, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
    }


def _make_fleet_row(
    agent_name: str = "demo-agent",
    agent_version: str = "v1",
    workload_type: str = "code-review",
    total_runs: int = 42,
    success_count: int = 35,
    error_count: int = 7,
    anomaly_count: int = 5,
    avg_cost: float = 0.41,
) -> dict[str, Any]:
    return {
        "agent_name": agent_name,
        "agent_version": agent_version,
        "workload_type": workload_type,
        "period_start": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "period_end": datetime(2026, 1, 7, tzinfo=timezone.utc),
        "total_runs": total_runs,
        "success_count": success_count,
        "error_count": error_count,
        "loop_count": 2,
        "anomaly_count": anomaly_count,
        "avg_duration_ms": 15000,
        "avg_cost": avg_cost,
    }


def _make_cohort_row(
    agent_name: str = "demo-agent",
    agent_version: str = "v1",
    total_runs: int = 30,
    success_count: int = 25,
    error_count: int = 5,
    avg_cost: float = 0.35,
    total_retries: int = 10,
    top_tools: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "agent_name": agent_name,
        "agent_version": agent_version,
        "total_runs": total_runs,
        "success_count": success_count,
        "error_count": error_count,
        "loop_count": 1,
        "anomaly_count": 2,
        "avg_duration_ms": 14000,
        "avg_cost": avg_cost,
        "total_tool_calls": 100,
        "total_retries": total_retries,
        "top_tools": top_tools or {"search": 60, "read": 30, "write": 10},
    }


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_health_fail(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("db down"))
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/health")
            assert resp.status_code == 503


class TestRunTimeline:
    def test_run_found(self, client: TestClient) -> None:
        mock_conn = AsyncMock()

        async def fetchrow(*args: object, **kwargs: object) -> dict[str, Any] | None:
            return _make_run_row()

        async def fetch(*args: object, **kwargs: object) -> list[dict[str, Any]]:
            return [_make_anomaly_row()]

        mock_conn.fetchrow = fetchrow
        mock_conn.fetch = fetch
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/runs/run_123")
            assert resp.status_code == 200
            data = resp.json()
            assert data["run"]["run_id"] == "run_123"
            assert data["run"]["estimated_cost_usd"] == 1.82
            assert data["run"]["retry_count"] == 3
            assert data["summary"]["tool_call_count"] == 9
            assert data["summary"]["loop_detected"] is True
            assert len(data["anomalies"]) == 1
            assert data["anomalies"][0]["anomaly_id"] == "anom_1"

    def test_run_not_found(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/runs/unknown")
            assert resp.status_code == 404
            assert resp.json()["detail"]["code"] == "run_not_found"

    def test_run_no_anomalies(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=_make_run_row())
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/runs/run_456")
            assert resp.status_code == 200
            data = resp.json()
            assert data["anomalies"] == []


class TestFleet:
    def test_fleet_returns_rows(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[_make_fleet_row()])
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/fleet")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["rows"]) == 1
            row = data["data"]["rows"][0]
            assert row["agent_name"] == "demo-agent"
            assert row["run_count"] == 42
            assert row["success_rate"] == 0.8333
            assert row["anomaly_count"] == 5

    def test_fleet_empty(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/fleet")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["rows"] == []
            assert data["meta"]["total"] == 0

    def test_fleet_with_filters(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[_make_fleet_row()])
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/fleet?agent_name=demo-agent&agent_version=v1")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["rows"]) == 1


class TestCompare:
    def test_compare_both_versions(self, client: TestClient) -> None:
        mock_conn = AsyncMock()

        async def fetchrow(*args: object, **kwargs: object) -> dict[str, Any] | None:
            version = str(args[2]) if len(args) > 2 else ""
            if version == "v1":
                return _make_cohort_row(agent_version="v1", total_runs=30, avg_cost=0.35)
            if version == "v2":
                return _make_cohort_row(agent_version="v2", total_runs=28, avg_cost=0.49)
            return None

        mock_conn.fetchrow = fetchrow
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get(
                "/api/v1/compare?agent_name=demo-agent&version_a=v1&version_b=v2"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["left"]["version"] == "v1"
            assert data["right"]["version"] == "v2"
            assert data["deltas"]["avg_cost_usd"] is not None
            assert data["deltas"]["success_rate"] is not None
            assert len(data["tool_deltas"]) > 0

    def test_compare_one_version_missing(self, client: TestClient) -> None:
        mock_conn = AsyncMock()

        async def fetchrow(*args: object, **kwargs: object) -> dict[str, Any] | None:
            version = str(args[2]) if len(args) > 2 else ""
            return _make_cohort_row(agent_version="v1") if version == "v1" else None

        mock_conn.fetchrow = fetchrow
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get(
                "/api/v1/compare?agent_name=demo-agent&version_a=v1&version_b=v3"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["warning"] == "sparse_cohorts"

    def test_compare_sparse_cohorts(self, client: TestClient) -> None:
        mock_conn = AsyncMock()

        async def fetchrow(*args: object, **kwargs: object) -> dict[str, Any] | None:
            version = str(args[2]) if len(args) > 2 else ""
            if version == "v1":
                return _make_cohort_row(agent_version="v1", total_runs=3)
            if version == "v2":
                return _make_cohort_row(agent_version="v2", total_runs=2)
            return None

        mock_conn.fetchrow = fetchrow
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get(
                "/api/v1/compare?agent_name=demo-agent&version_a=v1&version_b=v2"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["warning"] == "sparse_cohorts"


class TestAnomalies:
    def test_anomalies_list(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=2)
        mock_conn.fetch = AsyncMock(
            return_value=[
                _make_anomaly_row(anomaly_id="anom_1"),
                _make_anomaly_row(
                    anomaly_id="anom_2",
                    anomaly_type="cost_spike",
                    severity="medium",
                ),
            ]
        )
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/anomalies")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["items"]) == 2
            assert data["meta"]["total"] == 2
            assert data["data"]["items"][0]["anomaly_id"] == "anom_1"

    def test_anomalies_empty(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/anomalies")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["items"] == []
            assert data["meta"]["total"] == 0

    def test_anomalies_with_filters(self, client: TestClient) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(
            return_value=[_make_anomaly_row(anomaly_type="loop")]
        )
        mock_pool = _make_mock_pool(mock_conn)

        with patch("api.routes.get_pool", return_value=mock_pool):
            resp = client.get("/api/v1/anomalies?severity=high&anomaly_type=loop")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["items"]) == 1