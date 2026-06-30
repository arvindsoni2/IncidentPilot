"""Plain Python end-to-end incident workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agent.adapters.llm import create_llm_provider
from agent.app.config import Settings
from agent.app.services import (
    EvidenceCollector,
    LLMDiagnosisService,
    RuleDiagnosisEngine,
    SREReportGenerator,
    add_hypotheses,
    add_recommendations,
    create_agent_run,
    create_incident,
    finish_agent_run,
    resolve_configured_service,
    save_report,
)
from agent.workflows.base import (
    IncidentAnalysisResult,
    IncidentWorkflow,
    format_incident_ref,
)

WORKFLOW_VERSION = "plain-python-v1"
PROMPT_VERSIONS = {
    "incident_diagnosis": "v1",
    "hypothesis_ranking": "v1",
    "incident_report": "v1",
}


class PlainPythonIncidentWorkflow(IncidentWorkflow):
    def __init__(
        self,
        *,
        settings: Settings,
        session: Session,
        evidence_collector: EvidenceCollector | None = None,
        rules_engine: RuleDiagnosisEngine | None = None,
        llm_service: LLMDiagnosisService | None = None,
        report_generator: SREReportGenerator | None = None,
    ) -> None:
        self.settings = settings
        self.session = session
        self.evidence_collector = evidence_collector or EvidenceCollector(
            settings=settings, session=session
        )
        self.rules_engine = rules_engine or RuleDiagnosisEngine()
        self.llm_service = llm_service or LLMDiagnosisService(
            provider=create_llm_provider(settings)
        )
        self.report_generator = report_generator or SREReportGenerator()

    def analyze_service(
        self, service_name: str, trigger_type: str = "manual"
    ) -> IncidentAnalysisResult:
        service = resolve_configured_service(
            self.session, self.settings, service_name
        )
        incident = create_incident(
            self.session,
            service_id=service.id,
            trigger_type=trigger_type,
            status="new",
            severity="medium",
            summary=f"Analysis requested for {service.name}",
            llm_status="not_requested",
        )
        run = create_agent_run(
            self.session,
            incident_id=incident.id,
            workflow_version=WORKFLOW_VERSION,
            prompt_versions=PROMPT_VERSIONS,
            model=self.settings.llm.model,
        )
        try:
            incident.status = "analyzing"
            self.session.commit()

            context = self.evidence_collector.collect(
                service_name=service.name,
                incident_id=incident.id,
            )
            baseline = self.rules_engine.diagnose(context)
            analysis = self.llm_service.enhance(baseline)
            markdown = self.report_generator.generate(analysis)

            add_hypotheses(
                self.session,
                incident_id=incident.id,
                hypotheses=[
                    item.model_dump()
                    for item in analysis.hypotheses
                ],
            )
            add_recommendations(
                self.session,
                incident_id=incident.id,
                recommendations=[
                    item.model_dump()
                    for item in analysis.recommendations
                ],
            )
            save_report(
                self.session,
                incident_id=incident.id,
                markdown=markdown,
                json_payload=analysis.model_dump(mode="json"),
            )

            incident.status = "diagnosed"
            incident.severity = analysis.severity
            incident.summary = analysis.summary
            incident.llm_status = analysis.llm_status
            incident.diagnosed_at = datetime.now(timezone.utc)
            self.session.commit()
            finish_agent_run(self.session, run, status="completed")

            return IncidentAnalysisResult(
                incident_id=incident.id,
                incident_ref=format_incident_ref(incident.id),
                summary=analysis.summary,
                severity=analysis.severity,
                llm_status=analysis.llm_status,
            )
        except Exception as error:
            incident.status = "failed"
            incident.summary = f"Analysis failed: {error}"
            self.session.commit()
            finish_agent_run(
                self.session, run, status="failed", error=str(error)
            )
            raise
