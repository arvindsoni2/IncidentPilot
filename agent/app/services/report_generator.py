"""Deterministic SRE-style Markdown report generation."""

from datetime import datetime

from agent.app.schemas import IncidentAnalysisJSON


class SREReportGenerator:
    def generate(
        self,
        analysis: IncidentAnalysisJSON,
        *,
        timeline: list[tuple[str, datetime]] | None = None,
        evidence_timestamps: dict[str, datetime] | None = None,
    ) -> str:
        evidence_timestamps = evidence_timestamps or {}
        evidence = "\n".join(
            (
                f"- `{item.ref}` **{item.type}** ({item.source})"
                f"{self._timestamp_suffix(evidence_timestamps.get(item.ref))}: "
                f"{item.summary}"
            )
            for item in analysis.evidence
        ) or "- No evidence was collected."
        timeline_lines = "\n".join(
            f"- **{label}:** {timestamp.isoformat()}"
            for label, timestamp in (timeline or [])
        ) or (
            "- Incident observed and evidence collected.\n"
            "- Deterministic rules diagnosis completed."
        )
        gaps = "\n".join(
            f"- {gap}" for gap in analysis.evidence_gaps
        ) or "- None recorded."
        hypotheses = "\n".join(
            (
                f"{item.rank}. **{item.cause}** "
                f"(confidence: {item.confidence:.0%}) — {item.reasoning} "
                f"[evidence: {', '.join(item.evidence_refs)}]"
            )
            for item in analysis.hypotheses
        )
        recommendations = "\n".join(
            (
                f"- **{item.title}** (`{item.action_key}`): {item.rationale} "
                f"Execution enabled: **no**; executed: **no**."
            )
            for item in analysis.recommendations
        )
        verification = "\n".join(
            f"- {step}" for step in analysis.verification_plan
        ) or "- Re-run health and dependency checks after manual intervention."
        follow_up = "\n".join(
            f"- {item}" for item in analysis.follow_up_actions
        ) or "- Review incident evidence and record the confirmed cause."

        return f"""# Incident Report: INC-{analysis.incident_id:03d}

## Summary

{analysis.summary}

## Service affected

{analysis.service}

## Severity

{analysis.severity}

## Current status

{analysis.current_status}

## Timeline

{timeline_lines}
- LLM status: `{analysis.llm_status}`.

## Evidence

{evidence}

### Evidence gaps

{gaps}

## Ranked hypotheses

{hypotheses}

## Recommendation

{recommendations}

## Verification plan

{verification}

## Follow-up actions

{follow_up}

> IncidentPilot MVP is read-only. No remediation action was executed.
"""

    @staticmethod
    def _timestamp_suffix(timestamp: datetime | None) -> str:
        return f", collected {timestamp.isoformat()}" if timestamp else ""
