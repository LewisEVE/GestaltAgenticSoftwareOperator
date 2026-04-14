"""Integration tests for the FastAPI application surface."""

from __future__ import annotations

import os

from httpx import ASGITransport, AsyncClient

from gestalt.main import create_app


async def test_health_and_cycle_endpoints_work() -> None:
    """The application should expose health and cycle endpoints."""

    os.environ["GESTALT_REDIS_URL"] = "redis://localhost:6379/0"
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        live = await client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "live"

        ready = await client.get("/health/ready")
        assert ready.status_code == 200

        cycle = await client.post(
            "/api/v1/cycles/run",
            headers={"Authorization": "Bearer change-me"},
            json={"objective": "Analyze latency regression", "source": "api", "metadata": {}},
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["accepted"] is True
        assert payload["trace_id"]
