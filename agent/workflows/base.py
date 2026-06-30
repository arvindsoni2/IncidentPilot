"""Incident workflow interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class IncidentAnalysisResult:
    incident_id: int
    incident_ref: str
    summary: str
    severity: str
    llm_status: str


def format_incident_ref(incident_id: int) -> str:
    return f"INC-{incident_id:03d}"


class IncidentWorkflow(ABC):
    @abstractmethod
    def analyze_service(
        self, service_name: str, trigger_type: str = "manual"
    ) -> IncidentAnalysisResult:
        """Analyze a service without executing remediation."""
