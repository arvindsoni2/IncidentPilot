"""FastAPI/Jinja/HTMX dashboard routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent import __version__
from agent.app.database import create_session_factory, initialise_database
from agent.app.models import HealthCheckResult, Service
from agent.app.services import (
    ScenarioRunner,
    ScenarioRunnerError,
    get_incident_detail,
    list_incidents,
    resolve_configured_service,
)
from agent.workflows import PlainPythonIncidentWorkflow, format_incident_ref

router = APIRouter()


def _ensure_database(request: Request) -> None:
    if request.app.state.session_factory is not None:
        return
    engine = initialise_database(request.app.state.settings)
    request.app.state.database_engine = engine
    request.app.state.session_factory = create_session_factory(engine)


async def database_session(request: Request) -> AsyncIterator[Session]:
    _ensure_database(request)
    with request.app.state.session_factory() as session:
        yield session


def _templates(request: Request):
    return request.app.state.templates


def _sync_services(request: Request, session: Session) -> list[Service]:
    settings = request.app.state.settings
    for configured in settings.services:
        if configured.get("enabled", True):
            resolve_configured_service(session, settings, configured["name"])
    return list(session.scalars(select(Service).order_by(Service.name)))


def _service_cards(request: Request, session: Session) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for service in _sync_services(request, session):
        latest = session.scalar(
            select(HealthCheckResult)
            .where(HealthCheckResult.service_id == service.id)
            .order_by(
                HealthCheckResult.checked_at.desc(),
                HealthCheckResult.id.desc(),
            )
            .limit(1)
        )
        cards.append(
            {
                "service": service,
                "status": latest.status if latest else "unknown",
                "last_check": latest.checked_at if latest else None,
            }
        )
    return cards


def _template_context(
    request: Request,
    *,
    page: str,
    **values: Any,
) -> dict[str, Any]:
    return {
        "request": request,
        "page": page,
        "version": __version__,
        "format_incident_ref": format_incident_ref,
        **values,
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "incidentpilot"}


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: Session = Depends(database_session),
) -> HTMLResponse:
    incidents = list_incidents(session)
    return _templates(request).TemplateResponse(
        request=request,
        name="dashboard.html",
        context=_template_context(
            request,
            page="dashboard",
            service_cards=_service_cards(request, session),
            active_incidents=[
                item for item in incidents if item.status in {"new", "analyzing", "diagnosed"}
            ],
            recent_incidents=incidents[:5],
        ),
    )


@router.get("/partials/service-cards", response_class=HTMLResponse)
async def service_cards_partial(
    request: Request,
    session: Session = Depends(database_session),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request=request,
        name="partials/service_cards.html",
        context=_template_context(
            request,
            page="dashboard",
            service_cards=_service_cards(request, session),
        ),
    )


@router.get("/partials/incidents", response_class=HTMLResponse)
async def incidents_partial(
    request: Request,
    session: Session = Depends(database_session),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request=request,
        name="partials/incident_table.html",
        context=_template_context(
            request,
            page="incidents",
            incidents=list_incidents(session),
        ),
    )


@router.get("/services", response_class=HTMLResponse)
async def services_page(
    request: Request,
    session: Session = Depends(database_session),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request=request,
        name="services.html",
        context=_template_context(
            request,
            page="services",
            service_cards=_service_cards(request, session),
        ),
    )


@router.get("/incidents", response_class=HTMLResponse)
async def incidents_page(
    request: Request,
    session: Session = Depends(database_session),
) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request=request,
        name="incidents.html",
        context=_template_context(
            request,
            page="incidents",
            incidents=list_incidents(session),
        ),
    )


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail_page(
    incident_id: int,
    request: Request,
    session: Session = Depends(database_session),
) -> HTMLResponse:
    incident = get_incident_detail(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _templates(request).TemplateResponse(
        request=request,
        name="incident_detail.html",
        context=_template_context(
            request,
            page="incidents",
            incident=incident,
        ),
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    session: Session = Depends(database_session),
) -> HTMLResponse:
    incidents = [incident for incident in list_incidents(session) if incident.reports]
    return _templates(request).TemplateResponse(
        request=request,
        name="reports.html",
        context=_template_context(
            request,
            page="reports",
            incidents=incidents,
        ),
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    settings = request.app.state.settings
    database_driver = settings.database.url.split(":", 1)[0]
    return _templates(request).TemplateResponse(
        request=request,
        name="settings.html",
        context=_template_context(
            request,
            page="settings",
            settings=settings,
            database_driver=database_driver,
        ),
    )


@router.post("/actions/analyze/{service_name}")
async def analyze_action(
    service_name: str,
    request: Request,
    session: Session = Depends(database_session),
) -> RedirectResponse:
    factory = request.app.state.workflow_factory
    workflow = (
        factory(request.app.state.settings, session)
        if factory
        else PlainPythonIncidentWorkflow(
            settings=request.app.state.settings,
            session=session,
        )
    )
    try:
        result = workflow.analyze_service(service_name, "web_manual")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return RedirectResponse(
        url=f"/incidents/{result.incident_id}",
        status_code=303,
    )


@router.post("/actions/scenarios/{scenario_id}")
async def scenario_action(
    scenario_id: str,
    request: Request,
) -> RedirectResponse:
    factory = request.app.state.scenario_runner_factory
    runner = (
        factory(request.app.state.settings)
        if factory
        else ScenarioRunner(settings=request.app.state.settings)
    )
    try:
        if scenario_id.lower() == "reset":
            runner.reset()
        else:
            runner.trigger(scenario_id)
    except ScenarioRunnerError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return RedirectResponse(url="/", status_code=303)


def _report_or_404(session: Session, incident_id: int):
    incident = get_incident_detail(session, incident_id)
    if incident is None or not incident.reports:
        raise HTTPException(status_code=404, detail="Report not found")
    return incident, incident.reports[-1]


@router.get("/reports/{incident_id}/export.json")
async def report_export_json(
    incident_id: int,
    session: Session = Depends(database_session),
) -> JSONResponse:
    _incident, report = _report_or_404(session, incident_id)
    return JSONResponse(report.json_payload)


@router.get("/reports/{incident_id}/download.md")
async def report_download_markdown(
    incident_id: int,
    session: Session = Depends(database_session),
) -> PlainTextResponse:
    incident, report = _report_or_404(session, incident_id)
    return PlainTextResponse(
        report.markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": (f'attachment; filename="{format_incident_ref(incident.id)}.md"')
        },
    )
