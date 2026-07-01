from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

import httpx
import pytest
from sqlalchemy import select

from agent.app.config import load_settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.models import Incident
from agent.app.services import EvidenceCollector, get_incident_detail
from agent.workflows import PlainPythonIncidentWorkflow

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("INCIDENTPILOT_LIVE_TESTS") != "1",
        reason="set INCIDENTPILOT_LIVE_TESTS=1 via the live harness",
    ),
]


def cli(*arguments: str) -> str:
    completed = subprocess.run(
        ["uv", "run", "incidentpilot", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        pytest.fail(
            f"CLI command failed: {' '.join(arguments)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout


def wait_for_backend(*, healthy: bool, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=2) as response:
                is_healthy = response.status == 200
        except (OSError, urllib.error.HTTPError):
            is_healthy = False
        if is_healthy is healthy:
            return
        time.sleep(1)
    pytest.fail(f"backend did not become {'healthy' if healthy else 'unhealthy'}")


class FixedHTTP:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def get(self, url: str, timeout: float):
        return httpx.Response(
            self.status_code,
            request=httpx.Request("GET", url),
        )


class RulesOnly:
    def enhance(self, baseline):
        return baseline


@pytest.fixture(autouse=True)
def healthy_demo_baseline():
    cli("scenarios", "reset")
    wait_for_backend(healthy=True)
    yield
    cli("scenarios", "reset")
    wait_for_backend(healthy=True)


@pytest.mark.parametrize(
    ("scenario_id", "expected_cause"),
    [
        ("FS-001", "backend_container_stopped"),
        ("FS-002", "dependency_unavailable"),
    ],
)
def test_live_failure_to_persisted_report_and_reset(
    scenario_id: str,
    expected_cause: str,
) -> None:
    cli("scenarios", "trigger", scenario_id)
    wait_for_backend(healthy=False)

    analysis_output = cli("analyze", "--service", "backend").strip()
    incident_ref = analysis_output.split("\t", maxsplit=1)[0]
    assert incident_ref.startswith("INC-")

    report = json.loads(cli("reports", "export-json", incident_ref))
    assert report["service"] == "backend"
    assert report["hypotheses"][0]["cause"] == expected_cause
    assert report["recommendations"][0]["executed"] is False
    assert report["evidence"]

    settings = load_settings()
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as session:
        incident_id = int(incident_ref.removeprefix("INC-"))
        incident = session.scalar(select(Incident).where(Incident.id == incident_id))
        assert incident is not None
        assert incident.status == "diagnosed"
        assert incident.agent_runs[0].status == "completed"
        assert len(incident.reports) == 1
    engine.dispose()

    cli("scenarios", "reset")
    wait_for_backend(healthy=True)


def test_wc001_live_runtime_with_injected_http_500() -> None:
    settings = load_settings()
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as session:
        healthy = PlainPythonIncidentWorkflow(
            settings=settings,
            session=session,
            evidence_collector=EvidenceCollector(
                settings=settings,
                session=session,
                http_client=FixedHTTP(200),
            ),
            llm_service=RulesOnly(),
        )
        healthy.analyze_service("backend", "WC-001-baseline")

        incident_result = PlainPythonIncidentWorkflow(
            settings=settings,
            session=session,
            evidence_collector=EvidenceCollector(
                settings=settings,
                session=session,
                http_client=FixedHTTP(500),
            ),
            llm_service=RulesOnly(),
        ).analyze_service("backend", "WC-001")
        incident = get_incident_detail(session, incident_result.incident_id)
        assert incident is not None
        payload = incident.reports[-1].json_payload["what_changed"]
        assert payload["counts"]["material"] == 1
        assert payload["counts"]["supporting_context"] == 1
        assert payload["material_changes"][0]["rule_id"] == ("WC_HTTP_STATUS_PRIMARY_200_TO_500")
        assert "## What Changed?" in incident.reports[-1].markdown
    engine.dispose()
