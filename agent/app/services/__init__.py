"""Application service layer."""

from agent.app.services.eval_runner import (
    EvalCheck,
    EvalResult,
    EvalRunner,
)
from agent.app.services.evidence_collector import (
    CollectedEvidence,
    EvidenceCollector,
    HealthEndpointEvidence,
    IncidentContext,
)
from agent.app.services.health_poller import HealthPoller, PollResult
from agent.app.services.incident_lifecycle import (
    auto_resolve_after_health_successes,
    close_incident,
    mark_incident_resolved,
)
from agent.app.services.llm_diagnosis import LLMDiagnosisService
from agent.app.services.persistence import (
    add_evidence,
    add_hypotheses,
    add_recommendations,
    create_agent_run,
    create_incident,
    create_service,
    delete_eval_runs_before,
    finish_agent_run,
    get_incident_detail,
    get_service,
    get_service_by_name,
    list_eval_runs,
    list_incidents,
    list_services,
    resolve_configured_service,
    save_eval_run,
    save_report,
)
from agent.app.services.report_generator import SREReportGenerator
from agent.app.services.rule_diagnosis import RuleDiagnosisEngine
from agent.app.services.scenario_runner import (
    ScenarioDefinition,
    ScenarioResult,
    ScenarioRunner,
    ScenarioRunnerError,
)
from agent.app.services.what_changed import (
    WhatChangedAdvisoryService,
    compare_with_latest,
    comparison_failed_result,
    latest_healthy_snapshot,
    render_what_changed_markdown,
    save_healthy_snapshot,
    snapshot_eligible,
    snapshot_payload,
)

__all__ = [
    "CollectedEvidence",
    "EvidenceCollector",
    "HealthEndpointEvidence",
    "IncidentContext",
    "LLMDiagnosisService",
    "HealthPoller",
    "PollResult",
    "auto_resolve_after_health_successes",
    "close_incident",
    "mark_incident_resolved",
    "RuleDiagnosisEngine",
    "SREReportGenerator",
    "ScenarioDefinition",
    "ScenarioResult",
    "ScenarioRunner",
    "ScenarioRunnerError",
    "EvalCheck",
    "EvalResult",
    "EvalRunner",
    "add_evidence",
    "add_hypotheses",
    "add_recommendations",
    "create_incident",
    "create_agent_run",
    "create_service",
    "delete_eval_runs_before",
    "get_incident_detail",
    "get_service",
    "get_service_by_name",
    "finish_agent_run",
    "list_incidents",
    "list_eval_runs",
    "list_services",
    "save_report",
    "save_eval_run",
    "resolve_configured_service",
    "compare_with_latest",
    "comparison_failed_result",
    "latest_healthy_snapshot",
    "render_what_changed_markdown",
    "save_healthy_snapshot",
    "snapshot_eligible",
    "snapshot_payload",
    "WhatChangedAdvisoryService",
]
