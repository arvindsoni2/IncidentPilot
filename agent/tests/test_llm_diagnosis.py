from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.adapters.llm import LLMProvider, LLMProviderError
from agent.app.schemas import (
    EvidenceItem,
    HypothesisItem,
    IncidentAnalysisJSON,
    RecommendationItem,
)
from agent.app.services import LLMDiagnosisService, SREReportGenerator


class FakeProvider(LLMProvider):
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: LLMProviderError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.prompt = ""

    def generate_json(self, prompt: str) -> dict[str, Any]:
        self.prompt = prompt
        if self.error:
            raise self.error
        return self.response or {}


def baseline() -> IncidentAnalysisJSON:
    return IncidentAnalysisJSON(
        incident_id=1,
        service="backend",
        severity="high",
        summary="Backend stopped",
        current_status="container_stopped",
        evidence=[
            EvidenceItem(
                ref="evidence:1",
                type="container_status",
                source="docker",
                summary="backend is exited",
            )
        ],
        hypotheses=[
            HypothesisItem(
                rank=1,
                cause="backend_container_stopped",
                confidence=0.99,
                evidence_refs=["evidence:1"],
                reasoning="Runtime reports exited.",
            )
        ],
        recommendations=[
            RecommendationItem(
                action_key="restart_container",
                title="Restore backend manually",
                rationale="A human should restore it.",
            )
        ],
    )


def valid_response() -> dict[str, Any]:
    return {
        "summary": "Docker evidence shows the backend is stopped.",
        "hypotheses": [
            {
                "rank": 1,
                "cause": "backend_container_stopped",
                "confidence": 0.99,
                "evidence_refs": ["evidence:1"],
                "reasoning": "The runtime reports an exited container.",
            }
        ],
        "recommendations": [
            {
                "action_key": "restart_container",
                "title": "Restore backend manually",
                "rationale": "A human should inspect and restore it.",
                "requires_approval": True,
                "allowed_by_policy": False,
                "execution_enabled_in_mvp": False,
                "executed": False,
            }
        ],
        "verification_plan": [
            "Verify runtime status after manual intervention."
        ],
        "follow_up_actions": ["Record the confirmed cause."],
    }


def test_llm_success_is_validated_and_combined() -> None:
    provider = FakeProvider(response=valid_response())

    result = LLMDiagnosisService(provider=provider).enhance(baseline())

    assert result.llm_status == "available"
    assert result.rules_only is False
    assert result.severity == "high"
    assert result.hypotheses[0].evidence_refs == ["evidence:1"]
    assert result.recommendations[0].executed is False
    assert "terminal" in provider.prompt
    assert '"service": "backend"' in provider.prompt


def test_provider_timeout_falls_back_to_rules() -> None:
    provider = FakeProvider(
        error=LLMProviderError(
            code="timeout", message="timed out", attempts=2
        )
    )

    result = LLMDiagnosisService(provider=provider).enhance(baseline())

    assert result.llm_status == "unavailable"
    assert result.rules_only is True
    assert result.hypotheses[0].cause == "backend_container_stopped"
    assert any("timed out" in gap for gap in result.evidence_gaps)


def test_invalid_or_ungrounded_output_falls_back_safely() -> None:
    invalid = valid_response()
    invalid["hypotheses"][0]["evidence_refs"] = ["evidence:invented"]

    result = LLMDiagnosisService(
        provider=FakeProvider(response=invalid)
    ).enhance(baseline())

    assert result.llm_status == "unavailable"
    assert result.hypotheses[0].evidence_refs == ["evidence:1"]
    assert result.recommendations[0].executed is False


def test_llm_cannot_relax_deterministic_action_policy() -> None:
    unsafe = valid_response()
    unsafe["recommendations"][0]["requires_approval"] = False
    unsafe["recommendations"][0]["allowed_by_policy"] = True

    result = LLMDiagnosisService(
        provider=FakeProvider(response=unsafe)
    ).enhance(baseline())

    assert result.llm_status == "unavailable"
    assert result.recommendations[0].requires_approval is True
    assert result.recommendations[0].allowed_by_policy is False


def test_report_contains_required_sections_and_safety_statement() -> None:
    analysis = LLMDiagnosisService(
        provider=FakeProvider(response=valid_response())
    ).enhance(baseline())

    report = SREReportGenerator().generate(analysis)

    for section in (
        "Summary",
        "Service affected",
        "Severity",
        "Current status",
        "Timeline",
        "Evidence",
        "Ranked hypotheses",
        "Recommendation",
        "Verification plan",
        "Follow-up actions",
    ):
        assert f"## {section}" in report
    assert "No remediation action was executed" in report
    assert "executed: **no**" in report


def test_report_correlates_timeline_and_evidence_timestamps() -> None:
    analysis = LLMDiagnosisService(
        provider=FakeProvider(response=valid_response())
    ).enhance(baseline())
    observed_at = datetime(2026, 6, 30, 10, 0, tzinfo=timezone.utc)
    collected_at = datetime(2026, 6, 30, 10, 0, 1, tzinfo=timezone.utc)

    report = SREReportGenerator().generate(
        analysis,
        timeline=[("Detected", observed_at)],
        evidence_timestamps={
            analysis.evidence[0].ref: collected_at,
        },
    )

    assert "**Detected:** 2026-06-30T10:00:00+00:00" in report
    assert "collected 2026-06-30T10:00:01+00:00" in report
