from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.main import create_app
from agent.app.services import (
    add_evidence,
    add_hypotheses,
    add_recommendations,
    create_agent_run,
    create_incident,
    create_service,
    finish_agent_run,
    save_report,
)
from agent.workflows import IncidentAnalysisResult


def web_settings(database_url: str) -> Settings:
    return Settings.model_validate(
        {
            "database": {"url": database_url},
            "services": [
                {
                    "name": "backend",
                    "runtime": "docker",
                    "container_name": "incidentpilot-demo-backend",
                    "health_url": "http://127.0.0.1:8001/health",
                    "polling_interval_seconds": 30,
                    "criticality": "high",
                    "dependencies": ["postgres"],
                },
                {
                    "name": "postgres",
                    "runtime": "docker",
                    "container_name": "incidentpilot-demo-postgres",
                    "criticality": "high",
                    "dependencies": [],
                },
            ],
        }
    )


def seed_incident(settings: Settings) -> int:
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as session:
        service = create_service(
            session,
            name="backend",
            runtime="docker",
            container_name="incidentpilot-demo-backend",
            health_url="http://127.0.0.1:8001/health",
            criticality="high",
            dependencies=["postgres"],
        )
        incident = create_incident(
            session,
            service_id=service.id,
            trigger_type="manual",
            status="diagnosed",
            severity="high",
            summary="Backend container stopped",
            llm_status="available",
        )
        evidence = add_evidence(
            session,
            incident_id=incident.id,
            type="container_status",
            source="docker",
            summary="Backend is exited",
            raw_payload={"running": False},
        )
        add_hypotheses(
            session,
            incident_id=incident.id,
            hypotheses=[
                {
                    "rank": 1,
                    "cause": "backend_container_stopped",
                    "confidence": 0.99,
                    "evidence_refs": [f"evidence:{evidence.id}"],
                    "reasoning": "Runtime reports the container exited.",
                }
            ],
        )
        add_recommendations(
            session,
            incident_id=incident.id,
            recommendations=[
                {
                    "action_key": "restart_container",
                    "title": "Restore backend manually",
                    "rationale": "A human should restore the service.",
                    "requires_approval": True,
                    "allowed_by_policy": False,
                }
            ],
        )
        save_report(
            session,
            incident_id=incident.id,
            markdown="# Incident Report\n\nNo remediation executed.",
            json_payload={
                "incident_id": incident.id,
                "service": "backend",
                "executed": False,
                "what_changed": {
                    "status": "available",
                    "rule_summary": "HTTP failed while the dependency remained healthy.",
                    "counts": {
                        "material": 1,
                        "supporting_context": 0,
                        "other": 0,
                        "total": 1,
                    },
                    "material_changes": [
                        {
                            "title": "Primary HTTP endpoint started failing",
                            "severity": "critical",
                            "before": {"value": "200 OK"},
                            "after": {"value": "500 Internal Server Error"},
                            "why_it_matters": "The primary endpoint is failing.",
                            "evidence_refs": ["evidence:1"],
                            "rule_id": "WC_HTTP_STATUS_PRIMARY_200_TO_500",
                        }
                    ],
                    "supporting_context": [],
                    "other_changes": [],
                    "llm": {"status": "not_attempted"},
                },
            },
        )
        incident_id = incident.id
    engine.dispose()
    return incident_id


async def request(
    app,
    method: str,
    path: str,
    *,
    follow_redirects: bool = True,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=follow_redirects,
    ) as client:
        return await client.request(method, path)


def test_all_dashboard_pages_render_with_sample_incident(
    tmp_path: Path,
) -> None:
    settings = web_settings(f"sqlite:///{tmp_path / 'web.db'}")
    incident_id = seed_incident(settings)
    app = create_app(settings)

    pages = {
        "/": "Dashboard",
        "/services": "Services",
        "/incidents": "Incidents",
        f"/incidents/{incident_id}": "Ranked hypotheses",
        "/reports": "Reports",
        "/settings": "Safety policy",
    }
    for path, expected in pages.items():
        response = asyncio.run(request(app, "GET", path))
        assert response.status_code == 200, path
        assert expected in response.text

    detail = asyncio.run(request(app, "GET", f"/incidents/{incident_id}"))
    assert "backend_container_stopped" in detail.text
    assert "Execution disabled in MVP" in detail.text
    assert "No remediation executed" in detail.text
    assert "/static/htmx-2.0.8.min.js" in detail.text
    assert "unpkg.com" not in detail.text
    assert "Collected" in detail.text
    assert "available" in detail.text
    assert "What Changed?" in detail.text
    assert "Primary HTTP endpoint started failing" in detail.text
    assert "1 changes detected" in detail.text


def test_htmx_partials_render(tmp_path: Path) -> None:
    settings = web_settings(f"sqlite:///{tmp_path / 'partials.db'}")
    seed_incident(settings)
    app = create_app(settings)

    cards = asyncio.run(request(app, "GET", "/partials/service-cards"))
    incidents = asyncio.run(request(app, "GET", "/partials/incidents"))

    assert cards.status_code == 200
    assert "Analyze service" in cards.text
    assert 'class="action-form"' in cards.text
    assert 'data-action-scope="analysis"' in cards.text
    assert "hx-post=" not in cards.text
    assert incidents.status_code == 200
    assert "INC-001" in incidents.text


def test_vendored_htmx_asset_is_served() -> None:
    app = create_app(Settings())

    response = asyncio.run(request(app, "GET", "/static/htmx-2.0.8.min.js"))

    assert response.status_code == 200
    assert "htmx" in response.text[:500].lower()


def test_failed_run_is_explained_on_incident_detail(
    tmp_path: Path,
) -> None:
    settings = web_settings(f"sqlite:///{tmp_path / 'failed.db'}")
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as session:
        service = create_service(
            session,
            name="backend",
            container_name="incidentpilot-demo-backend",
        )
        incident = create_incident(
            session,
            service_id=service.id,
            trigger_type="manual",
            status="failed",
            summary="Analysis failed: runtime disappeared",
        )
        run = create_agent_run(
            session,
            incident_id=incident.id,
            workflow_version="plain-python-v1",
            prompt_versions={},
            model=None,
        )
        finish_agent_run(
            session,
            run,
            status="failed",
            error="runtime disappeared",
        )
        incident_id = incident.id
    engine.dispose()

    response = asyncio.run(request(create_app(settings), "GET", f"/incidents/{incident_id}"))

    assert response.status_code == 200
    assert "Analysis failed" in response.text
    assert "runtime disappeared" in response.text
    assert "failed run were retained" in response.text


def test_dashboard_actions_have_consistent_busy_states(
    tmp_path: Path,
) -> None:
    settings = web_settings(f"sqlite:///{tmp_path / 'actions.db'}")
    app = create_app(settings)

    dashboard = asyncio.run(request(app, "GET", "/"))
    services = asyncio.run(request(app, "GET", "/services"))

    assert dashboard.status_code == 200
    assert dashboard.text.count('data-action-scope="scenario"') == 3
    assert "Stopping backend…" in dashboard.text
    assert "Stopping database…" in dashboard.text
    assert "Resetting demo…" in dashboard.text
    assert "/static/app.js" in dashboard.text
    assert 'id="action-announcer"' in dashboard.text
    assert services.status_code == 200
    assert services.text.count('data-action-scope="analysis"') == 2
    assert "Analyzing backend…" in services.text


def test_settings_hides_database_and_provider_secrets() -> None:
    settings = Settings.model_validate(
        {
            "database": {"url": "postgresql://secret-user:super-secret@db/incidentpilot"},
            "llm": {
                "provider": "ollama",
                "model": "safe-model",
                "base_url": "http://token-value@ollama:11434",
            },
        }
    )
    app = create_app(settings)

    response = asyncio.run(request(app, "GET", "/settings"))

    assert response.status_code == 200
    assert "postgresql" in response.text
    assert "safe-model" in response.text
    assert "super-secret" not in response.text
    assert "secret-user" not in response.text
    assert "token-value" not in response.text


def test_analyze_action_calls_workflow_and_redirects(
    tmp_path: Path,
) -> None:
    settings = web_settings(f"sqlite:///{tmp_path / 'analyze.db'}")
    seed_incident(settings)
    app = create_app(settings)
    calls: list[tuple[str, str]] = []

    class Workflow:
        def analyze_service(self, service_name: str, trigger_type: str):
            calls.append((service_name, trigger_type))
            return IncidentAnalysisResult(
                incident_id=1,
                incident_ref="INC-001",
                summary="done",
                severity="high",
                llm_status="available",
            )

    app.state.workflow_factory = lambda settings, session: Workflow()

    response = asyncio.run(
        request(
            app,
            "POST",
            "/actions/analyze/backend",
            follow_redirects=False,
        )
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/incidents/1"
    assert calls == [("backend", "web_manual")]


def test_report_export_and_download_routes(tmp_path: Path) -> None:
    settings = web_settings(f"sqlite:///{tmp_path / 'exports.db'}")
    incident_id = seed_incident(settings)
    app = create_app(settings)

    exported = asyncio.run(request(app, "GET", f"/reports/{incident_id}/export.json"))
    downloaded = asyncio.run(request(app, "GET", f"/reports/{incident_id}/download.md"))

    assert exported.status_code == 200
    assert exported.json()["service"] == "backend"
    assert exported.json()["executed"] is False
    assert downloaded.status_code == 200
    assert downloaded.text.startswith("# Incident Report")
    assert 'filename="INC-001.md"' in downloaded.headers["content-disposition"]
