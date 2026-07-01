"""Healthy snapshot persistence and deterministic incident comparison."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.adapters.llm import LLMProvider, LLMProviderError
from agent.app.models import HealthySnapshot, Service
from agent.app.schemas import (
    ChangeMateriality,
    ChangeSeverity,
    ComparisonFailureMetadata,
    ComparisonFailureReason,
    EvidenceValue,
    LlmAdvisoryMetadata,
    LlmAdvisoryStatus,
    LlmFailureReason,
    ServiceIdentity,
    WhatChangedAdvisoryResponse,
    WhatChangedCard,
    WhatChangedCounts,
    WhatChangedDiagnostics,
    WhatChangedResult,
    WhatChangedStatus,
    empty_counts,
)
from agent.app.services.evidence_collector import IncidentContext

SAFE_HTTP_FIELDS = [
    "method",
    "scheme",
    "host",
    "path_without_query",
    "status_code",
    "response_classification",
    "latency_ms",
    "content_type",
    "content_length",
    "retry_after",
]
UNSAFE_ADVISORY = re.compile(
    r"\b(?:sudo|docker\s+(?:restart|rm|exec)|kubectl|restart|rollback|"
    r"delete|execute|shell|fixed|remediated)\b",
    re.IGNORECASE,
)


def service_identity(service: Service, context: IncidentContext) -> ServiceIdentity:
    labels = context.metadata.labels if context.metadata else {}
    project = labels.get("com.docker.compose.project")
    compose_service = labels.get("com.docker.compose.service")
    if project and compose_service:
        return ServiceIdentity(
            strategy="compose_project_service",
            compose_project=project,
            service_name=compose_service,
            container_name=service.container_name,
        )
    return ServiceIdentity(strategy="container_name", container_name=service.container_name)


def _observed_at(context: IncidentContext) -> datetime:
    values = [item.collected_at for item in context.evidence_items if item.collected_at]
    return max(values) if values else datetime.now(timezone.utc)


def _ref(context: IncidentContext, evidence_type: str) -> str:
    item = next((item for item in context.evidence_items if item.type == evidence_type), None)
    return item.ref if item else f"incident:{context.incident_id}:{evidence_type}"


def snapshot_payload(context: IncidentContext) -> dict[str, Any]:
    health = context.health
    metadata = context.metadata
    parsed = urlsplit(health.url) if health else None
    return {
        "runtime": {
            "container_name": context.target_status.container_name,
            "container_status": context.target_status.state,
            "running": context.target_status.running,
            "health_status": context.target_status.health,
            "container_id": metadata.container_id if metadata else None,
            "image_id": metadata.image_id if metadata else None,
            "image_tag": metadata.image_name if metadata else None,
            "restart_count": metadata.restart_count if metadata else 0,
            "ports": metadata.ports if metadata else {},
            "runtime_adapter": context.runtime,
            "evidence_ref": _ref(context, "container_status"),
        },
        "http": {
            "method": "GET",
            "scheme": parsed.scheme if parsed else None,
            "host": parsed.hostname if parsed else None,
            "path_without_query": parsed.path if parsed else None,
            "status_code": health.status_code if health else None,
            "response_classification": (
                "healthy"
                if health and health.healthy
                else "failing"
                if health and health.available
                else "unavailable"
            ),
            "latency_ms": health.latency_ms if health else None,
            "evidence_ref": _ref(context, "health_endpoint"),
        },
        "dependencies": {
            name: {
                "dependency_name": name,
                "dependency_type": "container",
                "status": value.state,
                "reachable": value.error is None and value.running,
                "latency_ms": value.latency_ms,
                "failure_category": value.error.code if value.error else None,
                "evidence_ref": next(
                    (
                        item.ref
                        for item in context.evidence_items
                        if item.type == "dependency_status" and name in item.summary
                    ),
                    f"incident:{context.incident_id}:dependency:{name}",
                ),
            }
            for name, value in context.dependencies.items()
        },
        "observed_at": _observed_at(context).isoformat(),
        "collection_run": f"incident:{context.incident_id}",
    }


def snapshot_eligible(context: IncidentContext) -> tuple[bool, list[str], float]:
    missing: list[str] = []
    if context.target_status.error or not context.target_status.running:
        missing.append("runtime")
    if context.health is None or not context.health.healthy:
        missing.append("http")
    if any(value.error or not value.running for value in context.dependencies.values()):
        missing.append("dependencies")
    times = [item.collected_at for item in context.evidence_items if item.collected_at]
    window = (max(times) - min(times)).total_seconds() if len(times) > 1 else 0.0
    if window > 60:
        missing.append("collection_window")
    return not missing, missing, window


def save_healthy_snapshot(
    session: Session, service: Service, context: IncidentContext
) -> HealthySnapshot | None:
    eligible, _missing, _window = snapshot_eligible(context)
    if not eligible:
        return None
    record = HealthySnapshot(
        snapshot_id=f"hs_{uuid4().hex}",
        service_id=service.id,
        service_identity=service_identity(service, context).model_dump(mode="json"),
        evidence_payload=snapshot_payload(context),
        observed_at=_observed_at(context),
    )
    session.add(record)
    session.flush()
    ordered = list(
        session.scalars(
            select(HealthySnapshot)
            .where(HealthySnapshot.service_id == service.id)
            .order_by(
                HealthySnapshot.observed_at.desc(),
                HealthySnapshot.created_at.desc(),
                HealthySnapshot.snapshot_id.desc(),
            )
        )
    )
    for old in ordered[21:]:
        session.delete(old)
    session.commit()
    session.refresh(record)
    return record


def latest_healthy_snapshot(session: Session, service_id: int) -> HealthySnapshot | None:
    return session.scalar(
        select(HealthySnapshot)
        .where(HealthySnapshot.service_id == service_id)
        .order_by(
            HealthySnapshot.observed_at.desc(),
            HealthySnapshot.created_at.desc(),
            HealthySnapshot.snapshot_id.desc(),
        )
        .limit(1)
    )


def _card(
    *,
    context: IncidentContext,
    before: Any,
    after: Any,
    title: str,
    category: str,
    severity: ChangeSeverity,
    materiality: ChangeMateriality,
    rank: int,
    impact: str,
    why: str,
    rule_id: str,
    refs: list[str],
) -> WhatChangedCard:
    observed = _observed_at(context)
    return WhatChangedCard(
        id=f"{rule_id.lower()}_{context.incident_id}",
        title=title,
        category=category,
        severity=severity,
        materiality=materiality,
        rank=rank,
        before=EvidenceValue(label="Last known healthy", value=str(before)),
        after=EvidenceValue(label="Incident evidence", value=str(after), observed_at=observed),
        impact=impact,
        why_it_matters=why,
        evidence_refs=refs,
        timestamp=observed,
        rule_id=rule_id,
    )


def _latency_rule(before: float | None, after: float | None, prefix: str):
    if before is None or after is None:
        return None
    delta = after - before
    if delta >= 1000 and after >= before * 3:
        return (
            ChangeSeverity.HIGH,
            100 if prefix == "HTTP" else 120,
            f"WC_{prefix}_LATENCY_HIGH_INCREASE",
        )
    if delta >= 500 and after >= before * 2:
        return (
            ChangeSeverity.MEDIUM,
            110 if prefix == "HTTP" else 130,
            f"WC_{prefix}_LATENCY_MEDIUM_INCREASE",
        )
    return None


def compare_with_latest(
    session: Session, service: Service, context: IncidentContext, *, llm_configured: bool
) -> WhatChangedResult:
    identity = service_identity(service, context)
    llm = LlmAdvisoryMetadata(
        status=LlmAdvisoryStatus.NOT_ATTEMPTED
        if llm_configured
        else LlmAdvisoryStatus.NOT_CONFIGURED,
        configured=llm_configured,
        attempted=False,
    )
    baseline = latest_healthy_snapshot(session, service.id)
    diagnostics = WhatChangedDiagnostics(
        required_dependencies=list(context.dependencies),
        safe_metadata_fields=SAFE_HTTP_FIELDS,
    )
    if baseline is None:
        return WhatChangedResult(
            status=WhatChangedStatus.NO_BASELINE,
            service_identity=identity,
            incident_observed_at=_observed_at(context),
            rule_summary=(
                "What Changed? comparison skipped because no last known healthy "
                "snapshot exists yet."
            ),
            counts=empty_counts(),
            llm=llm,
            diagnostics=diagnostics,
        )
    current = snapshot_payload(context)
    old = baseline.evidence_payload
    cards: list[WhatChangedCard] = []
    old_http, new_http = old["http"], current["http"]
    http_refs = [old_http["evidence_ref"], new_http["evidence_ref"]]
    if old_http["status_code"] == 200 and new_http["status_code"] == 500:
        cards.append(
            _card(
                context=context,
                before="200 OK",
                after="500 Internal Server Error",
                title="Primary HTTP endpoint started failing",
                category="http",
                severity=ChangeSeverity.CRITICAL,
                materiality=ChangeMateriality.MATERIAL,
                rank=40,
                impact="The primary watched endpoint is no longer serving successful responses.",
                why=(
                    "A primary endpoint moving from healthy to HTTP 500 is a "
                    "strong app/service-layer incident signal."
                ),
                rule_id="WC_HTTP_STATUS_PRIMARY_200_TO_500",
                refs=http_refs,
            )
        )
    elif (
        old_http["response_classification"] == "healthy"
        and new_http["response_classification"] == "unavailable"
    ):
        cards.append(
            _card(
                context=context,
                before="healthy",
                after="unavailable",
                title="Primary HTTP endpoint became unavailable",
                category="http",
                severity=ChangeSeverity.CRITICAL,
                materiality=ChangeMateriality.MATERIAL,
                rank=10,
                impact="The primary endpoint could not be reached.",
                why="An unavailable primary endpoint is a direct outage signal.",
                rule_id="WC_HTTP_PRIMARY_UNAVAILABLE",
                refs=http_refs,
            )
        )
    elif (
        old_http["response_classification"] == "healthy"
        and new_http["response_classification"] == "failing"
    ):
        cards.append(
            _card(
                context=context,
                before="healthy",
                after="failing",
                title="Primary HTTP response classification changed to failing",
                category="http",
                severity=ChangeSeverity.CRITICAL,
                materiality=ChangeMateriality.MATERIAL,
                rank=50,
                impact="The watched endpoint is returning a failing response.",
                why="A healthy-to-failing primary response is a direct incident signal.",
                rule_id="WC_HTTP_CLASSIFICATION_HEALTHY_TO_FAILING",
                refs=http_refs,
            )
        )
    latency = _latency_rule(old_http.get("latency_ms"), new_http.get("latency_ms"), "HTTP")
    if latency:
        severity, rank, rule_id = latency
        cards.append(
            _card(
                context=context,
                before=f"{old_http['latency_ms']}ms",
                after=f"{new_http['latency_ms']}ms",
                title="Primary HTTP latency materially increased",
                category="http",
                severity=severity,
                materiality=ChangeMateriality.MATERIAL,
                rank=rank,
                impact="The watched endpoint is responding materially more slowly.",
                why="The increase crossed both absolute and relative latency thresholds.",
                rule_id=rule_id,
                refs=http_refs,
            )
        )
    old_runtime, new_runtime = old["runtime"], current["runtime"]
    runtime_refs = [old_runtime["evidence_ref"], new_runtime["evidence_ref"]]
    if old_runtime["running"] and not new_runtime["running"]:
        cards.append(
            _card(
                context=context,
                before="running",
                after=new_runtime["container_status"],
                title="Runtime container is not running",
                category="runtime",
                severity=ChangeSeverity.CRITICAL,
                materiality=ChangeMateriality.MATERIAL,
                rank=20,
                impact="The watched service container stopped running.",
                why="A stopped service container directly prevents service delivery.",
                rule_id="WC_RUNTIME_CONTAINER_NOT_RUNNING",
                refs=runtime_refs,
            )
        )
    if (
        old_runtime.get("health_status") == "healthy"
        and new_runtime.get("health_status") == "unhealthy"
    ):
        cards.append(
            _card(
                context=context,
                before="healthy",
                after="unhealthy",
                title="Runtime health changed to unhealthy",
                category="runtime",
                severity=ChangeSeverity.HIGH,
                materiality=ChangeMateriality.MATERIAL,
                rank=70,
                impact="The container runtime health check is failing.",
                why="Runtime health degradation is evidence of service instability.",
                rule_id="WC_RUNTIME_HEALTH_STATUS_CHANGED",
                refs=runtime_refs,
            )
        )
    restart_delta = new_runtime.get("restart_count", 0) - old_runtime.get("restart_count", 0)
    if restart_delta > 0:
        cards.append(
            _card(
                context=context,
                before=old_runtime.get("restart_count", 0),
                after=new_runtime.get("restart_count", 0),
                title="Runtime restart count increased",
                category="runtime",
                severity=ChangeSeverity.HIGH if restart_delta >= 2 else ChangeSeverity.MEDIUM,
                materiality=ChangeMateriality.MATERIAL,
                rank=80 if restart_delta >= 2 else 90,
                impact="The container restarted during the comparison window.",
                why="New restarts can indicate crashes or runtime instability.",
                rule_id="WC_RUNTIME_RESTART_COUNT_INCREASED",
                refs=runtime_refs,
            )
        )
    if old_runtime.get("image_id") != new_runtime.get("image_id") or old_runtime.get(
        "image_tag"
    ) != new_runtime.get("image_tag"):
        cards.append(
            _card(
                context=context,
                before=old_runtime.get("image_tag") or old_runtime.get("image_id"),
                after=new_runtime.get("image_tag") or new_runtime.get("image_id"),
                title="Runtime image changed",
                category="runtime",
                severity=ChangeSeverity.MEDIUM,
                materiality=ChangeMateriality.MATERIAL,
                rank=140,
                impact="The running container image differs from the healthy baseline.",
                why="A deployment or image drift may correlate with the incident.",
                rule_id="WC_RUNTIME_IMAGE_CHANGED",
                refs=runtime_refs,
            )
        )
    if old_runtime.get("ports") != new_runtime.get("ports"):
        cards.append(
            _card(
                context=context,
                before=old_runtime.get("ports"),
                after=new_runtime.get("ports"),
                title="Runtime ports changed",
                category="runtime",
                severity=ChangeSeverity.MEDIUM,
                materiality=ChangeMateriality.MATERIAL,
                rank=150,
                impact="Published container ports differ from the healthy baseline.",
                why="Port drift can make an otherwise running service unreachable.",
                rule_id="WC_RUNTIME_PORTS_CHANGED",
                refs=runtime_refs,
            )
        )
    http_failed = new_http["response_classification"] != "healthy"
    for name, previous in old.get("dependencies", {}).items():
        current_dep = current["dependencies"].get(name)
        if not current_dep:
            continue
        refs = [previous["evidence_ref"], current_dep["evidence_ref"]]
        if previous["reachable"] and not current_dep["reachable"]:
            cards.append(
                _card(
                    context=context,
                    before="healthy",
                    after="unreachable",
                    title=f"Required dependency {name} became unreachable",
                    category="dependency",
                    severity=ChangeSeverity.CRITICAL,
                    materiality=ChangeMateriality.MATERIAL,
                    rank=30,
                    impact="A required dependency is unavailable.",
                    why="Every configured dependency is required/core in v0.3.",
                    rule_id="WC_DEPENDENCY_BECAME_UNREACHABLE",
                    refs=refs,
                )
            )
        elif previous["reachable"] and current_dep["reachable"] and http_failed:
            cards.append(
                _card(
                    context=context,
                    before="healthy",
                    after="healthy",
                    title=f"Dependency {name} remained healthy",
                    category="dependency",
                    severity=ChangeSeverity.INFO,
                    materiality=ChangeMateriality.SUPPORTING_CONTEXT,
                    rank=500,
                    impact="The dependency remained reachable during the HTTP failure.",
                    why="This points toward the app/service layer rather than the dependency.",
                    rule_id="WC_DEPENDENCY_REMAINED_HEALTHY_WHILE_HTTP_FAILED",
                    refs=refs,
                )
            )
        dependency_latency = _latency_rule(
            previous.get("latency_ms"),
            current_dep.get("latency_ms"),
            "DEPENDENCY",
        )
        if dependency_latency:
            severity, rank, rule_id = dependency_latency
            cards.append(
                _card(
                    context=context,
                    before=f"{previous['latency_ms']}ms",
                    after=f"{current_dep['latency_ms']}ms",
                    title=f"Dependency {name} latency materially increased",
                    category="dependency",
                    severity=severity,
                    materiality=ChangeMateriality.MATERIAL,
                    rank=rank,
                    impact="A required dependency is responding materially more slowly.",
                    why=(
                        "The increase crossed both absolute and relative dependency "
                        "latency thresholds."
                    ),
                    rule_id=rule_id,
                    refs=refs,
                )
            )
    priority = {"material": 0, "supporting_context": 1, "other": 2}
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    category_order = {"http": 0, "dependency": 1, "runtime": 2}
    cards.sort(
        key=lambda card: (
            priority[card.materiality.value],
            card.rank,
            severity_order[card.severity.value],
            category_order[card.category],
            card.rule_id,
            card.id,
        )
    )
    material = [c for c in cards if c.materiality == ChangeMateriality.MATERIAL]
    supporting = [c for c in cards if c.materiality == ChangeMateriality.SUPPORTING_CONTEXT]
    other = [c for c in cards if c.materiality == ChangeMateriality.OTHER]
    refs = list(dict.fromkeys(ref for card in cards for ref in card.evidence_refs))
    summary = (
        "The primary HTTP endpoint changed from healthy to failing while the "
        "dependency remained healthy."
        if any(c.rule_id == "WC_HTTP_STATUS_PRIMARY_200_TO_500" for c in cards)
        and any(c.rule_id == "WC_DEPENDENCY_REMAINED_HEALTHY_WHILE_HTTP_FAILED" for c in cards)
        else f"Deterministic comparison detected {len(cards)} relevant changes."
    )
    return WhatChangedResult(
        status=WhatChangedStatus.AVAILABLE,
        baseline_snapshot_id=baseline.snapshot_id,
        baseline_observed_at=baseline.observed_at,
        incident_observed_at=_observed_at(context),
        service_identity=identity,
        rule_summary=summary,
        summary_evidence_refs=refs,
        summary_generated_at=datetime.now(timezone.utc),
        material_changes=material,
        supporting_context=supporting,
        other_changes=other,
        counts=WhatChangedCounts(
            material=len(material),
            supporting_context=len(supporting),
            other=len(other),
            total=len(cards),
        ),
        llm=llm,
        diagnostics=diagnostics,
    )


def comparison_failed_result(
    service: Service,
    context: IncidentContext,
    *,
    llm_configured: bool,
    reason: ComparisonFailureReason = ComparisonFailureReason.RULE_ENGINE_ERROR,
) -> WhatChangedResult:
    messages = {
        ComparisonFailureReason.BASELINE_LOAD_FAILED: (
            "Unable to load the healthy baseline snapshot."
        ),
        ComparisonFailureReason.INCIDENT_EVIDENCE_INCOMPLETE: (
            "Incident evidence was incomplete, so comparison could not be completed."
        ),
        ComparisonFailureReason.SNAPSHOT_SCHEMA_INVALID: (
            "The healthy baseline snapshot did not match the expected schema."
        ),
        ComparisonFailureReason.RULE_ENGINE_ERROR: (
            "The What Changed rule engine failed before comparison could be completed."
        ),
        ComparisonFailureReason.WHAT_CHANGED_RENDER_ERROR: (
            "The What Changed section could not be rendered."
        ),
        ComparisonFailureReason.UNKNOWN: "What Changed comparison could not be completed.",
    }
    failed_at = datetime.now(timezone.utc)
    return WhatChangedResult(
        status=WhatChangedStatus.COMPARISON_FAILED,
        service_identity=service_identity(service, context),
        incident_observed_at=_observed_at(context),
        rule_summary=("What Changed? comparison unavailable; normal diagnosis completed."),
        counts=empty_counts(),
        llm=LlmAdvisoryMetadata(
            status=(
                LlmAdvisoryStatus.NOT_ATTEMPTED
                if llm_configured
                else LlmAdvisoryStatus.NOT_CONFIGURED
            ),
            configured=llm_configured,
            attempted=False,
        ),
        diagnostics=WhatChangedDiagnostics(
            comparison_failure=ComparisonFailureMetadata(
                failed=True,
                reason=reason,
                message=messages[reason],
                failed_at=failed_at,
                fallback_used="normal_diagnosis_only",
                error_ref=f"wc-error-{uuid4().hex[:12]}",
            ),
            required_dependencies=list(context.dependencies),
        ),
    )


class WhatChangedAdvisoryService:
    """Optional tool-free advisory constrained to deterministic cards."""

    def __init__(self, provider: LLMProvider, model: str) -> None:
        self.provider = provider
        self.model = model

    def enhance(self, result: WhatChangedResult) -> WhatChangedResult:
        if result.status != WhatChangedStatus.AVAILABLE:
            return result
        cards_payload = [
            card.model_dump(mode="json")
            for card in (result.material_changes + result.supporting_context + result.other_changes)
        ]
        prompt = (
            "Explain only the supplied deterministic change cards. Return JSON with "
            "summary and per_change_notes keyed by card id. Do not add facts, severity, "
            "ranking, actions, commands, remediation, restart, delete, exec, or rollback. "
            f"Cards: {json.dumps(cards_payload)}"
        )
        validation_failed = False
        last_reason: LlmFailureReason | None = None
        for attempt in range(2):
            try:
                response = WhatChangedAdvisoryResponse.model_validate(
                    self.provider.generate_json(prompt)
                )
                self._validate(result, response)
                notes = response.per_change_notes
                return result.model_copy(
                    update={
                        "ai_advisory_summary": response.summary,
                        "material_changes": self._notes(result.material_changes, notes),
                        "supporting_context": self._notes(result.supporting_context, notes),
                        "other_changes": self._notes(result.other_changes, notes),
                        "llm": LlmAdvisoryMetadata(
                            status=LlmAdvisoryStatus.ACCEPTED,
                            configured=True,
                            attempted=True,
                            retry_attempted=attempt == 1,
                            model=self.model,
                            advisory_accepted=True,
                            generated_at=datetime.now(timezone.utc),
                        ),
                    },
                    deep=True,
                )
            except (ValidationError, ValueError):
                validation_failed = True
                last_reason = LlmFailureReason.INVALID_RESPONSE
                prompt += "\nPrevious output was invalid. Return safe schema-only advisory."
            except LLMProviderError as error:
                last_reason = self._failure_reason(error.code)
                if last_reason == LlmFailureReason.POLICY_BLOCKED:
                    break
        return result.model_copy(
            update={
                "llm": LlmAdvisoryMetadata(
                    status=(
                        LlmAdvisoryStatus.VALIDATION_FAILED
                        if validation_failed
                        else LlmAdvisoryStatus.FAILED
                    ),
                    configured=True,
                    attempted=True,
                    retry_attempted=True,
                    model=self.model,
                    failed=not validation_failed,
                    failure_reason=None if validation_failed else last_reason,
                    validation_failed=validation_failed,
                    validation_reason=("unsafe_or_invalid_advisory" if validation_failed else None),
                    advisory_hidden=validation_failed,
                    fallback_used="deterministic_rule_summary",
                )
            },
            deep=True,
        )

    @staticmethod
    def _validate(result: WhatChangedResult, response: WhatChangedAdvisoryResponse) -> None:
        text = " ".join([response.summary, *response.per_change_notes.values()])
        if UNSAFE_ADVISORY.search(text):
            raise ValueError("unsafe advisory")
        ids = {
            card.id
            for card in (result.material_changes + result.supporting_context + result.other_changes)
        }
        if not set(response.per_change_notes) <= ids:
            raise ValueError("unknown card id")

    @staticmethod
    def _notes(cards: list[WhatChangedCard], notes: dict[str, str]) -> list[WhatChangedCard]:
        return [card.model_copy(update={"ai_advisory_note": notes.get(card.id)}) for card in cards]

    @staticmethod
    def _failure_reason(code: str) -> LlmFailureReason:
        mapping = {
            "timeout": LlmFailureReason.TIMEOUT,
            "invalid_response": LlmFailureReason.INVALID_RESPONSE,
            "policy_blocked": LlmFailureReason.POLICY_BLOCKED,
            "empty_response": LlmFailureReason.EMPTY_RESPONSE,
        }
        return mapping.get(code, LlmFailureReason.PROVIDER_ERROR)


def render_what_changed_markdown(result: WhatChangedResult) -> str:
    if result.status == WhatChangedStatus.NO_BASELINE:
        return f"\n## What Changed?\n\n{result.rule_summary}\n"
    if result.status == WhatChangedStatus.COMPARISON_FAILED:
        return (
            "\n## What Changed?\n\nWhat Changed? comparison unavailable; "
            "normal diagnosis completed.\n"
        )
    lines = ["", "## What Changed?", "", result.rule_summary or "", ""]
    for heading, cards in (
        ("Material Changes", result.material_changes),
        ("Supporting Context", result.supporting_context),
        ("Other Changes", result.other_changes),
    ):
        lines.extend([f"### {heading}", ""])
        if not cards:
            lines.extend([f"No {heading.lower()} detected.", ""])
        for card in cards:
            lines.extend(
                [
                    f"#### {card.severity.value.title()} — {card.title}",
                    "",
                    f"- Before: {card.before.value}",
                    f"- Now: {card.after.value}",
                    f"- Impact: {card.impact}",
                    f"- Why it matters: {card.why_it_matters}",
                    f"- Evidence: {', '.join(card.evidence_refs)}",
                    f"- Rule: {card.rule_id}",
                    "",
                ]
            )
    return "\n".join(lines)
