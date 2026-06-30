"""Deterministic diagnosis rules grounded in collected evidence."""

from __future__ import annotations

from agent.app.schemas import (
    EvidenceItem,
    HypothesisItem,
    IncidentAnalysisJSON,
    RecommendationItem,
)
from agent.app.services.evidence_collector import IncidentContext


class RuleDiagnosisEngine:
    def diagnose(
        self,
        context: IncidentContext,
        *,
        llm_available: bool = True,
    ) -> IncidentAnalysisJSON:
        evidence = [
            EvidenceItem(
                ref=item.ref,
                type=item.type,
                source=item.source,
                summary=item.summary,
            )
            for item in context.evidence_items
        ]
        gaps = self._evidence_gaps(context, llm_available=llm_available)
        target_ref = self._refs(context, "container_status")
        health_ref = self._refs(context, "health_endpoint")
        dependency_refs = self._refs(context, "dependency_status")
        log_refs = self._refs(context, "runtime_logs")
        deployment_refs = self._refs(context, "deployment_events")

        unhealthy_dependencies = [
            name
            for name, status in context.dependencies.items()
            if status.error
            or not status.running
            or status.health in {"unhealthy", "starting"}
        ]
        target_unavailable = (
            context.target_status.error is not None
            or not context.target_status.running
        )
        health_failed = context.health is not None and not context.health.healthy

        if target_unavailable:
            severity = self._target_outage_severity(context)
            summary = f"{context.service_name} container is not running"
            hypotheses = [
                HypothesisItem(
                    rank=1,
                    cause=f"{context.service_name}_container_stopped",
                    confidence=0.99,
                    evidence_refs=target_ref,
                    reasoning=(
                        "The runtime reports that the target container is not "
                        "running, which directly explains service unavailability."
                    ),
                )
            ]
            recommendations = [
                RecommendationItem(
                    action_key="restart_container",
                    title=f"Restore {context.service_name} manually",
                    rationale=(
                        "A human should verify the failure context and restore, "
                        "start, or restart the target service."
                    ),
                    requires_approval=True,
                    allowed_by_policy=False,
                )
            ]
            current_status = "container_stopped"
        elif health_failed and unhealthy_dependencies:
            severity = self._dependency_outage_severity(
                context, unhealthy_dependencies
            )
            dependency_names = ", ".join(unhealthy_dependencies)
            summary = (
                f"{context.service_name} health is failing because dependency "
                f"{dependency_names} is unavailable"
            )
            hypotheses = [
                HypothesisItem(
                    rank=1,
                    cause="dependency_unavailable",
                    confidence=0.95,
                    evidence_refs=self._nonempty_refs(
                        dependency_refs + health_ref, target_ref
                    ),
                    reasoning=(
                        "The target is running but its health endpoint fails "
                        "while a configured dependency is stopped or unhealthy."
                    ),
                )
            ]
            recommendations = [
                RecommendationItem(
                    action_key="restore_dependency_service",
                    title=f"Restore {dependency_names} first",
                    rationale=(
                        "A human should restore the failed dependency before "
                        f"reassessing {context.service_name}."
                    ),
                    requires_approval=True,
                    allowed_by_policy=False,
                )
            ]
            current_status = "dependency_unavailable"
        elif health_failed:
            severity = (
                "high" if context.criticality in {"high", "critical"} else "medium"
            )
            summary = (
                f"{context.service_name} is running but its health endpoint fails"
            )
            hypotheses = [
                HypothesisItem(
                    rank=1,
                    cause="application_level_failure",
                    confidence=0.75,
                    evidence_refs=self._nonempty_refs(
                        health_ref + target_ref + log_refs + deployment_refs,
                        target_ref,
                    ),
                    reasoning=(
                        "The container is running and configured dependencies "
                        "are healthy, so logs, configuration, and recent "
                        "deployments are the next likely evidence sources."
                    ),
                )
            ]
            recommendations = [
                RecommendationItem(
                    action_key="inspect_application_evidence",
                    title="Inspect logs, configuration, and recent deployments",
                    rationale=(
                        "Review the collected evidence and correct the "
                        "application-level issue manually."
                    ),
                    requires_approval=False,
                    allowed_by_policy=True,
                )
            ]
            current_status = "health_check_failed"
        else:
            severity = "low"
            summary = (
                f"No active failure was detected for {context.service_name}"
            )
            all_refs = [item.ref for item in context.evidence_items]
            hypotheses = [
                HypothesisItem(
                    rank=1,
                    cause="no_failure_detected",
                    confidence=0.9,
                    evidence_refs=self._nonempty_refs(all_refs, ["evidence:none"]),
                    reasoning=(
                        "The target is running and no failing health or "
                        "dependency evidence is present."
                    ),
                )
            ]
            recommendations = [
                RecommendationItem(
                    action_key="continue_monitoring",
                    title="Continue monitoring",
                    rationale="No remediation is indicated by current evidence.",
                    requires_approval=False,
                    allowed_by_policy=True,
                )
            ]
            current_status = "healthy"

        return IncidentAnalysisJSON(
            incident_id=context.incident_id,
            service=context.service_name,
            severity=severity,
            summary=summary,
            current_status=current_status,
            evidence=evidence,
            evidence_gaps=gaps,
            hypotheses=hypotheses,
            recommendations=recommendations,
            llm_status="not_requested" if llm_available else "unavailable",
            rules_only=True,
        )

    @staticmethod
    def _target_outage_severity(context: IncidentContext) -> str:
        if (
            context.criticality in {"high", "critical"}
            or context.service_name == "backend"
        ):
            return "high"
        return "medium"

    @staticmethod
    def _dependency_outage_severity(
        context: IncidentContext, unavailable: list[str]
    ) -> str:
        if context.criticality == "critical" and len(unavailable) > 1:
            return "critical"
        if context.criticality in {"high", "critical"}:
            return "high"
        return "medium"

    @staticmethod
    def _refs(context: IncidentContext, evidence_type: str) -> list[str]:
        return [
            item.ref
            for item in context.evidence_items
            if item.type == evidence_type
        ]

    @staticmethod
    def _nonempty_refs(
        preferred: list[str], fallback: list[str]
    ) -> list[str]:
        return list(dict.fromkeys(preferred)) or fallback

    @staticmethod
    def _evidence_gaps(
        context: IncidentContext, *, llm_available: bool
    ) -> list[str]:
        gaps: list[str] = []
        if context.metrics is not None and not context.metrics.available:
            gaps.append(
                f"Prometheus metrics unavailable: "
                f"{context.metrics.error or 'unknown error'}"
            )
        if context.logs.error is not None:
            gaps.append(
                f"Runtime logs unavailable: {context.logs.error.message}"
            )
        if not llm_available:
            gaps.append(
                "LLM unavailable; diagnosis is deterministic rules-only"
            )
        return gaps
