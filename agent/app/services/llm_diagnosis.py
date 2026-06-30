"""Safe LLM enhancement with deterministic fallback."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from agent.adapters.llm import LLMProvider, LLMProviderError
from agent.app.schemas import IncidentAnalysisJSON, LLMAnalysisResponse

PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "incident_diagnosis.md"
)


class LLMDiagnosisService:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        prompt_path: Path = PROMPT_PATH,
    ) -> None:
        self.provider = provider
        self.prompt_path = prompt_path

    def enhance(
        self, baseline: IncidentAnalysisJSON
    ) -> IncidentAnalysisJSON:
        prompt = self._build_prompt(baseline)
        try:
            raw = self.provider.generate_json(prompt)
            response = LLMAnalysisResponse.model_validate(raw)
            self._validate_grounding(baseline, response)
        except (LLMProviderError, ValidationError, ValueError) as error:
            return self._fallback(baseline, str(error))

        return baseline.model_copy(
            update={
                "summary": response.summary,
                "hypotheses": response.hypotheses,
                "recommendations": response.recommendations,
                "verification_plan": response.verification_plan,
                "follow_up_actions": response.follow_up_actions,
                "llm_status": "available",
                "rules_only": False,
            },
            deep=True,
        )

    def _build_prompt(self, baseline: IncidentAnalysisJSON) -> str:
        instructions = self.prompt_path.read_text(encoding="utf-8")
        return (
            f"{instructions}\n\n"
            "## Structured incident context\n\n"
            f"```json\n{baseline.model_dump_json(indent=2)}\n```\n"
        )

    @staticmethod
    def _validate_grounding(
        baseline: IncidentAnalysisJSON,
        response: LLMAnalysisResponse,
    ) -> None:
        known_refs = {item.ref for item in baseline.evidence}
        for hypothesis in response.hypotheses:
            unknown = set(hypothesis.evidence_refs) - known_refs
            if unknown:
                raise ValueError(
                    f"LLM referenced unknown evidence: {sorted(unknown)}"
                )

        allowed_actions = {
            recommendation.action_key: recommendation
            for recommendation in baseline.recommendations
        }
        proposed_actions = {
            recommendation.action_key
            for recommendation in response.recommendations
        }
        if not proposed_actions <= allowed_actions.keys():
            raise ValueError(
                "LLM proposed an action outside the deterministic rule output"
            )
        for recommendation in response.recommendations:
            policy = allowed_actions[recommendation.action_key]
            if (
                recommendation.requires_approval
                != policy.requires_approval
                or recommendation.allowed_by_policy
                != policy.allowed_by_policy
            ):
                raise ValueError(
                    "LLM attempted to alter deterministic action policy"
                )

    @staticmethod
    def _fallback(
        baseline: IncidentAnalysisJSON, reason: str
    ) -> IncidentAnalysisJSON:
        gaps = list(baseline.evidence_gaps)
        gaps.append(f"LLM unavailable or invalid; rules-only fallback: {reason}")
        return baseline.model_copy(
            update={
                "evidence_gaps": gaps,
                "llm_status": "unavailable",
                "rules_only": True,
            },
            deep=True,
        )
