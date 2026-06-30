import asyncio

import httpx

from agent.app.main import app


async def request(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def test_health_route() -> None:
    response = asyncio.run(request("/health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "incidentpilot",
    }


def test_home_page_renders() -> None:
    response = asyncio.run(request("/"))

    assert response.status_code == 200
    assert "IncidentPilot" in response.text
