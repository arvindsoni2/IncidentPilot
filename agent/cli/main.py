"""Typer CLI entrypoint."""

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import typer
import uvicorn
from sqlalchemy.orm import Session

from agent import __version__
from agent.adapters.runtime import create_runtime_adapter
from agent.app.config import load_settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.services import (
    EvalRunner,
    HealthPoller,
    ScenarioRunner,
    ScenarioRunnerError,
    close_incident,
    delete_eval_runs_before,
    get_incident_detail,
    list_eval_runs,
    list_incidents,
    mark_incident_resolved,
)
from agent.workflows import PlainPythonIncidentWorkflow, format_incident_ref

app = typer.Typer(
    name="incidentpilot",
    help="Local-first, read-only incident triage.",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Database lifecycle commands.")
services_app = typer.Typer(help="Inspect configured services.")
runtime_app = typer.Typer(help="Inspect read-only container runtime state.")
incidents_app = typer.Typer(help="Inspect incident history.")
reports_app = typer.Typer(help="View and export incident reports.")
scenarios_app = typer.Typer(
    help="Trigger fixed failure scenarios in the demo stack only."
)
health_app = typer.Typer(help="Run and inspect service health checks.")
poll_app = typer.Typer(help="Run configurable health polling.")
evals_app = typer.Typer(help="Run golden incident evaluations.")
app.add_typer(db_app, name="db")
app.add_typer(services_app, name="services")
app.add_typer(runtime_app, name="runtime")
app.add_typer(incidents_app, name="incidents")
app.add_typer(reports_app, name="reports")
app.add_typer(scenarios_app, name="scenarios")
app.add_typer(health_app, name="health")
app.add_typer(poll_app, name="poll")
app.add_typer(evals_app, name="evals")


@app.callback()
def main() -> None:
    """IncidentPilot command-line interface."""


@app.command()
def version() -> None:
    """Show the installed IncidentPilot version."""

    typer.echo(f"IncidentPilot {__version__}")


@app.command("web")
def web(
    host: str | None = typer.Option(
        None, "--host", help="Bind host; defaults to configured localhost."
    ),
    port: int | None = typer.Option(
        None, "--port", min=1, max=65535
    ),
) -> None:
    """Start the IncidentPilot dashboard."""

    settings = load_settings()
    uvicorn.run(
        "agent.app.main:app",
        host=host or settings.app.host,
        port=port or settings.app.port,
    )


@db_app.command("init")
def db_init() -> None:
    """Create or upgrade the configured database schema."""

    settings = load_settings()
    engine = initialise_database(settings)
    typer.echo(
        "Database initialized/upgraded: "
        f"{engine.url.render_as_string(hide_password=True)}"
    )
    engine.dispose()


@services_app.command("list")
def services_list() -> None:
    """List configured monitored services."""

    settings = load_settings()
    if not settings.services:
        typer.echo("No services configured.")
        return
    for service in settings.services:
        runtime = service.get("runtime") or settings.runtime.default
        enabled = service.get("enabled", True)
        typer.echo(
            f"{service.get('name', '<unnamed>')}\t{runtime}\t"
            f"{service.get('container_name', '<unset>')}\t"
            f"{'enabled' if enabled else 'disabled'}"
        )


def _configured_service(settings, service_name: str) -> dict:
    for service in settings.services:
        if service.get("name") == service_name:
            return service
    raise typer.BadParameter(f"Unknown configured service: {service_name}")


@services_app.command("status")
def service_status(
    service: str = typer.Option(..., "--service", help="Configured service name."),
) -> None:
    """Show structured runtime status for a configured service."""

    settings = load_settings()
    configured = _configured_service(settings, service)
    adapter = create_runtime_adapter(
        settings, service_runtime=configured.get("runtime")
    )
    status = adapter.get_container_status(configured["container_name"])
    typer.echo(json.dumps(asdict(status), indent=2))
    if status.error:
        raise typer.Exit(code=1)


@runtime_app.command("containers")
def runtime_containers(
    runtime: str = typer.Option(..., "--runtime", help="docker or podman"),
) -> None:
    """List containers through the selected read-only runtime adapter."""

    settings = load_settings()
    try:
        adapter = create_runtime_adapter(settings, service_runtime=runtime)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    result = adapter.list_containers()
    typer.echo(json.dumps(asdict(result), indent=2))
    if result.error:
        raise typer.Exit(code=1)


def _parse_incident_ref(value: str) -> int:
    normalized = value.upper()
    if normalized.startswith("INC-"):
        normalized = normalized[4:]
    try:
        incident_id = int(normalized)
    except ValueError as error:
        raise typer.BadParameter(
            "Incident must look like INC-001 or a numeric ID"
        ) from error
    if incident_id <= 0:
        raise typer.BadParameter("Incident ID must be positive")
    return incident_id


def _database_session() -> Iterator[tuple[Session, object]]:
    settings = load_settings()
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as session:
        yield session, settings
    engine.dispose()


@app.command("analyze")
def analyze(
    service: str = typer.Option(..., "--service", help="Configured service name."),
) -> None:
    """Run read-only incident analysis for a service."""

    for session, settings in _database_session():
        result = PlainPythonIncidentWorkflow(
            settings=settings, session=session
        ).analyze_service(service)
        typer.echo(
            f"{result.incident_ref}\t{result.severity}\t"
            f"{result.llm_status}\t{result.summary}"
        )


@incidents_app.command("list")
def incidents_list() -> None:
    """List recent incidents."""

    for session, _settings in _database_session():
        incidents = list_incidents(session)
        if not incidents:
            typer.echo("No incidents recorded.")
            return
        for incident in incidents:
            typer.echo(
                f"{format_incident_ref(incident.id)}\t"
                f"{incident.service.name}\t{incident.severity}\t"
                f"{incident.status}\t{incident.detected_at.isoformat()}"
            )


@incidents_app.command("show")
def incidents_show(incident_ref: str) -> None:
    """Show incident detail as JSON."""

    incident_id = _parse_incident_ref(incident_ref)
    for session, _settings in _database_session():
        incident = get_incident_detail(session, incident_id)
        if incident is None:
            raise typer.BadParameter(f"Unknown incident: {incident_ref}")
        payload = {
            "id": format_incident_ref(incident.id),
            "service": incident.service.name,
            "status": incident.status,
            "severity": incident.severity,
            "trigger_type": incident.trigger_type,
            "summary": incident.summary,
            "llm_status": incident.llm_status,
            "evidence": [
                {
                    "id": evidence.id,
                    "type": evidence.type,
                    "source": evidence.source,
                    "summary": evidence.summary,
                }
                for evidence in incident.evidence
            ],
            "hypotheses": [
                {
                    "rank": item.rank,
                    "cause": item.cause,
                    "confidence": item.confidence,
                    "evidence_refs": item.evidence_refs,
                }
                for item in incident.hypotheses
            ],
            "recommendations": [
                {
                    "action_key": item.action_key,
                    "title": item.title,
                    "execution_enabled_in_mvp": item.execution_enabled_in_mvp,
                    "executed": item.executed,
                }
                for item in incident.recommendations
            ],
        }
        typer.echo(json.dumps(payload, indent=2))


def _incident_report(session: Session, incident_ref: str):
    incident = get_incident_detail(
        session, _parse_incident_ref(incident_ref)
    )
    if incident is None or not incident.reports:
        raise typer.BadParameter(
            f"No report found for incident: {incident_ref}"
        )
    return incident, incident.reports[-1]


@reports_app.command("show")
def reports_show(incident_ref: str) -> None:
    """Print an incident Markdown report."""

    for session, _settings in _database_session():
        _incident, report = _incident_report(session, incident_ref)
        typer.echo(report.markdown)


@reports_app.command("export-json")
def reports_export_json(incident_ref: str) -> None:
    """Print a structured incident report as JSON."""

    for session, _settings in _database_session():
        _incident, report = _incident_report(session, incident_ref)
        typer.echo(json.dumps(report.json_payload, indent=2))


@reports_app.command("download-markdown")
def reports_download_markdown(
    incident_ref: str,
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Write an incident Markdown report to a local file."""

    for session, _settings in _database_session():
        incident, report = _incident_report(session, incident_ref)
        destination = output or Path(
            f"{format_incident_ref(incident.id)}.md"
        )
        destination.write_text(report.markdown, encoding="utf-8")
        typer.echo(str(destination))


@scenarios_app.command("list")
def scenarios_list() -> None:
    """List allowlisted demo failure scenarios."""

    runner = ScenarioRunner(settings=load_settings())
    for scenario in runner.list_scenarios():
        typer.echo(f"{scenario.id}\t{scenario.description}")


@scenarios_app.command("trigger")
def scenarios_trigger(scenario_id: str) -> None:
    """Trigger one fixed demo failure scenario."""

    runner = ScenarioRunner(settings=load_settings())
    try:
        result = runner.trigger(scenario_id)
    except ScenarioRunnerError as error:
        typer.echo(f"Scenario failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"{result.scenario_id} triggered safely for the demo stack."
    )


@scenarios_app.command("reset")
def scenarios_reset() -> None:
    """Restore the demo stack to a healthy baseline."""

    runner = ScenarioRunner(settings=load_settings())
    try:
        result = runner.reset()
    except ScenarioRunnerError as error:
        typer.echo(f"Reset failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"{result.scenario_id} completed for the demo stack."
    )


@health_app.command("check")
def health_check(
    service: str = typer.Option(..., "--service", help="Configured service name."),
) -> None:
    """Run one health check for a configured service."""

    for session, settings in _database_session():
        result = HealthPoller(
            settings=settings, session=session
        ).check_service(service)
        check = result.health_check
        typer.echo(
            f"{service}\t{check.status}\t"
            f"{check.http_status_code or '-'}\t"
            f"{check.latency_ms if check.latency_ms is not None else '-'}ms"
        )
        if result.incident_id is not None:
            typer.echo(
                f"incident={format_incident_ref(result.incident_id)}"
            )
        if check.status not in {"healthy", "not_configured"}:
            raise typer.Exit(code=1)


@health_app.command("list")
def health_list(
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
) -> None:
    """List recent persisted health checks."""

    for session, settings in _database_session():
        poller = HealthPoller(settings=settings, session=session)
        checks = poller.list_health_checks(limit=limit)
        if not checks:
            typer.echo("No health checks recorded.")
            return
        for check in checks:
            typer.echo(
                f"{check.id}\tservice_id={check.service_id}\t"
                f"{check.status}\t{check.http_status_code or '-'}\t"
                f"{check.checked_at.isoformat()}"
            )


@poll_app.command("run")
def poll_run(
    once: bool = typer.Option(
        False, "--once", help="Poll configured services once and exit."
    ),
) -> None:
    """Run health polling until interrupted, or once with --once."""

    for session, settings in _database_session():
        poller = HealthPoller(settings=settings, session=session)
        if once:
            results = poller.run_once()
            typer.echo(f"Completed {len(results)} health checks.")
            return
        typer.echo("Health poller running. Press Ctrl+C to stop.")
        try:
            poller.run_forever()
        except KeyboardInterrupt:
            typer.echo("Health poller stopped.")


@incidents_app.command("resolve")
def incidents_resolve(incident_ref: str) -> None:
    """Manually mark an active incident resolved."""

    incident_id = _parse_incident_ref(incident_ref)
    for session, _settings in _database_session():
        try:
            incident = mark_incident_resolved(session, incident_id)
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error
        typer.echo(
            f"{format_incident_ref(incident.id)} resolved."
        )


@incidents_app.command("close")
def incidents_close(incident_ref: str) -> None:
    """Close a resolved incident."""

    incident_id = _parse_incident_ref(incident_ref)
    for session, _settings in _database_session():
        try:
            incident = close_incident(session, incident_id)
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error
        typer.echo(f"{format_incident_ref(incident.id)} closed.")


@evals_app.command("run")
def evals_run(
    scenario: str | None = typer.Option(
        None, "--scenario", help="FS-001 or FS-002; omit to run all."
    ),
) -> None:
    """Run deterministic golden-file incident evaluations."""

    for session, settings in _database_session():
        try:
            results = EvalRunner(
                settings=settings, session=session
            ).run(scenario)
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error
    payload: object = (
        results[0].model_dump(mode="json")
        if scenario
        else [result.model_dump(mode="json") for result in results]
    )
    typer.echo(json.dumps(payload, indent=2))
    if not all(result.passed for result in results):
        raise typer.Exit(code=1)


def _eval_run_payload(run) -> dict:
    return {
        "id": run.id,
        "scenario_id": run.scenario_id,
        "passed": run.passed,
        "model": run.model,
        "prompt_versions": run.prompt_versions,
        "output_path": run.output_path,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat(),
        "checks": [
            {
                "name": check.name,
                "passed": check.passed,
                "expected": check.expected,
                "actual": check.actual,
            }
            for check in run.checks
        ],
    }


@evals_app.command("list")
def evals_list(
    limit: int = typer.Option(20, "--limit", min=1, max=1000),
) -> None:
    """List persisted deterministic evaluation runs."""

    for session, _settings in _database_session():
        runs = list_eval_runs(session, limit=limit)
        if not runs:
            typer.echo("No evaluation runs recorded.")
            return
        for run in runs:
            typer.echo(
                f"{run.id}\t{run.scenario_id}\t"
                f"{'passed' if run.passed else 'failed'}\t"
                f"{run.completed_at.isoformat()}"
            )


@evals_app.command("export")
def evals_export(
    output: Path = typer.Option(..., "--output", "-o"),
    limit: int = typer.Option(1000, "--limit", min=1, max=10000),
) -> None:
    """Export persisted evaluation history as JSON."""

    for session, _settings in _database_session():
        payload = [
            _eval_run_payload(run)
            for run in list_eval_runs(session, limit=limit)
        ]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        typer.echo(str(output))


@evals_app.command("prune")
def evals_prune(
    older_than_days: int = typer.Option(
        ..., "--older-than-days", min=1
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Confirm permanent deletion."
    ),
) -> None:
    """Delete persisted eval runs older than a deliberate cutoff."""

    if not yes:
        raise typer.BadParameter("Pass --yes to confirm deletion")
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=older_than_days
    )
    for session, _settings in _database_session():
        deleted = delete_eval_runs_before(session, cutoff=cutoff)
        typer.echo(f"Deleted {deleted} evaluation runs.")


if __name__ == "__main__":
    app()
