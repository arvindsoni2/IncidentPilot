from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from agent.adapters.runtime import ContainerMetadata, ContainerStatus, LogEvidence
from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.models import HealthySnapshot
from agent.app.schemas import WhatChangedCounts, WhatChangedResult
from agent.app.services import (
    EvidenceCollector,
    WhatChangedAdvisoryService,
    get_incident_detail,
)
from agent.workflows import PlainPythonIncidentWorkflow


class Runtime:
    def __init__(self, running=True):
        self.running = running

    def get_container_status(self, name):
        return ContainerStatus(
            container_name=name, state="running" if self.running else "exited", running=self.running
        )

    def get_recent_logs(self, name, since_seconds, max_bytes):
        return LogEvidence(container_name=name, since_seconds=since_seconds, max_bytes=max_bytes)

    def get_container_metadata(self, name):
        return ContainerMetadata(
            container_name=name,
            image_name="demo:1",
            image_id="sha256:1",
            labels={"com.docker.compose.project": "demo", "com.docker.compose.service": "backend"},
        )


class HTTP:
    def __init__(self, status):
        self.status = status

    def get(self, url, timeout):
        import httpx

        return httpx.Response(self.status, request=httpx.Request("GET", url))


def settings(path: Path):
    return Settings.model_validate(
        {
            "database": {"url": f"sqlite:///{path}"},
            "metrics": {"enabled": False},
            "services": [
                {
                    "name": "backend",
                    "container_name": "backend",
                    "health_url": "http://user:secret@backend/health?token=secret",
                    "dependencies": ["db"],
                },
                {"name": "db", "container_name": "db", "dependencies": []},
            ],
        }
    )


def collector(config, session, status):
    return EvidenceCollector(
        settings=config,
        session=session,
        runtime_factory=lambda *args, **kwargs: Runtime(),
        http_client=HTTP(status),
    )


class NoLLM:
    def enhance(self, baseline):
        return baseline


def workflow(config, session, status):
    return PlainPythonIncidentWorkflow(
        settings=config,
        session=session,
        evidence_collector=collector(config, session, status),
        llm_service=NoLLM(),
    )


def test_wc001_and_safe_metadata(tmp_path):
    config = settings(tmp_path / "wc.db")
    engine = initialise_database(config)
    factory = create_session_factory(engine)
    with factory() as session:
        healthy = workflow(config, session, 200).analyze_service("backend")
        assert (
            get_incident_detail(session, healthy.incident_id)
            .reports[0]
            .json_payload["what_changed"]["status"]
            == "no_baseline"
        )

        failed = workflow(config, session, 500).analyze_service("backend")
        payload = (
            get_incident_detail(session, failed.incident_id).reports[0].json_payload["what_changed"]
        )
        assert payload["counts"] == {"material": 1, "supporting_context": 1, "other": 0, "total": 2}
        assert payload["material_changes"][0]["rank"] == 40
        assert payload["supporting_context"][0]["rank"] == 500
        snapshot = session.scalar(select(HealthySnapshot))
        assert snapshot.evidence_payload["http"]["path_without_query"] == "/health"
        serialized = str(snapshot.evidence_payload)
        assert "secret" not in serialized
        assert "token" not in serialized
    engine.dispose()


def test_counts_reject_inconsistent_total():
    with pytest.raises(ValueError):
        WhatChangedCounts(material=1, supporting_context=1, other=0, total=1)


def test_retention_keeps_latest_plus_twenty(tmp_path):
    config = settings(tmp_path / "retention.db")
    engine = initialise_database(config)
    factory = create_session_factory(engine)
    with factory() as session:
        for _ in range(22):
            workflow(config, session, 200).analyze_service("backend")
        assert len(list(session.scalars(select(HealthySnapshot)))) == 21
    engine.dispose()


class AdvisoryProvider:
    def __init__(self, unsafe=False):
        self.unsafe = unsafe
        self.calls = 0

    def generate_json(self, prompt):
        self.calls += 1
        return {
            "summary": (
                "Run sudo docker restart backend"
                if self.unsafe
                else "The HTTP failure occurred while the dependency remained healthy."
            ),
            "per_change_notes": {},
        }


def test_advisory_accepts_safe_text_and_hides_unsafe_text(tmp_path):
    config = settings(tmp_path / "advisory.db")
    engine = initialise_database(config)
    factory = create_session_factory(engine)
    with factory() as session:
        workflow(config, session, 200).analyze_service("backend")
        incident = workflow(config, session, 500).analyze_service("backend")
        raw = get_incident_detail(session, incident.incident_id).reports[0].json_payload
        result = WhatChangedResult.model_validate(raw["what_changed"])

        safe = WhatChangedAdvisoryService(AdvisoryProvider(), "test").enhance(result)
        assert safe.llm.status == "accepted"
        assert safe.ai_advisory_summary

        provider = AdvisoryProvider(unsafe=True)
        unsafe = WhatChangedAdvisoryService(provider, "test").enhance(result)
        assert unsafe.llm.status == "validation_failed"
        assert unsafe.ai_advisory_summary is None
        assert provider.calls == 2
    engine.dispose()
