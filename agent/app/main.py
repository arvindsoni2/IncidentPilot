"""IncidentPilot FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent import __version__
from agent.app.config import Settings, load_settings
from agent.app.web.routes import router

AGENT_DIRECTORY = Path(__file__).resolve().parents[1]
TEMPLATE_DIRECTORY = AGENT_DIRECTORY / "templates"
STATIC_DIRECTORY = AGENT_DIRECTORY / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(
        title="IncidentPilot",
        version=__version__,
        description="Read-only incident triage for containerised services.",
    )
    application.state.settings = settings or load_settings()
    application.state.database_engine = None
    application.state.session_factory = None
    application.state.templates = Jinja2Templates(
        directory=str(TEMPLATE_DIRECTORY)
    )
    application.state.workflow_factory = None
    application.state.scenario_runner_factory = None
    application.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIRECTORY)),
        name="static",
    )
    application.include_router(router)
    return application


app = create_app()
