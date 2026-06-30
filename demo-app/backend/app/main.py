"""Small failure-friendly FastAPI service used by the IncidentPilot demo."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TypedDict

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.responses import Response

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("incidentpilot.demo.backend")

REQUEST_COUNTS: dict[tuple[str, str], int] = {}


class DatabaseStatus(TypedDict):
    healthy: bool
    latency_ms: float
    error: str | None


def _check_database_sync() -> DatabaseStatus:
    started = time.perf_counter()
    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "2")),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {
            "healthy": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": None,
        }
    except (KeyError, psycopg.Error, ValueError) as error:
        logger.error("Database health check failed: %s", error)
        return {
            "healthy": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": str(error),
        }


async def database_status() -> DatabaseStatus:
    return await asyncio.to_thread(_check_database_sync)


app = FastAPI(title="IncidentPilot Demo Backend", version="0.1.0")


async def _health_response(endpoint: str) -> JSONResponse:
    database = await database_status()
    healthy = database["healthy"]
    status_code = 200 if healthy else 503
    counter_key = (endpoint, str(status_code))
    REQUEST_COUNTS[counter_key] = REQUEST_COUNTS.get(counter_key, 0) + 1
    payload = {
        "status": "healthy" if healthy else "unhealthy",
        "service": "demo-backend",
        "database": database,
    }
    if healthy:
        logger.info("%s succeeded; database latency %.2fms", endpoint, database["latency_ms"])
    else:
        logger.warning("%s failed because the database is unavailable", endpoint)
    return JSONResponse(payload, status_code=status_code)


@app.get("/health")
async def health() -> JSONResponse:
    return await _health_response("/health")


@app.get("/ready")
async def ready() -> JSONResponse:
    return await _health_response("/ready")


@app.get("/db-check")
async def db_check() -> JSONResponse:
    return await _health_response("/db-check")


@app.get("/metrics")
async def metrics() -> Response:
    lines = [
        "# HELP demo_backend_up Whether the demo backend process is running.",
        "# TYPE demo_backend_up gauge",
        "demo_backend_up 1",
        "# HELP demo_backend_http_requests_total Demo backend HTTP requests.",
        "# TYPE demo_backend_http_requests_total counter",
    ]
    lines.extend(
        (
            "demo_backend_http_requests_total"
            f'{{endpoint="{endpoint}",status="{status}"}} {count}'
        )
        for (endpoint, status), count in sorted(REQUEST_COUNTS.items())
    )
    return Response(
        "\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4",
    )
