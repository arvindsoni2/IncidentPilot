from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import httpx


def load_demo_backend() -> ModuleType:
    if importlib.util.find_spec("psycopg") is None:
        psycopg_stub = ModuleType("psycopg")

        class PsycopgError(Exception):
            pass

        psycopg_stub.Error = PsycopgError
        psycopg_stub.connect = lambda *args, **kwargs: None
        sys.modules["psycopg"] = psycopg_stub

    module_path = (
        Path(__file__).resolve().parents[2]
        / "demo-app"
        / "backend"
        / "app"
        / "main.py"
    )
    spec = importlib.util.spec_from_file_location("demo_backend_main", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo_backend = load_demo_backend()


async def get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=demo_backend.app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://demo",
    ) as client:
        return await client.get(path)


def test_health_and_db_check_are_healthy_when_database_is_available(
    monkeypatch,
) -> None:
    async def healthy_database():
        return {"healthy": True, "latency_ms": 1.25, "error": None}

    monkeypatch.setattr(demo_backend, "database_status", healthy_database)

    health = asyncio.run(get("/health"))
    db_check = asyncio.run(get("/db-check"))

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert db_check.status_code == 200


def test_health_and_ready_fail_when_database_is_unavailable(
    monkeypatch,
) -> None:
    async def unavailable_database():
        return {
            "healthy": False,
            "latency_ms": 2.0,
            "error": "connection refused",
        }

    monkeypatch.setattr(demo_backend, "database_status", unavailable_database)

    health = asyncio.run(get("/health"))
    ready = asyncio.run(get("/ready"))

    assert health.status_code == 503
    assert health.json()["status"] == "unhealthy"
    assert health.json()["database"]["error"] == "connection refused"
    assert ready.status_code == 503


def test_metrics_endpoint_is_available() -> None:
    response = asyncio.run(get("/metrics"))

    assert response.status_code == 200
    assert "demo_backend_http_requests_total" in response.text
