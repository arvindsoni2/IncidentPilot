"""Golden-file evaluations for deterministic incident key facts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.adapters.metrics import MetricsSnapshot
from agent.adapters.runtime import ContainerStatus, LogEvidence
from agent.app.config import Settings
from agent.app.schemas import IncidentAnalysisJSON
from agent.app.services.evidence_collector import (
    CollectedEvidence,
    HealthEndpointEvidence,
    IncidentContext,
)
from agent.app.services.persistence import save_eval_run
from agent.app.services.report_generator import SREReportGenerator
from agent.app.services.rule_diagnosis import RuleDiagnosisEngine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GOLDEN_DIRECTORY = PROJECT_ROOT / "tests" / "golden-files"
SUPPORTED_SCENARIOS = ("FS-001", "FS-002")
PROMPT_VERSIONS = {
    "incident_diagnosis": "v1",
    "hypothesis_ranking": "v1",
    "incident_report": "v1",
}
REQUIRED_REPORT_SECTIONS = (
    "Summary",
    "Timeline",
    "Evidence",
    "Ranked hypotheses",
    "Recommendation",
    "Verification plan",
    "Follow-up actions",
)


class EvalCheck(BaseModel):
    name: str
    passed: bool
    expected: Any | None = None
    actual: Any | None = None


class EvalResult(BaseModel):
    scenario_id: str
    passed: bool
    checks: list[EvalCheck]
    model: str
    prompt_versions: dict[str, str]


class EvalRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        golden_directory: Path = DEFAULT_GOLDEN_DIRECTORY,
        output_directory: Path | None = None,
        session: Session | None = None,
    ) -> None:
        self.settings = settings
        self.golden_directory = golden_directory
        self.output_directory = output_directory or Path(settings.evals.output_directory)
        self.session = session
        self.rules = RuleDiagnosisEngine()
        self.reports = SREReportGenerator()

    def run(self, scenario_id: str | None = None) -> list[EvalResult]:
        scenarios = (
            [self._normalise_scenario(scenario_id)] if scenario_id else list(SUPPORTED_SCENARIOS)
        )
        results = [self._evaluate(item) for item in scenarios]
        for result in results:
            output_path = self._persist(result)
            if self.session is not None:
                save_eval_run(
                    self.session,
                    scenario_id=result.scenario_id,
                    passed=result.passed,
                    model=result.model,
                    prompt_versions=result.prompt_versions,
                    checks=[check.model_dump(mode="json") for check in result.checks],
                    output_path=str(output_path),
                )
        return results

    def _evaluate(self, scenario_id: str) -> EvalResult:
        expected = self._load_expected(scenario_id)
        analysis = self.rules.diagnose(self._fixture_context(scenario_id), llm_available=False)
        report = self.reports.generate(analysis)
        checks = self._checks(
            analysis=analysis,
            report=report,
            expected=expected,
        )
        return EvalResult(
            scenario_id=scenario_id,
            passed=all(check.passed for check in checks),
            checks=checks,
            model=self.settings.llm.model,
            prompt_versions=dict(PROMPT_VERSIONS),
        )

    @staticmethod
    def _checks(
        *,
        analysis: IncidentAnalysisJSON,
        report: str,
        expected: dict[str, Any],
    ) -> list[EvalCheck]:
        payload = analysis.model_dump(mode="json")
        try:
            IncidentAnalysisJSON.model_validate(payload)
            schema_valid = True
        except ValueError:
            schema_valid = False
        sections_present = all(f"## {section}" in report for section in REQUIRED_REPORT_SECTIONS)
        no_action_executed = all(
            not recommendation.executed and not recommendation.execution_enabled_in_mvp
            for recommendation in analysis.recommendations
        )
        return [
            EvalCheck(name="schema_valid", passed=schema_valid),
            EvalCheck(
                name="service_correct",
                passed=analysis.service == expected["service"],
                expected=expected["service"],
                actual=analysis.service,
            ),
            EvalCheck(
                name="severity_present",
                passed=analysis.severity in {"low", "medium", "high", "critical"},
                actual=analysis.severity,
            ),
            EvalCheck(
                name="evidence_present",
                passed=bool(analysis.evidence),
                actual=len(analysis.evidence),
            ),
            EvalCheck(
                name="rank1_cause_correct",
                passed=analysis.hypotheses[0].cause == expected["rank1_cause"],
                expected=expected["rank1_cause"],
                actual=analysis.hypotheses[0].cause,
            ),
            EvalCheck(
                name="recommendation_present",
                passed=bool(analysis.recommendations),
                actual=len(analysis.recommendations),
            ),
            EvalCheck(
                name="recommendation_action_correct",
                passed=analysis.recommendations[0].action_key == expected["recommendation_action"],
                expected=expected["recommendation_action"],
                actual=analysis.recommendations[0].action_key,
            ),
            EvalCheck(
                name="report_sections_present",
                passed=sections_present,
                expected=list(REQUIRED_REPORT_SECTIONS),
            ),
            EvalCheck(
                name="no_action_executed",
                passed=no_action_executed,
                expected=True,
                actual=no_action_executed,
            ),
            EvalCheck(
                name="llm_status_recorded",
                passed=analysis.llm_status in {"not_requested", "available", "unavailable"},
                actual=analysis.llm_status,
            ),
        ]

    def _load_expected(self, scenario_id: str) -> dict[str, Any]:
        path = self.golden_directory / f"{scenario_id.lower()}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _persist(self, result: EvalResult) -> Path:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.output_directory / (f"{result.scenario_id.lower()}-{timestamp}.json")
        path.write_text(
            result.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _normalise_scenario(scenario_id: str) -> str:
        normalized = scenario_id.upper()
        if normalized not in SUPPORTED_SCENARIOS:
            raise ValueError(f"Unsupported eval scenario: {scenario_id}")
        return normalized

    @staticmethod
    def _fixture_context(scenario_id: str) -> IncidentContext:
        fs001 = scenario_id == "FS-001"
        evidence = [
            CollectedEvidence(
                id=1,
                type="container_status",
                source="docker",
                summary=(
                    "backend container is exited" if fs001 else "backend container is running"
                ),
            ),
            CollectedEvidence(
                id=2,
                type="runtime_logs",
                source="docker",
                summary="bounded runtime logs collected",
            ),
            CollectedEvidence(
                id=3,
                type="health_endpoint",
                source="http://backend/health",
                summary="health endpoint returned HTTP 503",
            ),
            CollectedEvidence(
                id=4,
                type="dependency_status",
                source="docker",
                summary=(
                    "postgres container is running" if fs001 else "postgres container is exited"
                ),
            ),
            CollectedEvidence(
                id=5,
                type="metrics_snapshot",
                source="prometheus",
                summary="Prometheus unavailable in rules-only eval fixture",
            ),
        ]
        return IncidentContext(
            incident_id=1,
            service_id=1,
            service_name="backend",
            runtime="docker",
            criticality="high",
            target_status=ContainerStatus(
                container_name="incidentpilot-demo-backend",
                state="exited" if fs001 else "running",
                running=not fs001,
            ),
            logs=LogEvidence(
                container_name="incidentpilot-demo-backend",
                logs="bounded fixture logs",
                since_seconds=900,
                max_bytes=50_000,
            ),
            health=HealthEndpointEvidence(
                url="http://backend/health",
                available=True,
                healthy=False,
                status_code=503,
                latency_ms=1.0,
            ),
            dependencies={
                "postgres": ContainerStatus(
                    container_name="incidentpilot-demo-postgres",
                    state="running" if fs001 else "exited",
                    running=fs001,
                )
            },
            metrics=MetricsSnapshot(available=False, error="fixture degraded mode"),
            evidence_refs=[item.id for item in evidence],
            evidence_items=evidence,
        )
