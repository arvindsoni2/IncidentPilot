import httpx

from agent.adapters.metrics import PrometheusMetricsAdapter


def test_prometheus_adapter_returns_samples() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"job": "backend"}, "value": [1, "1"]}],
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    snapshot = PrometheusMetricsAdapter(
        base_url="http://prometheus",
        client=client,
    ).query_snapshot({"up": "up"})

    assert snapshot.available is True
    assert snapshot.samples["up"][0]["value"][1] == "1"
    client.close()


def test_prometheus_adapter_returns_unavailable_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    snapshot = PrometheusMetricsAdapter(
        base_url="http://prometheus",
        client=client,
    ).query_snapshot({"up": "up"})

    assert snapshot.available is False
    assert "connection refused" in (snapshot.error or "")
    client.close()


def test_named_service_queries_cover_up_requests_and_errors() -> None:
    observed_queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_queries.append(
            request.url.params.get("query", "")
        )
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = PrometheusMetricsAdapter(
        base_url="http://prometheus",
        client=client,
    )

    snapshot = adapter.query_service_snapshot()

    assert snapshot.available is True
    assert set(snapshot.samples) == {
        "target_up",
        "request_rate",
        "error_rate",
    }
    assert 'up{job="demo-backend"}' in observed_queries
    assert any("demo_backend_http_requests_total[5m]" in item for item in observed_queries)
    assert any('status=~"5.."' in item for item in observed_queries)
    client.close()
