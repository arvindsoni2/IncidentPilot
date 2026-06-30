"""Explicit incident lifecycle transitions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agent.app.models import Incident


def mark_incident_resolved(
    session: Session,
    incident_id: int,
    *,
    consecutive_successes: int | None = None,
) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise ValueError(f"Unknown incident ID: {incident_id}")
    if consecutive_successes is not None and consecutive_successes < 3:
        return incident
    if incident.status not in {"new", "analyzing", "diagnosed"}:
        raise ValueError(
            f"Cannot resolve incident in status {incident.status}"
        )
    incident.status = "resolved"
    incident.resolved_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(incident)
    return incident


def auto_resolve_after_health_successes(
    session: Session,
    incident_id: int,
    consecutive_successes: int,
) -> Incident:
    return mark_incident_resolved(
        session,
        incident_id,
        consecutive_successes=consecutive_successes,
    )


def close_incident(session: Session, incident_id: int) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise ValueError(f"Unknown incident ID: {incident_id}")
    if incident.status != "resolved":
        raise ValueError("Only resolved incidents can be closed")
    incident.status = "closed"
    incident.closed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(incident)
    return incident
