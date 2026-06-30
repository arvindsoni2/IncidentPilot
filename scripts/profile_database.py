#!/usr/bin/env python3
"""Measure synchronous IncidentPilot persistence on a disposable SQLite DB."""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.services.persistence import (
    add_evidence,
    create_incident,
    create_service,
    get_incident_detail,
    list_incidents,
)


def milliseconds(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def profile(iterations: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="incidentpilot-profile-") as folder:
        database_path = Path(folder) / "profile.db"
        settings = Settings.model_validate(
            {"database": {"url": f"sqlite:///{database_path}"}}
        )
        engine = initialise_database(settings)
        factory = create_session_factory(engine)
        writes: list[float] = []
        detail_reads: list[float] = []

        with factory() as session:
            service = create_service(
                session,
                name="profile-backend",
                container_name="incidentpilot-profile-backend",
            )
            incident_ids: list[int] = []
            for index in range(iterations):
                started = perf_counter()
                incident = create_incident(
                    session,
                    service_id=service.id,
                    trigger_type="profile",
                    status="diagnosed",
                    summary=f"Profile incident {index}",
                )
                add_evidence(
                    session,
                    incident_id=incident.id,
                    type="profile",
                    source="local",
                    summary="Synthetic profiling evidence",
                )
                writes.append(milliseconds(started))
                incident_ids.append(incident.id)

            started = perf_counter()
            incidents = list_incidents(session)
            list_read_ms = milliseconds(started)

            for incident_id in incident_ids:
                started = perf_counter()
                assert get_incident_detail(session, incident_id) is not None
                detail_reads.append(milliseconds(started))

        engine.dispose()

    return {
        "iterations": iterations,
        "database": "temporary SQLite",
        "write_incident_and_evidence_ms": summarize(writes),
        "list_incidents_ms": list_read_ms,
        "incident_detail_ms": summarize(detail_reads),
        "records_listed": len(incidents),
    }


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    percentile_index = max(0, int(len(ordered) * 0.95) - 1)
    return {
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "p95": ordered[percentile_index],
        "max": max(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    arguments = parser.parse_args()
    if arguments.iterations < 1:
        parser.error("--iterations must be at least 1")
    print(json.dumps(profile(arguments.iterations), indent=2))


if __name__ == "__main__":
    main()
